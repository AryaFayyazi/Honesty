#!/bin/bash
# Monitor-aware EXPLORATION pilot (exploration scenario pool, seed 42 worlds): both notice styles, x- only, 4 seeds.
set -euo pipefail
for st in reasoning internal; do
  python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=aware_explore_$st out_name=aware_explore_$st \
    "seeds=[0,1,2,3]" "cf_values=[unsafe]"
done
