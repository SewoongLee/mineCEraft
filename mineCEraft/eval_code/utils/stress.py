# eval_code/utils/stress.py
"""
Von Mises stress for Minecraft-like block structures (SPH / meshfree solid),
ported from "Minecraft SPH V8" and optimized for Python.

Reference:
- https://arxiv.org/pdf/2212.08124
- https://github.com/abuganza/minecraft_sph
-------------------------------------------------------------------------------
"""

# Material / physical parameters used in this solver:
# - young (E) [Pa]: Young's modulus, controls elastic stiffness (higher => stiffer).
# - nu (ν): Poisson's ratio, controls lateral contraction (0~0.49 typical for 3D solids).
# - eta (η): deviatoric viscosity coefficient (higher => more damping / less vibration).
# - rho (ρ) [kg/m^3]: density; each block mass is approximated by m = rho * Vol (Vol=1 here).
#   Larger rho => smaller acceleration for the same force (more inertia, often more stable).
# - alpha (α): hourglass strength factor (numerical stabilization).
# - Ehg [Pa]: hourglass "stiffness" scale (numerical stabilization).
#
# Simulation / loading parameters:
# - dt [s]: time step size (explicit integration; too large => instability).
# - n_t_steps: number of time steps (total simulated time ~ dt * n_t_steps).
# - loading_time_percent [%]: ramp-up duration for external load to avoid sudden shock.
# - block_load / load_block_weight [N]: per-block external force applied in -y direction.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# =============================================================================
# Helpers: coords -> arrays
# =============================================================================

def _coords_to_X(coords: Sequence[Dict[str, Any]]) -> np.ndarray:
    """Convert a list of {"x","y","z",...} dicts to an (n,3) float array."""
    X0 = np.zeros((len(coords), 3), dtype=float)
    for i, c in enumerate(coords):
        X0[i, 0] = float(c["x"])
        X0[i, 1] = float(c["y"])
        X0[i, 2] = float(c["z"])
    return X0


