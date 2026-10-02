"""Wheel odometry dead-reckoning, corrected by scan-match poses (complementary filter)."""
import numpy as np

GAIN = 0.12  # weight of a scan-match correction

def run(odom: np.ndarray, scans: np.ndarray, out_t: np.ndarray):
    """odom: t, v, w (20 Hz). scans: t, x, y, yaw (2 Hz). Returns x, y, yaw at out_t."""
    x = y = yaw = 0.0
    si, xs, ys, yaws, oi = 0, [], [], [], 0
    for k in range(len(odom) - 1):
        t, v, w = odom[k]
        dt = odom[k + 1, 0] - t
        x += v * np.cos(yaw) * dt
        y += v * np.sin(yaw) * dt
        yaw += w * dt
        while si < len(scans) and scans[si, 0] <= odom[k + 1, 0] + 1e-9:
            _, sx, sy, syaw = scans[si]
            x += GAIN * (sx - x)
            y += GAIN * (sy - y)
            yaw += GAIN * np.arctan2(np.sin(syaw - yaw), np.cos(syaw - yaw))
            si += 1
        while oi < len(out_t) and out_t[oi] <= odom[k + 1, 0] + 1e-9:
            xs.append(x); ys.append(y); yaws.append(yaw); oi += 1
    while oi < len(out_t):
        xs.append(x); ys.append(y); yaws.append(yaw); oi += 1
    return np.array(xs), np.array(ys), np.array(yaws)
