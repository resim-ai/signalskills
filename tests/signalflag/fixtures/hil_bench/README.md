# motor-hil

Hardware-in-the-loop tests for the MC4 motor controller. Jenkins (bench PC `hil-bench-01`) runs

```
pytest tests/hil -m hil --junitxml=out/junit.xml
```

against the controller on `/dev/ttyACM0`. Each test logs its current/velocity trace to `out/<test>/trace.csv`;
the session reads the device identity (serial, firmware) over serial into `out/device.json`.
`--hil-backend=sim` runs against the plant model instead of hardware (no bench needed).
