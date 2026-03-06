from collections import deque, defaultdict
from typing import List, Dict, Any, Tuple, Set, Optional, Literal
from .utils.coords import to_int, xyz_lists


def _get_centroid(coords: List[Dict[str, Any]]) -> Tuple[int, int, int]:
    """Bounding box center (integer)."""
    if not coords:
        return (0, 0, 0)
    xs, ys, zs = xyz_lists(coords)
    return (
        (min(xs) + max(xs)) // 2,
        (min(ys) + max(ys)) // 2,
        (min(zs) + max(zs)) // 2,
    )


def _get_start_positions(
    coords: List[Dict[str, Any]],
    *,
    start_material: Optional[str] = None,
) -> List[Tuple[int, int, int]]:
    """
    Return start positions as (x, y, z). If start_material given, blocks matching
    that substring; else use structure centroid.
    """
    if not coords:
        return []
    if start_material:
        out: List[Tuple[int, int, int]] = []
        for c in coords:
            if start_material.lower() in str(c.get("material", "")).lower():
                out.append((to_int(c["x"]), to_int(c.get("y", 0)), to_int(c["z"])))
        return out
    cx, cy, cz = _get_centroid(coords)
    return [(cx, cy, cz)]


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


def _slices_along_axis(
    surface: Dict[Tuple[int, int], int],
    fix_z: bool,
) -> List[List[Tuple[int, int]]]:
    """
    Return 1D slices: fix_z=True -> slices at fixed z (param=x); fix_z=False -> at fixed x (param=z).
    Each slice is a sorted list of (param, y).
    """
    grouped: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
    for (x, z), y in surface.items():
        key, param_y = (z, (x, y)) if fix_z else (x, (z, y))
        grouped[key].append(param_y)
    return [sorted(grouped[key], key=lambda p: p[0]) for key in sorted(grouped)]


def _get_axis_aligned_slices(
    surface: Dict[Tuple[int, int], int],
) -> List[List[Tuple[int, int]]]:
    """
    All axis-aligned 1D slices: fixed z (vary x) and fixed x (vary z).
    Each slice = list of (param, y) sorted by param. Used for existence check.
    """
    return _slices_along_axis(surface, fix_z=True) + _slices_along_axis(surface, fix_z=False)


# Tolerance for non-strict concavity (allow small numerical error).
_CONCAVE_TOL = 1e-9


def _is_1d_profile_concave(
    profile: List[Tuple[int, int]],
    sign: int,
    strict: bool | Literal["non-flat"],
    verbose: bool,
    slice_name: str,
) -> bool:
    """
    True if the 1D profile (param, y) sorted by param is concave: every chord lies
    on or below the profile (top, sign=1) or on or above (bottom, sign=-1).
    """
    if not profile:
        return True
    if len(profile) == 1:
        return strict is False  # Only non-strict accepts single point as concave

    ys = [p[1] for p in profile]
    all_flat = all(y == ys[0] for y in ys)
    if strict == "non-flat" and all_flat:
        if verbose:
            print(f"Not concave: 1D slice {slice_name} is completely flat (all y={ys[0]})")
        return False

    n = len(profile)
    for i in range(n):
        for j in range(i + 1, n):
            y_i, y_j = profile[i][1], profile[j][1]
            if strict is True and j == i + 1 and y_i == y_j:
                if verbose:
                    print(f"Not concave: flat segment in 1D slice {slice_name} (indices {i}–{j}, y={y_i})")
                return False
            for k in range(i, j + 1):
                t = (k - i) / (j - i) if j > i else 1.0
                expected_y = y_i + t * (y_j - y_i)
                actual_y = profile[k][1]
                diff = sign * (actual_y - expected_y)
                is_endpoint = k == i or k == j
                # strict=True: interior points must have diff > 0; else: diff >= -tol
                fails = (strict is True and not is_endpoint and diff <= 0) or (
                    strict is not True and diff < -_CONCAVE_TOL
                )
                if fails:
                    if verbose:
                        print(f"Not concave: index {k} diff={diff:.2f} in 1D slice {slice_name} (segment {i}–{j})")
                    return False
    return True


