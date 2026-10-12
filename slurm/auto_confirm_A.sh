#!/bin/bash
# run the preregistered v37 confirmatory analysis as soon as chain A's v37 tail (pre_int_lab 3287) has finished
cd /home/arya/new_safety/cape
while squeue -h -j 3287 2>/dev/null | grep -q .; do sleep 60; done
source /data/models/cape_ws/venv/bin/activate; export OMP_NUM_THREADS=8
log=/data/models/cape_ws/outputs/slurm_logs/auto_confirm_A.log
echo "start $(date)" > $log
nice -n 10 python scripts/98_v37_analysis.py stage=confirm >> $log 2>&1
cp results/prereg_v37/summary.json results/prereg_v37/summary_gemma_gptoss_partial.json 2>>$log
echo "end $(date)" >> $log
