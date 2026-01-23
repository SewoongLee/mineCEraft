from collections import deque
from typing import List, Dict, Any, Tuple, Set, Optional
from .utils.coords import to_int, xyz_lists

def _center_of_mass(coords: List[Dict[str, Any]]) -> Tuple[float, float, float]:
    """
    Compute the (x, y, z) center of mass assuming equal weights per block.
    Returns floats.
    """
    if not coords:
        return (0.0, 0.0, 0.0)
    xs, ys, zs = xyz_lists(coords)
    n = len(xs)
    return (sum(xs) / n, sum(ys) / n, sum(zs) / n)

def is_convex_from_above(
    coords: List[Dict[str, Any]], 
    strict: bool = False,
    verbose: bool = False
) -> bool:
    """
    Check if the structure is convex when viewed from above.
    
    Mathematical Definition:
    A structure is "convex from above" if, when viewing from above (looking down the -y axis),
    the top surface forms a convex shape. This means:
    - For any two points p1=(x1,z1) and p2=(x2,z2) on the top surface with heights y1 and y2,
    - For any point p=(x,z) on the line segment between p1 and p2 with linearly interpolated height:
        expected_y = y1 + t*(y2 - y1), where t ∈ [0,1] is the parameter along the line
    - The actual height at p must satisfy: actual_y >= expected_y
    - This ensures the surface bulges upward (convex when viewed from above), not downward (concave)
    
    Examples:
    - Arch shape [1, 2, 1]: middle is higher → convex from above ✓
    - Inverted arch [2, 1, 2]: middle is lower → concave from above ✗
    - Flat surface [2, 2, 2]: all equal → convex from above (non-strict) ✓
    
    When strict=True, use strict inequalities (<, >).
    When strict=False (mathematical standard), use non-strict inequalities (<=, >=); 
    equality is allowed (flat surfaces/planes are considered convex).
    When strict='non-flat', equality is allowed, but the top surface should not be 
    completely flat without any convexity (i.e., must have some upward bulge).
    
    Args:
        coords: List of block coordinate dictionaries with 'x', 'y', 'z' keys.
        strict: If False (default), use non-strict inequalities (<=, >=). 
                If True, use strict inequalities (<, >).
                If 'non-flat', allow equality but reject completely flat surfaces.
        verbose: If True, print detailed diagnostic messages.
    
    Returns:
        True if the structure is convex from above, else False.
    """
    if not coords:
        return True
    
    # Step 1: Extract top surface - for each (x, z) pair, get the maximum y value
    # This represents the highest block at each (x, z) position
    top_surface: Dict[Tuple[int, int], int] = {}
    for coord in coords:
        x = to_int(coord["x"])
        y = to_int(coord["y"])
        z = to_int(coord["z"])
        key = (x, z)
        
        if key not in top_surface or y > top_surface[key]:
            top_surface[key] = y
    
    if not top_surface:
        return True
    
    # Get all (x, z) points from the top surface
    top_points = set(top_surface.keys())
    
    if len(top_points) <= 1:
        # 0 or 1 points are always convex (trivial cases)
        return True
    
    # Step 2: Check convexity by verifying that for any two points in the top surface,
    # the y-values at all points on the line segment between them satisfy:
    # actual_y >= expected_y (where expected_y is the linear interpolation)
    # This ensures the surface bulges upward, making it convex when viewed from above.
    # 
    # Mathematical formulation:
    # For points p1=(x1,z1,y1) and p2=(x2,z2,y2), and any point p=(x,z) on the line segment:
    #   t = distance(p, p1) / distance(p2, p1)  [parameter along the line, 0 ≤ t ≤ 1]
    #   expected_y = y1 + t*(y2 - y1)  [linear interpolation]
    #   actual_y = top_surface[(x, z)]
    # Condition: actual_y >= expected_y  (for convex from above)
    
    def get_line_points(p1: Tuple[int, int], p2: Tuple[int, int]) -> List[Tuple[int, int]]:
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
    
    # Handle strict='non-flat' mode: check if the entire structure is completely flat
    # If all points have the same y-value, it's completely flat and should be rejected
    if strict == 'non-flat':
        all_y_values = list(top_surface.values())
        if len(all_y_values) > 0 and all(y == all_y_values[0] for y in all_y_values):
            if verbose:
                print(f"Non-convex: entire structure is completely flat (all y={all_y_values[0]})")
            return False
    
    # Check all pairs of points to verify convexity condition
    top_points_list = list(top_points)
    for i in range(len(top_points_list)):
        for j in range(i + 1, len(top_points_list)):
            p1 = top_points_list[i]
            p2 = top_points_list[j]
            
            # Get all points on the line segment between p1 and p2
            line_points = get_line_points(p1, p2)
            
            # Get y-values at endpoints
            y1 = top_surface[p1]
            y2 = top_surface[p2]
            
            # For strict=True mode: if the line segment has only 2 points (endpoints) 
            # and they have the same y-value, it's a flat line and should be rejected
            if strict is True and len(line_points) == 2 and y1 == y2:
                if verbose:
                    print(f"Non-convex: flat line from {p1} (y={y1}) to {p2} (y={y2})")
                return False
            
            # For convexity, all points on the line segment should be in the top surface
            # (the set of (x, z) points should form a convex set in 2D)
            # This ensures there are no "holes" or missing blocks on the line segment
            for (x, z) in line_points:
                if (x, z) not in top_surface:
                    if verbose:
                        print(f"Non-convex: point ({x}, {z}) on line from {p1} to {p2} is not in top surface")
                    return False
            
            # Check y-values: for convexity from above, the y-values should bulge upward
            # (i.e., actual_y >= linearly interpolated expected_y)
            # This is the key condition: the surface must be above or on the line connecting endpoints
            for k, (x, z) in enumerate(line_points):
                # Linear interpolation: expected_y = y1 + t*(y2 - y1), where t = k/(n-1)
                if len(line_points) > 1:
                    t = k / (len(line_points) - 1)
                    expected_y = y1 + t * (y2 - y1)
                else:
                    expected_y = y1
                
                actual_y = top_surface[(x, z)]
                
                # For convexity from above: actual_y >= expected_y
                # If actual_y < expected_y, the surface bulges downward, making it concave from above
                if strict is True:
                    # For strict convexity, reject downward bulges (actual_y < expected_y)
                    # and flat surfaces (actual_y == expected_y). 
                    # Only accept upward bulges (actual_y > expected_y).
                    # Note: endpoints will always have actual_y == expected_y, so we skip them
                    is_endpoint = (k == 0) or (k == len(line_points) - 1)
                    if not is_endpoint and actual_y <= expected_y:
                        if verbose:
                            print(f"Non-convex: point ({x}, {z}) has y={actual_y} <= expected {expected_y:.2f} "
                                  f"on line from {p1} (y={y1}) to {p2} (y={y2})")
                        return False
                else:
                    # Non-strict mode: allow actual_y >= expected_y (including equality for flat surfaces)
                    # Use small epsilon to handle floating point precision issues
                    if actual_y < expected_y - 1e-9:
                        if verbose:
                            print(f"Non-convex: point ({x}, {z}) has y={actual_y} < expected {expected_y:.2f} "
                                  f"on line from {p1} (y={y1}) to {p2} (y={y2})")
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
