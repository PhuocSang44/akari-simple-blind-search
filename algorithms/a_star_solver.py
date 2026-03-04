from core import State, Board, Position
import heapq

from core.constraints import is_goal_state, count_adjacent_bulbs


class AStarSolver:
    def __init__(self):
        self.nodes_expanded =0

    def solve(self, board):
        init_white_cells = board.white_cells()
        init_bulbs = set()
        initial_state = State(init_white_cells, init_bulbs,
                              self.calculate_fitness(len(init_white_cells), len(init_bulbs)))
        solution = self._a_star(board, initial_state)

        return {
            'solution': solution,
            'nodes_expanded': self.nodes_expanded,
            'solved': solution is not None
        }

    def light_on(self, next_cell, unlit_cells, vis_cells):
        vis_set = set(vis_cells)
        unlit_cells[:] = [c for c in unlit_cells if c != next_cell and c not in vis_set]

    def calculate_fitness(self, num_bulbs, num_white_cells):
        return num_bulbs + num_white_cells

    def numbered_wall_constraint(self, board: Board, state: State, pos: Position) -> bool:
        for neighbour in board.neighbors(pos):
            if board.is_numbered_wall(neighbour):
                required = board.get_number(neighbour)
                current = count_adjacent_bulbs(board, state, neighbour)
                if current + 1 > required:
                    return False

        return True

    def get_successors(self, board, state):
        original = state.get_curr_white_cells()
        unlit_cells = list(original)
        line_up = list(original)

        if not unlit_cells:
            return []

        bulb_pos = state.bulb_positions()
        next_cell = unlit_cells[0]
        successors = []

        if self.numbered_wall_constraint(board, state, next_cell):

            vis_cells = board.visible_cells(next_cell)
            self.light_on(next_cell, unlit_cells, vis_cells)
            bulb_pos.add(next_cell)
            add_bulb_state = State(unlit_cells, bulb_pos,
                                   self.calculate_fitness(len(unlit_cells),
                                                          len(bulb_pos)))
            successors.append(add_bulb_state)

        line_up.pop(0)
        no_add_state = State(line_up, state.bulb_positions(),
                             self.calculate_fitness(len(line_up),
                                                    len(state.bulb_positions())))

        successors.append(no_add_state)

        return successors

    def _a_star(self, board, init_state):
        self.nodes_expanded +=1
        frontier = []
        heapq.heappush(frontier, init_state)

        while frontier:
            self.nodes_expanded += 1
            print(self.nodes_expanded)

            curr_state = heapq.heappop(frontier)
            if is_goal_state(board, curr_state):
                return curr_state.copy()

            for next_state in self.get_successors(board, curr_state):
                heapq.heappush(frontier, next_state)

        return None
