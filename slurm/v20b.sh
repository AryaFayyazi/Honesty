#!/bin/bash
set -uo pipefail
for arm in E2 F2; do
  python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=v20b$arm out_name=v20b${arm}_minus "seeds=[0,1,2,3,4,5,6,7]" "cf_values=[unsafe]" || echo "V20B FAILED $arm"
done
