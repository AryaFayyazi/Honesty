#!/bin/bash
# User rule 2026-10-05: "after we get the headline results (v49 finished), keep using 1 gpu again".
# Trigger = results/prereg_v49/headline_done.json, written by the v49 H1-H3 analysis once all four models are analysed.
# Then: snapshot all results (verified, read-only) and switch the guard to SOFT one-GPU mode (no job is cancelled;
# the GPU count drains to one as soon as either running job ends).
cd /home/arya/new_safety/cape
while [ ! -f results/prereg_v49/headline_done.json ]; do sleep 120; done
slurm/archive_results.sh || echo "$(date '+%F %T') archive FAILED" >> /data/models/cape_ws/archive/ARCHIVE_LOG.txt
echo "soft $(date -Iseconds) v49 headline done" > slurm/ONE_GPU_MODE
echo "$(date '+%F %T') v49 headline done -> SOFT ONE-GPU MODE flag set" >> /data/models/cape_ws/outputs/slurm_logs/gpu_guard.log
