from typing import List, Dict, Any, Tuple
from .utils import to_int, xyz_lists

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