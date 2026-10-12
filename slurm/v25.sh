#!/bin/bash
set -uo pipefail
for arm in R1 R1c; do
  python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=v25$arm out_name=v25${arm}_minus "seeds=[0,1,2,3,4,5,6,7]" "cf_values=[unsafe]" || echo "V25 FAILED $arm"
done
