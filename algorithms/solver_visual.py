"""Step-by-step visual DFS solver for UI integration.

This module wraps the enhanced DFS algorithm with a step-emission mechanism
so the UI can visualise every placement, backtrack, and propagation event.

Design
------
* The solver runs in a **background thread**.
* Each significant event is pushed to a ``queue.Queue`` as a ``Step`` object.
* After emitting a step the solver **blocks** on a ``threading.Event`` until
  the UI signals it may continue (allowing speed control / pause).
* A separate ``stop_event`` lets the UI abort the solver at any time.

The core and algorithm packages are **not** modified.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set

from core.board import Board
from core.constraints import (
    can_place_bulb,
    compute_illumination,
    count_adjacent_bulbs,
    is_goal_state,
)
from core.state import State
from core.types import Position


# ── Step data ────────────────────────────────────────────────────

class StepType(Enum):
    START           = auto()
    PLACE_BULB      = auto()   # normal branch
    REMOVE_BULB     = auto()   # backtrack
    FORCED_BULB     = auto()   # constraint propagation
    REMOVE_FORCED   = auto()   # undo forced on backtrack
    FORBIDDEN       = auto()   # cell marked forbidden
    CONTRADICTION   = auto()   # dead-end detected
    GOAL_CHECK      = auto()
    SOLVED          = auto()
    NO_SOLUTION     = auto()


@dataclass
class Step:
    step_type: StepType
    position: Optional[Position] = None
    nodes_expanded: int = 0
    depth: int = 0
    bulb_count: int = 0
    message: str = ""
    bulb_positions: Set[Position] = field(default_factory=set)
    lit_cells: Set[Position] = field(default_factory=set)
    elapsed: float = 0.0
    candidates: List[Position] = field(default_factory=list)


class _SolverStopped(Exception):
    """Raised internally when the UI requests the solver to stop."""


# ── Visual DFS Solver (enhanced) ────────────────────────────────

class VisualDFSSolver:
    """DFS solver with constraint propagation that emits UI steps."""

    def __init__(
        self,
        board: Board,
        step_queue: queue.Queue,
        continue_event: threading.Event,
        stop_event: threading.Event,
    ) -> None:
        self.board = board
        self._queue = step_queue
        self._continue = continue_event
        self._stop = stop_event

        self.nodes_expanded = 0
        self.depth = 0
        self._start_time = 0.0

    # ── helpers ───────────────────────────────────────────────────

    def _elapsed(self) -> float:
        return time.perf_counter() - self._start_time

    def _emit(self, step: Step) -> None:
        """Push *step* onto the queue and block until the UI says continue."""
        self._queue.put(step)
        while not self._stop.is_set():
            if self._continue.wait(timeout=0.02):
                self._continue.clear()
                return
        raise _SolverStopped

    def _snap(
        self,
        stype: StepType,
        state: State,
        pos: Optional[Position] = None,
        msg: str = "",
        candidates: Optional[List[Position]] = None,
    ) -> Step:
        bulbs = state.bulb_positions()
        lit = compute_illumination(self.board, state)
        return Step(
            step_type=stype,
            position=pos,
            nodes_expanded=self.nodes_expanded,
            depth=self.depth,
            bulb_count=len(bulbs),
            message=msg,
            bulb_positions=bulbs,
            lit_cells=lit,
            elapsed=self._elapsed(),
            candidates=candidates or [],
        )

    # ── public entry point ────────────────────────────────────────

    def solve(self) -> None:
        """Run the solver (call from a worker thread)."""
        self.nodes_expanded = 0
        self.depth = 0
        self._start_time = time.perf_counter()
        state = State()

        self._emit(self._snap(StepType.START, state, msg="Solver started"))

        try:
            result = self._dfs(state, forbidden=set())
            if result is not None:
                self._emit(self._snap(StepType.SOLVED, result, msg="Solution found!"))
            else:
                self._emit(self._snap(StepType.NO_SOLUTION, state, msg="No solution exists"))
        except _SolverStopped:
            pass  # UI requested stop — silently exit

    # ── constraint propagation ────────────────────────────────────

    @staticmethod
    def _free_neighbors(board: Board, state: State, pos: Position, forbidden: Set[Position]):
        return [
            n for n in board.neighbors(pos)
            if board.is_empty(n) and not state.has_bulb(n) and n not in forbidden
        ]

    def _propagate(self, state: State, forbidden: Set[Position]):
        added: List[Position] = []
        changed = True
        while changed:
            if self._stop.is_set():
                raise _SolverStopped
            changed = False
            for nc in self.board.numbered_cells():
                required = self.board.get_number(nc)
                current = count_adjacent_bulbs(self.board, state, nc)
                if current > required:
                    return True, added
                free = self._free_neighbors(self.board, state, nc, forbidden)
                remaining = required - current
                if remaining > len(free):
                    return True, added
                if remaining == 0:
                    for n in free:
                        if n not in forbidden:
                            forbidden.add(n)
                            changed = True
                elif remaining == len(free):
                    for n in free:
                        if not can_place_bulb(self.board, state, n):
                            return True, added
                        state.add_bulb(n)
                        added.append(n)
                        self._emit(self._snap(
                            StepType.FORCED_BULB, state, n,
                            f"Forced bulb at ({n[0]},{n[1]})"
                        ))
                        changed = True
        return False, added

    # ── target & candidate selection ──────────────────────────────

    def _select_unlit(self, state: State):
        lit = compute_illumination(self.board, state)
        for c in self.board.white_cells():
            if c not in lit:
                return c
        return None

    def _candidates(self, state: State, forbidden: Set[Position], target: Position):
        seen: set = set()
        result: List[Position] = []
        for pos in [target] + list(self.board.visible_cells(target)):
            if pos in seen:
                continue
            seen.add(pos)
            if not self.board.is_empty(pos):
                continue
            if state.has_bulb(pos) or pos in forbidden:
                continue
            if can_place_bulb(self.board, state, pos):
                result.append(pos)
        return result

    # ── recursive DFS ─────────────────────────────────────────────

    def _dfs(self, state: State, forbidden: Set[Position]) -> Optional[State]:
        if self._stop.is_set():
            raise _SolverStopped

        self.nodes_expanded += 1
        local_forbidden = set(forbidden)
        contradiction, forced = self._propagate(state, local_forbidden)

        try:
            if contradiction:
                self._emit(self._snap(
                    StepType.CONTRADICTION, state,
                    msg=f"Contradiction at depth {self.depth}"
                ))
                return None

            if is_goal_state(self.board, state):
                return state.copy()

            target = self._select_unlit(state)
            if target is None:
                return None

            cands = self._candidates(state, local_forbidden, target)
            if not cands:
                self._emit(self._snap(
                    StepType.CONTRADICTION, state,
                    msg=f"No candidates for ({target[0]},{target[1]})"
                ))
                return None

            for pos in cands:
                state.add_bulb(pos)
                self.depth += 1
                self._emit(self._snap(
                    StepType.PLACE_BULB, state, pos,
                    f"Place bulb at ({pos[0]},{pos[1]})  depth={self.depth}",
                    candidates=cands,
                ))

                result = self._dfs(state, local_forbidden)
                if result is not None:
                    return result

                state.remove_bulb(pos)
                self.depth -= 1
                self._emit(self._snap(
                    StepType.REMOVE_BULB, state, pos,
                    f"Backtrack ({pos[0]},{pos[1]})  depth={self.depth}",
                ))

            return None

        finally:
            for p in forced:
                state.remove_bulb(p)
