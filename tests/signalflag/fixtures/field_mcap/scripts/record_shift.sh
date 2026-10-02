#!/usr/bin/env bash
# Started by systemd at shift start on each robot; stopped at shift end.
set -euo pipefail
robot="$(hostname)"
out="/data/logs/${robot}/$(date -u +%F)"
ros2 run topic_tools throttle messages /odom 1.0 /odom_throttled &
ros2 run topic_tools throttle messages /localization/pose 1.0 /localization/pose_throttled &
exec ros2 bag record -s mcap -o "$out" \
  /odom_throttled:=/odom /localization/pose_throttled:=/localization/pose \
  /gps/fix /diagnostics /teleop/takeover
