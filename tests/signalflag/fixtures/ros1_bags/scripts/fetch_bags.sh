#!/usr/bin/env bash
# usage: scripts/fetch_bags.sh [pattern]   e.g. 'track_2024-*'
set -euo pipefail
aws s3 sync s3://acme-track-archive/bags/ bags/ --exclude '*' --include "*/${1:-*}.bag" --no-progress
