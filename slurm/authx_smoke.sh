#!/bin/bash
# prereg v26 s.3: x+ validity smoke (authx, seed 0) -> then CPU: python scripts/46_authx.py stage=smoke
set -uo pipefail
sha256sum -c results/v26_prereg.sha256 || { echo "V26 LOCK MISMATCH"; exit 1; }
python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=authx out_name=authx_smoke_plus "seeds=[0]" "cf_values=[safe]" || echo "AUTHX SMOKE FAILED"
python scripts/46_authx.py stage=smoke || true
