from typing import Iterable, Tuple, Dict, Any, List

def to_int(v) -> int:
    return int(str(v).strip())

def xyz_lists(items: Iterable[Dict[str, Any]]) -> Tuple[List[int], List[int], List[int]]:
    xs, ys, zs = [], [], []
    for c in items:
        xs.append(to_int(c["x"]))
        ys.append(to_int(c["y"]))
        zs.append(to_int(c["z"]))
    return xs, ys, zs
