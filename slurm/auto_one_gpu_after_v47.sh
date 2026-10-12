#!/bin/bash
# User decision 2026-10-05 ~09:55: switch to ONE GPU after the v47 interim and the Gemma/gpt-oss/Muse v49 results (Qwen finishes on 1 GPU).
# Waits for v47 features (3348; implies v47 labels 3347) and Muse v49 regeneration labels (3362; Gemma/gpt-oss 3360 already done),
# runs the v47 interim analysis and a partial v49 analysis, archives, then sets SOFT one-GPU mode (nothing is cancelled).
cd /home/arya/new_safety/cape; LOG=/data/models/cape_ws/outputs/slurm_logs
for j in 3347 3348 3362; do while squeue -h -j $j 2>/dev/null | grep -q .; do sleep 120; done; done
.venv/bin/python scripts/112_v47_analysis.py look=interim > $LOG/auto_v47_interim.log 2>&1
.venv/bin/python scripts/125_v49_analysis.py > $LOG/auto_v49_partial.log 2>&1
slurm/archive_results.sh >> $LOG/auto_v47_interim.log 2>&1 || true
echo "soft $(date -Iseconds) after v47 interim + v49 (Gemma/gpt-oss/Muse)" > slurm/ONE_GPU_MODE
echo "$(date '+%F %T') v47 interim + partial v49 done -> SOFT ONE-GPU MODE flag set" >> $LOG/gpu_guard.log
