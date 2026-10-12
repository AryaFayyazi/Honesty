#!/bin/bash
set -uo pipefail
for arm in E F; do
  python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=v20$arm out_name=v20${arm}_minus "seeds=[0,1,2,3,4,5,6,7]" "cf_values=[unsafe]" || echo "V20 FAILED $arm"
done
python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=v20N out_name=v20N_minus "seeds=[0,1,2,3]" "cf_values=[unsafe]" || echo "V20 FAILED N"
