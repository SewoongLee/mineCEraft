from typing import List, Dict, Any
from .utils.stress import compute_von_mises_stress


def is_stress_safe(
    coords: List[Dict[str, Any]],
    von_mises_stress: float,
) -> int:
    """
    Return 1 if the maximum von Mises stress is below the threshold (safe), else 0.
    
    Computes von Mises stress for the structure and checks if the maximum
    stress value is within the safe threshold.
    
    Args:
        coords: [{"x":..,"y":..,"z":.., ...}, ...]
        von_mises_stress: Safe stress threshold in Pa. Returns 1 if max stress <= threshold.
    
    Returns:
        1 if max stress <= threshold (safe), else 0
    """
    if not coords:
        return 1
    
    von_mises = compute_von_mises_stress(coords)
    max_stress = float(max(von_mises))
    
    return 1 if max_stress <= von_mises_stress else 0
