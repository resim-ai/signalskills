"""Replay recorded scenarios through the perception stack and record what it publishes.

For each scenarios/<name>.yaml: plays recordings/<name>.mcap frame by frame and writes
  outputs/<name>/replay.mcap  (/camera/front/image annotated, /perception/detections, /perception/tracks,
                               /perception/latency, /diagnostics)
  outputs/<name>/camera.mp4   (annotated preview, 10 fps)
  outputs/<name>/replay.gif   (every 4th annotated frame)
"""
import argparse, base64, io, json, shutil, subprocess, sys, zlib
from pathlib import Path

import numpy as np
import yaml
from mcap.reader import make_reader
from mcap.writer import CompressionType, Writer
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from perception.stack import LATENCY, PREVIEW_SCALE, PerceptionStack  # noqa: E402

STACK = "acme/perception:2026.09.4"
_STAMP = {"type": "object", "properties": {"sec": {"type": "integer"}, "nanosec": {"type": "integer"}}}
_HEADER = {"type": "object", "properties": {"stamp": _STAMP, "frame_id": {"type": "string"}}}
_BOX = {"type": "object", "properties": {k: {"type": "number"} for k in ("x_min", "y_min", "x_max", "y_max")}}
_CLASS = {"type": "string", "enum": ["car", "pedestrian", "cyclist", "truck"]}
SCHEMAS = {
    "/camera/front/image": ("sensor_msgs/msg/CompressedImage", {"header": _HEADER, "format": {"type": "string"},
                                                               "data": {"type": "string", "contentEncoding": "base64"}}),
    "/perception/detections": ("acme_perception_msgs/msg/Detection2DArray", {"header": _HEADER, "detections": {
        "type": "array", "items": {"type": "object", "properties": {
            "class": _CLASS, "score": {"type": "number"}, "bbox_2d": _BOX, "range_m": {"type": "number"}}}}}),
    "/perception/tracks": ("acme_perception_msgs/msg/Track2DArray", {"header": _HEADER, "tracks": {
        "type": "array", "items": {"type": "object", "properties": {
            "track_id": {"type": "integer"}, "class": _CLASS, "bbox_2d": _BOX, "range_m": {"type": "number"},
            "age": {"type": "integer"}}}}}),
    "/perception/latency": ("acme_perception_msgs/msg/Latency", {"header": _HEADER, "input_stamp": _STAMP,
                                                                 "output_stamp": _STAMP, "e2e_ms": {"type": "number"}}),
    "/diagnostics": ("diagnostic_msgs/msg/DiagnosticArray", {"header": _HEADER, "status": {"type": "array", "items": {
        "type": "object", "properties": {"level": {"type": "integer"}, "name": {"type": "string"},
                                         "message": {"type": "string"}, "hardware_id": {"type": "string"},
                                         "values": {"type": "array", "items": {"type": "object", "properties": {
                                             "key": {"type": "string"}, "value": {"type": "string"}}}}}}}}),
}


def _stamp(ns: int) -> dict:
    return {"sec": ns // 1_000_000_000, "nanosec": ns % 1_000_000_000}


def _annotate(img: Image.Image, dets: list) -> Image.Image:
    out = img.copy()
    d = ImageDraw.Draw(out)
    for det in dets:
        b = det["bbox_2d"]
        d.rectangle([int(b["x_min"] / PREVIEW_SCALE), int(b["y_min"] / PREVIEW_SCALE),
                     max(int(b["x_min"] / PREVIEW_SCALE), int(b["x_max"] / PREVIEW_SCALE) - 1),
                     max(int(b["y_min"] / PREVIEW_SCALE), int(b["y_max"] / PREVIEW_SCALE) - 1)],
                    outline=(0, 255, 0) if det["class"] != "pedestrian" else (255, 0, 255))
    return out


def _jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=55, optimize=True)
    return buf.getvalue()


