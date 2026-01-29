from collections import deque
from typing import List, Dict, Any, Tuple, Set, Optional, Literal
from .utils.coords import to_int, xyz_lists


def _extract_surface(
    coords: List[Dict[str, Any]],
    mode: Literal["top", "bottom"],
) -> Dict[Tuple[int, int], int]:
    """
    Extract the top or bottom surface: for each (x, z), the max y (top) or min y (bottom).
    Returns a dict mapping (x, z) -> y.
    """
    surface: Dict[Tuple[int, int], int] = {}
    for coord in coords:
        x = to_int(coord["x"])
        y = to_int(coord["y"])
        z = to_int(coord["z"])
        key = (x, z)
        if key not in surface:
            surface[key] = y
        elif mode == "top" and y > surface[key]:
            surface[key] = y
        elif mode == "bottom" and y < surface[key]:
            surface[key] = y
    return surface


def _get_line_points(p1: Tuple[int, int], p2: Tuple[int, int]) -> List[Tuple[int, int]]:
    """
    Get all integer grid points on the line segment from p1 to p2.
    Uses Bresenham's line algorithm for discrete grid traversal.
    """
    x1, z1 = p1
    x2, z2 = p2
    points = []
    dx = abs(x2 - x1)
    dz = abs(z2 - z1)
    sx = 1 if x1 < x2 else -1
    sz = 1 if z1 < z2 else -1
    err = dx - dz
    x, z = x1, z1
    while True:
        points.append((x, z))
        if x == x2 and z == z2:
            break
        e2 = 2 * err
        if e2 > -dz:
            err -= dz
            x += sx
        if e2 < dx:
            err += dx
            z += sz
    return points


def _surface_concave(
    surface: Dict[Tuple[int, int], int],
    strict: bool | Literal["non-flat"],
    verbose: bool,
    sign: int,
    surface_name: str,
) -> bool:
    """
    Check if a 2D surface (x,z) -> y is concave along the given sign.
    sign=1: top surface concavity (actual_y >= expected_y, bulge upward).
    sign=-1: bottom surface concavity (actual_y <= expected_y, bulge downward when viewed from above).
    """
    if not surface:
        return True
    points = set(surface.keys())
    if len(points) <= 1:
        return True

    if strict == "non-flat":
        ys = list(surface.values())
        if ys and all(y == ys[0] for y in ys):
            if verbose:
                print(f"Not concave: entire {surface_name} is completely flat (all y={ys[0]})")
            return False

    points_list = list(points)
    for i in range(len(points_list)):
        for j in range(i + 1, len(points_list)):
            p1, p2 = points_list[i], points_list[j]
            line_points = _get_line_points(p1, p2)
            y1, y2 = surface[p1], surface[p2]

            if strict is True and len(line_points) == 2 and y1 == y2:
                if verbose:
                    print(f"Not concave: flat line from {p1} (y={y1}) to {p2} (y={y2}) on {surface_name}")
                return False

            for (x, z) in line_points:
                if (x, z) not in surface:
                    if verbose:
                        print(f"Not concave: point ({x}, {z}) on line from {p1} to {p2} is not in {surface_name}")
                    return False

            for k, (x, z) in enumerate(line_points):
                if len(line_points) > 1:
                    t = k / (len(line_points) - 1)
                    expected_y = y1 + t * (y2 - y1)
                else:
                    expected_y = y1
                actual_y = surface[(x, z)]
                diff = sign * (actual_y - expected_y)

                if strict is True:
                    is_endpoint = (k == 0) or (k == len(line_points) - 1)
                    if not is_endpoint and diff <= 0:
                        if verbose:
                            print(f"Not concave: point ({x}, {z}) diff={diff:.2f} on line {p1}->{p2} on {surface_name}")
                        return False
                else:
                    if diff < -1e-9:
                        if verbose:
                            print(f"Not concave: point ({x}, {z}) diff={diff:.2f} on line {p1}->{p2} on {surface_name}")
                        return False
    return True


