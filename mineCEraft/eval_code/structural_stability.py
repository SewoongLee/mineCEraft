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
        if y <= 0:
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


def _max_horizontal_span_from_origin(
    origin: Tuple[int, int, int],
    pos_to_indices: Dict[Tuple[int, int, int], List[int]],
) -> int:
    """
    Given an origin position (x, y, z), compute the maximum number of blocks
    that extend contiguously in any horizontal cardinal direction.

    For example, if blocks exist at:
      (0, 1, 0) [origin]
      (1, 1, 0)
      (2, 1, 0)
      (3, 1, 0)

    then the span from origin in +x is 3.
    We return the maximum span over (+x, -x, +z, -z).
    """
    x0, y0, z0 = origin
    max_span = 0

    for dx, dy, dz in HORIZONTAL_OFFSETS:
        # dy is always 0 here, but we keep it for completeness.
        steps = 0
        cx, cy, cz = x0, y0, z0
        while True:
            cx += dx
            cy += dy
            cz += dz
            if (cx, cy, cz) in pos_to_indices:
                steps += 1
            else:
                break

        if steps > max_span:
            max_span = steps

    return max_span


# Horizontal neighbors only (same y, +/-1 in x or z)
HORIZONTAL_OFFSETS: Tuple[Tuple[int, int, int], ...] = (
    (+1, 0, 0),
    (-1, 0, 0),
    (0, 0, +1),
    (0, 0, -1),
)

# Base support strength per material (rough, tutorial-level values).
# For stone we choose 4.5 so that:
#   get_block_support_strength(stone_anchor_with_1_neighbor) = int(4.5 * 2) = 9
# which matches our “max span 9” assumption from earlier.
MATERIAL_BASE_SUPPORT_STRENGTH: Dict[str, float] = {
    "dirt": 2.0,   # gives ~4 blocks max span when alone
    "wood": 3.0,   # gives ~6 blocks max span when alone
    "stone": 4.5,  # gives ~9 blocks max span when alone
}


def _build_pos_index_map(
    coords: List[Dict[str, Any]]
) -> Dict[Tuple[int, int, int], List[int]]:
    """
    Build a mapping from (x, y, z) -> list of indices in `coords`.
    Multiple blocks may occupy the same position, so we keep a list.
    """
    pos_to_indices: Dict[Tuple[int, int, int], List[int]] = defaultdict(list)
    for i, c in enumerate(coords):
        x = to_int(c["x"])
        y = to_int(c["y"])
        z = to_int(c["z"])
        pos_to_indices[(x, y, z)].append(i)
    return pos_to_indices


def get_block_support_strength(
    coords: List[Dict[str, Any]],
    index: int,
    pos_to_indices: Dict[Tuple[int, int, int], List[int]],
    base_strength_lookup: Dict[str, float] = MATERIAL_BASE_SUPPORT_STRENGTH,
) -> int:
    """
    Reference: https://github.com/xBigEllx/realistic-block-physics-mirror/blob/mc-1.20.x/src/main/java/xbigellx/rbp/internal/physics/PhysicsHelper.java

    In our simplified context:

      - `coords` is a list of block dicts with keys "x", "y", "z", "material".
      - `index` is the index of the block we are evaluating.
      - `base_strength_lookup[material]` plays the role of
        blockDefinition().physics().supportStrength().

    We count how many horizontally adjacent blocks exist and then return:

        int(base_support_strength * (1 + neighbor_count))

    which mirrors the Java logic (starting count at 1, then adding 1 for each
    horizontal neighbor).
    """
    if not (0 <= index < len(coords)):
        raise IndexError("index out of range for coords list")

    block = coords[index]
    material = block.get("material")
    if material is None:
        raise KeyError("Each coord dict must have a 'material' key")

    base_strength = float(base_strength_lookup.get(material, 0.0))

    x0 = to_int(block["x"])
    y0 = to_int(block["y"])
    z0 = to_int(block["z"])

    # Start with count = 1 (the block itself).
    count = 1.0

    # Count horizontal neighbors on the same y-level.
    for dx, dy, dz in HORIZONTAL_OFFSETS:
        nx, ny, nz = x0 + dx, y0 + dy, z0 + dz
        if (nx, ny, nz) in pos_to_indices:
            count += 1.0

    return int(base_strength * count)


def are_all_blocks_supported(
    coords: List[Dict[str, Any]],
) -> int:
    """
    Return 1 if every (relevant) support block has enough support strength
    to handle its horizontal span, otherwise return 0.

    The logic is based on https://github.com/xBigEllx/realistic-block-physics-mirror/blob/mc-1.20.x/src/main/java/xbigellx/rbp/internal/physics/PhysicsHelper.java

      - We treat blocks at y <= 0 or blocks that have another block directly
        below them as "supports" (anchors).
      - For each such support block, we:
          1) Compute its support strength using get_block_support_strength,
             which increases with the number of horizontal neighbors.
          2) Compute the maximum horizontal span (number of contiguous blocks)
             extending from that block in any cardinal direction.
          3) Check span <= support_strength.

      - If any support block is overloaded (span > support_strength), we return 0.
      - Otherwise we return 1.

    Example usage with a stone cantilever:

        stable_coords = [
            {"x": 0, "y": 0, "z": 0, "material": "stone"},
            {"x": 0, "y": 1, "z": 0, "material": "stone"},
            # horizontal beam from x=1..9 at y=1
            *({"x": x, "y": 1, "z": 0, "material": "stone"} for x in range(1, 10))
        ]
        assert are_all_blocks_supported(stable_coords) == 1

    This matches our earlier assumption that stone can safely span 9 blocks
    from a single support.
    """
    if not coords:
        # Empty structure is trivially supported.
        return 1

    # Build a position -> indices map once and reuse it.
    pos_to_indices = _build_pos_index_map(coords)

    # Consider each block that has vertical support as an "anchor".
    for (x, y, z), idx_list in pos_to_indices.items():
        # A block is considered vertically supported if:
        #   - it is at ground level or below (y <= 0), or
        #   - there is another block directly beneath it at (x, y-1, z).
        below = (x, y - 1, z)
        has_vertical_support = (y <= 0) or (below in pos_to_indices)

        if not has_vertical_support:
            # Floating blocks without vertical support are ignored as anchors
            # in this simplified model. In a more complete model you might
            # treat them as automatically unstable.
            continue

        # For each block at this position (usually 1), check whether its
        # horizontal span exceeds its support strength.
        for idx in idx_list:
            support_strength = get_block_support_strength(
                coords=coords,
                index=idx,
                pos_to_indices=pos_to_indices,
            )
            span = _max_horizontal_span_from_origin(
                origin=(x, y, z),
                pos_to_indices=pos_to_indices,
            )

            if span > support_strength:
                # This support block is overloaded -> structure collapses.
                return 0

    # No support block is overloaded -> structure is considered stable.
    return 1
