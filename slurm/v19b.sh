#!/bin/bash
set -uo pipefail
for arm in none orc dry; do
  python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=v19b$arm out_name=v19b${arm}_minus "seeds=[0,1,2,3]" "cf_values=[unsafe]" || echo "V19B FAILED $arm minus"
done
for arm in none dry; do
  python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=v19b$arm out_name=v19b${arm}_plus "seeds=[0,1]" "cf_values=[safe]" || echo "V19B FAILED $arm plus"
done
