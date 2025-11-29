from collections import Counter
from typing import List, Dict, Any


def _material_matches(material: str, expected_material: str, use_substring_match: bool) -> bool:
    """
    Check if material matches expected_material using exact or substring matching.
    
    Args:
        material: The material string to check (may be None or empty)
        expected_material: The material to match against
        use_substring_match: If True, use substring matching; if False, use exact matching
    
    Returns:
        True if material matches expected_material, False otherwise
    """
    if not material:
        return False
    material_str = str(material)
    if use_substring_match:
        return expected_material in material_str
    else:
        return material_str == expected_material


def is_block_cnt_equal_to(coords: List[Dict[str, Any]], expected_count: int) -> bool:
    """Return True if number of blocks equals expected_count, else False."""
    return len(coords) == expected_count


def is_block_cnt_larger_than(
    coords: List[Dict[str, Any]], 
    cnt: int,
    expected_material: str = None,
    use_substring_match: bool = False,
) -> bool:
    """
    Return True if number of blocks (matching expected_material if provided) is larger than cnt, else False.
    
    Args:
        coords: List of coordinate dicts with keys {"x", "y", "z"} and optional {"material"}
        cnt: The minimum count (exclusive) that blocks must exceed
        expected_material: Optional material to filter by. If None, counts all blocks.
        use_substring_match: If True, use substring matching (e.g., 'red' matches 'red_wool');
                           if False, use exact matching (default). Only used if expected_material is provided.
    
    Returns:
        True if count of matching blocks > cnt, else False
    """
    if expected_material is None:
        # Count all blocks
        return len(coords) > cnt
    else:
        # Count only blocks matching the expected material
        matching_count = sum(
            1 for c in coords
            if _material_matches(c.get("material"), expected_material, use_substring_match)
        )
        return matching_count > cnt


def is_all_material_equal_to(
    coords: List[Dict[str, Any]], 
    expected_material: str,
    use_substring_match: bool = False,
) -> bool:
    """
    Return True if all coords use the expected material, else False.
    
    Args:
        coords: List of coordinate dicts with keys {"x", "y", "z"} and optional {"material"}
        expected_material: The material type to check for
        use_substring_match: If True, use substring matching (e.g., 'red' matches 'red_wool');
                           if False, use exact matching (default)
    
    Returns:
        True if all coords match expected_material, else False
    """
    if not coords:
        return False
    if use_substring_match:
        return all(
            _material_matches(c.get("material"), expected_material, use_substring_match=True)
            for c in coords
        )
    else:
        unique = {c.get("material") for c in coords}
        return unique == {expected_material}
    

def is_corner_material_equal_to(
    coords: List[Dict[str, Any]],
    expected_material: str,
    height_y: int = 2,
    ratio_threshold: float = 0.5,
    use_substring_match: bool = False,
) -> bool:
    """
    Return True if at least ratio_threshold of corner blocks at height_y match expected_material, else False.

    Corner blocks are defined as blocks that maximize one of the following expressions
    among all blocks at the specified height:
    - (x + z): top-right corner
    - (x - z): bottom-right corner
    - (-x + z): top-left corner
    - (-x - z): bottom-left corner

    Args:
        coords: List of coordinate dicts with keys {"x", "y", "z"} and optional {"material"}
        expected_material: The material type to check for
        height_y: The y-coordinate (height) to filter blocks at
        ratio_threshold: Minimum ratio (0.0-1.0) of corner blocks that must match expected_material
        use_substring_match: If True, use substring matching (e.g., 'red' matches 'red_wool');
                           if False, use exact matching (default)

    Returns:
        True if ratio of matching corner blocks >= ratio_threshold, else False
    """
    # Filter blocks at the specified height
    blocks_at_height = [c for c in coords if int(c.get("y", 0)) == height_y]

    # If there are no blocks at height_y, return False
    # Reason: Cannot determine corner blocks without any blocks at the specified height
    if not blocks_at_height:
        return False

    # Calculate the four corner metrics for each block
    # Each block will have values for: (x+z), (x-z), (-x+z), (-x-z)
    corner_metrics = []
    for c in blocks_at_height:
        x, z = int(c.get("x", 0)), int(c.get("z", 0))
        metrics = {
            "x+z": x + z,
            "x-z": x - z,
            "-x+z": -x + z,
            "-x-z": -x - z,
        }
        corner_metrics.append((c, metrics))

    # Find the maximum value for each corner metric
    max_x_plus_z = max(m["x+z"] for _, m in corner_metrics)
    max_x_minus_z = max(m["x-z"] for _, m in corner_metrics)
    max_minus_x_plus_z = max(m["-x+z"] for _, m in corner_metrics)
    max_minus_x_minus_z = max(m["-x-z"] for _, m in corner_metrics)

    # Find all blocks that are at the maximum for at least one corner metric
    corner_blocks = []
    for c, metrics in corner_metrics:
        is_corner = (
            metrics["x+z"] == max_x_plus_z
            or metrics["x-z"] == max_x_minus_z
            or metrics["-x+z"] == max_minus_x_plus_z
            or metrics["-x-z"] == max_minus_x_minus_z
        )
        if is_corner:
            corner_blocks.append(c)

    # If no corner blocks found (shouldn't happen, but safety check)
    if not corner_blocks:
        return False

    # Count how many corner blocks match the expected material
    matching_count = sum(
        1 for c in corner_blocks 
        if _material_matches(c.get("material"), expected_material, use_substring_match)
    )

    # Check if the ratio meets the threshold
    ratio = matching_count / len(corner_blocks)
    return ratio >= ratio_threshold


