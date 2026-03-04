from typing import List
from core.types import Position
import os

_WALL_CHARS = {"#", "0", "1", "2", "3", "4"}
class Board:
    def __init__(self, grid: List[List[str]]) -> None:
        # Store as a tuple-of-tuples so the board is effectively immutable.
        self._grid = tuple(tuple(row) for row in grid)
        self._height = len(self._grid)
        self._width = len(self._grid[0]) if self._height > 0 else 0

        # Pre-compute commonly queried cell lists once.
        self._white_cells = []
        self._numbered_cells = []
        for r in range(self._height):
            for c in range(self._width):
                ch = self._grid[r][c]
                if ch == ".":
                    self._white_cells.append((r, c))
                elif ch in {"0", "1", "2", "3", "4"}:
                    self._numbered_cells.append((r, c))

        # Pre-compute neighbors and visible cells for every position.
        self._neighbors_cache: dict = {}
        self._visible_cache: dict = {}
        for r in range(self._height):
            for c in range(self._width):
                pos = (r, c)
                # neighbors
                nbrs = []
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self._height and 0 <= nc < self._width:
                        nbrs.append((nr, nc))
                self._neighbors_cache[pos] = nbrs
                # visible cells (ray-cast in 4 directions, stop at walls)
                vis = []
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr, nc = r + dr, c + dc
                    while 0 <= nr < self._height and 0 <= nc < self._width:
                        if self._grid[nr][nc] in _WALL_CHARS:
                            break
                        vis.append((nr, nc))
                        nr += dr
                        nc += dc
                self._visible_cache[pos] = vis

    @classmethod
    def from_file(cls, filename: str) -> "Board":
        """Load a Board from a plain-text puzzle file.

        File format (each line = one row):
        * Tokens are separated by whitespace **or** run together with no
          separator.
        * Valid tokens: ``#``, ``0``-``4``, ``.``

        Example (space-separated)::

            . . 1 . #
            . # . . .
            1 . . . .

        Example (no separator)::

            ..1.#
            .#...
            1....

        Args:
            filename: Path to the puzzle file (absolute or relative to cwd).

        Returns:
            A new :class:`Board` instance.

        Raises:
            FileNotFoundError: If *filename* does not exist.
            ValueError: If the file contains an unrecognised cell character.
        """
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Puzzle file not found: '{filename}'")

        valid = {".", "#", "0", "1", "2", "3", "4"}
        grid: List[List[str]] = []

        with open(filename, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line or line.startswith(";") or line.startswith("//"):
                    continue  # skip blank lines and comment lines
                # Support both space-separated tokens and no-separator runs.
                tokens = line.split() if " " in line or "\t" in line else list(line)
                for tok in tokens:
                    if tok not in valid:
                        raise ValueError(
                            f"Unrecognised cell character '{tok}' in '{filename}'."
                        )
                grid.append(tokens)

        return cls(grid)

    @property
    def width(self) -> int:
        return self._width #number of columns

    @property
    def height(self) -> int:
        return self._height #number of rows

    def in_bounds(self, pos: Position):
        r, c = pos
        return 0 <= r < self._height and 0 <= c < self._width

    def is_wall(self, pos: Position):
        r, c = pos
        return self._grid[r][c] in _WALL_CHARS

    def is_numbered_wall(self, pos: Position):
        r, c = pos
        return self._grid[r][c] in {"0", "1", "2", "3", "4"}

    def get_number(self, pos: Position) -> int:
        r, c = pos
        ch = self._grid[r][c]
        if ch not in {"0", "1", "2", "3", "4"}:
            raise ValueError(f"Cell {pos} is not a numbered wall (got '{ch}').")
        return int(ch)

    def is_empty(self, pos: Position):
        r, c = pos
        return self._grid[r][c] == "." #empty cell (white cell)

    def neighbors(self, pos: Position) -> List[Position]:
        "Neighbor is up/down/left/right adjacent cell (regardless of walls)."
        return self._neighbors_cache[pos]

    def visible_cells(self, pos: Position) -> List[Position]:
        """Return all cells visible from *pos* in four cardinal directions.
        A cell is visible if it can be reached by moving in a straight line
        without crossing a wall.  The starting cell itself is **not** included.
        Walls are not included.
        """
        return self._visible_cache[pos]

    def white_cells(self) -> List[Position]:
        return list(self._white_cells)

    def numbered_cells(self) -> List[Position]:
        return list(self._numbered_cells)

    def __str__(self) -> str:
        """Return a printable grid using the original cell characters."""
        return "\n".join(" ".join(row) for row in self._grid)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Board({self._width}x{self._height})"
