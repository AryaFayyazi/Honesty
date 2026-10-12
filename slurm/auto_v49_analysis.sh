#!/bin/bash
# Run the v49 H1-H3 analysis as soon as every input job has finished (Gemma/gpt-oss regen labels 3360, Muse regen labels 3362,
# Muse fresh features 3348, Qwen features 3370 and regen labels 3372). The analysis writes headline_done.json when all four models
# have H1 and H2, which makes slurm/auto_one_gpu_after_v49.sh switch the cluster to one GPU.
cd /home/arya/new_safety/cape
for j in 3360 3362 3348 3370 3372; do while squeue -h -j $j 2>/dev/null | grep -q .; do sleep 120; done; done
.venv/bin/python scripts/125_v49_analysis.py > /data/models/cape_ws/outputs/slurm_logs/auto_v49_analysis.log 2>&1
echo "$(date '+%F %T') v49 analysis ran; headline_done=$(test -f results/prereg_v49/headline_done.json && echo yes || echo no)" >> /data/models/cape_ws/outputs/slurm_logs/gpu_guard.log
