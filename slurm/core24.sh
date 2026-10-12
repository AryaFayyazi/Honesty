#!/bin/bash
set -uo pipefail
python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=core24 out_name=core24_minus "seeds=[0,1]" "cf_values=[unsafe]" || echo "C24 FAILED minus"
python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=core24 out_name=core24_plus "seeds=[0,1]" "cf_values=[safe]" || echo "C24 FAILED plus"
