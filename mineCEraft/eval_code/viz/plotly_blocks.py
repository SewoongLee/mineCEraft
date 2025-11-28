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
- A cube has 6 faces; each face is two triangles → 12 triangles per cube.
"""

from typing import Dict, List, Any, Tuple, Iterable, Optional
import plotly.graph_objects as go
from .material_colors import MATERIAL_COLOR

def _cube_vertices(x: int, y: int, z: int, size: int = 1) -> List[Tuple[int, int, int]]:
    """
    Return the 8 vertices of an axis-aligned cube located at (x, y, z) with edge length `size`.
    Vertices are ordered to simplify face construction.
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

def plot(
    coords: Iterable[Dict[str, Any]],
    *,
    title: str = "",
    alpha: float = 0.5,
    cube_size: int = 1,
    show_legend: bool = False,
) -> go.Figure:
    """
    Render block coordinates as cubes in an interactive Plotly figure.

    Args:
        coords: iterable of dicts with keys {"x","y","z"} and optional {"material"}.
        title: plot title.
        alpha: cube face opacity (0.0 — 1.0).
        cube_size: edge length for each cube (usually 1).
        show_legend: if True, add a simple color legend for known materials.

    Returns:
        plotly.graph_objects.Figure
    """
    # Accumulate all cube vertices and face triangles into flat arrays for Mesh3d
    plot_x: List[int] = []
    plot_y: List[int] = []
    plot_z: List[int] = []
    tri_i: List[int] = []
    tri_j: List[int] = []
    tri_k: List[int] = []
    face_colors: List[str] = []
    
    # Track materials actually used in the plot
    materials_used: Dict[str, str] = {}  # material_name -> color

    for c in coords:
        x, y, z = int(c["x"]), int(c["y"]), int(c["z"])
        material = (c.get("material") or "").strip()
        color = _material_to_color(material)
        
        # Track this material if it's a known material (not the black fallback)
        if material and material in MATERIAL_COLOR:
            materials_used[material] = color

        # Build the 8 cube vertices in Minecraft coords
        verts = _cube_vertices(x, y, z, size=cube_size)
        base_idx = len(plot_x)  # current vertex offset in the global arrays

        # Map (mc_x, mc_y, mc_z) -> (plot_x, plot_y, plot_z) = (x, z, y)
        for vx, vy, vz in verts:
            plot_x.append(vx)    # horizontal X
            plot_y.append(vz)    # depth (MC z)
            plot_z.append(vy)    # vertical (MC y) → Plotly Z

        # For each face (quad), emit 2 triangles in (i, j, k)
        for a, b, c_idx, d in _CUBE_FACES:
            i0, i1, i2, i3 = base_idx + a, base_idx + b, base_idx + c_idx, base_idx + d
            # Triangle 1: (i0, i1, i2)
            tri_i.append(i0); tri_j.append(i1); tri_k.append(i2)
            face_colors.append(color)
            # Triangle 2: (i0, i2, i3)
            tri_i.append(i0); tri_j.append(i2); tri_k.append(i3)
            face_colors.append(color)

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

    if show_legend and materials_used:
        # Create a tiny legend using invisible Scatter3d markers
        # Only show materials that are actually present in the plot
        legend_traces = []
        for name, color in sorted(materials_used.items()):
            legend_traces.append(go.Scatter3d(
                x=[None], y=[None], z=[None],
                mode="markers",
                marker=dict(size=8, color=color),
                name=name
            ))
        for tr in legend_traces:
            fig.add_trace(tr)

    return fig

# Example:
# fig = plot(coords, title="Arched Bridge (Cubes)", alpha=0.5, show_legend=True)
# fig.show()
