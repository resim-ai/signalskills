"""Serial protocol for the MC4 controller: line-based ASCII commands."""
import json

class SerialController:
    def __init__(self, port: str, baud: int = 921600):
        import serial  # pyserial
        self._s = serial.Serial(port, baud, timeout=1.0)

    def _cmd(self, line: str) -> str:
        self._s.write((line + "\n").encode())
        return self._s.readline().decode().strip()

    def identify(self) -> dict:
        return json.loads(self._cmd("ID?"))

    def set_velocity(self, rpm: float) -> None:
        self._cmd(f"VEL {rpm:.1f}")

    def set_current_limit(self, amps: float) -> None:
        self._cmd(f"ILIM {amps:.2f}")

    def lock_rotor(self, locked: bool) -> None:
        self._cmd(f"BRAKE {int(locked)}")  # bench brake fixture

    def sample(self) -> tuple[float, float, float, int]:
        """-> (t_s, current_a, velocity_rpm, fault_code)"""
        t, i, v, f = self._cmd("SAMPLE?").split(",")
        return float(t), float(i), float(v), int(f)

    def close(self) -> None:
        self.set_velocity(0)
        self._s.close()