def _surface_has_concave_slice(
    surface: Dict[Tuple[int, int], int],
    strict: bool | Literal["non-flat"],
    verbose: bool,
    sign: int,
    surface_name: str,
) -> bool:
    """
    Existence check: True if at least one axis-aligned 1D slice is concave.
    strict only changes the concavity criterion per slice, not the existence logic.
    """
    if not surface:
        return True
    for idx, profile in enumerate(_get_axis_aligned_slices(surface)):
        if _is_1d_profile_concave(profile, sign, strict, verbose, f"{surface_name} (slice {idx})"):
            return True
    return False


def is_top_surface_concave(
    coords: List[Dict[str, Any]],
    strict: bool | Literal["non-flat"] = False,
    verbose: bool = False,
) -> bool:
    """
    Check whether the top surface has concavity (existence check).

    We consider axis-aligned 1D slices only: slices at fixed z (varying x) and
    slices at fixed x (varying z). Return True if at least one such slice is
    concave. This way, e.g. an arch bridge with a concave footpath plus
    non-concave handrails still passes, because the footpath slice is concave.

    Definition of concave for one 1D slice (ordered by x or z):
    For every pair of points on the slice and every point between them, the
    actual height y must be >= the linearly interpolated height (expected_y).
    So the profile bulges upward (arch-shaped).

    strict only changes the criterion for "concave" on that slice, not the
    existence logic (always: one slice suffices).
    - strict=False: allow equality (flat segments allowed).
    - strict=True: require strict inequality at non-endpoints; flat segments
      (two endpoints with same y) do not count as concave.
    - strict='non-flat': allow equality but the slice must not be completely
      flat (all same y); at least some upward bulge required.

    Args:
        coords: List of block coordinate dictionaries with 'x', 'y', 'z' keys.
        strict: False (default), True, or 'non-flat' (see above).
        verbose: If True, print detailed diagnostic messages.

    Returns:
        True if at least one axis-aligned slice of the top surface is concave.
    """
    if not coords:
        return True
    surface = _extract_surface(coords, "top")
    return _surface_has_concave_slice(surface, strict, verbose, sign=1, surface_name="top surface")


def is_bottom_surface_concave(
    coords: List[Dict[str, Any]],
    strict: bool | Literal["non-flat"] = False,
    verbose: bool = False,
) -> bool:
    """
    Check whether the bottom surface has concavity (existence check).

    Same as is_top_surface_concave but for the bottom surface (min y per (x, z)).
    We require at least one axis-aligned 1D slice to be concave: for that slice,
    actual y <= linearly interpolated expected y (bottom bulges downward).

    strict has the same semantics as in is_top_surface_concave.

    Args:
        coords: List of block coordinate dictionaries with 'x', 'y', 'z' keys.
        strict: Same semantics as is_top_surface_concave.
        verbose: If True, print detailed diagnostic messages.

    Returns:
        True if at least one axis-aligned slice of the bottom surface is concave.
    """
    if not coords:
        return True
    surface = _extract_surface(coords, "bottom")
    return _surface_has_concave_slice(surface, strict, verbose, sign=-1, surface_name="bottom surface")



