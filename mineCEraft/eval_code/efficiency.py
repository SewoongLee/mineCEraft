from typing import List, Dict, Any
from .utils.coords import to_int


def l1_dist(coords: List[Dict[str, Any]], required_step: int = 1) -> int:
    """
    Path-efficiency: verify that consecutive blocks are placed on adjacent cells
    with Manhattan distance == required_step (default = 1).
    Return 1 if all steps match, else 0.
    """
    if not coords or len(coords) == 1:
        return 1  # trivially OK

    for i in range(1, len(coords)):
        a, b = coords[i - 1], coords[i]
        step = abs(to_int(a["x"]) - to_int(b["x"])) \
             + abs(to_int(a["y"]) - to_int(b["y"])) \
             + abs(to_int(a["z"]) - to_int(b["z"]))
        if step != required_step:
            return 0
    return 1
