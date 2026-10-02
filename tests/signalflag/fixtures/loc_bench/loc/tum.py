import numpy as np

def read_tum(path) -> np.ndarray:
    """-> (n, 8): t x y z qx qy qz qw"""
    return np.loadtxt(path, comments="#", ndmin=2)

def write_tum(path, t, x, y, yaw) -> None:
    z = np.zeros_like(x)
    rows = np.column_stack([t, x, y, z, z, z, np.sin(yaw / 2), np.cos(yaw / 2)])
    np.savetxt(path, rows, fmt=["%.3f"] + ["%.5f"] * 7, header="timestamp tx ty tz qx qy qz qw")
