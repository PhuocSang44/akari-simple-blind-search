from __future__ import annotations
from typing import Set

from core import Board
from core.types import Position


class State:
    """Represents the current placement of light bulbs on a board.

    A *State* is a thin, mutable container that **only** stores which cells
    contain a bulb.
    It deliberately does **not** cache illumination, fitness, or constraint information
    => those are computed on demand by other modules.
    """

    def __init__(self,
                 curr_white_cells: list = None,
                 curr_bulbs: set = None,
                 f_n_value: int = None) -> None:
        """Create an empty state (no bulbs placed)."""
        self._bulbs: Set[Position] = set() \
            if curr_bulbs is None else curr_bulbs #added for A*

        # used in A*
        self._curr_white_cells: list = curr_white_cells if curr_white_cells is not None else []
        self._f_n = f_n_value if f_n_value is not None else None

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

        new_state._curr_white_cells = list(self._curr_white_cells) \
            if self._curr_white_cells else []  #added for A*

        new_state._f_n = self._f_n

        return new_state

    def get_f_n(self):
        return self._f_n

    def get_curr_white_cells(self):
        return self._curr_white_cells

    def __lt__(self, other):
        return self._f_n < other.get_f_n()
"""
import heapq

from src.state import State


def a_star_solver(initial_board):
    frontier = []

    start_state = State(initial_board)
    heapq.heappush(frontier, start_state)

    max_memory_states = 0
    states = 0

    while frontier:
        print(states)
        states += 1

        max_memory_states = max(max_memory_states, len(frontier))

        current_state = heapq.heappop(frontier)

        if current_state.board.is_goal():
            return current_state.board, max_memory_states

        for next_state in current_state.get_successors():
            heapq.heappush(frontier, next_state)

    return None, max_memory_states


"""
"""
SELF DEFINITIONS
'.' is white cell
'*' is lit cell
'B' is Bulb
'X' is block cell with no number
'0-4' is block cell with number

CONSTRAINTS
All cells are lit by at least on bulb
All bulbs are placed correctly next to the black numbered cells
No bulbs see each other
"""
"""
class State:
    def __init__(self, board, r_idx=0, c_idx=0, n_bulbs=0):
        self.board = board
        self.r_idx = r_idx
        self.c_idx = c_idx

        self.g_n = n_bulbs

        self.h_n = self.calculate_heuristic()
        self.f_n = self.g_n + self.h_n #f(n) = g(n) + h(n)

    def calculate_heuristic(self):
        count = 0
        for row in range(self.board.n_rows):
            for col in range(self.board.n_cols):
                if self.board.grid[row][col] == '.' and not self.board.is_lit(row, col):
                    count += 1
        return count

    #operator overloading
    def __lt__(self, other):
        return self.f_n < other.f_n

    def get_successors(self):
        successors = []
        r_idx, c_idx = self.r_idx, self.c_idx
        board = self.board

        if c_idx + 1 < board.n_cols:
            next_r, next_c = r_idx, c_idx + 1
        else:
            next_r, next_c = r_idx + 1, 0

        if r_idx >= board.n_rows:
            return successors

        cell_value = board.grid[r_idx][c_idx]
        if cell_value.isdigit() or cell_value == 'X':
            successors.append(State(board, next_r, next_c, self.g_n))
            return successors

        #Child Node: place the bulb
        if self.board.is_legal_to_place_bulb(r_idx, c_idx):
            #deep copy
            new_board = board.copy()
            new_board.light_switch_on(r_idx, c_idx)
            fast_r, fast_c = new_board.get_next_actionable_cell(next_r, next_c)
            successors.append(State(new_board, fast_r, fast_c, self.g_n + 1))

        #Child Node: empty
        successors.append(State(board, next_r, next_c, self.g_n))

        return successors
        
"""
"""
SELF DEFINITIONS
'.' is white cell
'*' is lit cell
'B' is Bulb
'X' is block cell with no number
'0-4' is block cell with number

CONSTRAINTS
All cells are lit by at least on bulb
All bulbs are placed correctly next to the black numbered cells
No bulbs see each other
"""
"""
import copy


class Board:
    def __init__(self, grid):
        self.grid = grid  # 2D List
        self.n_rows = len(grid)
        self.n_cols= len(grid[0])

    @staticmethod
    def from_file(filename):
        with open(filename, 'r') as f:
            lines = f.readlines()
            # Skip the first line (dimensions) and read the rest
            grid = [line.split() for line in lines[1:]]
        return Board(grid)

    def is_valid(self, r, c):
        return 0 <= r < self.n_rows and 0 <= c < self.n_cols

    def is_lit(self, r_idx, c_idx):
        return self.grid[r_idx][c_idx] == '*'

    def copy(self):
        return Board(copy.deepcopy(self.grid))

    def get_next_actionable_cell(self, start_r, start_c):
        r, c = start_r, start_c
        while r < self.n_rows:
            if self.grid[r][c] == '.':
                return r, c

            c += 1
            if c >= self.n_cols:
                c = 0
                r += 1

        return r, c

    def is_legal_to_place_bulb(self, r_idx, c_idx):

        #No bulbs see each other
        if self.is_lit(r_idx, c_idx) or self.grid[r_idx][c_idx] == 'B':
            return False

        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        for dr, dc in directions:
            nr, nc = r_idx + dr, c_idx + dc

            #Neighbors in the board
            if self.is_valid(nr, nc):
                neighbor_value = self.grid[nr][nc]

                if neighbor_value.isdigit():
                    limit = int(neighbor_value)

                    current_bulbs = 0
                    #check neighbors of neighbor
                    for ddr, ddc in directions:
                        nnr, nnc = nr + ddr, nc + ddc
                        if self.is_valid(nnr, nnc) and self.grid[nnr][nnc] == 'B':
                            current_bulbs += 1

                    if current_bulbs >= limit:
                        return False

        return True

    def light_switch_on(self, r_idx, c_idx):
        self.grid[r_idx][c_idx] = 'B'

        # 2. Cast light Up, Down, Left, Right
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

        for dr, dc in directions:
            nr, nc = r_idx + dr, c_idx + dc

            # Keep moving in the current direction until blocked
            while self.is_valid(nr, nc):
                cell_value = self.grid[nr][nc]

                if cell_value == 'X' or cell_value.isdigit():
                    break

                if cell_value == '.':
                    self.grid[nr][nc] = '*'

                nr += dr
                nc += dc

    def is_goal(self):
        for row in range(self.n_rows):
            for col in range(self.n_cols):
                if self.grid[row][col] == '.':
                    return False

        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        for row in range(self.n_rows):
            for col in range(self.n_cols):
                cell_value = self.grid[row][col]

                if cell_value.isdigit():
                    limit = int(cell_value)
                    current_bulbs = 0

                    for dr, dc in directions:
                        nr, nc = row + dr, col + dc
                        if self.is_valid(nr, nc) and self.grid[nr][nc] == 'B':
                            current_bulbs += 1

                    if current_bulbs != limit:
                        return False

        return True

    def display(self):

        print('--------------------')
        for row in self.grid:
            print(" ".join(row))
"""
    
