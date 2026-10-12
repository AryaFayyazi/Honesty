#!/bin/bash
# v27 main run, only if the smoke integration check passes (otherwise exit 0 so the chain continues)
set -uo pipefail
export TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True
/data/models/cape_ws/envs/tau2/bin/python scripts/47_tau2_port.py smokecheck smk2 || { echo "V27 SMOKE CHECK FAILED - main run skipped"; exit 0; }
bash slurm/tau2_run.sh 8 v27 P0_none,P0_enf,P0_orc,P0_orc_enf,P1_none
