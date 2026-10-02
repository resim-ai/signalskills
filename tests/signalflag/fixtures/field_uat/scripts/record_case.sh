#!/usr/bin/env bash
# usage: scripts/record_case.sh <release> <case> <robot> <n>
set -euo pipefail
out="field/$1/$2_$3_$4"
ros2 bag record -s mcap -o "$out" /odom /localization/pose /diagnostics /estop/state \
  /docking/state /route/status /perception/nearest_obstacle
mv "$out"/*.mcap "$out.mcap" && rmdir "$out"
