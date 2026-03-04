from typing import Set

from core.board import Board
from core.state import State
from core.types import Position

def count_adjacent_bulbs(board: Board, state: State, pos: Position) -> int:
    count = 0
    for neighbour in board.neighbors(pos):
        if state.has_bulb(neighbour):
            count += 1
    return count

def can_place_bulb(board: Board, state: State, pos: Position) -> bool:
    if not board.is_empty(pos):
        return False

    for visible in board.visible_cells(pos):
        if state.has_bulb(visible):
            return False

    for neighbour in board.neighbors(pos):
        if board.is_numbered_wall(neighbour):
            required = board.get_number(neighbour)
            current = count_adjacent_bulbs(board, state, neighbour)
            # After placement, the count will increase by 1.
            if current + 1 > required:
                return False

    return True

def compute_illumination(board: Board, state: State) -> Set[Position]:
    lit = set()
    for bulb_pos in state.bulb_positions():
        # The bulb itself is illuminated.
        lit.add(bulb_pos)
        # All cells visible from the bulb are illuminated.
        for cell in board.visible_cells(bulb_pos):
            lit.add(cell)
    return lit

def number_constraint_violations(board: Board, state: State) -> int:
    total = 0
    for pos in board.numbered_cells():
        required = board.get_number(pos)
        actual = count_adjacent_bulbs(board, state, pos)
        total += abs(required - actual)
    return total

# def bulb_conflicts(board: Board, state: State) -> int:
#     conflicts = 0
#     bulbs = state.bulb_positions()
#     for bulb_pos in bulbs:
#         for visible in board.visible_cells(bulb_pos):
#             if visible in bulbs:
#                 conflicts += 1
#     # Each conflict is discovered twice (A sees B, B sees A).
#     return conflicts // 2

def is_goal_state(board: Board, state: State):
    # Condition 3 – no bulb conflicts.
    # if bulb_conflicts(board, state) > 0:
    #     return False

    # Condition 2 – all numbered constraints exactly met.
    if number_constraint_violations(board, state) > 0:
        return False

    # Condition 1 – every white cell is illuminated.
    lit = compute_illumination(board, state)
    for cell in board.white_cells():
        if cell not in lit:
            return False

    return True

