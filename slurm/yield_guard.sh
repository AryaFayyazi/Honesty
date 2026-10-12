#!/bin/bash
# Yield guard (user rule 2026-10-10 ~13:00): we may use the second GPU, but if ANY other user has a GPU job waiting,
# our second-GPU job must stop so theirs can start. Our main-lane job (the earliest-started of ours) is never touched.
# Runs detached (nohup); polls every 20 s; logs every action to slurm/yield_guard.log.
#   yield  : requeue + hold our most recently started running job (scontrol requeuehold) -> its GPU frees for them.
#   resume : when no other user's GPU job is waiting, release the jobs we held (they then wait for a free GPU as usual).
ME=$USER; LOG=/home/arya/new_safety/cape/slurm/yield_guard.log; STATE=/home/arya/new_safety/cape/slurm/.yield_held
touch $STATE
log() { echo "$(date '+%F %T') $*" | tee -a $LOG; }
log "guard started (pid $$)"
while true; do
  # other users' pending jobs that request a GPU (any reason except held/dependency/begin-time)
  WAIT=$(squeue -h -t PENDING -o "%i|%u|%b|%r" 2>/dev/null | awk -F'|' -v me=$ME '$2!=me && $3 ~ /gpu/ && $4 !~ /Dependency|JobHeld|BeginTime/ {print $1":"$2":"$4}')
  # our running jobs, earliest start first
  MINE=$(squeue -h -u $ME -t RUNNING -o "%S|%i|%j" 2>/dev/null | sort | awk -F'|' '{print $2":"$3}')
  NMINE=$(echo "$MINE" | grep -c . )
  if [ -n "$WAIT" ] && [ "$NMINE" -ge 2 ]; then
    VICTIM=$(echo "$MINE" | tail -1); VID=${VICTIM%%:*}
    log "YIELD: other user waiting [$WAIT]; we run $NMINE jobs; requeue+hold our latest $VICTIM"
    if scontrol requeuehold $VID 2>>$LOG; then echo $VID >> $STATE; log "yielded $VID"; else log "requeuehold $VID FAILED"; fi
  elif [ -z "$WAIT" ] && [ -s $STATE ]; then
    for J in $(sort -u $STATE); do
      st=$(squeue -h -j $J -o "%T|%r" 2>/dev/null)
      if echo "$st" | grep -q "JobHeld"; then scontrol release $J 2>>$LOG && log "RESUME: no other user waiting; released $J"; fi
    done
    : > $STATE
  fi
  sleep 20
done
