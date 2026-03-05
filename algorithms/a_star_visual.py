"""Step-by-step visual A* solver (enhanced) for UI integration.

This module wraps the enhanced A* algorithm with a step-emission mechanism
so the UI can visualise every placement, propagation, and expansion event.

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
from typing import List, Optional, Set

from core.board import Board
from core.constraints import (
    can_place_bulb,
    compute_illumination,
    count_adjacent_bulbs,
    is_goal_state,
)
from core.state import State
from core.types import Position
from algorithms.visual_common import Step, StepType

import heapq



class _SolverStopped(Exception):
    """Raised internally when the UI requests the solver to stop."""


# ── A* node ──────────────────────────────────────────────────────

class _AStarNode:
    __slots__ = ("state", "f_n", "forbidden")

    def __init__(self, state: State, f_n: float,
                 forbidden: Set[Position]) -> None:
        self.state = state
        self.f_n = f_n
        self.forbidden = forbidden

    def __lt__(self, other: "_AStarNode") -> bool:
        return self.f_n < other.f_n


# ── Visual A* Solver (enhanced) ─────────────────────────────────

class VisualAStarSolver:
    """A* solver with constraint propagation that emits UI steps."""

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
        frontier_size: int = 0,
        f_n: float = 0.0,
    ) -> Step:
        bulbs = state.bulb_positions()
        lit = compute_illumination(self.board, state)
        return Step(
            step_type=stype,
            position=pos,
            nodes_expanded=self.nodes_expanded,
            frontier_size=frontier_size,
            bulb_count=len(bulbs),
            f_n=f_n,
            message=msg,
            bulb_positions=bulbs,
            lit_cells=lit,
            elapsed=self._elapsed(),
            candidates=candidates or [],
        )

    # ── constraint propagation ────────────────────────────────────

    @staticmethod
    def _free_neighbors(board: Board, state: State, pos: Position,
                        forbidden: Set[Position]):
        return [
            n for n in board.neighbors(pos)
            if board.is_empty(n) and not state.has_bulb(n) and n not in forbidden
        ]

    def _propagate(self, state: State, forbidden: Set[Position]) -> bool:
        """Returns True on contradiction."""
        changed = True
        while changed:
            if self._stop.is_set():
                raise _SolverStopped
            changed = False
            for nc in self.board.numbered_cells():
                required = self.board.get_number(nc)
                current = count_adjacent_bulbs(self.board, state, nc)
                if current > required:
                    return True
                free = self._free_neighbors(self.board, state, nc, forbidden)
                remaining = required - current
                if remaining > len(free):
                    return True
                if remaining == 0:
                    for n in free:
                        if n not in forbidden:
                            forbidden.add(n)
                            changed = True
                elif remaining == len(free):
                    for n in free:
                        if not can_place_bulb(self.board, state, n):
                            return True
                        state.add_bulb(n)
                        self._emit(self._snap(
                            StepType.FORCED_BULB, state, n,
                            f"Forced bulb at ({n[0]},{n[1]})"
                        ))
                        changed = True
        return False

    # ── target & candidate selection ──────────────────────────────

    def _select_unlit(self, state: State) -> Optional[Position]:
        lit = compute_illumination(self.board, state)
        for c in self.board.white_cells():
            if c not in lit:
                return c
        return None

    def _candidates(self, state: State, forbidden: Set[Position],
                    target: Position) -> List[Position]:
        result: List[Position] = []
        for pos in [target] + list(self.board.visible_cells(target)):
            if pos in forbidden:
                continue
            if can_place_bulb(self.board, state, pos):
                result.append(pos)
        return result

    # ── heuristic & f(n) ─────────────────────────────────────────

    def _heuristic(self, state: State) -> int:
        lit = compute_illumination(self.board, state)
        return sum(1 for cell in self.board.white_cells() if cell not in lit)

    def _f(self, state: State) -> float:
        return len(state.bulb_positions()) + self._heuristic(state)

    # ── make node (propagate + score) ─────────────────────────────

    def _make_node(self, state: State) -> Optional[_AStarNode]:
        forbidden: Set[Position] = set()
        contradiction = self._propagate(state, forbidden)
        if contradiction:
            self._emit(self._snap(
                StepType.CONTRADICTION, state,
                msg="Contradiction during propagation"
            ))
            return None
        f_n = self._f(state)
        return _AStarNode(state, f_n, forbidden)

    # ── public entry point ────────────────────────────────────────

    def solve(self) -> None:
        """Run the solver (call from a worker thread)."""
        self.nodes_expanded = 0
        self._start_time = time.perf_counter()
        state = State()

        self._emit(self._snap(StepType.START, state, msg="A* solver started"))

        try:
            frontier: list = []
            root = self._make_node(state)
            if root is None:
                self._emit(self._snap(
                    StepType.NO_SOLUTION, state,
                    msg="No solution exists (root contradiction)"
                ))
                return
            heapq.heappush(frontier, root)

            while frontier:
                if self._stop.is_set():
                    raise _SolverStopped

                node = heapq.heappop(frontier)
                curr_state = node.state
                self.nodes_expanded += 1

                # ── Emit pop event ────────────────────────────────
                self._emit(self._snap(
                    StepType.POP_NODE, curr_state,
                    msg=f"Pop node #{self.nodes_expanded}  f={node.f_n:.0f}  "
                        f"bulbs={len(curr_state.bulb_positions())}  "
                        f"frontier={len(frontier)}",
                    frontier_size=len(frontier),
                    f_n=node.f_n,
                ))

                # ── Goal check ────────────────────────────────────
                if is_goal_state(self.board, curr_state):
                    self._emit(self._snap(
                        StepType.SOLVED, curr_state,
                        msg=f"Solution found! nodes={self.nodes_expanded}"
                    ))
                    return

                # ── Target selection ──────────────────────────────
                target = self._select_unlit(curr_state)
                if target is None:
                    continue

                cands = self._candidates(curr_state, node.forbidden, target)
                if not cands:
                    self._emit(self._snap(
                        StepType.CONTRADICTION, curr_state,
                        msg=f"No candidates for ({target[0]},{target[1]})"
                    ))
                    continue

                # ── Expand candidates ─────────────────────────────
                for pos in cands:
                    if self._stop.is_set():
                        raise _SolverStopped

                    child_state = curr_state.copy()
                    child_state.add_bulb(pos)

                    self._emit(self._snap(
                        StepType.PLACE_BULB, child_state, pos,
                        f"Try bulb at ({pos[0]},{pos[1]})  "
                        f"target=({target[0]},{target[1]})",
                        candidates=cands,
                        frontier_size=len(frontier),
                    ))

                    child_node = self._make_node(child_state)
                    if child_node is not None:
                        heapq.heappush(frontier, child_node)

            # Frontier exhausted
            self._emit(self._snap(
                StepType.NO_SOLUTION, State(),
                msg="No solution exists"
            ))

        except _SolverStopped:
            pass  # UI requested stop — silently exit

