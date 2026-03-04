from __future__ import annotations
from typing import Set
from core.types import Position


class State:
    """Represents the current placement of light bulbs on a board.

    A *State* is a thin, mutable container that **only** stores which cells
    contain a bulb.  It deliberately does **not** cache illumination, fitness, or constraint information => those are computed on demand by other modules.
    """

    def __init__(self) -> None:
        """Create an empty state (no bulbs placed)."""
        self._bulbs: Set[Position] = set()

    # ------------------------------------------------------------------
    # Bulb manipulation
    # ------------------------------------------------------------------
    def add_bulb(self, pos: Position):
        self._bulbs.add(pos)

    def remove_bulb(self, pos: Position):
        self._bulbs.remove(pos)

    def has_bulb(self, pos: Position) -> bool:
        return pos in self._bulbs

    def bulb_positions(self) -> Set[Position]:
        """Return a **copy** of the current set of bulb positions."""
        return set(self._bulbs)

    def copy(self) -> "State":
        """Return an independent deep copy of this state."""
        new_state = State()
        new_state._bulbs = set(self._bulbs)
        return new_state


    
