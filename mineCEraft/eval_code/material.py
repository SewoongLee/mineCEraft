from collections import Counter
from typing import List, Dict, Any

def is_quantity_correct(coords: List[Dict[str, Any]], expected_count: int) -> int:
    """Return 1 if number of blocks equals expected_count, else 0."""
    return 1 if len(coords) == expected_count else 0

def is_type_correct(coords: List[Dict[str, Any]], expected_material: str) -> int:
    """
    Return 1 if all coords use the expected material, else 0.
    """
    if not coords:
        return 0
    unique = {c.get("material") for c in coords}
    return 1 if unique == {expected_material} else 0

def material_distribution(coords: List[Dict[str, Any]]) -> Counter:
    """(Optional helper) Count materials for reporting."""
    return Counter(c.get("material") for c in coords)
