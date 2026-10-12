#!/bin/bash
cd /home/arya/new_safety/cape
while squeue -h -j 3313 2>/dev/null | grep -q . || squeue -h -j 3312 2>/dev/null | grep -q .; do sleep 60; done
source /data/models/cape_ws/venv/bin/activate; export OMP_NUM_THREADS=16
nice -n 10 python scripts/105_v40_analysis.py > /data/models/cape_ws/outputs/slurm_logs/auto_v40.log 2>&1
