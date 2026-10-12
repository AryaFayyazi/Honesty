#!/bin/bash
# Gap-proof job monitor (state persisted in .monitor_snapshot / .monitor_guardlines across re-arms).
G=/data/models/cape_ws/outputs/slurm_logs/gpu_guard.log; SNAP=/home/arya/new_safety/cape/slurm/.monitor_snapshot; GL=/home/arya/new_safety/cape/slurm/.monitor_guardlines
prev=$(cat $SNAP 2>/dev/null || squeue -u $USER -h -o "%i %j %t" | sort); gl=$(cat $GL 2>/dev/null || wc -l < $G); seen=""
while true; do
  cur=$(squeue -u $USER -h -o "%i %j %t" | sort) || { sleep 30; continue; }
  comm -23 <(echo "$prev" | awk '{print $1" "$2}' | sort) <(echo "$cur" | awk '{print $1" "$2}' | sort) | while read id name; do
    log=/data/models/cape_ws/outputs/slurm_logs/$name-$id.out
    err=$(grep -v APIServer $log 2>/dev/null | grep -c -E "Traceback|Error:|FAILED|CUDA out of memory|Killed|exited during startup")
    echo "FINISHED $id $name (error-lines=$err) $(grep '^end' $log 2>/dev/null)"
  done
  comm -13 <(echo "$prev" | grep " R$" | sort) <(echo "$cur" | grep " R$" | sort) | while read id name st; do echo "STARTED $id $name"; done
  for j in $(squeue -u $USER -h -o "%i %r" | awk '$2=="DependencyNeverSatisfied"{print $1}'); do case " $seen " in *" $j "*) ;; *) echo "STUCK $j $(squeue -h -j $j -o %j) DependencyNeverSatisfied (upstream failed)"; seen="$seen $j";; esac; done
  n=$(wc -l < $G); if [ "$n" -gt "$gl" ]; then tail -n $((n-gl)) $G | sed 's/^/GUARD: /'; gl=$n; fi
  prev=$cur; echo "$cur" > $SNAP; echo $gl > $GL; sleep 60
done
