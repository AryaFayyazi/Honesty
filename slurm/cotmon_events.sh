#!/bin/bash
set -uo pipefail
for p in "v2fresh_minus v2fresh" "v4fresh_minus v4fresh"; do set -- $p
  python scripts/25_cot_monitor_events.py set=$1 bench=$2 || echo "COTMON FAILED $1"
done
python scripts/25_cot_monitor_events.py set=v4fresh_minus bench=v4fresh judge=google/gemma-4-26B-A4B-it || echo "COTMON FAILED gemma"
python scripts/25_cot_monitor_events.py set=v2fresh_minus bench=v2fresh judge=google/gemma-4-26B-A4B-it || echo "COTMON FAILED gemma v2"