def is_top_surface_concave(
    coords: List[Dict[str, Any]],
    strict: bool | Literal["non-flat"] = False,
    verbose: bool = False,
) -> bool:
    """
    Check if the top surface of the structure is concave.
    
    Mathematical Definition:
    A top surface is concave if:
    - For any two points p1=(x1,z1) and p2=(x2,z2) on the top surface with heights y1 and y2,
    - For any point p=(x,z) on the line segment between p1 and p2 with linearly interpolated height:
        expected_y = y1 + t*(y2 - y1), where t ∈ [0,1] is the parameter along the line
    - The actual height at p must satisfy: actual_y >= expected_y
    - This ensures the surface bulges upward (concave), not downward
    
    Examples:
    - Arch shape [1, 2, 1]: middle is higher → concave ✓
    - Inverted arch [2, 1, 2]: middle is lower → not concave ✗
    - Flat surface [2, 2, 2]: all equal → concave (non-strict) ✓
    
    When strict=True, use strict inequalities (<, >).
    When strict=False (mathematical standard), use non-strict inequalities (<=, >=); 
    equality is allowed (flat surfaces/planes are considered concave).
    When strict='non-flat', equality is allowed, but the top surface should not be 
    completely flat without any concavity (i.e., must have some upward bulge).
    
    Args:
        coords: List of block coordinate dictionaries with 'x', 'y', 'z' keys.
        strict: If False (default), use non-strict inequalities (<=, >=). 
                If True, use strict inequalities (<, >).
                If 'non-flat', allow equality but reject completely flat surfaces.
        verbose: If True, print detailed diagnostic messages.
    
    Returns:
        True if the top surface is concave, else False.
    """
    if not coords:
        return True
    surface = _extract_surface(coords, "top")
    return _surface_concave(surface, strict, verbose, sign=1, surface_name="top surface")


def is_bottom_surface_concave(
    coords: List[Dict[str, Any]],
    strict: bool | Literal["non-flat"] = False,
    verbose: bool = False,
) -> bool:
    """
    Check if the bottom surface of the structure is concave (when viewed from below).
    
    The bottom surface is defined as the minimum y at each (x, z). For an arch,
    the underside should also be curved: between any two points on the bottom
    surface, the actual y should be <= the linearly interpolated expected y
    (i.e., the bottom bulges downward / dips in the middle).
    
    When strict=True, use strict inequalities; when strict=False, allow equality.
    When strict='non-flat', reject completely flat bottom surfaces.
    
    Args:
        coords: List of block coordinate dictionaries with 'x', 'y', 'z' keys.
        strict: Same semantics as is_top_surface_concave.
        verbose: If True, print detailed diagnostic messages.
    
    Returns:
        True if the bottom surface is concave, else False.
    """
    if not coords:
        return True
    surface = _extract_surface(coords, "bottom")
    return _surface_concave(surface, strict, verbose, sign=-1, surface_name="bottom surface")



def are_doors_passable(coords: List[Dict[str, Any]], verbose: bool = False) -> bool:
    """
    Check if all doors are passable. A door fails if at either y or y+1 level,
    3 or more of the 4 adjacent positions are blocked.
    """
    if not coords:
        return True
    
    blocks: Set[Tuple[int, int, int]] = set()
    doors: List[Tuple[int, int, int]] = []
    
    for p in coords:
        pos = (int(p["x"]), int(p["y"]), int(p["z"]))
        blocks.add(pos)
        if "door" in p.get("material", "").lower():
            doors.append(pos)
    
    if not doors:
        return True
    
    neighbors = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    seen = set()
    
    for x, y, z in doors:
        if (x, z) in seen:
            continue
        seen.add((x, z))
        
        for cy in [y, y + 1]:
            blocked_count = sum(1 for dx, dz in neighbors if (x + dx, cy, z + dz) in blocks)
            if blocked_count >= 3:
                if verbose:
                    print(f"Door at ({x}, {cy}, {z}): {blocked_count}/4 sides blocked")
                return False
    
    return True
    
    
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
    #    Door blocks are 2 blocks tall, so a door at height y-1 also occupies height y.
    occupied: Set[Tuple[int, int]] = set()
    for p in coords:
        if p.get("y") == y:
            occupied.add((int(p["x"]), int(p["z"])))
        elif p.get("y") == y - 1:
            # Check if this is a door block (doors are 2 blocks tall)
            block_name = p.get("material", "")
            if "door" in block_name.lower():
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


