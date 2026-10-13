#!/bin/bash
# v78 (prereg docs/preregistration_v78.md): gate-then-ask with the LIVE model approver (v67 escalation approver; Qwen, same weights,
# greedy, unsteered); escalated asks go to the environment's approval channel. Qwen agent; 100 x- + 200 x+ v54 confirmation sites, K=12;
# paired none_hf in the same run; reports judged (as the channel-approver run, tag _esc64). Run via slurm/run.sh.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
timeout 20h python scripts/160_v59b_gate_always.py actor=qwen38 policy=escalate_model tag=_escmodel K=12 n_per_world=200 n_minus=100 report=true stage=run || echo "v78 run FAILED"
python scripts/160_v59b_gate_always.py actor=qwen38 tag=_escmodel K=12 stage=analyze_tag || echo "v78 D1/D2' analysis FAILED"
python scripts/202_v78_live_approver.py || echo "v78 approver analysis FAILED"
exit 0
