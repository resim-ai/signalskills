"""Diff-drive robot driving along +x next to a wall at y = 0, optional obstacles ahead."""
from dataclasses import dataclass
import numpy as np
from minisim.bus import Bus

@dataclass
class Obstacle:
    name: str
    x: float
    y: float
    radius: float

class Sim:
    DT = 0.02
    WALL_SENSOR_RANGE_M = 1.0
    OBSTACLE_RATE_HZ = 10

    def __init__(self, bus: Bus, wall_offset: float | None = None, obstacles=(), speed=0.6, seed=0):
        self.bus, self.offset, self.obstacles, self.speed = bus, wall_offset, list(obstacles), speed
        self.rng = np.random.default_rng(seed)
        self.t, self.x, self.y, self.yaw, self.v, self.w = 0.0, 0.0, 0.5 if wall_offset is None else 0.5, 0.0, 0.0, 0.0
        self.k = 0

    def _wall_range(self):
        r = self.y / max(np.cos(self.yaw), 0.2) + self.rng.normal(0, 0.01)
        return r if r < self.WALL_SENSOR_RANGE_M else None

    def step(self):
        target_v = self.speed
        for ob in self.obstacles:
            d = ob.x - self.x - ob.radius - 0.25
            if d < 1.5 and abs(ob.y - self.y) < ob.radius + 0.35:
                target_v = min(target_v, max(0.0, 0.5 * (d - 0.25)))
        self.v += np.clip(target_v - self.v, -1.2 * self.DT, 0.8 * self.DT)
        if self.offset is not None:
            r = self._wall_range()
            self.w = 0.0 if r is None else float(np.clip(2.0 * (self.offset - r) - 1.5 * self.yaw, -1, 1))
        self.yaw += self.w * self.DT
        self.x += self.v * np.cos(self.yaw) * self.DT
        self.y += self.v * np.sin(self.yaw) * self.DT
        self.t = round(self.t + self.DT, 6)
        self.k += 1
        ns = int(round(self.t * 1e9))
        self.bus.publish("clock", ns, {"sim_time_s": self.t, "wall_time_s": round(self.t * 1.02, 4), "rtf": 0.98})
        self.bus.publish("odometry", ns, {"x": round(self.x, 4), "y": round(self.y, 4), "yaw": round(self.yaw, 4),
                                          "vx": round(self.v, 4), "wz": round(self.w, 4)})
        if self.obstacles and self.k % int(1 / (self.DT * self.OBSTACLE_RATE_HZ)) == 0:
            for ob in self.obstacles:
                d = float(np.hypot(ob.x - self.x, ob.y - self.y) - ob.radius)
                self.bus.publish("obstacle_state", ns, {"obstacle_id": ob.name, "distance_m": round(d, 4),
                                                        "relative_speed_mps": round(-self.v, 4),
                                                        "in_path": bool(abs(ob.y - self.y) < ob.radius + 0.35)})

    def run(self, seconds: float):
        for _ in range(int(round(seconds / self.DT))):
            self.step()
