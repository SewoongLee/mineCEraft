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


def material_sequence_order(
    coords: List[Dict[str, Any]], 
    material_sequence: List[str],
    use_substring_match: bool = True
) -> int:
    """
    Verify that materials in coords follow the specified sequence order.
    Consecutive blocks with the same material are compressed into a single material
    for sequence comparison (e.g., stone, stone, stone, dirt -> stone, dirt).
    
    Args:
        coords: List of coordinate dicts with keys {"x", "y", "z"} and optional {"material"}
        material_sequence: List of material names in expected order 
                          (e.g., ["concrete", "stone", "dirt", "wood", "red", "door"])
        use_substring_match: If True (default), use substring matching 
                            (e.g., 'red' matches 'red_wool', 'redstone', etc.)
    
    Returns:
        1 if materials follow the sequence order, else 0
    
    Examples:
        # Substring match for "red" materials (default behavior)
        coords = [
            {"x": 0, "y": 0, "z": 0, "material": "concrete"},
            {"x": 1, "y": 0, "z": 0, "material": "stone"},
            {"x": 2, "y": 0, "z": 0, "material": "red_wool"},
            {"x": 3, "y": 0, "z": 0, "material": "door"},
        ]
        material_sequence_order(coords, ["concrete", "stone", "red", "door"])  # Returns 1
        
        # Consecutive same materials are compressed
        coords = [
            {"x": 0, "y": 0, "z": 0, "material": "stone"},
            {"x": 1, "y": 0, "z": 0, "material": "stone"},
            {"x": 2, "y": 0, "z": 0, "material": "stone"},
            {"x": 3, "y": 0, "z": 0, "material": "dirt"},
            {"x": 4, "y": 0, "z": 0, "material": "dirt"},
            {"x": 5, "y": 0, "z": 0, "material": "wood"},
        ]
        material_sequence_order(coords, ["stone", "dirt", "wood"])  # Returns 1
    """
    if not coords:
        return 1 if not material_sequence else 0
    
    if not material_sequence:
        return 1  # No sequence to check, trivially OK
    
    seq_idx = 0  # Current position in material_sequence
    prev_material = None  # Track previous material to compress consecutive duplicates
    
    for coord in coords:
        material = coord.get("material")
        if not material:
            return 0
        
        material_str = str(material)
        
        # Skip if material is the same as previous (compress consecutive duplicates)
        # Use exact string matching for duplicate detection, regardless of use_substring_match
        if prev_material is not None and material_str == prev_material:
            continue  # Same material, skip
        
        # Material changed, check against sequence
        expected_material = material_sequence[seq_idx]
        
        # Check if current material matches expected material at current sequence position
        if use_substring_match:
            matches = expected_material in material_str
        else:
            matches = material_str == expected_material
        
        if matches:
            # Move to next material in sequence
            seq_idx += 1
            prev_material = material_str
            # If we've completed the entire sequence, return success
            if seq_idx >= len(material_sequence):
                return 1
        else:
            # Material doesn't match current sequence position
            return 0
    
    # Check if we completed the entire sequence
    return 1 if seq_idx >= len(material_sequence) else 0