# eval_code/stress.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np


# -----------------------------
# Public result type
# -----------------------------

@dataclass
class VonMisesResult:
    """Return object for compute_von_mises_stress()."""
    von_mises: np.ndarray          # (n,) in Pa
    sigma: np.ndarray              # (n,3,3) in Pa
    F: np.ndarray                  # (n,3,3)
    x: np.ndarray                  # (n,3) deformed positions
    meta: Dict[str, Any]


# -----------------------------
# Utilities: coords <-> arrays
# -----------------------------

def _coords_to_X(coords: Sequence[Dict[str, Any]]) -> np.ndarray:
    """Convert coords list to (n,3) float array."""
    X = np.zeros((len(coords), 3), dtype=float)
    for i, c in enumerate(coords):
        X[i, 0] = float(c["x"])
        X[i, 1] = float(c["y"])
        X[i, 2] = float(c["z"])
    return X


def _min_y_supports(X0: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """Indices of blocks with minimum y; used as fixed supports."""
    ymin = float(np.min(X0[:, 1]))
    return np.where(np.abs(X0[:, 1] - ymin) <= eps)[0].astype(int)


# -----------------------------
# Neighbor list (mod-style)
# -----------------------------

def _find_neighbors_reference(X0: np.ndarray, h: float) -> np.ndarray:
    """
    Build a symmetric boolean neighbor matrix using reference positions X0.
    Matches Java findNeighbors(): neighbor if distance < h_threshold.
    """
    n = X0.shape[0]
    neigh = np.zeros((n, n), dtype=bool)
    for i in range(n):
        for j in range(i + 1, n):
            d = np.linalg.norm(X0[i] - X0[j])
            if d < h:
                neigh[i, j] = True
                neigh[j, i] = True
    return neigh


# -----------------------------
# Kernel: W and gradW (mod-style)
# -----------------------------

def _eval_W(Rij: np.ndarray, h: float) -> float:
    """
    Java:
      W = (15/pi/h^6) * (h - |R|)^3
    Note: Java does not clamp for r>=h, but neighbor list ensures r<h.
    """
    r = float(np.linalg.norm(Rij))
    return (15.0 / (np.pi * (h ** 6))) * ((h - r) ** 3)


def _eval_gradW(Rij: np.ndarray, h: float, eps: float = 1e-12) -> np.ndarray:
    """
    Java:
      scale = -3 * (15/pi/h^6) * (h-r)^2 / r
      gradW = Rij * scale
    """
    r = float(np.linalg.norm(Rij))
    if r < eps:
        return np.zeros(3, dtype=float)
    scale = -3.0 * ((15.0 / (np.pi * (h ** 6))) * ((h - r) ** 2)) / r
    return Rij * scale


# -----------------------------
# Linear algebra helpers
# -----------------------------

def _safe_inv_3x3(A: np.ndarray, rcond: float = 1e-12) -> np.ndarray:
    """
    In Java, Matrix.inverse() is called directly.
    In Python, we fall back to pseudo-inverse if singular.
    """
    try:
        return np.linalg.inv(A)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(A, rcond=rcond)


# -----------------------------
# Mod-equivalent SPH routines
# -----------------------------

def _calculate_FAinv(
    i: int,
    X0: np.ndarray,
    x: np.ndarray,
    neigh: np.ndarray,
    h: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Equivalent of Java calculate_FAinv():
      F* = sum (rij ⊗ gradW(Rij))
      A  = sum (Rij ⊗ gradW(Rij))
      Ainv = inv(A)
      F = F* @ Ainv
    Returns (F, Ainv).
    """
    n = X0.shape[0]
    Xi = X0[i]
    xi = x[i]
    Fstar = np.zeros((3, 3), dtype=float)
    A = np.zeros((3, 3), dtype=float)

    for j in range(n):
        if not neigh[i, j]:
            continue
        Rij = X0[j] - Xi
        rij = x[j] - xi
        gradW = _eval_gradW(Rij, h)  # Volj=1
        # Outer product (vector * vector^T)
        Fstar += np.outer(rij, gradW)
        A += np.outer(Rij, gradW)

    Ainv = _safe_inv_3x3(A)
    F = Fstar @ Ainv
    return F, Ainv


def _calculate_P_stvk_with_viscosity(
    F: np.ndarray,
    Ft: np.ndarray,
    dt: float,
    young: float,
    nu: float,
    eta: float,
) -> np.ndarray:
    """
    Java calculate_P() for mat[0]==1 (StVK) with deviatoric viscosity term.

    - E = 0.5*(C - I), C = F^T F
    - S = lambda*tr(E)*I + 2*mu*E
    - Viscosity:
        Fdot = (F - Ft)/dt
        L = Fdot * inv(F)
        d = 0.5*(L + L^T)
        d' = d - (tr(d)/3) I
        P = F*S + d' * inv(F)^T * (2*J*eta)
    """
    I = np.eye(3)
    C = F.T @ F
    E = 0.5 * (C - I)
    trE = float(np.trace(E))
    J = float(np.linalg.det(F))

    lame_lam = young * nu / ((1.0 + nu) * (1.0 - nu))   # matches Java for mat[0]==1
    lame_mu = young / (2.0 * (1.0 + nu))

    S = lame_lam * trE * I + 2.0 * lame_mu * E

    # Viscosity part
    Fdot = (F - Ft) / dt
    Finv = _safe_inv_3x3(F)
    L = Fdot @ Finv
    d = 0.5 * (L + L.T)
    dprime = d - (np.trace(d) / 3.0) * I
    P = F @ S + (dprime @ Finv.T) * (2.0 * J * eta)

    return P


def _calculate_Fint_with_hourglass(
    i: int,
    X0: np.ndarray,
    x: np.ndarray,
    neigh: np.ndarray,
    PP_tilde: np.ndarray,  # stored as P @ Ainv (mod-style)
    F: np.ndarray,
    h: float,
    alpha: float,
    Ehg: float,
) -> np.ndarray:
    """
    Equivalent of Java calculate_Fint():
      Fint += (PP[i] + PP[j]) @ gradW(Rij) * (Voli*Volj)
      Fhg  += hourglass term

    Here Voli=Volj=1 (like Java code uses 1.0).
    """
    n = X0.shape[0]
    Xi = X0[i]
    xi = x[i]

    Fint = np.zeros(3, dtype=float)
    Fhg = np.zeros(3, dtype=float)

    for j in range(n):
        if not neigh[i, j]:
            continue

        Rij = X0[j] - Xi
        rij = x[j] - xi

        rijmag = float(np.linalg.norm(rij))
        Rijmag = float(np.linalg.norm(Rij))
        if rijmag <= 1e-12 or Rijmag <= 1e-12:
            continue

        gradW = _eval_gradW(Rij, h)

        # Internal force contribution (mod uses PP_tilde = P @ Ainv)
        Fint += (PP_tilde[i] + PP_tilde[j]) @ gradW  # Voli*Volj = 1

        # Hourglass control (copied from Java logic)
        rij_pred = F[i] @ Rij
        rji_pred = F[j] @ (-Rij)

        deltai = float(np.dot((rij_pred - rij), rij)) / rijmag
        deltaj = float(np.dot((rji_pred + rij), (-rij))) / rijmag

        W = _eval_W(Rij, h)
        coeff = -0.5 * alpha * Ehg * W * (deltai + deltaj) / (rijmag * (Rijmag ** 3))
        Fhg += rij * coeff

    return Fint + Fhg


def _von_mises_from_sigma(sigma: np.ndarray) -> float:
    """
    Java von Mises:
      sqrt((s11-s22)^2 + (s22-s33)^2 + (s33-s11)^2 + 6*(s23^2+s13^2+s12^2))/sqrt(2)
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


# -----------------------------
# Public API
# -----------------------------

def compute_von_mises_stress(
    coords: Sequence[Dict[str, Any]],
    *,
    h_threshold: float = 2.0,
    # Material (defaults match mod)
    young: float = 1e9,
    nu: float = 0.4,
    eta: float = 1e7,
    # Density and loads (defaults match mod)
    rho: float = 15000.0,
    dt: float = 1e-4,
    n_t_steps: int = 2000,
    loading_time_percent: float = 20.0,
    block_load: float = -900.0,
    load_block_weight: float = -900.0,
    # Stabilization (defaults match mod)
    alpha: float = 1.0,
    Ehg: float = 1e8,
    # Load blocks: if your coords don't include LoadBlock, keep empty
    loaded_blocks: Optional[Sequence[int]] = None,
    # Supports: fix all blocks at minimum y
    fix_min_y: bool = True,
    # Safety
    pinv_rcond: float = 1e-12,
) -> VonMisesResult:
    """
    Compute von Mises stress for Minecraft-like blocks using a mod-equivalent SPH solver.

    - Input: coords only (no deformed coords).
    - Output: von Mises stress for each block (length == len(coords)).

    This follows the Java SPHCodeProcedure logic:
      - neighbors from reference positions
      - velocity-verlet integration
      - PP stored as P @ Ainv
      - Fint includes hourglass control
      - sigma = (1/detF) * P * F^T (by converting PP back to P at the end)
    """
    if loaded_blocks is None:
        loaded_blocks = []

    X0 = _coords_to_X(coords)
    n = X0.shape[0]
    if n == 0:
        return VonMisesResult(
            von_mises=np.zeros((0,), dtype=float),
            sigma=np.zeros((0, 3, 3), dtype=float),
            F=np.zeros((0, 3, 3), dtype=float),
            x=np.zeros((0, 3), dtype=float),
            meta={"dt_used": dt, "steps": 0},
        )

    # Neighbor list built once on reference coords (mod behavior)
    neigh = _find_neighbors_reference(X0, h_threshold)

    # Supports: fix all blocks at minimum y (requested behavior)
    supports = _min_y_supports(X0) if fix_min_y else np.zeros((0,), dtype=int)

    # State initialization (mod behavior)
    x = X0.copy()
    V = np.zeros((n, 3), dtype=float)
    A = np.zeros((n, 3), dtype=float)

    # Per-particle tensors
    F = np.tile(np.eye(3)[None, :, :], (n, 1, 1)).copy()
    Ft_prev = F.copy()
    Ainv = np.tile(np.eye(3)[None, :, :], (n, 1, 1)).copy()
    PP_tilde = np.zeros((n, 3, 3), dtype=float)  # stores P @ Ainv

    def _enforce_supports():
        if supports.size == 0:
            return
        x[supports] = X0[supports]
        V[supports] = 0.0
        A[supports] = 0.0

    # Main timestep loop (mod structure)
    denom_steps = (loading_time_percent / 100.0) * float(n_t_steps)
    denom_steps = max(denom_steps, 1.0)

    for ti in range(int(n_t_steps)):
        # 1) Compute F and Ainv, then P, then store PP_tilde = P @ Ainv
        Ft_prev = F.copy()
        for i in range(n):
            Fi, Ainv_i = _calculate_FAinv(i, X0, x, neigh, h_threshold)
            # Use pseudo-inverse fallback settings if needed
            # (override _safe_inv_3x3 behavior by re-inverting here if you want)
            Ainv[i] = Ainv_i
            F[i] = Fi

        for i in range(n):
            Pi = _calculate_P_stvk_with_viscosity(F[i], Ft_prev[i], dt, young, nu, eta)
            PP_tilde[i] = Pi @ Ainv[i]  # mod does P = P.dot(Ainv)

        # 2) Compute internal forces (including hourglass)
        Fint = np.zeros((n, 3), dtype=float)
        for i in range(n):
            Fint[i] = _calculate_Fint_with_hourglass(
                i, X0, x, neigh, PP_tilde, F,
                h_threshold, alpha, Ehg
            )

        # 3) Force stepping (load ramp-up)
        step_factor = float(ti) / denom_steps
        if step_factor > 1.0:
            step_factor = 1.0

        ext_force = block_load * step_factor
        load_block_force = load_block_weight * step_factor

        Fext = np.zeros((n, 3), dtype=float)
        Fext[:, 1] = ext_force
        if len(loaded_blocks) > 0:
            idx = np.asarray(list(loaded_blocks), dtype=int)
            idx = idx[(idx >= 0) & (idx < n)]
            Fext[idx, 1] = (load_block_force + ext_force)

        # 4) Velocity-Verlet update (mod)
        V += A * (dt / 2.0)
        x += V * dt
        # Update acceleration from forces (mass = rho*Vol, Vol=1)
        A = (Fint + Fext) * (1.0 / rho)
        V += A * (dt / 2.0)

        # 5) Enforce supports (requested: min_y fixed)
        _enforce_supports()

    # Postprocess: sigma and von Mises (mod does P_correct = PP * inv(Ainv) = P)
    sigma = np.zeros((n, 3, 3), dtype=float)
    vm = np.zeros((n,), dtype=float)

    for i in range(n):
        detF = float(np.linalg.det(F[i]))
        if not np.isfinite(detF) or abs(detF) < 1e-12:
            continue

        # Recover P from stored PP_tilde: P = (P*Ainv) * inv(Ainv) = P
        A_i = _safe_inv_3x3(Ainv[i], rcond=pinv_rcond)  # equals inverse(Ainv) in ideal case
        P_correct = PP_tilde[i] @ A_i

        sigma[i] = (P_correct @ F[i].T) * (1.0 / detF)
        vm[i] = _von_mises_from_sigma(sigma[i])

    meta = {
        "dt_used": dt,
        "steps": int(n_t_steps),
        "supports_count": int(supports.size),
        "neighbors_avg": float(np.sum(neigh) / max(n, 1)),
        "step_factor_final": min(1.0, float(int(n_t_steps) - 1) / denom_steps),
    }

    return VonMisesResult(von_mises=vm, sigma=sigma, F=F, x=x, meta=meta)