def are_doors_passable(coords: List[Dict[str, Any]], verbose: bool = False) -> bool:
    """
    Check if all doors are passable. A door fails if at either y or y+1 level,
    3 or more of the 4 adjacent positions are blocked by non-door blocks.
    Adjacent doors (e.g. double door) do not count as blocking.
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
    
    door_set: Set[Tuple[int, int, int]] = set(doors)
    neighbors = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    seen = set()
    
    for x, y, z in doors:
        if (x, z) in seen:
            continue
        seen.add((x, z))
        
        for cy in [y, y + 1]:
            # Only count non-door blocks as blocking (so double doors are passable)
            blocked_count = sum(
                1 for dx, dz in neighbors
                if (x + dx, cy, z + dz) in blocks
                and (x + dx, cy, z + dz) not in door_set
            )
            if blocked_count >= 3:
                if verbose:
                    print(f"Door at ({x}, {cy}, {z}): {blocked_count}/4 sides blocked")
                return False
    
    return True


def are_adjacent(
    coords: List[Dict[str, Any]],
    materials: List[str],
    *,
    substring_match: bool = True,
    verbose: bool = False,
) -> bool:
    """
    Check if at least one block of materials[0] is adjacent (6-neighbor) to at
    least one block of materials[1]. materials must have length 2.

    Args:
        coords: Block dicts with "x","y","z", optional "material".
        materials: Exactly 2 material strings to check adjacency between.
        substring_match: If True, match by substring (e.g. "door" in "oak_door").
        verbose: Print failure reason.

    Returns:
        True if some block of materials[0] and some block of materials[1] are
        adjacent, else False.
    """
    if len(materials) != 2:
        if verbose:
            print("are_adjacent requires materials list of length 2")
        return False
    if not coords:
        return False

    a_sub, b_sub = materials[0].lower(), materials[1].lower()
    set_a: Set[Tuple[int, int, int]] = set()
    set_b: Set[Tuple[int, int, int]] = set()

    def matches(mat: str, sub: str) -> bool:
        m = str(mat or "").lower()
        return sub in m if substring_match else m == sub

    for c in coords:
        pos = (to_int(c["x"]), to_int(c.get("y", 0)), to_int(c["z"]))
        mat = c.get("material")
        if matches(mat, a_sub):
            set_a.add(pos)
        if matches(mat, b_sub):
            set_b.add(pos)

    if not set_a or not set_b:
        if verbose:
            print(f"No blocks matching {materials[0]!r} or {materials[1]!r} for adjacency")
        return False

    offsets = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]

    for dx, dy, dz in set_a:
        for ox, oy, oz in offsets:
            nb = (dx + ox, dy + oy, dz + oz)
            if nb in set_b:
                return True

    if verbose:
        print(f"No {materials[0]!r} block is adjacent to any {materials[1]!r} block")
    return False


def is_single_level(
    coords: List[Dict[str, Any]],
    *,
    start_material: Optional[str] = None,
    verbose: bool = False,
) -> bool:
    """
    Check no curb: from every start block (bed by default), a flat path on ground
    exists to outside. Bed must be on ground (floor_y); path at floor_y only.

    Args:
        coords: Block dicts with "x","y","z", optional "material".
        start_material: Substring for start blocks (e.g. "bed"). None = centroid.
        verbose: Print failure reason.

    Returns:
        True if from every start, flat path to outside exists.
    """
    if not coords:
        return True

    blocks_xyz: Set[Tuple[int, int, int]] = set()
    blocks_solid: Set[Tuple[int, int, int]] = set()
    for c in coords:
        p = (to_int(c["x"]), to_int(c.get("y", 0)), to_int(c["z"]))
        blocks_xyz.add(p)
        if "door" not in str(c.get("material", "")).lower():
            blocks_solid.add(p)

    floor_y = min(p[1] for p in blocks_xyz)
    if floor_y > -1:
        if verbose:
            print(f"Floor at y={floor_y} is above ground (y=-1); not single level")
        return False
    floor_at: Set[Tuple[int, int]] = {(x, z) for (x, y, z) in blocks_xyz if y == floor_y}
    if start_material:
        for c in coords:
            y = to_int(c.get("y", 0))
            if y == floor_y + 1 and start_material.lower() in str(c.get("material", "")).lower():
                floor_at.add((to_int(c["x"]), to_int(c["z"])))

    if not floor_at:
        return True

    min_x = min(p[0] for p in floor_at)
    max_x = max(p[0] for p in floor_at)
    min_z = min(p[1] for p in floor_at)
    max_z = max(p[1] for p in floor_at)

    def is_outside(x: int, z: int) -> bool:
        return x < min_x or x > max_x or z < min_z or z > max_z

    def head_y(x: int, z: int) -> int:
        return floor_y + 2 if (x, floor_y + 1, z) in blocks_solid else floor_y + 1

    def can_step_to(x: int, z: int) -> bool:
        if (x, z) in floor_at:
            return (x, head_y(x, z), z) not in blocks_solid
        if is_outside(x, z):
            return (x, floor_y, z) not in blocks_solid and (x, floor_y + 1, z) not in blocks_solid
        return False

    starts_xyz = _get_start_positions(coords, start_material=start_material)
    if not starts_xyz:
        return True

    ground_y = floor_y  # floor = ground for single level
    for (sx, sy, sz) in starts_xyz:
        if sy != ground_y + 1:  # bed must be exactly one block above ground
            if verbose:
                print(f"Start ({sx},{sy},{sz}) not on ground (must be at y={ground_y + 1})")
            return False
        if not can_step_to(sx, sz):
            if verbose:
                print(f"Start ({sx},{sz}) has no head clearance")
            return False

    def can_reach_outside(start: Tuple[int, int]) -> bool:
        q: deque = deque([start])
        seen: Set[Tuple[int, int]] = {start}
        while q:
            x, z = q.popleft()
            for dx, dz in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, nz = x + dx, z + dz
                if (nx, nz) in seen:
                    continue
                if is_outside(nx, nz) and can_step_to(nx, nz):
                    return True
                if (nx, nz) in floor_at and can_step_to(nx, nz):
                    seen.add((nx, nz))
                    q.append((nx, nz))
        return False

    for (sx, _, sz) in starts_xyz:
        if not can_reach_outside((sx, sz)):
            if verbose:
                print(f"Start ({sx},{sz}) cannot reach outside via flat path at y={floor_y}")
            return False
    return True


def _occupied_at_y_for_rooms(coords: List[Dict], y: int) -> Set[Tuple[int, int]]:
    """
    Build the set of occupied (x, z) cells at height y.
    Includes blocks at y and door blocks at y-1 (doors are 2 blocks tall).
    """
    occupied: Set[Tuple[int, int]] = set()
    for p in coords:
        if p.get("y") == y:
            occupied.add((int(p["x"]), int(p["z"])))
        elif p.get("y") == y - 1:
            block_name = p.get("material", "")
            if "door" in block_name.lower():
                occupied.add((int(p["x"]), int(p["z"])))
    return occupied


def _solid_blocks(coords: List[Dict[str, Any]], passable: Optional[Set[str]] = None) -> Set[Tuple[int, int, int]]:
    """
    Blocks that block passage. Exclude doors; exclude materials in passable (e.g. bed).
    Bed must be excluded for has_exit/has_wide_exit: if bed is solid, a 2x2 block cannot
    find a valid start position in a typical 5x5 room with bed at center.
    """
    passable = passable or set()
    out: Set[Tuple[int, int, int]] = set()
    for c in coords:
        mat = str(c.get("material", "")).lower()
        if "door" in mat:
            continue
        if passable and any(p in mat for p in passable):
            continue
        out.add((to_int(c["x"]), to_int(c.get("y", 0)), to_int(c["z"])))
    return out


def has_exit(
    coords: List[Dict[str, Any]],
    *,
    width: int = 2,
    depth: int = 1,
    height: int = 2,
    start_material: Optional[str] = None,
    verbose: bool = False,
) -> bool:
    """
    Check that a width x depth x height block can reach outside from start (or centroid).
    Default: start at centroid. 2x1x2 human, ±1 y step, doors passable.

    Args:
        coords: Block dicts with "x","y","z", optional "material".
        width, depth, height: Block dimensions.
        start_material: If given, start at blocks matching; else centroid.
        verbose: Print failure reason.

    Returns:
        True if can reach (x,z) outside bounding box.
    """
    if not coords:
        return True

    # Bed must be passable: if solid, a 2x2 block cannot find a valid start in a 5x5 room with bed at center
    solid = _solid_blocks(coords, passable={"bed"})
    xs, ys, zs = xyz_lists(coords)
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)

    def is_outside(x: int, z: int) -> bool:
        return x < min_x or x > max_x or z < min_z or z > max_z

    starts = _get_start_positions(coords, start_material=start_material)
    if not starts:
        return True

    def volume_clear(ox: int, oy: int, oz: int, orient_x: bool) -> bool:
        """Check width x depth x height volume clear. orient_x: width in x else in z."""
        dx = width if orient_x else depth
        dz = depth if orient_x else width
        for xx in range(ox, ox + dx):
            for zz in range(oz, oz + dz):
                for yy in range(oy, oy + height):
                    if (xx, yy, zz) in solid:
                        return False
        return True

    def try_start(sx: int, sy: int, sz: int) -> bool:
        for orient in [True, False]:
            if volume_clear(sx, sy, sz, orient):
                q: deque = deque([(sx, sy, sz, orient)])
                seen: Set[Tuple[int, int, int, bool]] = {(sx, sy, sz, orient)}
                while q:
                    x, y, z, o = q.popleft()
                    dx = width if o else depth
                    dz = depth if o else width
                    corners = [(x, z), (x + dx - 1, z), (x, z + dz - 1), (x + dx - 1, z + dz - 1)]
                    if all(is_outside(cx, cz) for cx, cz in corners):
                        return True
                    for dx, dz in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                        for dy in [-1, 0, 1]:
                            nx, ny, nz = x + dx, y + dy, z + dz
                            if ny < min_y or ny > max_y:
                                continue
                            if (nx, ny, nz, o) in seen:
                                continue
                            if volume_clear(nx, ny, nz, o):
                                seen.add((nx, ny, nz, o))
                                q.append((nx, ny, nz, o))
        return False

    for (sx, sy, sz) in starts:
        for dx, dz in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]:
            if try_start(sx + dx, sy, sz + dz):
                return True
    return False


def has_wide_exit(
    coords: List[Dict[str, Any]],
    *,
    width: int = 2,
    start_material: Optional[str] = None,
    verbose: bool = False,
) -> bool:
    """
    Check that a width x width x 2 block can exit. Same as has_exit with square footprint.
    """
    return has_exit(coords, width=width, depth=width, height=2, start_material=start_material, verbose=verbose)


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
    occupied = _occupied_at_y_for_rooms(coords, y)
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


def _cluster_radius(cluster: Set[Tuple[int, int]]) -> float:
    """
    Max L2 distance from cluster centroid to any point in the cluster.
    Returns 0 for empty or single-point cluster.
    """
    if len(cluster) <= 1:
        return 0.0
    pts = list(cluster)
    cx = sum(p[0] for p in pts) / len(pts)
    cz = sum(p[1] for p in pts) / len(pts)
    best = 0.0
    for (ax, az) in pts:
        d = ((ax - cx) ** 2 + (az - cz) ** 2) ** 0.5
        if d > best:
            best = d
    return best


def _cluster_diameter(cluster: Set[Tuple[int, int]]) -> float:
    """
    Max L2 distance between any two points in the cluster.
    Returns 0 for empty or single-point cluster.
    """
    if len(cluster) <= 1:
        return 0.0
    pts = list(cluster)
    best = 0.0
    for i in range(len(pts)):
        ax, az = pts[i]
        for j in range(i + 1, len(pts)):
            bx, bz = pts[j]
            d = ((ax - bx) ** 2 + (az - bz) ** 2) ** 0.5
            if d > best:
                best = d
    return best


def cluster_at_y_has_min_radius(
    coords: List[Dict[str, Any]],
    *,
    y: int,
    min_radius: float,
    use_8_neighbors: bool = False,
    verbose: bool = False,
) -> bool:
    """
    Check that at y there is exactly one cluster and its radius (max distance from
    centroid to any point) is at least min_radius.

    Args:
        coords: List of block coordinate dicts with "x", "y", "z".
        y: The y level at which to evaluate.
        min_radius: Minimum required radius (L2 from centroid to farthest point).
        use_8_neighbors: If True, use 8-neighborhood for clustering.
        verbose: If True, print why the check failed.

    Returns:
        True if exactly one cluster at y and its radius >= min_radius; else False.
    """
    clusters = _clusters_at_y(coords, y, use_8_neighbors=use_8_neighbors)
    if len(clusters) != 1:
        if verbose:
            print(f"cluster_at_y_has_min_radius: at y={y} found {len(clusters)} clusters, expected 1")
        return False
    r = _cluster_radius(clusters[0])
    if r < min_radius:
        if verbose:
            print(f"cluster_at_y_has_min_radius: at y={y} radius={r:.4f}, required >= {min_radius}")
        return False
    return True


def cluster_at_y_has_min_diameter(
    coords: List[Dict[str, Any]],
    *,
    y: int,
    min_diameter: float,
    use_8_neighbors: bool = False,
    verbose: bool = False,
) -> bool:
    """
    Check that at y there is exactly one cluster and its diameter (max L2 distance
    between any two points) is at least min_diameter.

    Args:
        coords: List of block coordinate dicts with "x", "y", "z".
        y: The y level at which to evaluate.
        min_diameter: Minimum required diameter (max pairwise L2 distance).
        use_8_neighbors: If True, use 8-neighborhood for clustering.
        verbose: If True, print why the check failed.

    Returns:
        True if exactly one cluster at y and its diameter >= min_diameter; else False.
    """
    clusters = _clusters_at_y(coords, y, use_8_neighbors=use_8_neighbors)
    if len(clusters) != 1:
        if verbose:
            print(f"cluster_at_y_has_min_diameter: at y={y} found {len(clusters)} clusters, expected 1")
        return False
    d = _cluster_diameter(clusters[0])
    if d < min_diameter:
        if verbose:
            print(f"cluster_at_y_has_min_diameter: at y={y} diameter={d:.4f}, required >= {min_diameter}")
        return False
    return True


def has_axis_symmetry(
    coords: List[Dict[str, Any]],
    *,
    verbose: bool = False,
) -> bool:
    """
    Check if the structure has bilateral (mirror) symmetry about any of the x, y, or z axes.

    For each axis, reflects blocks across the plane through the bounding box center.
    Returns True if the structure is symmetric about at least one axis.

    - X-axis symmetry: plane x = (min_x + max_x) / 2; (x,y,z) <-> (min_x+max_x-x, y, z)
    - Y-axis symmetry: plane y = (min_y + max_y) / 2; (x,y,z) <-> (x, min_y+max_y-y, z)
    - Z-axis symmetry: plane z = (min_z + max_z) / 2; (x,y,z) <-> (x, y, min_z+max_z-z)

    Args:
        coords: List of block coordinate dicts with "x", "y", "z".
        verbose: If True, print which axis (if any) has symmetry.

    Returns:
        True if symmetric about at least one axis, else False.
    """
    if not coords:
        return True

    blocks: Set[Tuple[int, int, int]] = set()
    for c in coords:
        blocks.add((to_int(c["x"]), to_int(c.get("y", 0)), to_int(c["z"])))

    xs = [p[0] for p in blocks]
    ys = [p[1] for p in blocks]
    zs = [p[2] for p in blocks]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)

    def is_symmetric_x() -> bool:
        if min_x == max_x:
            return False  # No extent in x, skip (trivial)
        for (x, y, z) in blocks:
            mirror_x = min_x + max_x - x
            if (mirror_x, y, z) not in blocks:
                return False
        return True

    def is_symmetric_y() -> bool:
        if min_y == max_y:
            return False  # No extent in y, skip (trivial)
        for (x, y, z) in blocks:
            mirror_y = min_y + max_y - y
            if (x, mirror_y, z) not in blocks:
                return False
        return True

    def is_symmetric_z() -> bool:
        if min_z == max_z:
            return False  # No extent in z, skip (trivial)
        for (x, y, z) in blocks:
            mirror_z = min_z + max_z - z
            if (x, y, mirror_z) not in blocks:
                return False
        return True

    for name, check in [("x", is_symmetric_x), ("y", is_symmetric_y), ("z", is_symmetric_z)]:
        if check():
            if verbose:
                print(f"Structure has {name}-axis symmetry")
            return True
    return False


def has_no_axis_symmetry(
    coords: List[Dict[str, Any]],
    *,
    verbose: bool = False,
) -> bool:
    """
    Check that the structure has no axis of symmetry (x, y, or z).

    Returns True if the structure is asymmetric about all three axes.
    Use this for prompts that require "no axis of symmetry".

    Args:
        coords: List of block coordinate dicts with "x", "y", "z".
        verbose: If True, print diagnostic messages.

    Returns:
        True if no axis of symmetry exists, else False.
    """
    return not has_axis_symmetry(coords, verbose=verbose)


def is_reachable_by_stairs(
    coords: List[Dict[str, Any]],
    min_floor_y: int,
) -> int:
    """
    Return 1 if a 2-block-tall, 1x1 human can reach a floor at y >= min_floor_y
    by walking and stepping up only +1 blocks (stairs) from some ground block at y=0.

    - BFS from any block at y=0 that has head clearance (y+1, y+2 empty).
    - Human can move horizontally on the same floor, or step up +1 to an adjacent block.
    - When stepping up to block at (x, y, z), requires (x,y+1,z) and (x,y+2,z) empty (no head bump).
    - 2-story: min_floor_y=4; 3-story: min_floor_y=8; etc.

    Args:
        coords: [{"x":..,"y":..,"z":.., ...}, ...] solid blocks
        min_floor_y: minimum y (floor level) that must be reachable
    """
    if not coords:
        return 0

    blocks: Set[Tuple[int, int, int]] = set()
    for c in coords:
        x, y, z = to_int(c["x"]), to_int(c["y"]), to_int(c["z"])
        blocks.add((x, y, z))

    def has_clearance(px: int, py: int, pz: int) -> bool:
        """Standing on block (px,py,pz): need (px,py+1,pz) and (px,py+2,pz) empty."""
        return (px, py + 1, pz) not in blocks and (px, py + 2, pz) not in blocks

    # Start from all ground blocks at y=0 with clearance
    queue: deque[Tuple[int, int, int]] = deque()
    visited: Set[Tuple[int, int, int]] = set()

    for (x, y, z) in blocks:
        if y == 0 and has_clearance(x, y, z):
            if (x, y, z) not in visited:
                visited.add((x, y, z))
                queue.append((x, y, z))

    if not queue:
        return 0

    # 4-neighbor in xz for horizontal and step-up
    xz_deltas = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    while queue:
        x, y, z = queue.popleft()
        if y >= min_floor_y:
            return 1

        for dx, dz in xz_deltas:
            # Same level
            nx, ny, nz = x + dx, y, z + dz
            npos = (nx, ny, nz)
            if npos in blocks and has_clearance(nx, ny, nz) and npos not in visited:
                visited.add(npos)
                queue.append(npos)

            # Step up +1
            nx, ny, nz = x + dx, y + 1, z + dz
            npos = (nx, ny, nz)
            if npos in blocks and has_clearance(nx, ny, nz) and npos not in visited:
                visited.add(npos)
                queue.append(npos)

    return 0