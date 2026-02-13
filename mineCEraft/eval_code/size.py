from typing import List, Dict, Any, Tuple
from .utils.coords import xyz_lists

def _ranges(coords: List[Dict[str, Any]]) -> Tuple[int, int, int]:
    """
    Return (dx, dy, dz) as coordinate ranges: max(axis) - min(axis).
    Assumes unit spacing between neighboring blocks.
    """
    xs, ys, zs = xyz_lists(coords)
    return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))

def is_equal(coords: List[Dict[str, Any]], *, xz: Tuple[int, int], y: int) -> int:
    """
    Exact size match (order-insensitive on x/z):
      - If unit grid without gaps, then range == (size - 1).
      - Checks {dx, dz} == {xz[0]-1, xz[1]-1} and dy == y-1.
    Returns 1 if equal, else 0.
    """
    if not coords:
        return 0

    dx, dy, dz = _ranges(coords)
    # order-insensitive compare for x/z
    want_xz = sorted([xz[0] - 1, xz[1] - 1])
    got_xz  = sorted([dx, dz])

    ok_xz = (got_xz == want_xz)
    ok_y  = (dy == y - 1)
    return 1 if (ok_xz and ok_y) else 0

def is_leq(coords: List[Dict[str, Any]], *, xz: Tuple[int, int], y: int) -> int:
    """
    Upper-bound check (order-insensitive on x/z):
      - Ensures the realized ranges do NOT exceed the requested ranges.
      - Interprets unit spacing: range <= (size - 1).
      - Accepts smaller shapes as long as they fit within the bounds.

    Returns 1 if within bounds, else 0.
    """
    if not coords:
        return 0

    dx, dy, dz = _ranges(coords)

    want_xz = sorted([xz[0] - 1, xz[1] - 1])
    got_xz  = sorted([dx, dz])

    ok_xz = (got_xz[0] <= want_xz[0] and got_xz[1] <= want_xz[1])
    ok_y  = (dy <= (y - 1))
    return 1 if (ok_xz and ok_y) else 0

def min_y_is_equal(coords: List[Dict[str, Any]], *, expected_y: int) -> int:
    """
    Check if the minimum y-coordinate (lowest block) equals expected_y.
    Useful for checking depth requirements (e.g., piles that should be 7 blocks deep).
    
    Args:
        coords: [{"x":..,"y":..,"z":.., ...}, ...]
        expected_y: The expected minimum y-coordinate value
    
    Returns:
        1 if min(y) == expected_y, else 0
    
    Example:
        # Check if lowest block is at y=-7 (7 blocks deep from y=0)
        min_y_is_equal(coords, expected_y=-7)
    """
    if not coords:
        return 0
    
    _, ys, _ = xyz_lists(coords)
    min_y = min(ys)
    return 1 if min_y == expected_y else 0

def min_y_is_leq(coords: List[Dict[str, Any]], *, max_y: int) -> int:
    """
    Check if the minimum y-coordinate (lowest block) is less than or equal to max_y.
    Useful for checking that structures reach at least a certain depth.
    
    Args:
        coords: [{"x":..,"y":..,"z":.., ...}, ...]
        max_y: The maximum allowed minimum y-coordinate (i.e., structure must be at least this deep)
    
    Returns:
        1 if min(y) <= max_y, else 0
    
    Example:
        # Check if structure reaches at least y=-7 (at least 7 blocks deep)
        min_y_is_leq(coords, max_y=-7)
    """
    if not coords:
        return 0
    
    _, ys, _ = xyz_lists(coords)
    min_y = min(ys)
    return 1 if min_y <= max_y else 0


def max_y_is_geq(coords: List[Dict[str, Any]], *, min_y: int) -> int:
    """
    Check if the maximum y-coordinate (highest block) is greater than or equal to min_y.
    Useful for checking that structures reach at least a certain height.
    
    Args:
        coords: [{"x":..,"y":..,"z":.., ...}, ...]
        min_y: The minimum required maximum y-coordinate (i.e., structure must reach at least this height)
    
    Returns:
        1 if max(y) >= min_y, else 0
    
    Example:
        # Check if structure reaches at least y=12 (e.g., 4-story building floor level)
        max_y_is_geq(coords, min_y=12)
    """
    if not coords:
        return 0
    
    _, ys, _ = xyz_lists(coords)
    max_y = max(ys)
    return 1 if max_y >= min_y else 0
