#!/bin/bash
# v62 (prereg docs/preregistration_v62.md): internal gate vs CoT-monitor gate at matched false alarms. Run via slurm/run.sh.
set -uo pipefail
timeout 4h python scripts/168_v62_cot_gate.py stage=monitor || { echo "v62 monitor FAILED"; exit 0; }
python scripts/168_v62_cot_gate.py stage=analyze || echo "v62 analysis FAILED"
exit 0
