from collections import deque
from typing import List, Dict, Any, Tuple, Set, Optional
from .utils.coords import to_int, xyz_lists

def center_of_mass(coords: List[Dict[str, Any]]) -> Tuple[float, float, float]:
    """
    Compute the (x, y, z) center of mass assuming equal weights per block.
    Returns floats.
    """
    if not coords:
        return (0.0, 0.0, 0.0)
    xs, ys, zs = xyz_lists(coords)
    n = len(xs)
    return (sum(xs) / n, sum(ys) / n, sum(zs) / n)

def edges_lower_than_center(coords: List[Dict[str, Any]], verbose: bool = False) -> int:
    """
    Condition (1): All boundary blocks (x in {minX,maxX} OR z in {minZ,maxZ})
    must have strictly lower height (y) than the global center-of-mass y.

    Returns:
        1 if condition holds, else 0.
    """
    if not coords:
        if verbose:
            print("[edges_lower_than_center] Empty coords.")
        return 0

    xs, ys, zs = xyz_lists(coords)
    com_x, com_y, com_z = center_of_mass(coords)

    min_x, max_x = min(xs), max(xs)
    min_z, max_z = min(zs), max(zs)

    # Collect edge blocks (x==min/max or z==min/max)
    edge_blocks: List[Dict[str, int]] = []
    for c in coords:
        x, y, z = to_int(c["x"]), to_int(c["y"]), to_int(c["z"])
        if x == min_x or x == max_x or z == min_z or z == max_z:
            edge_blocks.append({"x": x, "y": y, "z": z})

    if not edge_blocks:
        if verbose:
            print("[edges_lower_than_center] No boundary blocks detected.")
            print(f"  COM = ({com_x:.3f}, {com_y:.3f}, {com_z:.3f})")
        return 0

    offenders = [b for b in edge_blocks if b["y"] >= com_y]
    if offenders:
        if verbose:
            print("[edges_lower_than_center] FAIL: edge block(s) not strictly lower than COM.y")
            print(f"  COM = ({com_x:.3f}, {com_y:.3f}, {com_z:.3f})")
            for b in offenders[:5]:
                print(f"  offending edge block @ (x={b['x']}, y={b['y']}, z={b['z']}) >= COM.y")
            if len(offenders) > 5:
                print(f"  ... and {len(offenders) - 5} more")
        return 0

    if verbose:
        print("[edges_lower_than_center] PASS")
        print(f"  COM = ({com_x:.3f}, {com_y:.3f}, {com_z:.3f})")
    return 1

def center_column_above_center(coords: List[Dict[str, Any]], verbose: bool = False) -> int:
    """
    Condition (2): There exists at least one block exactly above the COM's (x,z)
    column (rounded), and the highest y on that column is strictly greater than COM.y.

    Returns:
        1 if condition holds, else 0.
    """
    if not coords:
        if verbose:
            print("[center_column_above_center] Empty coords.")
        return 0

    com_x, com_y, com_z = center_of_mass(coords)
    cx, cz = round(com_x), round(com_z)

    center_col_y = [to_int(c["y"]) for c in coords
                    if to_int(c["x"]) == cx and to_int(c["z"]) == cz]

    if not center_col_y:
        if verbose:
            print("[center_column_above_center] FAIL: no block on center column (x,z)=({},{})".format(cx, cz))
            print(f"  COM = ({com_x:.3f}, {com_y:.3f}, {com_z:.3f})")
        return 0

    top_y = max(center_col_y)
    if top_y <= com_y:
        if verbose:
            print("[center_column_above_center] FAIL: tallest center-column block not above COM.y")
            print(f"  COM = ({com_x:.3f}, {com_y:.3f}, {com_z:.3f}), tallest y on column = {top_y}")
        return 0

    if verbose:
        print("[center_column_above_center] PASS")
        print(f"  COM = ({com_x:.3f}, {com_y:.3f}, {com_z:.3f}), tallest y on column = {top_y}")
    return 1

def has_rooms(coords: List[Dict], room_cnt: int, y: int = 2) -> bool:
    """
    Determine whether there are at least `room_cnt` enclosed regions ("rooms")
    on the X-Z plane at height `y`.

    A "room" is defined as a connected component of empty cells (air) that is NOT
    reachable from the outside. We treat given coords at height y as occupied (walls).

    Connectivity uses 8-neighborhood (including diagonals). This makes corner leaks
    (missing corner blocks) invalidate rooms connected diagonally to the outside.
    
    Returns:
        True if there are at least room_cnt rooms, else False.
    """
    if room_cnt <= 0:
        return True

    # 1) Collect occupied cells at the given height y.
    occupied: Set[Tuple[int, int]] = set()
    for p in coords:
        if p.get("y") == y:
            occupied.add((int(p["x"]), int(p["z"])))

    if not occupied:
        return False

    # 2) Build a bounding box around occupied cells and expand by 1 cell
    #    to create an "outside frame" for flood fill.
    xs = [x for x, _ in occupied]
    zs = [z for _, z in occupied]
    min_x, max_x = min(xs) - 1, max(xs) + 1
    min_z, max_z = min(zs) - 1, max(zs) + 1

    def in_bounds(x: int, z: int) -> bool:
        return min_x <= x <= max_x and min_z <= z <= max_z

    # 8-direction neighbors (diagonals included).
    # This allows "corner cutting", which is what makes a missing corner break closure.
    neighbors8 = [
        (-1, -1), (0, -1), (1, -1),
        (-1,  0),          (1,  0),
        (-1,  1), (0,  1), (1,  1),
    ]

    # 3) Flood fill from the outside boundary to mark "outside air".
    outside: Set[Tuple[int, int]] = set()
    q = deque()

    # Push all boundary cells of the expanded bounding box that are not occupied.
    for x in range(min_x, max_x + 1):
        for z in (min_z, max_z):
            if (x, z) not in occupied and (x, z) not in outside:
                outside.add((x, z))
                q.append((x, z))
    for z in range(min_z, max_z + 1):
        for x in (min_x, max_x):
            if (x, z) not in occupied and (x, z) not in outside:
                outside.add((x, z))
                q.append((x, z))

    while q:
        cx, cz = q.popleft()
        for dx, dz in neighbors8:
            nx, nz = cx + dx, cz + dz
            if not in_bounds(nx, nz):
                continue
            if (nx, nz) in occupied:
                continue
            if (nx, nz) in outside:
                continue
            outside.add((nx, nz))
            q.append((nx, nz))

    # 4) Count enclosed empty components (air not in outside and not occupied).
    visited: Set[Tuple[int, int]] = set()
    rooms = 0

    for x in range(min_x, max_x + 1):
        for z in range(min_z, max_z + 1):
            if (x, z) in occupied:
                continue
            if (x, z) in outside:
                continue
            if (x, z) in visited:
                continue

            # Found a new enclosed component => one room.
            rooms += 1
            if rooms >= room_cnt:
                return True

            # BFS to mark this room component.
            rq = deque([(x, z)])
            visited.add((x, z))

            while rq:
                cx, cz = rq.popleft()
                for dx, dz in neighbors8:
                    nx, nz = cx + dx, cz + dz
                    if not in_bounds(nx, nz):
                        continue
                    if (nx, nz) in occupied:
                        continue
                    if (nx, nz) in outside:
                        continue
                    if (nx, nz) in visited:
                        continue
                    visited.add((nx, nz))
                    rq.append((nx, nz))

    return rooms >= room_cnt