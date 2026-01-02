# viz/plotly_blocks.py
"""
Plot Minecraft-like block coords as interactive cubes using Plotly Mesh3d.

Coordinate mapping:
- Minecraft axes: (x, y, z) with y = vertical (height).
- Plotly scene: we display height on the Z-axis (visually vertical).
  So we map (mc_x, mc_y, mc_z) -> (plot_x, plot_y, plot_z) = (x, z, y).

Mesh3d triangle indices:
- Mesh3d uses three integer arrays (i, j, k), where each (i[t], j[t], k[t]) triple
  indexes three vertices that form ONE triangle.
- A cube has 6 faces; each face is two triangles -> 12 triangles per cube.

Heatmap coloring:
- If `color` is provided (a numeric array with the same length as coords),
  each cube is colored by its corresponding value.
- Values are normalized to [0, 1] and mapped to a rainbow colorscale:
  purple -> blue -> cyan -> green -> yellow -> orange -> red.
- If `colorbar_title` is provided (truthy) and `color` is provided, a colorbar
  is shown via an invisible Scatter3d trace (Mesh3d facecolor does not support
  a colorbar directly).
"""

from typing import Dict, List, Any, Tuple, Iterable, Optional, Sequence
import numpy as np
import plotly.graph_objects as go
from plotly.colors import sample_colorscale

from .material_colors import MATERIAL_COLOR


# Custom rainbow colorscale (low -> high):
# purple -> blue -> cyan -> green -> yellow -> orange -> red
RAINBOW_SCALE = [
    [0.0, "#800080"],        # purple
    [1.0 / 6.0, "#0000FF"],  # blue
    [2.0 / 6.0, "#00FFFF"],  # cyan
    [3.0 / 6.0, "#00FF00"],  # green
    [4.0 / 6.0, "#FFFF00"],  # yellow
    [5.0 / 6.0, "#FFA500"],  # orange
    [1.0, "#FF0000"],        # red
]


def _cube_vertices(x: int, y: int, z: int, size: int = 1) -> List[Tuple[int, int, int]]:
    """
    Return the 8 vertices of an axis-aligned cube located at (x, y, z)
    with edge length `size`. Vertices are ordered to simplify face construction.
    """
    return [
        (x,         y,         z        ),
        (x + size,  y,         z        ),
        (x + size,  y + size,  z        ),
        (x,         y + size,  z        ),
        (x,         y,         z + size ),
        (x + size,  y,         z + size ),
        (x + size,  y + size,  z + size ),
        (x,         y + size,  z + size ),
    ]


# Each face is a quad expressed by 4 vertex indices (into the 8-vertex list above).
# We will split each quad into 2 triangles for Mesh3d.
_CUBE_FACES: List[Tuple[int, int, int, int]] = [
    (0, 1, 2, 3),  # front
    (4, 5, 6, 7),  # back
    (0, 1, 5, 4),  # bottom
    (2, 3, 7, 6),  # top
    (1, 2, 6, 5),  # right
    (0, 3, 7, 4),  # left
]


def _material_to_color(material: Optional[str]) -> str:
    """Return hex color for material; unknown maps to black."""
    return MATERIAL_COLOR.get((material or "").strip(), "#000000")


def _values_to_hex_colors(values: Sequence[float]) -> List[str]:
    """
    Map numeric values to hex colors using RAINBOW_SCALE.

    - Values are normalized to [0, 1] using min/max over finite values.
    - NaN/Inf values are treated as the minimum (mapped to purple).
    - If all finite values are identical, everything maps to purple.
    """
    v = np.asarray(values, dtype=float)
    finite = np.isfinite(v)

    # If nothing is finite, return all purple.
    if not finite.any():
        return ["#800080"] * len(v)

    vmin = float(np.nanmin(v[finite]))
    vmax = float(np.nanmax(v[finite]))

    if np.isclose(vmin, vmax):
        t = np.zeros_like(v, dtype=float)
    else:
        t = (v - vmin) / (vmax - vmin)
        t = np.clip(t, 0.0, 1.0)

    # Non-finite values map to the minimum.
    t[~finite] = 0.0

    # sample_colorscale returns validated colors (e.g., hex strings)
    return sample_colorscale(RAINBOW_SCALE, t.tolist())


