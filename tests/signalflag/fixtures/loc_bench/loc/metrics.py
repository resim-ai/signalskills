"""ATE (after rigid 2D alignment) and RPE (1 s segments), both RMSE in metres."""
import numpy as np

def _align(gt: np.ndarray, est: np.ndarray) -> np.ndarray:
    mg, me = gt.mean(0), est.mean(0)
    u, _, vt = np.linalg.svd((est - me).T @ (gt - mg))
    r = (u @ vt).T
    if np.linalg.det(r) < 0:
        vt[-1] *= -1
        r = (u @ vt).T
    return (est - me) @ r.T + mg

def ate_rmse(gt, est) -> float:
    g, e = gt[:, 1:3], _align(gt[:, 1:3], est[:, 1:3])
    return float(np.sqrt(np.mean(np.sum((g - e) ** 2, axis=1))))

def rpe_rmse(gt, est, delta_s: float = 1.0) -> float:
    dt = np.median(np.diff(gt[:, 0]))
    k = max(1, int(round(delta_s / dt)))
    dg = gt[k:, 1:3] - gt[:-k, 1:3]
    de = est[k:, 1:3] - est[:-k, 1:3]
    return float(np.sqrt(np.mean(np.sum((dg - de) ** 2, axis=1))))
