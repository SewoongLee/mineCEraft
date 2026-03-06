from typing import List, Dict, Any
import math
from .utils.stress import compute_von_mises_stress


def stress_score(
    coords: List[Dict[str, Any]],
    von_mises_stress: float,
) -> float:
    """
    Return a continuous score in [0, 1] based on (reference stress) / (computed max stress).
    Smaller computed stress yields a higher score; score is capped at 1.0.
    Returns 0.0 when stress cannot be computed (empty/invalid structure, solver failure).

    Args:
        coords: [{"x":..,"y":..,"z":.., ...}, ...]
        von_mises_stress: Reference stress threshold in Pa. Score = min(1.0, von_mises_stress / max_stress).

    Returns:
        Float in [0, 1]. 0.0 if computation fails or structure is invalid.
    """
    if not coords:
        return 0.0
    try:
        von_mises = compute_von_mises_stress(coords)
    except Exception:
        return 0.0
    if von_mises is None or len(von_mises) == 0:
        return 0.0
    max_stress = float(max(von_mises))
    if not math.isfinite(max_stress) or max_stress <= 0.0:
        return 0.0
    ratio = von_mises_stress / max_stress
    return min(1.0, max(0.0, ratio))
