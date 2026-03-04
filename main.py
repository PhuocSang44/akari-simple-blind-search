import sys
import os
from core.board import Board
from core.constraints import is_goal_state
from core.utils import time_execution, measure_memory, render_state
from algorithms.dfs_solver import DFSSolver
from algorithms.dfs_solver_enhance import DFSSolver as DFSSolverEnhanced

PUZZLES_DIR = "puzzles"

def run_dfs(board: Board) -> dict:
    """Thin wrapper so time_execution / measure_memory can call it."""
    solver = DFSSolver()
    return solver.solve(board)

def run_dfs_enhanced(board: Board) -> dict:
    """Thin wrapper so time_execution / measure_memory can call it."""
    solver = DFSSolverEnhanced()
    return solver.solve(board)

def test_puzzle(path: str) -> None:
    print(f"\n{'='*52}")
    print(f"  Puzzle : {path}")
    print(f"{'='*52}")

    try:
        board = Board.from_file(path)
    except FileNotFoundError:
        print("  [SKIP] file not found.\n")
        return

    print(f"  Size   : {board.width} x {board.height}")
    print(f"  Grid   :\n")
    for line in str(board).splitlines():
        print(f"    {line}")

    # # time measurement
    # result, elapsed = time_execution(run_dfs, board)

    # # memory measurement (re-run to capture peak allocation)
    # _, peak_bytes = measure_memory(run_dfs, board)

    # time measurement
    result, elapsed = time_execution(run_dfs_enhanced, board)

    # memory measurement (re-run to capture peak allocation)
    _, peak_bytes = measure_memory(run_dfs_enhanced, board)

    solved   = result["solved"]
    nodes    = result["nodes_expanded"]
    solution = result["solution"]

    print(f"\n  Solved        : {solved}")
    print(f"  Nodes expanded: {nodes}")
    print(f"  Time elapsed  : {elapsed * 1000:.3f} ms")
    print(f"  Peak memory   : {peak_bytes / 1024:.2f} KB")

    if solution:
        valid = is_goal_state(board, solution)
        print(f"  Goal verified : {valid}")
        print(f"\n  Solution board:\n")
        for line in render_state(board, solution).splitlines():
            print(f"    {line}")
    else:
        print("  No solution found.")

def resolve_path(arg: str) -> str:
    """Resolve a user-supplied name to a file path.

    Accepted forms (in order of precedence):
      - absolute or relative path as-is  (e.g. puzzles/easy.txt)
      - bare filename                    (e.g. easy.txt  -> puzzles/easy.txt)
      - filename without extension       (e.g. easy      -> puzzles/easy.txt)
    """
    if os.path.exists(arg):
        return arg
    # try inside PUZZLES_DIR
    candidate = os.path.join(PUZZLES_DIR, arg)
    if os.path.exists(candidate):
        return candidate
    # try adding .txt extension
    candidate_txt = candidate if candidate.endswith(".txt") else candidate + ".txt"
    if os.path.exists(candidate_txt):
        return candidate_txt
    # return original arg so test_puzzle prints a clean "not found" message
    return arg

def collect_puzzle_files() -> list:
    """Return all .txt files in PUZZLES_DIR, sorted, skipping test files."""
    if not os.path.isdir(PUZZLES_DIR):
        return []
    files = sorted(
        os.path.join(PUZZLES_DIR, f)
        for f in os.listdir(PUZZLES_DIR)
        if f.endswith(".txt") and not f.startswith("test")
    )
    return files

def main() -> None:
    args = sys.argv[1:]

    # ── GUI mode: python main.py --ui [puzzle] ────────────────────
    if "--ui" in args:
        args_copy = [a for a in args if a != "--ui"]
        puzzle_hint = args_copy[0] if args_copy else None
        from ui.game_ui import AkariUI
        app = AkariUI(initial_puzzle=puzzle_hint)
        app.run()
        return

    # ── CLI mode (original behaviour) ─────────────────────────────
    print("\nLight Up (Akari) -- DFS Solver")
    print("Legend: B=bulb  *=illuminated  .=dark  #=wall  0-4=numbered wall")
    print("Usage : python main.py [puzzle_name_or_path]")
    print("        python main.py --ui [puzzle]   (graphical mode)")

    if args:
        # single file mode
        path = resolve_path(args[0])
        test_puzzle(path)
    else:
        # run every puzzle in the puzzles/ directory
        files = collect_puzzle_files()
        if not files:
            print(f"\n  No puzzle files found in '{PUZZLES_DIR}/'.")
        for path in files:
            test_puzzle(path)

    print(f"\n{'='*52}\n")

if __name__ == "__main__":
    main()
