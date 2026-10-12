#!/bin/bash
cd /home/arya/new_safety/cape
while squeue -h -j 3306 2>/dev/null | grep -q .; do sleep 60; done
source /data/models/cape_ws/venv/bin/activate
python scripts/104_v39_analysis.py > /data/models/cape_ws/outputs/slurm_logs/auto_v39.log 2>&1