def plot(
    coords: Iterable[Dict[str, Any]],
    *,
    title: str = "",
    alpha: float = 0.5,
    cube_size: int = 1,
    show_legend: bool = True,
    color: Optional[Sequence[float]] = None,
    colorbar_title: Optional[str] = None,
) -> go.Figure:
    """
    Render block coordinates as cubes in an interactive Plotly figure.

    Args:
        coords: iterable of dicts with keys {"x","y","z"} and optional {"material"}.
        title: plot title.
        alpha: cube face opacity (0.0 — 1.0).
        cube_size: edge length for each cube (usually 1).
        show_legend: if True, add a simple color legend for known materials.
                     Ignored when `color` is provided (heatmap mode).
        color: optional numeric array with the same length as coords. If provided,
               cubes are colored by value using RAINBOW_SCALE.
        colorbar_title: if provided (truthy) and `color` is provided, show a colorbar
                        with this title. If None/""/False, no colorbar is shown.

    Returns:
        plotly.graph_objects.Figure
    """
    # Convert to list so we can safely index and measure length.
    coords = list(coords)
    n = len(coords)

    if color is not None and len(color) != n:
        raise ValueError(f"`color` length ({len(color)}) must match coords length ({n})")

    # Precompute per-cube colors in heatmap mode.
    heat_colors: Optional[List[str]] = None
    if color is not None:
        heat_colors = _values_to_hex_colors(color)

    # Accumulate all cube vertices and face triangles into flat arrays for Mesh3d.
    plot_x: List[int] = []
    plot_y: List[int] = []
    plot_z: List[int] = []
    tri_i: List[int] = []
    tri_j: List[int] = []
    tri_k: List[int] = []
    face_colors: List[str] = []

    # Track materials actually used in the plot (material legend mode only).
    materials_used: Dict[str, str] = {}  # material_name -> color

    for idx, c in enumerate(coords):
        x, y, z = int(c["x"]), int(c["y"]), int(c["z"])

        # Choose color source: heatmap values or per-material color.
        if heat_colors is not None:
            cube_color = heat_colors[idx]
        else:
            material = (c.get("material") or "").strip()
            cube_color = _material_to_color(material)

            # Track this material if it's a known material (not the black fallback).
            if material and material in MATERIAL_COLOR:
                materials_used[material] = cube_color

        # Build the 8 cube vertices in Minecraft coords.
        verts = _cube_vertices(x, y, z, size=cube_size)
        base_idx = len(plot_x)  # current vertex offset in the global arrays

        # Map (mc_x, mc_y, mc_z) -> (plot_x, plot_y, plot_z) = (x, z, y).
        for vx, vy, vz in verts:
            plot_x.append(vx)    # horizontal X
            plot_y.append(vz)    # depth (MC z)
            plot_z.append(vy)    # vertical (MC y) -> Plotly Z

        # For each face (quad), emit 2 triangles in (i, j, k).
        for a, b, c_idx, d in _CUBE_FACES:
            i0, i1, i2, i3 = base_idx + a, base_idx + b, base_idx + c_idx, base_idx + d

            # Triangle 1: (i0, i1, i2)
            tri_i.append(i0); tri_j.append(i1); tri_k.append(i2)
            face_colors.append(cube_color)

            # Triangle 2: (i0, i2, i3)
            tri_i.append(i0); tri_j.append(i2); tri_k.append(i3)
            face_colors.append(cube_color)

    fig = go.Figure(data=[go.Mesh3d(
        x=plot_x, y=plot_y, z=plot_z,
        i=tri_i, j=tri_j, k=tri_k,
        facecolor=face_colors,   # one color per triangle
        opacity=alpha,
        flatshading=True,
    )])

    fig.update_layout(
        title=title,
        scene=dict(
            xaxis_title="X",
            yaxis_title="Z",
            zaxis_title="Y (Height)",
            aspectmode="data",
        ),
        legend=dict(itemsizing="constant"),
        margin=dict(l=0, r=0, t=40, b=0),
    )

    # Add a material legend (only if not in heatmap mode).
    if heat_colors is None and show_legend and materials_used:
        # Create a tiny legend using invisible Scatter3d markers.
        legend_traces = []
        for name, mat_color in sorted(materials_used.items()):
            legend_traces.append(go.Scatter3d(
                x=[None], y=[None], z=[None],
                mode="markers",
                marker=dict(size=8, color=mat_color),
                name=name
            ))
        for tr in legend_traces:
            fig.add_trace(tr)

    # Add a colorbar in heatmap mode if and only if `colorbar_title` is truthy.
    if heat_colors and colorbar_title:
        v = np.asarray(color, dtype=float)  # type: ignore[arg-type]
        finite = np.isfinite(v)
        if finite.any():
            cmin = float(np.nanmin(v[finite]))
            cmax = float(np.nanmax(v[finite]))
        else:
            cmin, cmax = 0.0, 1.0

        # Invisible trace used only to display the colorbar.
        fig.add_trace(go.Scatter3d(
            x=[None], y=[None], z=[None],
            mode="markers",
            marker=dict(
                size=0.1,
                color=v,
                colorscale=RAINBOW_SCALE,
                cmin=cmin,
                cmax=cmax,
                colorbar=dict(title=str(colorbar_title)),
            ),
            showlegend=False
        ))

    return fig


# Example:
# fig = plot(coords, title="Bridge (Cubes)", alpha=0.6, show_legend=True)
# fig.show()
#
# Heatmap example:
# values = [0.1, 0.2, 0.3, 1.0]
# fig = plot(coords, color=values, colorbar_title="von Mises (Pa)")
# fig.show()
