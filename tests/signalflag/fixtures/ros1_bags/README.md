# test-track archive

ROS1 (Noetic) bags from the test track, 2022 to 2025: 40 bags, listed in `bags/INDEX.csv`.

- 4 are here in `bags/`, trimmed with `rosbag filter` to `/vehicle/pose`, `/vehicle/speed` and
  `/perception/objects` (track_perception_msgs/ObjectArray).
- The other 36 are full recordings (lidar, camera, tf) archived in `s3://acme-track-archive/bags/`; fetch with
  `scripts/fetch_bags.sh`.

The old car PC with ROS Noetic was decommissioned; nothing here has ROS installed.
