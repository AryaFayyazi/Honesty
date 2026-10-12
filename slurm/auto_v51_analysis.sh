#!/bin/bash
# Run the preregistered v51 confirmation analysis once every input exists: features (Muse 3348, Qwen 3370, Gemma/gpt-oss 3377)
# and zero-shot CoT-monitor scores (3378 Muse, 3379 Qwen, 3380 Gemma/gpt-oss).
cd /home/arya/new_safety/cape
for j in 3348 3370 3377 3378 3379 3380 3430; do while squeue -h -j $j 2>/dev/null | grep -q .; do sleep 120; done; done
.venv/bin/python scripts/134_v51_confirm.py stage=analyze > /data/models/cape_ws/outputs/slurm_logs/auto_v51_analysis.log 2>&1
echo "$(date '+%F %T') v51 analysis ran" >> /data/models/cape_ws/outputs/slurm_logs/gpu_guard.log
