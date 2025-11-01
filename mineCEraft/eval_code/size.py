from typing import List, Dict, Any, Tuple
from utils import xyz_lists

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
