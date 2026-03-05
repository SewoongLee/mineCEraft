from typing import List, Dict, Any
from .utils.coords import to_int


def l1_dist(coords: List[Dict[str, Any]]) -> float:
    """
    Path-efficiency: ratio of optimal to actual total L1 (Manhattan) distance.
    Optimal path has total L1 = len(coords) - 1 (each step = 1).
    Returns (len(coords)-1) / L1_total, in [0, 1]; 1.0 means fully efficient.
    """
    n = len(coords)
    if not coords or n == 1:
        return 1.0  # no moves or single block: trivially optimal

    l1_total = 0
    for i in range(1, n):
        a, b = coords[i - 1], coords[i]
        step = abs(to_int(a["x"]) - to_int(b["x"])) \
             + abs(to_int(a["y"]) - to_int(b["y"])) \
             + abs(to_int(a["z"]) - to_int(b["z"]))
        l1_total += step

    if l1_total <= 0:
        return 1.0
    optimal = n - 1
    return min(1.0, optimal / l1_total)
