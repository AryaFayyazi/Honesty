#!/usr/bin/env python
"""Prereg v24 health gate (format only): parse-error turn share <= 20% and final-answer share >= 50% in the smoke run."""
import json
import sys

import pandas as pd

from cape.utils.config import REPO_ROOT

rows = {}
for a in sys.argv[1:] or ["qwen3_4b", "qwen3_8b", "qwen3_14b", "qwen3_32b", "llama33_70b"]:
    p = REPO_ROOT / f"outputs/rollouts/v24smoke_{a}.parquet"
    if not p.exists():
        rows[a] = {"pass": False, "reason": "no smoke output"}
        continue
    e = pd.read_parquet(p)
    turns = [t for ev in e.events for t in ev]
    pe = sum(t["parse_error"] is not None for t in turns) / max(1, len(turns))
    fa = float((e.status == "final_answer").mean())
    rows[a] = {"parse_error_turn_share": round(pe, 3), "final_answer_share": round(fa, 3), "n_episodes": len(e),
               "status": e.status.value_counts().to_dict(), "pass": bool(pe <= 0.20 and fa >= 0.50)}
print(json.dumps(rows, indent=2))
(REPO_ROOT / "results/v24").mkdir(parents=True, exist_ok=True)
(REPO_ROOT / "results/v24/health_gate.json").write_text(json.dumps(rows, indent=2))
