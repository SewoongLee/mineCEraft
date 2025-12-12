# eval_code/stress.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class StressResult:
    # (n,) von Mises stress (Pa)
    von_mises: np.ndarray
    # (n, 3, 3) Cauchy stress tensor sigma (Pa)
    sigma: np.ndarray
    # (n, 3, 3) deformation gradient F
    F: np.ndarray


def _as_xyz_array(blocks: Sequence[dict]) -> np.ndarray:
    return np.asarray([[b["x"], b["y"], b["z"]] for b in blocks], dtype=float)


def _neighbor_mask(X: np.ndarray, h: float) -> np.ndarray:
    """Return (n,n) boolean neighbor mask, excluding i==j."""
    diff = X[:, None, :] - X[None, :, :]
    dist = np.linalg.norm(diff, axis=2)
    neigh = (dist < h) & (~np.eye(X.shape[0], dtype=bool))
    return neigh


def _gradW(Rij: np.ndarray, h: float, eps: float = 1e-12) -> np.ndarray:
    """
    Gradient of W(r) = 15/(pi*h^6) * (h - r)^3 for r<h, else 0.
    gradW = dW/dr * Rij/r, where dW/dr = -45/(pi*h^6) * (h - r)^2
    """
    r = np.linalg.norm(Rij)
    if r >= h or r < eps:
        return np.zeros(3, dtype=float)
    c = 15.0 / (np.pi * (h**6))
    dWdr = -3.0 * c * ((h - r) ** 2)  # -45/(pi*h^6) * (h-r)^2
    return dWdr * (Rij / r)


def _safe_inv(A: np.ndarray, rcond: float = 1e-12) -> np.ndarray:
    """Use inverse if well-conditioned; otherwise pseudoinverse."""
    try:
        return np.linalg.inv(A)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(A, rcond=rcond)


def compute_von_mises_stress(
    coords: Sequence[dict],
    *,
    deformed_coords: Optional[Sequence[dict]] = None,
    h_threshold: float = 2.0,
    young: float = 1e9,
    nu: float = 0.4,
    eta: float = 0.0,
    dt: float = 1.0,
    use_code_lame_lambda: bool = True,
) -> StressResult:
    """
    Compute per-block Cauchy stress and von Mises stress.

    - coords: reference positions X (list of {"x","y","z","material"})
    - deformed_coords: current positions x (same format). If None, uses coords.
    - eta, dt: damping term params (set eta=0 for purely elastic/static stress)
    - use_code_lame_lambda:
        True  -> lambda = E*nu/((1+nu)*(1-nu))  (matches the referenced Java mod code)
        False -> lambda = E*nu/((1+nu)*(1-2nu)) (standard 3D isotropic)
    """
    X = _as_xyz_array(coords)
    x = _as_xyz_array(deformed_coords) if deformed_coords is not None else X.copy()
    n = X.shape[0]
    if n == 0:
        return StressResult(von_mises=np.zeros((0,)), sigma=np.zeros((0, 3, 3)), F=np.zeros((0, 3, 3)))

    neigh = _neighbor_mask(X, h_threshold)

    # 1) compute F and Ainv per particle (Ainv used for corrected gradients)
    F = np.zeros((n, 3, 3), dtype=float)
    Ainv = np.zeros((n, 3, 3), dtype=float)

    for i in range(n):
        Fi = np.zeros((3, 3), dtype=float)
        Ai = np.zeros((3, 3), dtype=float)
        Xi = X[i]
        xi = x[i]
        for j in range(n):
            if not neigh[i, j]:
                continue
            Rij = X[j] - Xi
            rij = x[j] - xi
            gw = _gradW(Rij, h_threshold)  # (3,)
            # outer products: rij ⊗ gw  == rij[:,None] * gw[None,:]
            Fi += np.outer(rij, gw)
            Ai += np.outer(Rij, gw)

        Ainv_i = _safe_inv(Ai)
        F[i] = Fi @ Ainv_i
        Ainv[i] = Ainv_i

    # 2) compute 1st Piola stress P (St. Venant–Kirchhoff + optional damping)
    P = np.zeros((n, 3, 3), dtype=float)
    I = np.eye(3)

    mu = young / (2.0 * (1.0 + nu))
    if use_code_lame_lambda:
        lam = young * nu / ((1.0 + nu) * (1.0 - nu))
    else:
        lam = young * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))

    # For pure "one-shot" stress from given deformation, we can treat Ft=F (=> Fdot=0)
    Ft = F.copy()

    for i in range(n):
        Fi = F[i]
        C = Fi.T @ Fi
        Cinv = _safe_inv(C)
        E = 0.5 * (C - I)
        trE = np.trace(E)

        S = lam * trE * I + 2.0 * mu * E

        # damping term (optional)
        J = np.linalg.det(Fi) if np.isfinite(np.linalg.det(Fi)) else 1.0
        if eta != 0.0:
            Fdot = (Fi - Ft[i]) / dt
            Finv = _safe_inv(Fi)
            L = Fdot @ Finv
            d = 0.5 * (L + L.T)
            # isochoric part
            dprime = d - (np.trace(d) / 3.0) * I
            P[i] = Fi @ S + (dprime @ Finv.T) * (2.0 * J * eta)
        else:
            P[i] = Fi @ S

    # 3) Convert to Cauchy stress sigma (same mapping used for von Mises visualization):
    # sigma = (1/detF) * (P_correct * F^T), where P_correct = P * A (A = inv(Ainv))
    sigma = np.zeros((n, 3, 3), dtype=float)
    for i in range(n):
        detF = np.linalg.det(F[i])
        if not np.isfinite(detF) or abs(detF) < 1e-12:
            continue
        A = _safe_inv(Ainv[i])
        P_correct = P[i] @ A
        sigma[i] = (P_correct @ F[i].T) * (1.0 / detF)

    # 4) von Mises from sigma
    vm = np.zeros((n,), dtype=float)
    for i in range(n):
        s = sigma[i]
        vm[i] = (
            np.sqrt(
                (s[0, 0] - s[1, 1]) ** 2
                + (s[1, 1] - s[2, 2]) ** 2
                + (s[2, 2] - s[0, 0]) ** 2
                + 6.0 * (s[1, 2] ** 2 + s[0, 2] ** 2 + s[0, 1] ** 2)
            )
            / np.sqrt(2.0)
        )

    return StressResult(von_mises=vm, sigma=sigma, F=F)
