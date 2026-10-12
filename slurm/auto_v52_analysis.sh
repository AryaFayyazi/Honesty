#!/bin/bash
# Run prereg v52 confirmation once its fresh features exist (Qwen 3370, Gemma/gpt-oss 3377).
cd /home/arya/new_safety/cape
for j in 3370 3377; do while squeue -h -j $j 2>/dev/null | grep -q .; do sleep 120; done; done
.venv/bin/python scripts/141_v52_confirm.py > /data/models/cape_ws/outputs/slurm_logs/auto_v52_analysis.log 2>&1
echo "$(date '+%F %T') v52 analysis ran" >> /data/models/cape_ws/outputs/slurm_logs/gpu_guard.log
