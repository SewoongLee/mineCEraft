from typing import List, Dict, Any


def material_sequence_order(
    coords: List[Dict[str, Any]], 
    material_sequence: List[str],
    use_substring_match: bool = True
) -> int:
    """
    Verify that the materials in material_sequence appear in coords in order
    (as a subsequence). Other materials may appear between matched entries.
    
    Args:
        coords: List of coordinate dicts with keys {"x", "y", "z"} and optional {"material"}
        material_sequence: List of material names in expected order 
                          (e.g., ["concrete", "stone", "dirt", "wood", "red", "door"])
        use_substring_match: If True (default), use substring matching 
                            (e.g., 'red' matches 'red_wool', 'redstone', etc.)
    
    Returns:
        1 if all materials in material_sequence are found in coords in order, else 0
    
    Examples:
        # Subsequence check with interleaved materials
        coords = [
            {"x": 0, "y": 0, "z": 0, "material": "concrete"},
            {"x": 1, "y": 0, "z": 0, "material": "stone"},
            {"x": 2, "y": 0, "z": 0, "material": "concrete"},
            {"x": 3, "y": 0, "z": 0, "material": "wood"},
            {"x": 4, "y": 0, "z": 0, "material": "red_wool"},
        ]
        material_sequence_order(coords, ["concrete", "stone", "wood", "red"])  # Returns 1
        
        # Order matters: "dirt" must come before "wood"
        coords = [
            {"x": 0, "y": 0, "z": 0, "material": "concrete"},
            {"x": 1, "y": 0, "z": 0, "material": "wood"},
            {"x": 2, "y": 0, "z": 0, "material": "dirt"},
        ]
        material_sequence_order(coords, ["concrete", "dirt", "wood"])  # Returns 0
    """
    if not material_sequence:
        return 1
    
    if not coords:
        return 0
    
    seq_idx = 0

    for coord in coords:
        material = coord.get("material")
        if not material:
            continue
        
        material_str = str(material)
        expected = material_sequence[seq_idx]
        
        if use_substring_match:
            matches = expected in material_str
        else:
            matches = material_str == expected
        
        if matches:
            seq_idx += 1
            if seq_idx >= len(material_sequence):
                return 1
    
    return 1 if seq_idx >= len(material_sequence) else 0
