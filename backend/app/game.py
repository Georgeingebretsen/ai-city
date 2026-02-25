import math
import random

from .models import COLOR_NAMES


def distribute_tiles(grid_size: int, agent_ids: list[int]) -> list[tuple[int, int, int]]:
    """Give each agent a contiguous rectangular region of the grid.

    Recursively splits the grid along the longer axis, proportional
    to the number of agents on each side.  For 4 agents this produces
    exact quadrants (corners); other counts get a treemap-style layout.

    Returns list of (x, y, owner_id).
    """
    assignments: list[tuple[int, int, int]] = []

    def _assign(agents: list[int], x0: int, y0: int, x1: int, y1: int):
        if len(agents) == 1:
            for x in range(x0, x1):
                for y in range(y0, y1):
                    assignments.append((x, y, agents[0]))
            return

        mid = len(agents) // 2
        left, right = agents[:mid], agents[mid:]

        if (x1 - x0) >= (y1 - y0):
            # Split vertically
            split = x0 + round((x1 - x0) * len(left) / len(agents))
            _assign(left, x0, y0, split, y1)
            _assign(right, split, y0, x1, y1)
        else:
            # Split horizontally
            split = y0 + round((y1 - y0) * len(left) / len(agents))
            _assign(left, x0, y0, x1, split)
            _assign(right, x0, split, x1, y1)

    _assign(list(agent_ids), 0, 0, grid_size, grid_size)
    return assignments


def distribute_paint(agent_ids: list[int], grid_size: int) -> list[tuple[int, str, int]]:
    """Give each agent 4 random colors with enough total paint to cover the grid.

    Quantity per color is calculated so that total paint across all agents
    exactly covers the grid (ceiling division ensures no shortfall with
    odd agent counts). Ensures all 8 colors are covered across agents.
    Returns list of (agent_id, color, quantity).
    """
    n = len(agent_ids)
    colors = list(COLOR_NAMES)
    quantity = math.ceil(grid_size ** 2 / (n * 4))

    # First pass: ensure coverage — round-robin assign colors to agents
    agent_colors: dict[int, set[str]] = {aid: set() for aid in agent_ids}
    shuffled = list(colors)
    random.shuffle(shuffled)
    for i, color in enumerate(shuffled):
        agent_colors[agent_ids[i % n]].add(color)

    # Second pass: top up each agent to exactly 4 colors
    for aid in agent_ids:
        available = [c for c in colors if c not in agent_colors[aid]]
        while len(agent_colors[aid]) < 4:
            pick = random.choice(available)
            agent_colors[aid].add(pick)
            available.remove(pick)

    result = []
    for aid in agent_ids:
        for color in agent_colors[aid]:
            result.append((aid, color, quantity))
    return result
