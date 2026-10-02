# fleet-logs

Shift recordings from the warehouse AMRs. The on-robot recorder (`scripts/record_shift.sh`) writes one mcap
per shift to `logs/<robot>/<date>.mcap`; the nightly sync copies them here.

| Topic | Type | Rate | Notes |
|---|---|---|---|
| `/odom` | nav_msgs/Odometry | 1 Hz (throttled) | wheel odometry |
| `/localization/pose` | geometry_msgs/PoseWithCovarianceStamped | 1 Hz (throttled) | map-frame localizer output |
| `/gps/fix` | sensor_msgs/NavSatFix | 1 Hz | outdoor yard only (amr-03) |
| `/diagnostics` | diagnostic_msgs/DiagnosticArray | 0.2 Hz | localization, autonomy mode, battery |
| `/teleop/takeover` | acme_fleet_msgs/Takeover | on event | operator e-stop / takeover |

No ground truth is recorded.
