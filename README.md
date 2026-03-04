# Light Up (Akari) Solver

A Python solver for the **Light Up** (also known as *Akari*) logic puzzle, built as an Introduction to AI assignment.

---

## What is Light Up?

Light Up is a grid-based logic puzzle. The goal is to place light bulbs on white cells so that:

- Every white cell is illuminated (lit by at least one bulb in its row or column).
- No two bulbs shine directly on each other (no bulb can see another bulb in a straight line).
- Numbered black walls indicate exactly how many bulbs must be placed in the four adjacent cells.

---

## How to Run

Make sure you have **Python 3.8+** installed.

```bash
# Solve a specific puzzle
python main.py easy
python main.py puzzles/hard.txt

# Solve all puzzles in the puzzles/ folder at once
python main.py
```

The solver prints the board, stats (time, memory, nodes expanded), and the solution grid.

---

## Puzzle File Format

Puzzles are plain `.txt` files. Each character represents one cell:

| Character | Meaning                                      |
|-----------|----------------------------------------------|
| `.`       | Empty white cell (may receive a bulb)        |
| `#`       | Black wall (no number)                       |
| `0–4`     | Numbered black wall (adjacent bulb count)    |

**Example** (`sample.txt`):
```
....2
..#..
```

Spaces between characters are also accepted.

---

## Project Structure

```
.
├── main.py                     # Entry point
├── algorithms/
│   ├── dfs_solver.py           # Plain DFS solver
│   └── dfs_solver_enhance.py   # DFS with smarter suggestions (see below)
├── core/
│   ├── board.py                # Board representation
│   ├── state.py                # Search state (bulb placements)
│   ├── constraints.py          # Rule checking and illumination logic
│   ├── types.py                # Shared type aliases
│   └── utils.py                # Timing, memory, and display helpers
├── puzzles/                    # Puzzle files (.txt) + answer keys
└── ui/                         # Visual game interface
```

---

## Solvers

### Plain DFS (`dfs_solver.py`)

A straightforward depth-first search. It picks an unlit cell and tries placing a bulb in every position that could illuminate it, backtracking when a contradiction is found.

### Enhanced DFS (`dfs_solver_enhance.py`)

The same DFS backbone, but with smarter suggestions before each branching step — it looks ahead to identify cells that are already forced or provably impossible, helping the search avoid dead ends much earlier. This typically reduces the number of nodes explored significantly on harder puzzles.

To switch solvers, edit the commented-out lines in `main.py` (swap `run_dfs` for `run_dfs_enhanced`).

---

## Output Legend

```
B  = light bulb placed here
*  = illuminated cell
.  = dark (unlit) cell
#  = black wall
0–4 = numbered wall
```

---