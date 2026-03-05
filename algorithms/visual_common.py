"""Shared step data types for visual solvers.

Both DFS and A* visual solvers emit ``Step`` objects through a queue.
This module defines the unified ``StepType`` enum and ``Step`` dataclass
so the UI can handle both algorithms with a single ``_apply_step`` method.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Set

from core.types import Position


class StepType(Enum):
    START           = auto()
    PLACE_BULB      = auto()   # normal branch
    REMOVE_BULB     = auto()   # DFS backtrack
    FORCED_BULB     = auto()   # constraint propagation
    REMOVE_FORCED   = auto()   # DFS undo forced on backtrack
    FORBIDDEN       = auto()   # cell marked forbidden
    CONTRADICTION   = auto()   # dead-end detected
    POP_NODE        = auto()   # A* node popped from frontier
    GOAL_CHECK      = auto()
    SOLVED          = auto()
    NO_SOLUTION     = auto()


@dataclass
class Step:
    step_type: StepType
    position: Optional[Position] = None
    nodes_expanded: int = 0
    # DFS-specific
    depth: int = 0
    # A*-specific
    frontier_size: int = 0
    f_n: float = 0.0
    # common
    bulb_count: int = 0
    message: str = ""
    bulb_positions: Set[Position] = field(default_factory=set)
    lit_cells: Set[Position] = field(default_factory=set)
    elapsed: float = 0.0
    candidates: List[Position] = field(default_factory=list)

