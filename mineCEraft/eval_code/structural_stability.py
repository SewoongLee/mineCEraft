from collections import deque, defaultdict
from typing import List, Dict, Any, Tuple, Set
from .utils import to_int

def is_ground_connected(
    coords: List[Dict[str, Any]],
    mark_visit: bool = False,
) -> int:
    """
    Return 1 if every block is connected (via face adjacency) to at least one
    block with y <= 0. Otherwise return 0.

    - Face adjacency (6-neighborhood): +/-1 step on exactly one axis.
    - If `mark_visit=True`, each input coord dict receives a boolean `visit` flag
      indicating whether it was reached by the BFS from the ground.

    Args:
        coords: [{"x":..,"y":..,"z":.., ...}, ...]
        mark_visit: whether to set `visit` flags in-place on `coords`
    """

    # Empty set: no floating blocks to worry about.
    if not coords:
        return 1

    # Normalize coordinates and build a map from (x,y,z) -> list of indices.
    pos_to_indices = defaultdict(list)
    positions: List[Tuple[int, int, int]] = []

    for i, c in enumerate(coords):
        x, y, z = to_int(c["x"]), to_int(c["y"]), to_int(c["z"])
        positions.append((x, y, z))
        pos_to_indices[(x, y, z)].append(i)
        if mark_visit:
            c["visit"] = False

    # Initialize BFS queue with all "ground" blocks: y <= 0.
    queue: deque[Tuple[int, int, int]] = deque()
    visited: Set[Tuple[int, int, int]] = set()

    for (x, y, z) in positions:
        if y <= 0:  # ★ 여기만 바뀜: y == 0 → y <= 0
            if (x, y, z) not in visited:
                visited.add((x, y, z))
                queue.append((x, y, z))
            if mark_visit:
                for idx in pos_to_indices[(x, y, z)]:
                    coords[idx]["visit"] = True

    # If there are no ground-contact blocks at all (no y <= 0), everything is floating.
    if not queue:
        return 0

    # 6-neighborhood (face-adjacent) deltas: +/-1 along exactly one axis
    neighbors = [
        (+1, 0, 0), (-1, 0, 0),
        (0, +1, 0), (0, -1, 0),
        (0, 0, +1), (0, 0, -1),
    ]

    # Standard BFS: spread from ground up to all reachable blocks.
    while queue:
        x, y, z = queue.popleft()
        for dx, dy, dz in neighbors:
            nx, ny, nz = x + dx, y + dy, z + dz
            npos = (nx, ny, nz)
            if npos in pos_to_indices and npos not in visited:
                visited.add(npos)
                queue.append(npos)
                if mark_visit:
                    for idx in pos_to_indices[npos]:
                        coords[idx]["visit"] = True

    # If any position was never visited, it is floating.
    for p in positions:
        if p not in visited:
            return 0

    return 1
