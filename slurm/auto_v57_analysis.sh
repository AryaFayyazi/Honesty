#!/bin/bash
# runs the v57 analysis only when the extraction job SUCCEEDED and every fresh feature file + monitor output exists
cd /home/arya/new_safety/cape; source .venv/bin/activate; mkdir -p results/prereg_v57
while squeue -h -j 3474 2>/dev/null | grep -q .; do sleep 120; done
python - <<'PY' || { echo "v57 inputs incomplete; analysis NOT run" > results/prereg_v57/analysis.log; exit 0; }
import os, sys
need=["xm_gemma4_core24b_minus6789","xm_gemma4_core24b_minus10111213","xm_gemma4_core24b_reasoning_minus6789","xm_gemma4_core24b_obfuscate_minus10111213",
      "xm_gptoss20b_core24b_minus6789","xm_gptoss20b_core24b_minus10111213","xm_gptoss20b_core24b_reasoning_minus6789","xm_gptoss20b_core24b_obfuscate_minus10111213",
      "xm_qwen38_core24b_minus2345","xm_qwen38_core24b_reasoning_minus0123","xm_qwen38_core24b_obfuscate_minus0123",
      "xm_museglimmer_core24b_minus89","xm_museglimmer_core24b_minus1011","xm_museglimmer_core24b_minus1213","xm_museglimmer_core24b_minus1415"]
miss=[n for n in need if not os.path.exists(f"outputs/xm_feats/{n}.npz")]+[m for m in ["gemma4","gptoss20b","museglimmer","qwen38"] if not os.path.exists(f"outputs/v57/monitor_{m}.parquet")]
print("missing", miss); sys.exit(1 if miss else 0)
PY
python scripts/155_v57_analysis.py > results/prereg_v57/analysis.log 2>&1 || echo "v57 analysis FAILED" >> results/prereg_v57/analysis.log
