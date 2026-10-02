# egocentric video deliveries

Each delivery to a client is `deliveries/<delivery_id>/`:

- `videos/*.mp4`: head-camera clips, one task per clip (proxy resolution here; full-res stays in the bucket).
- `annotations.json`: per video `duration_s`, `fps`, `task`, `hand_visibility` segments, collector, device.

Today QA is someone skimming a sample of clips before we ship. We want every clip checked.
