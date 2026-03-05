"""A* Solver (Enhanced) for Light Up (Akari) with constraint propagation.

Same improvements as DFS Enhanced, applied to A*:
1. **Forced-cell propagation**: numbered walls with exactly k free
   neighbours needing k more bulbs → all forced immediately.
2. **Forbidden-cell propagation**: satisfied numbered walls → remaining
   free neighbours are forbidden.
3. **Early dead-end detection**: over-satisfied walls, impossible walls,
   and unlit cells with 0 candidates are pruned immediately.
4. **Smart branching**: find one unlit cell, try only legal candidates
   that can illuminate it (same as DFS enhanced).
5. **Proper A* heuristic**: f(n) = g(n) + h(n) where h(n) = actual
   unlit cells on the board.
"""

from typing import List, Optional, Set, Tuple

from core.board import Board
from core.state import State
from core.types import Position
from core.constraints import (
    can_place_bulb,
    compute_illumination,
    count_adjacent_bulbs,
    is_goal_state,
)
import heapq


# ── Constraint propagation (reused from dfs_solver_enhance) ─────────

def _free_neighbors(board, state, num_cell, forbidden: Set[Position]) -> List[Position]:
    """Empty neighbours of *num_cell* that are neither bulbs nor forbidden."""
    return [
        pos for pos in board.neighbors(num_cell)
        if board.is_empty(pos)
        and not state.has_bulb(pos)
        and pos not in forbidden
    ]


def _propagate(board, state, forbidden: Set[Position]) -> Tuple[bool, List[Position]]:
    """Iterative constraint propagation until fixpoint.

    Returns (is_contradiction, list_of_forced_bulbs).
    """
    added: List[Position] = []
    changed = True

    while changed:
        changed = False

        for num_cell_pos in board.numbered_cells():
            required = board.get_number(num_cell_pos)
            current = count_adjacent_bulbs(board, state, num_cell_pos)

            if current > required:
                return True, added  # over-satisfied

            free = _free_neighbors(board, state, num_cell_pos, forbidden)
            remaining = required - current

            if remaining > len(free):
                return True, added  # impossible to satisfy

            if remaining == 0:
                for n in free:
                    if n not in forbidden:
                        forbidden.add(n)
                        changed = True

            elif remaining == len(free):
                for n in free:
                    if not can_place_bulb(board, state, n):
                        return True, added
                    state.add_bulb(n)
                    added.append(n)
                    changed = True

    return False, added


# ── Candidate / target helpers ──────────────────────────────────────

def _select_unlit_cell(board, state) -> Optional[Position]:
    lit = compute_illumination(board, state)
    for cell in board.white_cells():
        if cell not in lit:
            return cell
    return None


def _generate_candidates(board, state, forbidden: Set[Position], target) -> List[Position]:
    seen = set()
    result = []
    for pos in [target] + list(board.visible_cells(target)):
        if pos in seen:
            continue
        seen.add(pos)
        if not board.is_empty(pos):
            continue
        if state.has_bulb(pos) or pos in forbidden:
            continue
        if can_place_bulb(board, state, pos):
            result.append(pos)
    return result


# ── A* node wrapper (state + propagation context for undo) ──────────

class _AStarNode:
    """Wraps a State with its f(n) score and propagation info for the heap."""

    __slots__ = ("state", "f_n", "forced_bulbs", "forbidden")

    def __init__(self, state: State, f_n: float,
                 forced_bulbs: List[Position],
                 forbidden: Set[Position]) -> None:
        self.state = state
        self.f_n = f_n
        self.forced_bulbs = forced_bulbs
        self.forbidden = forbidden

    def __lt__(self, other: "_AStarNode") -> bool:
        return self.f_n < other.f_n


# ── Solver ──────────────────────────────────────────────────────────

class AStarSolverEnhanced:
    def __init__(self) -> None:
        self.nodes_expanded: int = 0

    def solve(self, board: Board) -> dict:
        self.nodes_expanded = 0
        initial_state = State()
        solution = self._a_star(board, initial_state)
        return {
            "solution": solution,
            "nodes_expanded": self.nodes_expanded,
            "solved": solution is not None,
        }

    @staticmethod
    def _heuristic(board: Board, state: State) -> int:
        """h(n) = number of white cells not yet illuminated."""
        lit = compute_illumination(board, state)
        return sum(1 for cell in board.white_cells() if cell not in lit)

    def _f(self, board: Board, state: State) -> float:
        """f(n) = g(n) + h(n)."""
        return len(state.bulb_positions()) + self._heuristic(board, state)

    def _make_node(self, board: Board, state: State) -> Optional[_AStarNode]:
        """Apply propagation, compute f(n), return node or None if contradiction."""
        forbidden = set()
        contradiction, forced_bulbs = _propagate(board, state, forbidden)
        if contradiction:
            # Undo forced bulbs before discarding.
            for pos in forced_bulbs:
                state.remove_bulb(pos)
            return None
        f_n = self._f(board, state)
        return _AStarNode(state, f_n, forced_bulbs, forbidden)

    def _a_star(self, board: Board, init_state: State) -> Optional[State]:
        frontier: list = []

        root = self._make_node(board, init_state)
        if root is None:
            return None
        heapq.heappush(frontier, root)

        while frontier:
            node = heapq.heappop(frontier)
            state = node.state
            self.nodes_expanded += 1

            # ── Goal check ────────────────────────────────────────────
            if is_goal_state(board, state):
                result = state.copy()
                # Undo forced bulbs so state stays clean.
                for pos in node.forced_bulbs:
                    state.remove_bulb(pos)
                return result

            # ── Target selection ──────────────────────────────────────
            target = _select_unlit_cell(board, state)

            if target is not None:
                candidates = _generate_candidates(
                    board, state, node.forbidden, target
                )

                for pos in candidates:
                    child_state = state.copy()
                    child_state.add_bulb(pos)
                    child_node = self._make_node(board, child_state)
                    if child_node is not None:
                        heapq.heappush(frontier, child_node)

            # ── Undo forced bulbs from this node ──────────────────────
            for pos in node.forced_bulbs:
                state.remove_bulb(pos)

        return None

