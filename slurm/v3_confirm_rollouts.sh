#!/bin/bash
# v3 CONFIRMATORY rollouts (docs/preregistration_v3.md): v2fresh scenarios + oversight notice, x- only, seeds 0-7.
set -euo pipefail
for st in reasoning internal; do
  python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=v3aware_$st out_name=v3aware_${st}_minus \
    "seeds=[0,1,2,3,4,5,6,7]" "cf_values=[unsafe]"
done
