#!/bin/bash
cd /home/arya/new_safety/cape
while squeue -h -j 3355 2>/dev/null | grep -q . || squeue -h -j 3354 2>/dev/null | grep -q .; do sleep 60; done
source /data/models/cape_ws/venv/bin/activate
python scripts/113_v46b_analysis.py > /data/models/cape_ws/outputs/slurm_logs/auto_v46b.log 2>&1
