#!/bin/bash
# 2-GPU window ends 08:00 2026-10-04: at 05:30 stop new Muse-chain (B) jobs from starting until chain A's v37 tail
# (pre_int_lab 3287) is done. Remaining order (rev 22:10): A v37 -> B Muse v37 (rep_muse, rub3_muse, pre_int_muse, pre_lab_muse) -> steering 3250-3253 -> rec_muse 3292,3259 -> fresh_cplus 3280
# -> rdx_c 3281 -> clb_shadow 3278 -> clb_gate 3279 -> muse_plus 3298 -> rec_gemma4 3254 -> rec_gptoss 3255 -> tau2.
B="3294 3299 3245 3295 3257 3296 3297 3247 3292 3259 3273 3272 3293 3275 3250 3251 3252 3253"
log=/data/models/cape_ws/outputs/slurm_logs/serialize_0530.log
echo "serialize at $(date)" >> $log
for j in $B; do
  st=$(squeue -h -j $j -o %t 2>/dev/null)
  if [ "$st" = "PD" ]; then
    dep=$(squeue -h -j $j -o %E | sed 's/(unfulfilled)//g; s/(failed)//g')
    new="afterany:3287"; [ -n "$dep" ] && [ "$dep" != "(null)" ] && new="$dep,afterany:3287"
    scontrol update JobId=$j Dependency=$new && echo "  $j -> $new" >> $log
  fi
done
scontrol update JobId=3278 Dependency=afterany:3281,afterany:3259 && echo "  3278 (clb_shadow) -> afterany:3281,afterany:3259" >> $log
squeue -u arya -h -o "%i %j %t %E" >> $log