def _clusters_at_y(
    coords: List[Dict[str, Any]],
    y: int,
    *,
    use_8_neighbors: bool = False,
) -> List[Set[Tuple[int, int]]]:
    """
    At a given y level, find connected components (clusters) on the x-z plane.
    Each cluster is a set of (x, z) cells that have blocks at that y.

    Uses 4-neighbors by default (face-adjacent only) so that diagonally
    touching 1×1 piles stay separate. Set use_8_neighbors=True for diagonal connectivity.

    Returns:
        List of clusters; each cluster is a set of (x, z).
    """
    at_y: Set[Tuple[int, int]] = set()
    for p in coords:
        if to_int(p.get("y")) == y:
            at_y.add((to_int(p["x"]), to_int(p["z"])))

    if not at_y:
        return []

    neighbors = [
        (1, 0), (-1, 0), (0, 1), (0, -1),
    ]
    if use_8_neighbors:
        neighbors = [
            (-1, -1), (0, -1), (1, -1),
            (-1, 0), (1, 0),
            (-1, 1), (0, 1), (1, 1),
        ]

    clusters: List[Set[Tuple[int, int]]] = []
    remaining = set(at_y)

    while remaining:
        start = remaining.pop()
        cluster: Set[Tuple[int, int]] = {start}
        q: deque = deque([start])

        while q:
            x, z = q.popleft()
            for dx, dz in neighbors:
                nx, nz = x + dx, z + dz
                n = (nx, nz)
                if n in remaining:
                    remaining.discard(n)
                    cluster.add(n)
                    q.append(n)

        clusters.append(cluster)

    return clusters


def _min_distance_l2(
    cluster_a: Set[Tuple[int, int]],
    cluster_b: Set[Tuple[int, int]],
) -> float:
    """
    Minimum L2 (Euclidean) distance between any block in cluster_a and any in cluster_b.
    L2(a, b) = sqrt((ax - bx)^2 + (az - bz)^2).
    """
    best = float("inf")
    for (ax, az) in cluster_a:
        for (bx, bz) in cluster_b:
            d = ((ax - bx) ** 2 + (az - bz) ** 2) ** 0.5
            if d < best:
                best = d
    return best if best != float("inf") else 0.0


def cluster_count_at_y_is(
    coords: List[Dict[str, Any]],
    *,
    y: int,
    expected_count: int,
    use_8_neighbors: bool = False,
    verbose: bool = False,
) -> bool:
    """
    Check that at a given y level the number of clusters equals `expected_count`.

    Applies to both depth (below ground) and height (above ground). Clusters are
    computed on the x-z plane at the given y (4-neighbors by default so 1×1
    elements do not merge diagonally).

    Args:
        coords: List of block coordinate dicts with "x", "y", "z".
        y: The y level at which to count clusters (depth or height).
        expected_count: Expected number of clusters (e.g. number of piles or columns).
        use_8_neighbors: If True, use 8-neighborhood for clustering (diagonals count).
        verbose: If True, print why the check failed.

    Returns:
        True if the number of clusters at y equals expected_count; otherwise False.
    """
    clusters = _clusters_at_y(coords, y, use_8_neighbors=use_8_neighbors)
    n = len(clusters)
    if n != expected_count:
        if verbose:
            print(f"cluster_count_at_y_is: at y={y} found {n} clusters, expected {expected_count}")
        return False
    return True


def clusters_at_y_have_min_span(
    coords: List[Dict[str, Any]],
    *,
    y: int,
    min_span: float,
    use_8_neighbors: bool = False,
    verbose: bool = False,
) -> bool:
    """
    Check that at a given y level every pair of clusters is at least `min_span` apart.

    Span is the minimum L2 (Euclidean) distance between any two blocks from
    different clusters. So min_span = 5 means the closest blocks of any two
    clusters are at least 5 apart in straight-line distance. Using L2 correctly
    handles diagonal and triangular layouts (e.g. equilateral triangle).

    If there are 0 or 1 cluster at y, the condition is vacuously satisfied (True).

    Args:
        coords: List of block coordinate dicts with "x", "y", "z".
        y: The y level at which to evaluate (depth or height).
        min_span: Minimum required L2 (Euclidean) distance between any two clusters.
        use_8_neighbors: If True, use 8-neighborhood for clustering (diagonals count).
        verbose: If True, print why the check failed.

    Returns:
        True if every pair of clusters at y has min L2 distance >= min_span;
        otherwise False.
    """
    clusters = _clusters_at_y(coords, y, use_8_neighbors=use_8_neighbors)
    n = len(clusters)
    if n <= 1:
        return True
    for i in range(n):
        for j in range(i + 1, n):
            d = _min_distance_l2(clusters[i], clusters[j])
            if d < min_span:
                if verbose:
                    print(f"clusters_at_y_have_min_span: clusters {i} and {j} have min L2 distance {d:.4f}, required >= {min_span}")
                return False
    return True