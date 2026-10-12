#!/bin/bash
# detached watcher: when the v55 monitor job (3447) leaves the queue, run the v55 analysis on CPU (login node) and log it
cd /home/arya/new_safety/cape; source .venv/bin/activate
while squeue -h -j 3447 2>/dev/null | grep -q .; do sleep 120; done
python scripts/150_v55_analysis.py > results/prereg_v55/analysis.log 2>&1 || echo "v55 analysis FAILED" >> results/prereg_v55/analysis.log
