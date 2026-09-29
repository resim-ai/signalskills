#!/usr/bin/env bash
# new_workspace.sh <fixture> <name> -> prints a fresh workspace under $SKT/work/
set -euo pipefail
skt="$(cd "$(dirname "$0")/.." && pwd)"
repo="${REROBOT:-}"  # m6 and replay need a private rerobot checkout
ws="$skt/work/$2"
rm -rf "$ws" && mkdir -p "$ws"
case "$1" in
  m6)
    [ -n "$repo" ] || { echo "set REROBOT to a rerobot checkout" >&2; exit 2; }
    for run in "$repo"/autonomy/ws/runs/*/; do
      [ -f "$run/results.json" ] || continue  # results.json present defines a run
      name="$(basename "$run")"; mkdir -p "$ws/runs/$name"
      cp -r "$run/results.json" "$run/logs" "$ws/runs/$name/"
      [ -f "$run/replay.gif" ] && cp "$run/replay.gif" "$ws/runs/$name/"
      [ -d "$run/bag" ] && ln -s "$run/bag" "$ws/runs/$name/bag"
    done ;;
  replay)
    [ -n "$repo" ] || { echo "set REROBOT to a rerobot checkout" >&2; exit 2; }
    cp -r "$repo/test-orchestrator/"{README.md,compose.yaml,orchestrator,scenarios,schema,test-creator} "$ws/"
    ln -s "$repo/test-orchestrator/outputs" "$ws/outputs"
    ln -s "$repo/test-orchestrator/experiences" "$ws/experiences" ;;
  *) cp -r "$skt/fixtures/$1/." "$ws/" ;;
esac
git -C "$ws" init -q && git -C "$ws" add -A && git -C "$ws" commit -qm fixture
echo "$ws"
