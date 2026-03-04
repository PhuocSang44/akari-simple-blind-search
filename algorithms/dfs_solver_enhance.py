"""DFS Solver for Light Up (Akari) with constraint propagation.

Improvements over blind DFS
---------------------------
1. **Forced-cell propagation**: if a numbered wall has exactly *k* free
   neighbours and still needs exactly *k* more bulbs, every free neighbour
   is *forced* (placed immediately, no branching).

2. **Forbidden-cell propagation**: if a numbered wall is already fully
   satisfied, its remaining empty neighbours are *forbidden* (marked so
   no branch will ever try them).

3. **Early dead-end detection** (contradiction check):
   - ``current_bulbs > required``  →  wall over-satisfied.
   - ``required - current > |free_neighbours|``  →  can never be satisfied.
   - Any unlit cell with 0 legal placement candidates  →  dead end.

Notes on search category
------------------------
All three techniques are **constraint propagation** - the search is still
blind / systematic / complete:  no solution is ever skipped.
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

# Constraint propagation
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

    Iterates over numbered cells until fixpoint (no further changes):

    * **Forbidden** - numbered cell already satisfied → remaining free neighbours added to *forbidden* (they can never legally hold a bulb here).
    * **Forced** - ``remaining_needed == len(free_neighbours)`` → every
      free neighbour *must* hold a bulb; placed immediately.

    * **Contradiction** detected when:
        - ``current > required``
        - ``remaining_needed > len(free_neighbours)``
        - a forced placement is not legal (e.g. it would conflict with an existing bulb's line of sight)
    Parameters
    ----------
    forbidden: Mutable set; updated **in place** with newly derived forbidden cells.

    Returns
    -------
    is_contradiction : bool
    added_bulbs : list[Position] - Bulbs placed by propagation (caller must undo on backtrack).
    """
    added: List[Position] = []
    changed = True

    while changed:
        changed = False

        for num_cell_pos in board.numbered_cells():
            required = board.get_number(num_cell_pos)
            current  = count_adjacent_bulbs(board, state, num_cell_pos)

            if current > required:
                return True, added  # over-satisfied → contradiction

            free      = _free_neighbors(board, state, num_cell_pos, forbidden)
            remaining = required - current

            if remaining > len(free):
                return True, added  # impossible to satisfy → contradiction

            if remaining == 0:
                # Wall satisfied - forbid remaining free neighbours.
                for n in free:
                    if n not in forbidden:
                        forbidden.add(n)
                        changed = True

            elif remaining == len(free):
                # Every free neighbour is forced to be a bulb.
                for n in free:
                    if not can_place_bulb(board, state, n):
                        # Forced placement is illegal → contradiction.
                        return True, added
                    state.add_bulb(n)
                    added.append(n)
                    changed = True

    return False, added

def generate_candidates(board, state, forbidden: Set[Position], target) -> List[Position]:
    """Legal positions that would illuminate *target*, excluding forbidden cells."""
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

def _select_unlit_cell(board, state) -> Optional[Position]:
    lit = compute_illumination(board, state)
    for cell in board.white_cells():
        if cell not in lit:
            return cell

    return None   # all cells illuminated

class DFSSolver:
    """DFS solver with constraint propagation (forced/forbidden cells + dead-end detection)."""

    def __init__(self) -> None:
        self.nodes_expanded: int = 0

    def solve(self, board: Board) -> dict:
        self.nodes_expanded = 0
        initial_state = State()
        solution = self._dfs(board, initial_state, forbidden=set())
        return {
            "solution":       solution,
            "nodes_expanded": self.nodes_expanded,
            "solved":         solution is not None,
        }

    def _dfs(self, board, state, forbidden: Set[Position]) -> Optional[State]:
        self.nodes_expanded += 1

        # ── Constraint propagation (forced + forbidden) ───────────────
        # Work on a *local copy* of forbidden so sibling branches are
        # independent; forced bulbs are added to the shared *state*.
        local_forbidden = set(forbidden)
        contradiction, forced_bulbs = _propagate(board, state, local_forbidden)

        # Use try/finally to guarantee forced bulbs are always undone on
        # backtrack, even when an early return bypasses the normal flow.
        try:
            if contradiction:
                return None

            # ── Goal check ────────────────────────────────────────────
            if is_goal_state(board, state):
                return state.copy()   # copy captures forced bulbs too

            # ── Target selection (first unlit cell) ──────────────────
            target = _select_unlit_cell(board, state)

            if target is None:
                # All cells illuminated but goal test failed → dead end.
                return None

            # ── Candidate generation ──────────────────────────────────
            candidates = generate_candidates(board, state, local_forbidden, target)

            if not candidates:
                # _select_unlit_cell returned a 0-candidate cell → dead end.
                return None

            # ── Branch and backtrack ──────────────────────────────────
            for pos in candidates:
                state.add_bulb(pos)
                result = self._dfs(board, state, local_forbidden)
                state.remove_bulb(pos)

                if result is not None:
                    return result

            return None

        finally:
            # Always undo bulbs placed by propagation at this level.
            for pos in forced_bulbs:
                state.remove_bulb(pos)