def _min_y_supports(X0: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """Indices of blocks at minimum y (fixed supports)."""
    ymin = float(np.min(X0[:, 1]))
    return np.where(np.abs(X0[:, 1] - ymin) <= eps)[0].astype(int)


# =============================================================================
# Kernel functions (ported from the mod)
# =============================================================================

def _eval_W_from_r(r: np.ndarray, h: float) -> np.ndarray:
    """
    Mod kernel:
      W(r) = (15/pi/h^6) * (h - r)^3
    with support r < h.
    """
    return (15.0 / (np.pi * (h ** 6))) * ((h - r) ** 3)


def _eval_gradW_from_R(R: np.ndarray, r: np.ndarray, h: float, eps: float = 1e-12) -> np.ndarray:
    """
    Mod gradient:
      gradW = R * scale
      scale = -3 * (15/pi/h^6) * (h - r)^2 / r
    """
    safe_r = np.maximum(r, eps)
    scale = -3.0 * ((15.0 / (np.pi * (h ** 6))) * ((h - r) ** 2)) / safe_r
    return R * scale[:, None]


# =============================================================================
# Linear algebra helpers
# =============================================================================

def _safe_inv_3x3(A: np.ndarray, rcond: float = 1e-12) -> np.ndarray:
    """
    Invert a 3x3 matrix; if singular, fall back to pseudo-inverse.
    """
    try:
        return np.linalg.inv(A)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(A, rcond=rcond)


# =============================================================================
# Precomputation: build edges + cached reference terms
# =============================================================================

def _build_edges_and_reference_cache(
    X0: np.ndarray,
    h_threshold: float,
    *,
    max_neighbors: Optional[int],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Build edge list (i,j) with i<j and cache reference-only quantities per edge.

    Returns:
      ei, ej: (m,) int arrays
      Rij: (m,3) float
      Rijmag: (m,) float
      W: (m,) float
      gradW: (m,3) float
    """
    n = X0.shape[0]
    h = float(h_threshold)

    ei_list: List[int] = []
    ej_list: List[int] = []
    d_list: List[float] = []

    for i in range(n):
        Xi = X0[i]
        for j in range(i + 1, n):
            d = float(np.linalg.norm(Xi - X0[j]))
            if d < h:
                ei_list.append(i)
                ej_list.append(j)
                d_list.append(d)

    if len(ei_list) == 0:
        # No edges -> no coupling; return empty caches.
        ei = np.zeros((0,), dtype=int)
        ej = np.zeros((0,), dtype=int)
        Rij = np.zeros((0, 3), dtype=float)
        Rijmag = np.zeros((0,), dtype=float)
        W = np.zeros((0,), dtype=float)
        gradW = np.zeros((0, 3), dtype=float)
        return ei, ej, Rij, Rijmag, W, gradW

    ei = np.asarray(ei_list, dtype=int)
    ej = np.asarray(ej_list, dtype=int)

    Rij = X0[ej] - X0[ei]                           # (m,3)
    Rijmag = np.asarray(d_list, dtype=float)        # (m,)

    # Cache reference-only kernel values
    W = _eval_W_from_r(Rijmag, h)                   # (m,)
    gradW = _eval_gradW_from_R(Rij, Rijmag, h)      # (m,3)

    if max_neighbors is not None:
        # Enforce a per-node neighbor cap by keeping closest edges.
        # We first build a neighbor list by edges, sort by distance, and drop extras.
        cap = int(max_neighbors)
        keep = np.zeros((ei.shape[0],), dtype=bool)

        # Collect edges by node using python lists (fast enough in preprocessing).
        by_node: List[List[int]] = [[] for _ in range(n)]
        for e in range(ei.shape[0]):
            by_node[ei[e]].append(e)
            by_node[ej[e]].append(e)

        # Mark edges to keep based on distance ranking per node.
        # If an edge is kept by either endpoint, we keep it (slightly looser but stable).
        for node in range(n):
            edges = by_node[node]
            if len(edges) <= cap:
                keep[np.asarray(edges, dtype=int)] = True
                continue
            edges_arr = np.asarray(edges, dtype=int)
            order = np.argsort(Rijmag[edges_arr])
            chosen = edges_arr[order[:cap]]
            keep[chosen] = True

        # Apply mask
        ei = ei[keep]
        ej = ej[keep]
        Rij = Rij[keep]
        Rijmag = Rijmag[keep]
        W = W[keep]
        gradW = gradW[keep]

    return ei, ej, Rij, Rijmag, W, gradW


def _precompute_Ainv(
    n: int,
    ei: np.ndarray,
    ej: np.ndarray,
    Rij: np.ndarray,
    gradW: np.ndarray,
    pinv_rcond: float,
) -> np.ndarray:
    """
    Precompute Ainv per particle (reference-only):

      A_i = Σ_j (Rij ⊗ gradW(Rij))

    Important symmetry note:
    For an undirected edge (i,j) with Rij = Xj - Xi and gradW(Rij),
    the mod uses for the opposite direction (j,i):
      Rji = -Rij, gradW(Rji) = -gradW(Rij)
    and outer(Rji, gradW(Rji)) = outer(Rij, gradW(Rij)).
    Therefore the same outer product contributes to BOTH endpoints.
    """
    A = np.zeros((n, 3, 3), dtype=float)  # (n,3,3)

    # For each edge, compute outer(Rij, gradW) and add to A[i] and A[j].
    # outer: (m,3,3) where outer[e,a,b] = Rij[e,a] * gradW[e,b]
    outer_rg = Rij[:, :, None] * gradW[:, None, :]  # (m,3,3)

    # Scatter-add to endpoints.
    np.add.at(A, ei, outer_rg)
    np.add.at(A, ej, outer_rg)

    # Invert per particle (3x3). Looping n times is OK and stable.
    Ainv = np.zeros_like(A)
    for i in range(n):
        Ainv[i] = _safe_inv_3x3(A[i], rcond=float(pinv_rcond))
    return Ainv


# =============================================================================
# Stress / force / constitutive model (StVK + deviatoric viscosity) (ported)
# =============================================================================

def _calculate_P_stvk_with_viscosity(
    F: np.ndarray,
    Ft: np.ndarray,
    dt: float,
    young: float,
    nu: float,
    eta: float,
    pinv_rcond: float,
) -> np.ndarray:
    """
    Port of the mod's mat[0]==1 branch:

      C = F^T F
      E = 0.5 (C - I)
      S = lambda*tr(E)*I + 2*mu*E

      Fdot = (F - Ft)/dt
      L = Fdot * inv(F)
      d = 0.5(L + L^T)
      d' = d - (tr(d)/3)*I

      P = F*S + d' * inv(F)^T * (2*J*eta)
    """
    I = np.eye(3)
    C = F.T @ F
    E = 0.5 * (C - I)
    trE = float(np.trace(E))
    J = float(np.linalg.det(F))

    lame_lam = young * nu / ((1.0 + nu) * (1.0 - nu))
    lame_mu = young / (2.0 * (1.0 + nu))
    S = lame_lam * trE * I + 2.0 * lame_mu * E

    # Viscosity (becomes 0 if eta==0)
    Fdot = (F - Ft) / dt
    Finv = _safe_inv_3x3(F, rcond=float(pinv_rcond))
    L = Fdot @ Finv
    d = 0.5 * (L + L.T)
    dprime = d - (np.trace(d) / 3.0) * I

    return (F @ S) + (dprime @ Finv.T) * (2.0 * J * eta)


def _von_mises_from_sigma(sigma: np.ndarray) -> float:
    """
    Mod von Mises formula:
      vm = sqrt((s11-s22)^2 + (s22-s33)^2 + (s33-s11)^2 + 6*(s23^2+s13^2+s12^2)) / sqrt(2)
    """
    s = sigma
    return float(
        np.sqrt(
            (s[0, 0] - s[1, 1]) ** 2
            + (s[1, 1] - s[2, 2]) ** 2
            + (s[2, 2] - s[0, 0]) ** 2
            + 6.0 * (s[1, 2] ** 2 + s[0, 2] ** 2 + s[0, 1] ** 2)
        ) / np.sqrt(2.0)
    )


# =============================================================================
# Public API
# =============================================================================

def compute_von_mises_stress(
    coords: Sequence[Dict[str, Any]],
    *,
    # Neighbor cutoff (main control of interaction range)
    h_threshold: float = 2.0,
    max_neighbors: Optional[int] = None,
    # Material model (defaults match the mod)
    young: float = 1e9,
    nu: float = 0.4,
    eta: float = 0.0,
    # Mass/density and integration (defaults match typical "1999 step" runs)
    rho: float = 15000.0,          # [kg/m^3], used as mass density (mass ~ rho*Vol; Vol=1)
    dt: float = 1e-4,              # global time step (mod default)
    n_t_steps: int = 2000,         # 2000 steps => last printed index is 1999
    loading_time_percent: float = 20.0,
    # External loads (mod-style: direct per-particle force in y)
    block_load: float = -900.0,
    load_block_weight: float = -900.0,
    loaded_blocks: Optional[Sequence[int]] = None,
    # Stabilization (mod hourglass control)
    alpha: float = 1.0,
    Ehg: float = 1e8,
    # Supports (requested: fix all min-y blocks)
    fix_min_y: bool = True,
    # Numerical safety
    pinv_rcond: float = 1e-12,
    # Progress bar
    progress: bool = True,
) -> np.ndarray:
    if loaded_blocks is None:
        loaded_blocks = []

    X0 = _coords_to_X(coords)
    n = int(X0.shape[0])

    # Trivial case
    if n == 0:
        return np.zeros((0,), dtype=float)

    # Supports: fix all blocks with minimum y, as requested.
    supports = _min_y_supports(X0) if fix_min_y else np.zeros((0,), dtype=int)

    # Build edges and cache reference-only kernel quantities.
    ei, ej, Rij, Rijmag, W, gradW = _build_edges_and_reference_cache(
        X0, float(h_threshold), max_neighbors=max_neighbors
    )

    # Precompute Ainv per particle (reference-only).
    Ainv = _precompute_Ainv(n, ei, ej, Rij, gradW, float(pinv_rcond))

    # State variables
    x = X0.copy()                      # current positions
    V = np.zeros((n, 3), dtype=float)  # velocities
    A = np.zeros((n, 3), dtype=float)  # accelerations

    F = np.tile(np.eye(3)[None, :, :], (n, 1, 1)).copy()
    Ft_prev = F.copy()

    # The mod stores PP_tilde = P * Ainv, and uses PP_tilde in internal forces.
    PP_tilde = np.zeros((n, 3, 3), dtype=float)

    # Helper: enforce fixed supports at every step.
    def enforce_supports() -> None:
        if supports.size == 0:
            return
        x[supports] = X0[supports]
        V[supports] = 0.0
        A[supports] = 0.0

    # Load ramp setup (matches mod idea)
    denom_steps = (float(loading_time_percent) / 100.0) * float(n_t_steps)
    denom_steps = max(denom_steps, 1.0)

    # Progress iterator
    if progress:
        try:
            from tqdm.auto import tqdm  # type: ignore
            step_iter = tqdm(range(int(n_t_steps)), desc="SPH steps")
        except Exception:
            step_iter = range(int(n_t_steps))
    else:
        step_iter = range(int(n_t_steps))

    # Precompute constants used in hourglass coefficient to reduce per-edge work.
    # The mod uses: coeff ~ -0.5*alpha*Ehg*W / (rijmag * Rijmag^3) * (deltai+deltaj)
    # Rijmag is reference-only, so 1/(Rijmag^3) can be cached.
    eps = 1e-12
    inv_Rijmag3 = 1.0 / np.maximum(Rijmag, eps) ** 3  # (m,)

    # -----------------------------------------------------------------------------
    # Time integration loop
    # -----------------------------------------------------------------------------
    for ti in step_iter:
        Ft_prev = F.copy()

        # --- 1) Compute Fstar per node from current rij and cached gradW ---
        # rij for each edge (i->j)
        rij = x[ej] - x[ei]  # (m,3)

        # Fstar contribution per edge: outer(rij, gradW)
        outer_r_g = rij[:, :, None] * gradW[:, None, :]  # (m,3,3)

        Fstar = np.zeros((n, 3, 3), dtype=float)
        # As with A, the same outer product contributes to BOTH endpoints.
        np.add.at(Fstar, ei, outer_r_g)
        np.add.at(Fstar, ej, outer_r_g)

        # F_i = Fstar_i @ Ainv_i  (batch)
        F = np.einsum("nij,njk->nik", Fstar, Ainv)

        # --- 2) Constitutive model: compute P and store PP_tilde = P @ Ainv ---
        P = np.zeros((n, 3, 3), dtype=float)
        for i in range(n):
            P[i] = _calculate_P_stvk_with_viscosity(
                F[i], Ft_prev[i], float(dt), float(young), float(nu), float(eta), float(pinv_rcond)
            )
        PP_tilde = np.einsum("nij,njk->nik", P, Ainv)

        # --- 3) Internal forces using edge-based accumulation (Newton 3rd law enforced) ---
        Fint = np.zeros((n, 3), dtype=float)

        # Elastic/SPH force: contrib = (PP_i + PP_j) @ gradW_ij
        PPsum = PP_tilde[ei] + PP_tilde[ej]                  # (m,3,3)
        contrib = np.einsum("mij,mj->mi", PPsum, gradW)      # (m,3)
        np.add.at(Fint, ei, contrib)
        np.add.at(Fint, ej, -contrib)

        # Hourglass stabilization (ported from the mod, but accumulated edge-wise)
        rijmag = np.linalg.norm(rij, axis=1)                 # (m,)
        rijmag_safe = np.maximum(rijmag, eps)

        rij_pred = np.einsum("mij,mj->mi", F[ei], Rij)       # (m,3)  Fi @ Rij
        rji_pred = np.einsum("mij,mj->mi", F[ej], -Rij)      # (m,3)  Fj @ (-Rij)

        deltai = np.einsum("mi,mi->m", (rij_pred - rij), rij) / rijmag_safe
        deltaj = np.einsum("mi,mi->m", (rji_pred + rij), (-rij)) / rijmag_safe

        # Scalar coefficient per edge
        hg_coeff = (
            -0.5 * float(alpha) * float(Ehg)
            * W
            * (deltai + deltaj)
            / (rijmag_safe * inv_Rijmag3)
        )
        # Wait: we cached inv_Rijmag3 = 1/Rijmag^3, and the formula needs /Rijmag^3,
        # so we multiply by inv_Rijmag3, not divide by it.
        # Also formula has / (rijmag * Rijmag^3).
        hg_coeff = (
            -0.5 * float(alpha) * float(Ehg)
            * W
            * (deltai + deltaj)
            * inv_Rijmag3
            / rijmag_safe
        )

        Fhg_edge = rij * hg_coeff[:, None]                    # (m,3)
        np.add.at(Fint, ei, Fhg_edge)
        np.add.at(Fint, ej, -Fhg_edge)

        # --- 4) External force ramp ---
        step_factor = float(ti) / denom_steps
        if step_factor > 1.0:
            step_factor = 1.0

        ext_force = float(block_load) * step_factor
        load_block_force = float(load_block_weight) * step_factor

        Fext = np.zeros((n, 3), dtype=float)
        Fext[:, 1] = ext_force

        if len(loaded_blocks) > 0:
            idx = np.asarray(list(loaded_blocks), dtype=int)
            idx = idx[(idx >= 0) & (idx < n)]
            if idx.size > 0:
                Fext[idx, 1] = load_block_force + ext_force

        # --- 5) Velocity-Verlet integration ---
        V += A * (float(dt) / 2.0)
        x += V * float(dt)

        # Acceleration: a = F/m; here m ~ rho*Vol and Vol=1
        A = (Fint + Fext) * (1.0 / float(rho))

        V += A * (float(dt) / 2.0)

        # --- 6) Enforce supports (Dirichlet) ---
        enforce_supports()

    # -----------------------------------------------------------------------------
    # Postprocess: compute Cauchy stress sigma and von Mises
    # -----------------------------------------------------------------------------
    sigma = np.zeros((n, 3, 3), dtype=float)
    vm = np.zeros((n,), dtype=float)

    for i in range(n):
        detF = float(np.linalg.det(F[i]))
        if not np.isfinite(detF) or abs(detF) < 1e-12:
            continue
        # Cauchy stress in the mod: sigma = (1/J) * P * F^T
        sigma[i] = (P[i] @ F[i].T) * (1.0 / detF)
        vm[i] = _von_mises_from_sigma(sigma[i])

    return vm
