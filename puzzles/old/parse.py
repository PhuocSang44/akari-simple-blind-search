"""parse.py – Convert an Akari_dataset.json entry into .txt puzzle files.

Usage
-----
    python puzzles/parse.py <test_number>

Examples
--------
    python puzzles/parse.py 931
    python puzzles/parse.py 920

Output
------
* puzzles/<key>.txt         - problem board (uses . # 0-4 notation)
* puzzles/answers/<key>.txt - solution board (same + B for bulbs)

JSON format
-----------
  First line of "problem" / "solution" value: "<rows> <cols>"
  Then rows xcols tokens separated by spaces:
      -   → . (empty white cell)
      x   → # (unnumbered wall)
      0-4 → 0-4 (numbered wall)
      o   → B (bulb, solution only)
"""

import json
import os
import sys

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATASET_FILE = os.path.join(_SCRIPT_DIR, "Akari_dataset.json")
_ANSWERS_DIR = os.path.join(_SCRIPT_DIR, "answers")

# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

_PROBLEM_MAP = {"-": ".", "x": "#"}
_SOLUTION_MAP = {"-": ".", "x": "#", "o": "B"}


def _convert_row(tokens: list[str], char_map: dict[str, str]) -> str:
    """Convert a list of JSON tokens to a space-separated .txt row."""
    converted = []
    for tok in tokens:
        converted.append(char_map.get(tok, tok))  # numbers pass through unchanged
    return " ".join(converted)


def _parse_grid(raw: str, char_map: dict[str, str]) -> tuple[int, int, list[str]]:
    """Parse a JSON grid string.

    Returns
    -------
    (rows, cols, lines)  where *lines* are already converted .txt rows.
    """
    lines = raw.strip().split("\n")
    # First line contains dimensions: "<rows> <cols>"
    dims = lines[0].split()
    rows, cols = int(dims[0]), int(dims[1])
    grid_lines = []
    for line in lines[1:]:
        tokens = line.split()
        grid_lines.append(_convert_row(tokens, char_map))
    return rows, cols, grid_lines


def _write_txt(path: str, key: str, rows: int, cols: int,
               grid_lines: list[str], kind: str) -> None:
    """Write the converted grid to *path*."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"; {kind} - {key} ({rows}x{cols})\n")
        for row in grid_lines:
            f.write(row + "\n")


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def find_entry(data: dict, number: int) -> tuple[str, dict] | None:
    """Return (key, entry) whose key starts with ``<number>_``, or None."""
    prefix = f"{number}_"
    for key, entry in data.items():
        if key.startswith(prefix):
            return key, entry
    return None


def parse_and_write(number: int) -> None:
    # Load dataset
    if not os.path.isfile(_DATASET_FILE):
        print(f"[ERROR] Dataset file not found: {_DATASET_FILE}")
        sys.exit(1)

    with open(_DATASET_FILE, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    data = dataset.get("data", dataset)  # handle both {"data": {...}} and flat dict

    result = find_entry(data, number)
    if result is None:
        print(f"[ERROR] No entry found for test number {number} in dataset.")
        sys.exit(1)

    key, entry = result
    print(f"Found entry: {key}")

    # ---- Problem ----
    problem_raw = entry.get("problem", "")
    if not problem_raw:
        print(f"[WARN] Entry '{key}' has no 'problem' field – skipping problem file.")
    else:
        rows, cols, grid_lines = _parse_grid(problem_raw, _PROBLEM_MAP)
        out_path = os.path.join(_SCRIPT_DIR, f"{key}.txt")
        _write_txt(out_path, key, rows, cols, grid_lines, "Problem")
        print(f"  Problem  → {out_path}")

    # ---- Solution ----
    solution_raw = entry.get("solution", "")
    if not solution_raw:
        print(f"[WARN] Entry '{key}' has no 'solution' field – skipping solution file.")
    else:
        rows, cols, grid_lines = _parse_grid(solution_raw, _SOLUTION_MAP)
        out_path = os.path.join(_ANSWERS_DIR, f"{key}.txt")
        _write_txt(out_path, key, rows, cols, grid_lines, "Solution")
        print(f"  Solution → {out_path}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python puzzles/parse.py <test_number>")
        print("  e.g. python puzzles/parse.py 931")
        sys.exit(1)

    try:
        number = int(sys.argv[1])
    except ValueError:
        print(f"[ERROR] Test number must be an integer, got: {sys.argv[1]!r}")
        sys.exit(1)

    parse_and_write(number)


if __name__ == "__main__":
    main()
