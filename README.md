# Light Up (Akari) Solver

A Python solver for the **Light Up** (also known as *Akari*) logic puzzle, built as an Introduction to AI assignment.

---

## What is Light Up?

Light Up is a grid-based logic puzzle where the goal is to place light bulbs on white cells such that:

- Every white cell is **illuminated** (in the same row/column as at least one bulb, with no wall in between).
- **No two bulbs** shine directly on each other (no bulb can see another bulb in its line of sight).
- **Numbered black walls** indicate exactly how many bulbs must be placed in the four directly adjacent cells.

---

## Project Structure

```
.
├── main.py                          # DFS entry point (CLI)
├── run.py                           # A* entry point (CLI + GUI launcher)
├── algorithms/
│   ├── dfs_solver.py                # Plain DFS solver
│   ├── dfs_solver_enhance.py        # DFS with constraint propagation
│   ├── a_star_solver.py             # Plain A* solver
│   ├── a_star_solver_enhanced.py    # A* with constraint propagation
│   ├── dfs_visual.py                # Step-emitting DFS for the GUI
│   ├── a_star_visual.py             # Step-emitting A* for the GUI
│   └── visual_common.py             # Shared Step / StepType types for GUI
├── core/
│   ├── board.py                     # Board representation (immutable grid, cached queries)
│   ├── state.py                     # Mutable bulb-placement state
│   ├── constraints.py               # Rule checking & illumination logic
│   ├── types.py                     # Shared type aliases (Position, etc.)
│   └── utils.py                     # Timing, memory, and render helpers
├── ui/
│   ├── game_ui.py                   # Pygame dual-pane visualiser
│   ├── renderer.py                  # Board drawing routines
│   └── theme.py                     # DARK / LIGHT colour themes
└── puzzles/                         # Puzzle files (.txt) + answer keys
```

---

## Requirements

- **Python 3.12+** (recommended)
- **pygame** — only required for the graphical UI

Install dependencies (inside a virtual environment is recommended):

```bash
pip install pygame
```

---

## How to Run

### DFS Solver (CLI)

`main.py` runs the **Enhanced DFS** solver by default.

```bash
# Solve a single puzzle (name, filename, or full path all work)
python main.py testcase_1
python main.py puzzles/testcase_1.txt

# Solve every puzzle in the puzzles/ directory at once
python main.py
```

### A\* Solver (CLI)

`run.py` runs the **Enhanced A\*** solver.

```bash
# Solve a single puzzle
python run.py testcase_1

# Solve every puzzle in the puzzles/ directory
python run.py
```

### Graphical UI

Launch the side-by-side animated visualiser (requires pygame):

```bash
# Open the GUI with the default puzzle
python run.py --ui

# Open the GUI pre-loaded with a specific puzzle
python run.py --ui testcase_1
```

The GUI runs both the **DFS + Propagation** and **A\* + Propagation** solvers simultaneously in a dual-pane view, with configurable animation speed and a live step log.

---

## Solvers

### Plain DFS (`dfs_solver.py`)

A straightforward depth-first search with backtracking.

1. Pick the first unlit white cell as the **target**.
2. Generate all positions (the cell itself or any cell in its line of sight) that could legally illuminate it.
3. Try each candidate, recurse, and backtrack on failure.

### Enhanced DFS (`dfs_solver_enhance.py`)

Extends plain DFS with **constraint propagation** applied at every node before branching:

| Technique | Description |
|---|---|
| **Forced-cell propagation** | If a numbered wall still needs *k* bulbs and has exactly *k* free adjacent cells, all of them are placed immediately (no branching). |
| **Forbidden-cell propagation** | If a numbered wall is already fully satisfied, its remaining free neighbours are marked forbidden and never tried. |
| **Early dead-end detection** | Detects over-satisfied walls, unsatisfiable walls, and unlit cells with zero legal placements before expanding further. |

Propagation is undone cleanly on backtrack via `try/finally`.

### Plain A\* (`a_star_solver.py`)

Uses a priority queue (min-heap) ordered by a fitness function:

```
f(n) = g(n) + h(n)
     = number of bulbs placed + number of remaining unlit white cells
```

Each node either places a bulb on the first unlit cell or skips it, generating two successors per step.

### Enhanced A\* (`a_star_solver_enhanced.py`)

Combines A\* best-first search with the same constraint propagation as the Enhanced DFS:

```
f(n) = g(n) + h(n)
     = bulbs placed + unlit white cells remaining
```

- Propagation (forced/forbidden) is applied to every node popped from the frontier.
- Contradiction checks prune infeasible states before they are pushed.
- Children are only added to the heap if propagation succeeds.

---

## Puzzle File Format

Puzzles are plain `.txt` files. Lines beginning with `;` or `//` are treated as comments and ignored. Characters may be space-separated or run together.

| Character | Meaning |
|---|---|
| `.` | Empty white cell (may receive a bulb) |
| `#` | Plain black wall |
| `0` – `4` | Numbered black wall (required adjacent bulb count) |

**Example (`testcase_1.txt`):**

```
;3 3
. 1 .
. # .
. . 2
```

---

## Output

Each solver run prints a summary table:

```
====================================================
  Puzzle : puzzles/testcase_1.txt
====================================================
  Size   : 3 x 3
  Grid   :
    . 1 .
    . # .
    . . 2

  Solved        : True
  Nodes expanded: 12
  Time elapsed  : 0.421 ms
  Peak memory   : 18.34 KB
  Goal verified : True

  Solution board:
    B * *
    * # B
    * B 2
```

### Output Legend

| Symbol | Meaning |
|---|---|
| `B` | Light bulb placed here |
| `*` | Cell illuminated by a bulb |
| `.` | Dark (unlit) cell |
| `#` | Plain black wall |
| `0`–`4` | Numbered black wall |

---

## GUI Controls

| Control | Action |
|---|---|
| **▶ Run** | Start / resume animation |
| **⏸ Pause** | Pause at the current step |
| **■ Reset** | Reset both solvers to the initial state |
| **Puzzle ▼** | Dropdown to select a puzzle from `puzzles/` |
| **Speed slider** | Range from `0.25×` (2 s/step) to `Max` (no delay) |
| **Theme toggle** | Switch between Dark and Light colour themes |

Step types are colour-coded in the board and step log:

| Colour | Meaning |
|---|---|
| 🟡 Yellow | Bulb placement (branch) |
| 🔴 Red | Bulb removal (backtrack) |
| 🟢 Green | Forced bulb (propagation) |
| 🟠 Orange | Contradiction detected |
