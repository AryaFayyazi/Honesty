#!/bin/bash
# User rule (2026-10-12 ~00:55): two GPUs until 09:00, then ONE GPU at a time. At 09:00 PDT: requeue-hold our most recently
# started running job if two run (AgentDojo/τ² clients resume from their jsonl), stop yield_guard (exact PID), start gpu_guard.py
# in soft one-GPU mode (pending jobs chained serially). Log: slurm/at9_one_gpu.log
LOG=/home/arya/new_safety/cape/slurm/at9_one_gpu.log; cd /home/arya/new_safety/cape
echo "$(date '+%F %T') armed; firing at 2026-10-12 09:00" >> $LOG
while [ "$(date +%s)" -lt "$(date -d '2026-10-12 09:00' +%s)" ]; do sleep 30; done
MINE=$(squeue -h -u $USER -t RUNNING -o "%S|%i|%j" | sort | awk -F'|' '{print $2":"$3}'); N=$(echo "$MINE" | grep -c .)
if [ "$N" -ge 2 ]; then V=$(echo "$MINE" | tail -1); scontrol requeuehold ${V%%:*} && echo "$(date '+%F %T') requeue-held $V (one GPU from 09:00)" >> $LOG; fi
kill 2514646 2>/dev/null && echo "$(date '+%F %T') stopped yield_guard (pid 2514646)" >> $LOG
echo soft > slurm/ONE_GPU_MODE
nohup python3 slurm/gpu_guard.py >> /data/models/cape_ws/outputs/slurm_logs/gpu_guard.log 2>&1 &
echo "$(date '+%F %T') gpu_guard.py soft one-GPU mode started (pid $!)" >> $LOG
