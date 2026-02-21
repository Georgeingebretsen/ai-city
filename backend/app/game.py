import random

from .models import COLOR_NAMES


def distribute_tiles(grid_size: int, agent_ids: list[int]) -> list[tuple[int, int, int]]:
    """Randomly assign all tiles to agents. Returns list of (x, y, owner_id)."""
    all_coords = [(x, y) for x in range(grid_size) for y in range(grid_size)]
    random.shuffle(all_coords)

    assignments = []
    n = len(agent_ids)
    for i, (x, y) in enumerate(all_coords):
        owner = agent_ids[i % n]
        assignments.append((x, y, owner))
    return assignments


def distribute_paint(agent_ids: list[int]) -> list[tuple[int, str, int]]:
    """Give each agent 64 units each of 4 random colors.

    Ensures all 8 colors are covered across agents.
    Returns list of (agent_id, color, quantity).
    """
    n = len(agent_ids)
    colors = list(COLOR_NAMES)

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
            result.append((aid, color, 64))
    return result
