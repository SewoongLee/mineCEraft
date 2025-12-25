# eval_code/stress.py
"""
Compute von Mises stress for Minecraft-like block structures using a mod-equivalent
SPH/meshfree solid solver (ported from Minecraft SPH V8).
References:
- https://arxiv.org/pdf/2212.08124
- https://github.com/abuganza/minecraft_sph

Key design choices (matching the original Java mod behavior):
- Input is ONLY the initial block coordinates (no deformed coords are provided).
- The solver internally runs a timestep simulation to obtain deformed positions.
- Neighbors are built ONCE from reference coordinates using a cutoff radius h_threshold.
- Deformation gradient is computed with the correction matrix Ainv:
    F = (Σ (rij ⊗ ∇W(Rij))) * Ainv
- First Piola stress P is computed with St. Venant–Kirchhoff (StVK) + deviatoric viscosity.
- The code stores PP_tilde = P * Ainv (exactly like the Java mod),
  and uses PP_tilde for internal force accumulation.
- Internal force includes hourglass stabilization term (alpha, Ehg) from the mod.
- Supports are enforced by fixing all blocks at minimum y (requested behavior).
- External loading is applied as a per-particle force in the y direction, ramped
  over loading_time_percent of the total steps (mod behavior).

Optional:
- progress=True will display a tqdm progress bar if tqdm is installed.

Dependencies:
- numpy (required)
- tqdm (optional, only if progress=True)
"""

# Material / physical parameters used in this solver:
# - young (E) [Pa]: Young's modulus, controls elastic stiffness (higher => stiffer).
# - nu (ν) [-]: Poisson's ratio, controls lateral contraction (0~0.49 typical for 3D solids).
# - eta (η) [Pa·s-ish]: deviatoric viscosity coefficient (higher => more damping / less vibration).
# - rho (ρ) [kg/m^3]: density; each block mass is approximated by m = rho * Vol (Vol=1 here).
#   Larger rho => smaller acceleration for the same force (more inertia, often more stable).
# - alpha [-]: hourglass strength factor (numerical stabilization).
# - Ehg [Pa]: hourglass "stiffness" scale (numerical stabilization).
#
# Simulation / loading parameters:
# - dt [s]: time step size (explicit integration; too large => instability).
# - n_t_steps [-]: number of time steps (total simulated time ~ dt * n_t_steps).
# - loading_time_percent [%]: ramp-up duration for external load to avoid sudden shock.
# - block_load / load_block_weight [N]: per-block external force applied in -y direction.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np


# -----------------------------------------------------------------------------
# Public result type
# -----------------------------------------------------------------------------

@dataclass
class VonMisesResult:
    """
    Result of compute_von_mises_stress().

    Attributes
    ----------
    von_mises : (n,) ndarray
        von Mises stress per block in Pa.
    sigma : (n,3,3) ndarray
        Cauchy stress tensor per block in Pa.
    F : (n,3,3) ndarray
        Deformation gradient per block at the final step.
    x : (n,3) ndarray
        Deformed coordinates at the final step.
    meta : dict
        Useful debug information (dt_used, steps, supports_count, etc.).
    """
    von_mises: np.ndarray
    sigma: np.ndarray
    F: np.ndarray
    x: np.ndarray
    meta: Dict[str, Any]


# -----------------------------------------------------------------------------
# Basic utilities: coords -> arrays
# -----------------------------------------------------------------------------

def _coords_to_X(coords: Sequence[Dict[str, Any]]) -> np.ndarray:
    """Convert coords list of dicts to an (n,3) float array X0."""
    X0 = np.zeros((len(coords), 3), dtype=float)
    for i, c in enumerate(coords):
        X0[i, 0] = float(c["x"])
        X0[i, 1] = float(c["y"])
        X0[i, 2] = float(c["z"])
    return X0


