# perception replay

`docker compose --profile replay up` plays `scenarios/*.mcap` through the stack; outputs land in
`outputs/<scenario>/output.mcap` (`/perception/detections`, `/perception/tracks`). Image tag in `compose.yaml`.
