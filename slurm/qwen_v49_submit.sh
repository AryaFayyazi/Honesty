#!/bin/bash
# Submit the Qwen3.8 v49 chain (run ONLY after the smoke test passes: violation rate within +-5 pts of the original seed-0 subset).
set -euo pipefail; cd /home/arya/new_safety/cape
R="python scripts/20_server_rollouts.py actor=qwen38 port=8187 'cf_values=[unsafe]'"
ROLL="[ -f outputs/rollouts/core24b_minus2345.parquet ] || $R split=core24b out_name=core24b_minus2345 'seeds=[2,3,4,5]'; [ -f outputs/rollouts/core24b_reasoning_minus0123.parquet ] || $R split=core24b_reasoning out_name=core24b_reasoning_minus0123 'seeds=[0,1,2,3]'; [ -f outputs/rollouts/core24b_obfuscate_minus0123.parquet ] || $R split=core24b_obfuscate out_name=core24b_obfuscate_minus0123 'seeds=[0,1,2,3]'"
a=$(sbatch --parsable -J v49_roll_qw ${1:+--dependency=$1} slurm/run.sh bash -c "$ROLL")
LAB=""; for s in core24b_minus2345 core24b_reasoning_minus0123 core24b_obfuscate_minus0123; do LAB="$LAB python scripts/97_rubric_timeline.py trajectories=outputs/rollouts/$s.parquet;"; done
b=$(sbatch --parsable -J v49_lab_qw --dependency=afterany:$a slurm/run.sh bash -c "$LAB")
F="python scripts/94_report_feats.py actor=qwen38 bench=core24b 'sfx=[minus2345]' tag=_H; python scripts/94_report_feats.py actor=qwen38 bench=core24b_reasoning 'sfx=[minus0123]' tag=_H; python scripts/94_report_feats.py actor=qwen38 bench=core24b_obfuscate 'sfx=[minus0123]' tag=_H"
c=$(sbatch --parsable -J v49_feat_qw --dependency=afterany:$b slurm/run.sh bash -c "$F")
I="python scripts/96_prereport_intervene.py label_dir=outputs/disclosure_v37 actor=qwen38 port=8187"
G="$I 'conditions=[neutral,fta_contract]' bench=core24b 'sets=[core24b_minus2345]' name=v49_qwen38_core24b; $I 'conditions=[neutral,fta_contract]' bench=core24b_reasoning 'sets=[core24b_reasoning_minus0123]' name=v49_qwen38_core24b_reasoning; $I 'conditions=[neutral,fta_contract]' bench=core24b_obfuscate 'sets=[core24b_obfuscate_minus0123]' name=v49_qwen38_core24b_obfuscate"
# H4 development regenerations on the ORIGINAL Qwen sets (5 conditions; feed scripts/126)
G="$G; $I 'conditions=[neutral,generic,provenance,fta_transparency,fta_contract]' bench=core24b 'sets=[core24b_minus]' name=qwen38_core24b; $I 'conditions=[neutral,generic,provenance,fta_transparency,fta_contract]' bench=core24 'sets=[core24_minus]' name=qwen38_core24"
d=$(sbatch --parsable -J v49_gen_qw --dependency=afterany:$b slurm/run.sh bash -c "$G")
L2=""; for n in v49_qwen38_core24b v49_qwen38_core24b_reasoning v49_qwen38_core24b_obfuscate qwen38_core24b qwen38_core24; do L2="$L2 python scripts/97_rubric_timeline.py revised=outputs/prereport/$n.parquet;"; done
e=$(sbatch --parsable -J v49_lab2_qw --dependency=afterany:$d slurm/run.sh bash -c "$L2")
echo "qwen chain: roll $a lab $b feat $c gen $d lab2 $e"