def _check_material_equality_at_minmax_coordinate(
    coords: List[Dict[str, Any]],
    expected_material: str,
    height_y: int,
    ratio_threshold: float,
    coordinate_getter,
    direction: str,
    use_substring_match: bool = False,
) -> bool:
    """
    Helper function to check material equality at min/max coordinate boundaries.
    
    Checks if blocks at the minimum or maximum value of a coordinate (x or z) at a specific
    height match the expected material, based on a ratio threshold.
    
    Args:
        coords: List of coordinate dicts with keys {"x", "y", "z"} and optional {"material"}
        expected_material: The material type to check for
        height_y: The y-coordinate (height) to filter blocks at
        ratio_threshold: Minimum ratio (0.0-1.0) of boundary blocks that must match expected_material
        coordinate_getter: Function to extract coordinate value (e.g., lambda c: int(c.get("x", 0)))
        direction: Either "max" or "min" to determine which boundary to check
        use_substring_match: If True, use substring matching (e.g., 'red' matches 'red_wool');
                           if False, use exact matching (default)
    
    Returns:
        True if ratio of matching boundary blocks >= ratio_threshold, else False
    """
    # Filter blocks at the specified height
    blocks_at_height = [c for c in coords if int(c.get("y", 0)) == height_y]
    
    # If there are no blocks at height_y, return False
    # Reason: Cannot determine wall blocks without any blocks at the specified height
    if not blocks_at_height:
        return False
    
    # Find the boundary value (max or min) for the coordinate
    coordinate_values = [coordinate_getter(c) for c in blocks_at_height]
    boundary_value = max(coordinate_values) if direction == "max" else min(coordinate_values)
    
    # Find all blocks at the boundary
    wall_blocks = [
        c for c in blocks_at_height 
        if coordinate_getter(c) == boundary_value
    ]
    
    # If no wall blocks found (shouldn't happen, but safety check)
    if not wall_blocks:
        return False
    
    # Count how many wall blocks match the expected material
    matching_count = sum(
        1 for c in wall_blocks 
        if _material_matches(c.get("material"), expected_material, use_substring_match)
    )
    
    # Check if the ratio meets the threshold
    ratio = matching_count / len(wall_blocks)
    return ratio >= ratio_threshold


def is_max_x_material_equal_to(
    coords: List[Dict[str, Any]],
    expected_material: str,
    height_y: int = 2,
    ratio_threshold: float = 0.5,
    use_substring_match: bool = False,
) -> bool:
    """
    Return True if at least ratio_threshold of blocks at maximum x-coordinate (east wall)
    at height_y match expected_material, else False.
    
    Args:
        coords: List of coordinate dicts with keys {"x", "y", "z"} and optional {"material"}
        expected_material: The material type to check for
        height_y: The y-coordinate (height) to filter blocks at
        ratio_threshold: Minimum ratio (0.0-1.0) of wall blocks that must match expected_material
        use_substring_match: If True, use substring matching (e.g., 'red' matches 'red_wool');
                           if False, use exact matching (default)
    
    Returns:
        True if ratio of matching wall blocks >= ratio_threshold, else False
    """
    return _check_material_equality_at_minmax_coordinate(
        coords, expected_material, height_y, ratio_threshold,
        coordinate_getter=lambda c: int(c.get("x", 0)),
        direction="max",
        use_substring_match=use_substring_match
    )


