#!/bin/bash
set -uo pipefail
for st in assert conditional; do
  python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=v16$st out_name=v16${st}_minus "seeds=[0,1,2,3,4,5,6,7]" "cf_values=[unsafe]" || echo "V16 FAILED $st"
done
