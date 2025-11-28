from collections import Counter
from typing import List, Dict, Any


def is_quantity_correct(coords: List[Dict[str, Any]], expected_count: int) -> bool:
    """Return True if number of blocks equals expected_count, else False."""
    return len(coords) == expected_count


def is_type_correct(coords: List[Dict[str, Any]], expected_material: str) -> bool:
    """
    Return True if all coords use the expected material, else False.
    """
    if not coords:
        return False
    unique = {c.get("material") for c in coords}
    return unique == {expected_material}


def material_distribution(coords: List[Dict[str, Any]]) -> Counter:
    """(Optional helper) Count materials for reporting."""
    return Counter(c.get("material") for c in coords)


def is_corner_material_equal_to(
    coords: List[Dict[str, Any]],
    expected_material: str,
    height_y: int = 2,
    ratio_threshold: float = 0.5,
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
        1 for c in corner_blocks if c.get("material") == expected_material
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
        if c.get("material") == expected_material
    )
    
    # Check if the ratio meets the threshold
    ratio = matching_count / len(wall_blocks)
    return ratio >= ratio_threshold


def is_max_x_material_equal_to(
    coords: List[Dict[str, Any]],
    expected_material: str,
    height_y: int = 2,
    ratio_threshold: float = 0.5,
) -> bool:
    """
    Return True if at least ratio_threshold of blocks at maximum x-coordinate (east wall)
    at height_y match expected_material, else False.
    
    Args:
        coords: List of coordinate dicts with keys {"x", "y", "z"} and optional {"material"}
        expected_material: The material type to check for
        height_y: The y-coordinate (height) to filter blocks at
        ratio_threshold: Minimum ratio (0.0-1.0) of wall blocks that must match expected_material
    
    Returns:
        True if ratio of matching wall blocks >= ratio_threshold, else False
    """
    return _check_material_equality_at_minmax_coordinate(
        coords, expected_material, height_y, ratio_threshold,
        coordinate_getter=lambda c: int(c.get("x", 0)),
        direction="max"
    )


def is_min_x_material_equal_to(
    coords: List[Dict[str, Any]],
    expected_material: str,
    height_y: int = 2,
    ratio_threshold: float = 0.5,
) -> bool:
    """
    Return True if at least ratio_threshold of blocks at minimum x-coordinate (west wall)
    at height_y match expected_material, else False.
    
    Args:
        coords: List of coordinate dicts with keys {"x", "y", "z"} and optional {"material"}
        expected_material: The material type to check for
        height_y: The y-coordinate (height) to filter blocks at
        ratio_threshold: Minimum ratio (0.0-1.0) of wall blocks that must match expected_material
    
    Returns:
        True if ratio of matching wall blocks >= ratio_threshold, else False
    """
    return _check_material_equality_at_minmax_coordinate(
        coords, expected_material, height_y, ratio_threshold,
        coordinate_getter=lambda c: int(c.get("x", 0)),
        direction="min"
    )


def is_max_z_material_equal_to(
    coords: List[Dict[str, Any]],
    expected_material: str,
    height_y: int = 2,
    ratio_threshold: float = 0.5,
) -> bool:
    """
    Return True if at least ratio_threshold of blocks at maximum z-coordinate (south wall)
    at height_y match expected_material, else False.
    
    Args:
        coords: List of coordinate dicts with keys {"x", "y", "z"} and optional {"material"}
        expected_material: The material type to check for
        height_y: The y-coordinate (height) to filter blocks at
        ratio_threshold: Minimum ratio (0.0-1.0) of wall blocks that must match expected_material
    
    Returns:
        True if ratio of matching wall blocks >= ratio_threshold, else False
    """
    return _check_material_equality_at_minmax_coordinate(
        coords, expected_material, height_y, ratio_threshold,
        coordinate_getter=lambda c: int(c.get("z", 0)),
        direction="max"
    )


def is_min_z_material_equal_to(
    coords: List[Dict[str, Any]],
    expected_material: str,
    height_y: int = 2,
    ratio_threshold: float = 0.5,
) -> bool:
    """
    Return True if at least ratio_threshold of blocks at minimum z-coordinate (north wall)
    at height_y match expected_material, else False.
    
    Args:
        coords: List of coordinate dicts with keys {"x", "y", "z"} and optional {"material"}
        expected_material: The material type to check for
        height_y: The y-coordinate (height) to filter blocks at
        ratio_threshold: Minimum ratio (0.0-1.0) of wall blocks that must match expected_material
    
    Returns:
        True if ratio of matching wall blocks >= ratio_threshold, else False
    """
    return _check_material_equality_at_minmax_coordinate(
        coords, expected_material, height_y, ratio_threshold,
        coordinate_getter=lambda c: int(c.get("z", 0)),
        direction="min"
    )