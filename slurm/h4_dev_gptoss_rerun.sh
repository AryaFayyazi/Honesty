#!/bin/bash
# v49 H4 gpt-oss development sweep, rerun after the 3614 OOM (deviation 5: memory-budgeted batching, max_attn_gb=6; conditions,
# episodes, directions, seeds-per-batch scheme and the selection rule unchanged). Extraction, direction and smoke completed in 3614.
set -euo pipefail
A=gptoss20b
python scripts/127_steer_multi.py actor=$A episodes=outputs/reconcile/h4_${A}_dev_episodes.parquet out_name=h4dev_$A max_attn_gb=6 'conds=[none:0:caa:d16,caa_p2_d16:2:caa:d16,caa_p4_d16:4:caa:d16,caa_p8_d16:8:caa:d16,caa_p12_d16:12:caa:d16,rand_p8_d16:8:rand:d16]'
python scripts/97_rubric_timeline.py revised=outputs/reconcile/h4dev_$A.parquet
python scripts/135_h4_select.py actor=$A
