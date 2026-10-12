#!/bin/bash
# v64 addendum 1: gpt-oss gate-then-ask rerun with transcripts and reports (tag _esc64; the v59d _esc result stays the
# confirmatory one). The v59d run's report stage hit CUDA OOM and its transcripts were not saved. Run via slurm/run.sh.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
[ "$(date +%H%M)" -lt 0805 ] || [ "${V64_NO_CLOCK:-0}" = 1 ] || { echo "v64_gptoss: too late for the 2nd-GPU window; not run (requeue in the main chain)"; exit 0; }
timeout 3h python scripts/160_v59b_gate_always.py actor=gptoss20b policy=escalate tag=_esc64 K=12 n_per_world=200 n_minus=100 report=true stage=run || echo "v64 gpt-oss rerun FAILED"
exit 0