def _min_y_supports(X0: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """Return indices of blocks with minimum y (fixed supports)."""
    ymin = float(np.min(X0[:, 1]))
    return np.where(np.abs(X0[:, 1] - ymin) <= eps)[0].astype(int)


# -----------------------------------------------------------------------------
# Neighbor building (reference-based, built once)
# -----------------------------------------------------------------------------

def build_neighbors(
    X0: np.ndarray,
    h_threshold: float,
    *,
    max_neighbors: Optional[int] = None,
) -> List[np.ndarray]:
    """
    Build a neighbor list for each particle using reference coordinates X0.

    This is equivalent in *meaning* to the Java boolean Neighbor_list matrix:
      neighbor(i,j) = (||Xi - Xj|| < h_threshold)

    We store the result as adjacency lists to avoid scanning all j each timestep.

    Parameters
    ----------
    X0 : (n,3) ndarray
        Reference coordinates.
    h_threshold : float
        Cutoff radius for neighbors.
    max_neighbors : int or None
        If provided, cap neighbors per particle by keeping the closest ones.

    Returns
    -------
    neighbors : list of (k_i,) ndarrays
        neighbors[i] is an array of neighbor indices for particle i.
    """
    n = X0.shape[0]
    neighbors: List[List[int]] = [[] for _ in range(n)]

    # O(n^2) build. For large n, a spatial hash/grid would be better.
    for i in range(n):
        Xi = X0[i]
        for j in range(i + 1, n):
            d = float(np.linalg.norm(Xi - X0[j]))
            if d < h_threshold:
                neighbors[i].append(j)
                neighbors[j].append(i)

    if max_neighbors is not None:
        # Keep the closest max_neighbors for each i.
        # This preserves the "radius-based" candidate set first, then caps by distance.
        max_neighbors = int(max_neighbors)
        for i in range(n):
            if len(neighbors[i]) <= max_neighbors:
                continue
            Xi = X0[i]
            js = np.asarray(neighbors[i], dtype=int)
            ds = np.linalg.norm(X0[js] - Xi[None, :], axis=1)
            keep = js[np.argsort(ds)[:max_neighbors]]
            neighbors[i] = keep.tolist()

    return [np.asarray(neighbors[i], dtype=int) for i in range(n)]


# -----------------------------------------------------------------------------
# SPH kernel W and gradW (ported from Java)
# -----------------------------------------------------------------------------

def _eval_W(Rij: np.ndarray, h: float) -> float:
    """
    Java:
      W(R) = (15/pi/h^6) * (h - |R|)^3
    """
    r = float(np.linalg.norm(Rij))
    return (15.0 / (np.pi * (h ** 6))) * ((h - r) ** 3)


def _eval_gradW(Rij: np.ndarray, h: float, eps: float = 1e-12) -> np.ndarray:
    """
    Java:
      scale = -3 * (15/pi/h^6) * (h - r)^2 / r
      gradW = Rij * scale
    """
    r = float(np.linalg.norm(Rij))
    if r < eps:
        return np.zeros(3, dtype=float)
    scale = -3.0 * ((15.0 / (np.pi * (h ** 6))) * ((h - r) ** 2)) / r
    return Rij * scale


# -----------------------------------------------------------------------------
# Linear algebra helpers
# -----------------------------------------------------------------------------

def _safe_inv_3x3(A: np.ndarray, rcond: float = 1e-12) -> np.ndarray:
    """
    Java directly inverts A.
    Here we fall back to pseudo-inverse if singular/ill-conditioned.
    """
    try:
        return np.linalg.inv(A)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(A, rcond=rcond)


# -----------------------------------------------------------------------------
# Mod-equivalent SPH routines
# -----------------------------------------------------------------------------

def _calculate_FAinv(
    i: int,
    X0: np.ndarray,
    x: np.ndarray,
    neighbors: List[np.ndarray],
    h: float,
    pinv_rcond: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Equivalent to Java calculate_FAinv(pi,...):

      F* = Σ_j (rij ⊗ ∇W(Rij))
      A  = Σ_j (Rij ⊗ ∇W(Rij))
      Ainv = inv(A)
      F = F* @ Ainv

    Returns (F, Ainv).
    """
    Xi = X0[i]
    xi = x[i]

    Fstar = np.zeros((3, 3), dtype=float)
    A = np.zeros((3, 3), dtype=float)

    for j in neighbors[i]:
        Rij = X0[j] - Xi
        rij = x[j] - xi
        gradW = _eval_gradW(Rij, h)  # Vol_j = 1 in the mod
        Fstar += np.outer(rij, gradW)
        A += np.outer(Rij, gradW)

    Ainv = _safe_inv_3x3(A, rcond=pinv_rcond)
    F = Fstar @ Ainv
    return F, Ainv


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
    Port of Java calculate_P() for mat[0] == 1 (StVK + deviatoric viscosity):

    C = F^T F
    E = 0.5 (C - I)
    S = lambda*tr(E)*I + 2*mu*E

    Viscosity:
      Fdot = (F - Ft)/dt
      L = Fdot * inv(F)
      d = 0.5(L + L^T)
      d' = d - (tr(d)/3) I
      P = F*S + d' * inv(F)^T * (2*J*eta)

    Note: if eta == 0, the viscosity term becomes zero.
    """
    I = np.eye(3)
    C = F.T @ F
    E = 0.5 * (C - I)
    trE = float(np.trace(E))
    J = float(np.linalg.det(F))

    # Same formulas as the mod for mat[0] == 1
    lame_lam = young * nu / ((1.0 + nu) * (1.0 - nu))
    lame_mu = young / (2.0 * (1.0 + nu))

    S = lame_lam * trE * I + 2.0 * lame_mu * E

    # Deviatoric viscosity term
    Fdot = (F - Ft) / dt
    Finv = _safe_inv_3x3(F, rcond=pinv_rcond)
    L = Fdot @ Finv
    d = 0.5 * (L + L.T)
    dprime = d - (np.trace(d) / 3.0) * I

    P = F @ S + (dprime @ Finv.T) * (2.0 * J * eta)
    return P


def _calculate_Fint_with_hourglass(
    i: int,
    X0: np.ndarray,
    x: np.ndarray,
    neighbors: List[np.ndarray],
    PP_tilde: np.ndarray,   # stored as P @ Ainv, like the mod
    F_all: np.ndarray,
    h: float,
    alpha: float,
    Ehg: float,
) -> np.ndarray:
    """
    Port of Java calculate_Fint():

      Fint += (PP_tilde[i] + PP_tilde[j]) @ gradW(Rij) * (Voli*Volj)
      Fhg  += hourglass stabilization term

    The mod uses Vol_i = Vol_j = 1.
    """
    Xi = X0[i]
    xi = x[i]

    Fint = np.zeros(3, dtype=float)
    Fhg = np.zeros(3, dtype=float)

    for j in neighbors[i]:
        Rij = X0[j] - Xi
        rij = x[j] - xi

        rijmag = float(np.linalg.norm(rij))
        Rijmag = float(np.linalg.norm(Rij))
        if rijmag <= 1e-12 or Rijmag <= 1e-12:
            continue

        gradW = _eval_gradW(Rij, h)

        # Internal force contribution (mod uses PP_tilde directly)
        Fint += (PP_tilde[i] + PP_tilde[j]) @ gradW

        # Hourglass control (exact mod logic)
        rij_pred = F_all[i] @ Rij
        rji_pred = F_all[j] @ (-Rij)

        deltai = float(np.dot((rij_pred - rij), rij)) / rijmag
        deltaj = float(np.dot((rji_pred + rij), (-rij))) / rijmag

        W = _eval_W(Rij, h)
        coeff = -0.5 * alpha * Ehg * W * (deltai + deltaj) / (rijmag * (Rijmag ** 3))
        Fhg += rij * coeff

    return Fint + Fhg


def _von_mises_from_sigma(sigma: np.ndarray) -> float:
    """
    Same von Mises formula used in the Java mod:

      vm = sqrt(
            (s11-s22)^2 + (s22-s33)^2 + (s33-s11)^2
            + 6*(s23^2 + s13^2 + s12^2)
          ) / sqrt(2)
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


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def compute_von_mises_stress(
    coords: Sequence[Dict[str, Any]],
    *,
    # Neighbor cutoff (main control of interaction range)
    h_threshold: float = 2.0,
    max_neighbors: Optional[int] = None,
    # Material model (defaults match the mod)
    young: float = 1e9,
    nu: float = 0.4,
    eta: float = 0,
    # Mass/density and integration (defaults match typical "1999 step" runs)
    rho: float = 15000.0,          # [kg/m^3], used as mass density (mass = rho*Vol; Vol=1)
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
) -> VonMisesResult:
    """
    Run a mod-equivalent SPH simulation and return per-block von Mises stress.

    Parameters
    ----------
    coords : list[dict]
        Each dict has keys {"x","y","z"} and optional {"material"}.
        Only x,y,z are used here.
    h_threshold : float
        Neighbor cutoff radius (kernel support).
    max_neighbors : int or None
        Optional cap on neighbors per block (closest kept within cutoff).
    young, nu : float
        Young's modulus and Poisson ratio (StVK).
    eta : float
        Viscosity coefficient. Set eta=0.0 for purely elastic.
    rho : float
        Density used as mass = rho*Vol. Vol is assumed 1 for each block.
    dt : float
        Time step size (seconds in mod printout style).
    n_t_steps : int
        Number of steps. If 2000, the last index is 1999.
    loading_time_percent : float
        Ramp duration as percent of total steps, matching the mod:
          step_factor = ti / (loading_time_percent/100 * n_t_steps)
    block_load, load_block_weight : float
        Forces in the y direction applied to each block (and extra load blocks).
    loaded_blocks : sequence[int] or None
        Indices of blocks treated as "LoadBlock" blocks.
    alpha, Ehg : float
        Hourglass stabilization parameters (ported from the mod).
    fix_min_y : bool
        If True, blocks at minimum y are fixed each step.
    progress : bool
        If True and tqdm is installed, show a progress bar.

    Returns
    -------
    VonMisesResult
        Contains von_mises array of length len(coords), plus sigma, F, x, meta.
    """
    if loaded_blocks is None:
        loaded_blocks = []

    X0 = _coords_to_X(coords)
    n = int(X0.shape[0])

    # Handle empty input early.
    if n == 0:
        return VonMisesResult(
            von_mises=np.zeros((0,), dtype=float),
            sigma=np.zeros((0, 3, 3), dtype=float),
            F=np.zeros((0, 3, 3), dtype=float),
            x=np.zeros((0, 3), dtype=float),
            meta={"dt_used": float(dt), "steps": 0, "supports_count": 0},
        )

    # Neighbor list is built once from reference coordinates (mod behavior).
    neighbors = build_neighbors(X0, float(h_threshold), max_neighbors=max_neighbors)

    # Supports are enforced each step by snapping x back to X0 for min-y blocks.
    supports = _min_y_supports(X0) if fix_min_y else np.zeros((0,), dtype=int)

    # State initialization (mod behavior).
    x = X0.copy()                          # current positions
    V = np.zeros((n, 3), dtype=float)      # velocity
    A = np.zeros((n, 3), dtype=float)      # acceleration

    # Per-particle tensors.
    F = np.tile(np.eye(3)[None, :, :], (n, 1, 1)).copy()
    Ft_prev = F.copy()
    Ainv = np.tile(np.eye(3)[None, :, :], (n, 1, 1)).copy()
    PP_tilde = np.zeros((n, 3, 3), dtype=float)  # stores P @ Ainv, like the mod

    # Helper to enforce fixed supports robustly.
    def enforce_supports() -> None:
        if supports.size == 0:
            return
        x[supports] = X0[supports]
        V[supports] = 0.0
        A[supports] = 0.0

    # Precompute ramp denominator (exact mod pattern).
    denom_steps = (float(loading_time_percent) / 100.0) * float(n_t_steps)
    denom_steps = max(denom_steps, 1.0)

    # Optional tqdm progress bar.
    if progress:
        try:
            from tqdm.auto import tqdm  # type: ignore
            step_iter: Iterable[int] = tqdm(range(int(n_t_steps)), desc="SPH steps")
        except Exception:
            step_iter = range(int(n_t_steps))
    else:
        step_iter = range(int(n_t_steps))

    # -----------------------------------------------------------------------------
    # Main timestep loop (ported structure)
    # -----------------------------------------------------------------------------
    for ti in step_iter:
        # Keep previous deformation gradient for the viscosity term.
        Ft_prev = F.copy()

        # 1) Compute F and Ainv for all particles.
        for i in range(n):
            Fi, Ainv_i = _calculate_FAinv(i, X0, x, neighbors, float(h_threshold), float(pinv_rcond))
            F[i] = Fi
            Ainv[i] = Ainv_i

        # 2) Compute P (StVK + viscosity), then store PP_tilde = P @ Ainv (mod behavior).
        for i in range(n):
            Pi = _calculate_P_stvk_with_viscosity(
                F[i], Ft_prev[i], float(dt), float(young), float(nu), float(eta), float(pinv_rcond)
            )
            PP_tilde[i] = Pi @ Ainv[i]

        # 3) Compute internal forces (including hourglass control).
        Fint = np.zeros((n, 3), dtype=float)
        for i in range(n):
            Fint[i] = _calculate_Fint_with_hourglass(
                i, X0, x, neighbors, PP_tilde, F, float(h_threshold), float(alpha), float(Ehg)
            )

        # 4) External loading ramp (mod behavior).
        step_factor = float(ti) / denom_steps
        if step_factor > 1.0:
            step_factor = 1.0

        ext_force = float(block_load) * step_factor
        load_block_force = float(load_block_weight) * step_factor

        # Force vector in y direction.
        Fext = np.zeros((n, 3), dtype=float)
        Fext[:, 1] = ext_force

        if len(loaded_blocks) > 0:
            idx = np.asarray(list(loaded_blocks), dtype=int)
            idx = idx[(idx >= 0) & (idx < n)]
            if idx.size > 0:
                Fext[idx, 1] = load_block_force + ext_force

        # 5) Velocity-Verlet integration (exact mod style).
        V += A * (float(dt) / 2.0)
        x += V * float(dt)

        # Acceleration from total force. Mod uses mass = rho*Vol, with Vol=1.
        A = (Fint + Fext) * (1.0 / float(rho))

        V += A * (float(dt) / 2.0)

        # 6) Enforce supports.
        enforce_supports()

    # -----------------------------------------------------------------------------
    # Postprocess: compute Cauchy stress sigma and von Mises (mod behavior)
    # -----------------------------------------------------------------------------
    sigma = np.zeros((n, 3, 3), dtype=float)
    vm = np.zeros((n,), dtype=float)

    for i in range(n):
        detF = float(np.linalg.det(F[i]))
        if not np.isfinite(detF) or abs(detF) < 1e-12:
            # Singular/invalid deformation gradient => leave zero stress.
            continue

        # In the mod:
        #   PP_tilde = P @ Ainv
        #   P_correct = PP_tilde @ inv(Ainv) = P
        A_i = _safe_inv_3x3(Ainv[i], rcond=float(pinv_rcond))  # approximates inverse(Ainv)
        P_correct = PP_tilde[i] @ A_i

        # Cauchy stress: sigma = (1/J) * P * F^T
        sigma[i] = (P_correct @ F[i].T) * (1.0 / detF)
        vm[i] = _von_mises_from_sigma(sigma[i])

    # Some useful debug stats.
    neighbor_counts = np.array([len(neighbors[i]) for i in range(n)], dtype=int)
    meta: Dict[str, Any] = {
        "dt_used": float(dt),
        "steps": int(n_t_steps),
        "supports_count": int(supports.size),
        "neighbors_min": int(neighbor_counts.min()) if n > 0 else 0,
        "neighbors_max": int(neighbor_counts.max()) if n > 0 else 0,
        "neighbors_avg": float(neighbor_counts.mean()) if n > 0 else 0.0,
    }

    return VonMisesResult(von_mises=vm, sigma=sigma, F=F, x=x, meta=meta)
