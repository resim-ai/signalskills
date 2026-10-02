"""Plant model of the MC4 + bench motor, same interface as SerialController."""
import numpy as np

class SimController:
    DT = 0.002
    def __init__(self, firmware: str = "2.7.1", seed: int = 0):
        self.fw, self.t, self.v, self.i, self.cmd, self.ilim, self.locked = firmware, 0.0, 0.0, 0.0, 0.0, 6.0, False
        self.rng = np.random.default_rng(seed)
        self.stall_t = None

    def identify(self) -> dict:
        return {"model": "MC4", "serial": "MC4-SIM", "firmware": self.fw, "hw_rev": "C", "bootloader": "1.3.0"}

    def set_velocity(self, rpm): self.cmd = rpm
    def set_current_limit(self, amps): self.ilim = amps
    def lock_rotor(self, locked): self.locked, self.stall_t = locked, None

    def sample(self):
        kp = 0.012 if self.fw >= "2.7" else 0.016  # 2.7 retuned the velocity loop (softer)
        err = self.cmd - self.v
        self.i = float(np.clip(kp * err + 0.00013 * self.v, -self.ilim, self.ilim))
        if not self.locked:
            self.v += (self.i * 3100 - 0.4 * self.v) * self.DT
        fault = 0
        if self.locked and abs(self.i) >= self.ilim * 0.98:
            self.stall_t = self.stall_t if self.stall_t is not None else self.t
            fault = 3 if self.t - self.stall_t > 0.15 else 0
        self.t += self.DT
        return (round(self.t, 4), round(self.i + self.rng.normal(0, 0.01), 4),
                round(self.v + self.rng.normal(0, 2.0), 2), fault)

    def close(self): pass
