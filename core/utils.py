
import time
import tracemalloc
from typing import Any, Callable, Tuple

from core.board import Board
from core.constraints import compute_illumination
from core.state import State


# Performance measurement
def time_execution(func: Callable, *args: Any, **kwargs: Any) -> Tuple[Any, float]:
    """Execute *func* and return ``(result, elapsed_seconds)``.

    Args:
        func: The callable to time.
        *args: Positional arguments forwarded to *func*.
        **kwargs: Keyword arguments forwarded to *func*.

    Returns:
        A tuple of the function's return value and wall-clock elapsed time
        in seconds.
    """
    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return result, elapsed


def measure_memory(func: Callable, *args: Any, **kwargs: Any) -> Tuple[Any, int]:
    """Execute *func* and return ``(result, peak_memory_bytes)``.

    Uses :mod:`tracemalloc` to capture peak memory allocation during the
    call.  If ``tracemalloc`` is already running it will be restarted so
    that the snapshot only reflects *func*'s allocation.

    Args:
        func: The callable to measure.
        *args: Positional arguments forwarded to *func*.
        **kwargs: Keyword arguments forwarded to *func*.

    Returns:
        A tuple of the function's return value and peak memory usage in
        bytes.
    """
    # Ensure a clean tracing session.
    if tracemalloc.is_tracing():
        tracemalloc.stop()
    tracemalloc.start()
    try:
        result = func(*args, **kwargs)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, peak

def render_state(board: Board, state: State) -> str:
    lit = compute_illumination(board, state)
    rows = []
    for r in range(board.height):
        row_chars = []
        for c in range(board.width):
            pos = (r, c)
            if board.is_numbered_wall(pos):
                row_chars.append(str(board.get_number(pos)))
            elif board.is_wall(pos):
                row_chars.append("#")
            elif state.has_bulb(pos):
                row_chars.append("B")
            elif pos in lit:
                row_chars.append("*")
            else:
                row_chars.append(".")
        rows.append(" ".join(row_chars))
    return "\n".join(rows)



