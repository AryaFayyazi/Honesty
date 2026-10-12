#!/bin/bash
# prereg v26 main run (5,184 episodes). Refuses to start before the x+ validity smoke was read and approved.
set -uo pipefail
test -f results/v26/SMOKE_OK || { echo "NO results/v26/SMOKE_OK - skipping v26 main run"; exit 0; }
sha256sum -c results/v26_prereg.sha256 || { echo "V26 LOCK MISMATCH"; exit 1; }
for s in authx authxenf authxorc authxorcenf; do
  python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=$s out_name=${s}_minus "seeds=[0,1,2,3,4,5,6,7]" "cf_values=[unsafe]" || echo "V26 FAILED ${s}_minus"
done
for s in authx authxorc; do
  python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=$s out_name=${s}_plus "seeds=[0,1]" "cf_values=[safe]" || echo "V26 FAILED ${s}_plus"
done
python scripts/46_authx.py stage=audit || true
