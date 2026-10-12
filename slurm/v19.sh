#!/bin/bash
set -uo pipefail
python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=v19orc out_name=v19orc_minus "seeds=[0,1,2,3,4,5,6,7]" "cf_values=[unsafe]" || echo "V19 FAILED orc_minus"
python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=v19orcenf out_name=v19orcenf_minus "seeds=[0,1,2,3,4,5,6,7]" "cf_values=[unsafe]" || echo "V19 FAILED orcenf_minus"
python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=v19orc out_name=v19orc_plus "seeds=[0,1]" "cf_values=[safe]" || echo "V19 FAILED orc_plus"
