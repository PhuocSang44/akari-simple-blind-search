"""Pure DFS Solver for Light Up (Akari) - no constraint propagation."""

from typing import List, Optional

from core.board import Board
from core.state import State
from core.types import Position
from core.constraints import (
    can_place_bulb,
    compute_illumination,
    is_goal_state,
)

# ============= Helper functions for DFS branching =============
def generate_candidates(board, state, target: Position) -> List[Position]:
    """Generate all positions that would illuminate *target*.

        {target} and visible_cells(target)
    """
    candidates: List[Position] = []

    if can_place_bulb(board, state, target):
        candidates.append(target)

    for pos in board.visible_cells(target):
        if board.is_empty(pos) and not state.has_bulb(pos):
            if can_place_bulb(board, state, pos):
                candidates.append(pos)
    return candidates


def _select_unlit_cell(board, state) -> Optional[Position]:
    lit = compute_illumination(board, state)
    for cell in board.white_cells():
        if cell not in lit:
            return cell
    return None


class DFSSolver:

    def __init__(self) -> None:
        self.nodes_expanded: int = 0

    def solve(self, board: Board) -> dict:
        self.nodes_expanded = 0
        initial_state = State()
        solution = self._dfs(board, initial_state)
        return {
            "solution":       solution,
            "nodes_expanded": self.nodes_expanded,
            "solved":         solution is not None,
        }

    def _dfs(self, board: Board, state: State) -> Optional[State]:
        self.nodes_expanded += 1
        print(self.nodes_expanded)

        # ── Goal check ───────────────────────────────────────────────
        if is_goal_state(board, state):
            return state.copy()

        # ── Target selection ─────────────────────────────────────────
        target = _select_unlit_cell(board, state)

        if target is None:
            return None # No unlit cells, but not a goal state => dead end.

        # ── Candidate generation ─────────────────────────────────────
        candidates = generate_candidates(board, state, target)

        if not candidates:
            return None # No legal placements to illuminate target => dead end.

        # ── Branch and backtrack ─────────────────────────────────────
        for pos in candidates:
            state.add_bulb(pos)
            result = self._dfs(board, state)
            state.remove_bulb(pos)

            if result is not None:
                return result

        return None