def _write_mcap(path: Path, records: list) -> None:
    with open(path, "wb") as f:
        w = Writer(f, compression=CompressionType.NONE)
        w.start(profile="ros2", library="acme-replay 1.3.0")
        ids = {}
        for topic, (name, props) in SCHEMAS.items():
            sid = w.register_schema(name=name, encoding="jsonschema", data=json.dumps(
                {"title": name, "type": "object", "properties": props}, sort_keys=True).encode())
            ids[topic] = w.register_channel(topic=topic, message_encoding="json", schema_id=sid)
        seq = {}
        for t, order, topic, msg in sorted(records, key=lambda r: (r[0], r[1])):
            seq[topic] = seq.get(topic, 0) + 1
            w.add_message(ids[topic], log_time=t, publish_time=t, sequence=seq[topic],
                          data=json.dumps(msg, separators=(",", ":")).encode())
        w.finish()


def _mp4(path: Path, frames: list, fps: int = 10) -> None:
    a = np.stack([np.asarray(f) for f in frames])
    n, h, w, _ = a.shape
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                    "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
                    "-pix_fmt", "yuv420p", "-threads", "1", "-bitexact", "-fflags", "+bitexact",
                    "-flags:v", "+bitexact", "-map_metadata", "-1", str(path)], input=a.tobytes(), check=True)


def replay(scenario: Path) -> None:
    sc = yaml.safe_load(scenario.read_text())
    name = sc["name"]
    labels = {}
    for line in (ROOT / sc["labels"]).read_text().splitlines():
        row = json.loads(line)
        labels[row["stamp"]["sec"] * 1_000_000_000 + row["stamp"]["nanosec"]] = row["objects"]
    stack = PerceptionStack(seed=zlib.crc32(name.encode()))
    out = ROOT / "outputs" / name
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    records, frames, warn = [], [], 0
    with open(ROOT / sc["recording"], "rb") as f:
        for _, ch, m in make_reader(f).iter_messages(topics=["/camera/front/image"]):
            msg = json.loads(m.data)
            t_in = msg["header"]["stamp"]["sec"] * 1_000_000_000 + msg["header"]["stamp"]["nanosec"]
            img = Image.open(io.BytesIO(base64.b64decode(msg["data"]))).convert("RGB")
            r = stack.step(img, labels.get(t_in, []))
            t_out = t_in + int(round(r["e2e_ms"] * 1e6))
            hdr_in, hdr_out = {"stamp": _stamp(t_in), "frame_id": "camera_front"}, {"stamp": _stamp(t_out), "frame_id": "camera_front"}
            shown = _annotate(img, r["detections"])
            frames.append(shown)
            over = r["e2e_ms"] > LATENCY["budget_ms"]
            warn += over
            records += [
                (t_out, 0, "/camera/front/image", {"header": hdr_in, "format": "jpeg",
                                                   "data": base64.b64encode(_jpeg(shown)).decode()}),
                (t_out, 1, "/perception/detections", {"header": hdr_in, "detections": r["detections"]}),
                (t_out, 2, "/perception/tracks", {"header": hdr_in, "tracks": r["tracks"]}),
                (t_out, 3, "/perception/latency", {"header": hdr_out, "input_stamp": _stamp(t_in),
                                                   "output_stamp": _stamp(t_out), "e2e_ms": r["e2e_ms"]}),
                (t_out, 4, "/diagnostics", {"header": hdr_out, "status": [{
                    "level": 1 if over else 0, "name": "perception/stack", "hardware_id": "orin-0",
                    "message": f"e2e latency {r['e2e_ms']:.1f} ms over {LATENCY['budget_ms']:.0f} ms budget" if over else "OK",
                    "values": [{"key": "e2e_ms", "value": f"{r['e2e_ms']:.2f}"},
                               {"key": "derain", "value": str(r["derain"]).lower()},
                               {"key": "detections", "value": str(len(r["detections"]))}]}]}),
            ]
    _write_mcap(out / "replay.mcap", records)
    _mp4(out / "camera.mp4", frames)
    frames[0].save(out / "replay.gif", save_all=True, append_images=frames[4::4], duration=400, loop=0)
    print(f"[replay] {name}: {len(frames)} frames through {STACK} -> {out.relative_to(ROOT)}/ ({warn} diagnostics WARN)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", action="append", help="scenario name (repeatable); default: all")
    a = ap.parse_args()
    names = a.scenario or sorted(p.stem for p in (ROOT / "scenarios").glob("*.yaml"))
    for n in names:
        replay(ROOT / "scenarios" / f"{n}.yaml")
