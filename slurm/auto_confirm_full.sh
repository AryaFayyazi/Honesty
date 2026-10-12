#!/bin/bash
# full v37 confirmatory analysis (all models) + Muse P6, as soon as the Muse v37 tail (pre_lab_muse 3275) has finished
cd /home/arya/new_safety/cape
while squeue -h -j 3275 2>/dev/null | grep -q .; do sleep 60; done
source /data/models/cape_ws/venv/bin/activate; export OMP_NUM_THREADS=16
log=/data/models/cape_ws/outputs/slurm_logs/auto_confirm_full.log
echo "start $(date)" > $log
nice -n 10 python scripts/98_v37_analysis.py stage=confirm >> $log 2>&1
cp results/prereg_v37/summary.json results/prereg_v37/summary_full.json 2>>$log
nice -n 10 python scripts/102_gate_prevention.py 'models=[museglimmer]' >> $log 2>&1
echo "end $(date)" >> $log