def is_min_x_material_equal_to(
    coords: List[Dict[str, Any]],
    expected_material: str,
    height_y: int = 2,
    ratio_threshold: float = 0.5,
    use_substring_match: bool = False,
) -> bool:
    """
    Return True if at least ratio_threshold of blocks at minimum x-coordinate (west wall)
    at height_y match expected_material, else False.
    
    Args:
        coords: List of coordinate dicts with keys {"x", "y", "z"} and optional {"material"}
        expected_material: The material type to check for
        height_y: The y-coordinate (height) to filter blocks at
        ratio_threshold: Minimum ratio (0.0-1.0) of wall blocks that must match expected_material
        use_substring_match: If True, use substring matching (e.g., 'red' matches 'red_wool');
                           if False, use exact matching (default)
    
    Returns:
        True if ratio of matching wall blocks >= ratio_threshold, else False
    """
    return _check_material_equality_at_minmax_coordinate(
        coords, expected_material, height_y, ratio_threshold,
        coordinate_getter=lambda c: int(c.get("x", 0)),
        direction="min",
        use_substring_match=use_substring_match
    )


def is_max_z_material_equal_to(
    coords: List[Dict[str, Any]],
    expected_material: str,
    height_y: int = 2,
    ratio_threshold: float = 0.5,
    use_substring_match: bool = False,
) -> bool:
    """
    Return True if at least ratio_threshold of blocks at maximum z-coordinate (south wall)
    at height_y match expected_material, else False.
    
    Args:
        coords: List of coordinate dicts with keys {"x", "y", "z"} and optional {"material"}
        expected_material: The material type to check for
        height_y: The y-coordinate (height) to filter blocks at
        ratio_threshold: Minimum ratio (0.0-1.0) of wall blocks that must match expected_material
        use_substring_match: If True, use substring matching (e.g., 'red' matches 'red_wool');
                           if False, use exact matching (default)
    
    Returns:
        True if ratio of matching wall blocks >= ratio_threshold, else False
    """
    return _check_material_equality_at_minmax_coordinate(
        coords, expected_material, height_y, ratio_threshold,
        coordinate_getter=lambda c: int(c.get("z", 0)),
        direction="max",
        use_substring_match=use_substring_match
    )


def is_min_z_material_equal_to(
    coords: List[Dict[str, Any]],
    expected_material: str,
    height_y: int = 2,
    ratio_threshold: float = 0.5,
    use_substring_match: bool = False,
) -> bool:
    """
    Return True if at least ratio_threshold of blocks at minimum z-coordinate (north wall)
    at height_y match expected_material, else False.
    
    Args:
        coords: List of coordinate dicts with keys {"x", "y", "z"} and optional {"material"}
        expected_material: The material type to check for
        height_y: The y-coordinate (height) to filter blocks at
        ratio_threshold: Minimum ratio (0.0-1.0) of wall blocks that must match expected_material
        use_substring_match: If True, use substring matching (e.g., 'red' matches 'red_wool');
                           if False, use exact matching (default)
    
    Returns:
        True if ratio of matching wall blocks >= ratio_threshold, else False
    """
    return _check_material_equality_at_minmax_coordinate(
        coords, expected_material, height_y, ratio_threshold,
        coordinate_getter=lambda c: int(c.get("z", 0)),
        direction="min",
        use_substring_match=use_substring_match
    )


def is_highest_block_material_equal_to(
    coords: List[Dict[str, Any]],
    expected_material: str,
    ratio_threshold: float = 0.5,
    use_substring_match: bool = False,
) -> bool:
    """
    Return True if at least ratio_threshold of blocks at the highest y-coordinate (top layer)
    match expected_material, else False.
    
    Finds the maximum y-coordinate among all blocks and checks if blocks at that height
    match the expected material based on the ratio threshold.
    
    Args:
        coords: List of coordinate dicts with keys {"x", "y", "z"} and optional {"material"}
        expected_material: The material type to check for
        ratio_threshold: Minimum ratio (0.0-1.0) of highest blocks that must match expected_material
        use_substring_match: If True, use substring matching (e.g., 'red' matches 'red_wool');
                           if False, use exact matching (default)
    
    Returns:
        True if ratio of matching highest blocks >= ratio_threshold, else False
    """
    # If there are no blocks, return False
    # Reason: Cannot determine highest blocks without any blocks
    if not coords:
        return False
    
    # Find the maximum y-coordinate (highest height)
    max_y = max(int(c.get("y", 0)) for c in coords)
    
    # Filter blocks at the highest y-coordinate
    highest_blocks = [c for c in coords if int(c.get("y", 0)) == max_y]
    
    # If no highest blocks found (shouldn't happen, but safety check)
    if not highest_blocks:
        return False
    
    # Count how many highest blocks match the expected material
    matching_count = sum(
        1 for c in highest_blocks 
        if _material_matches(c.get("material"), expected_material, use_substring_match)
    )
    
    # Check if the ratio meets the threshold
    ratio = matching_count / len(highest_blocks)
    return ratio >= ratio_threshold