#!/usr/bin/env python
"""v58 analysis (CPU, main env). Prereg: docs/preregistration_v58.md. Reuses scripts/106 (paired McNemar, guards, degradation).
-> results/prereg_v58/confirm.json"""
import importlib.util
import json
import sys

import pandas as pd

from cape.utils.config import REPO_ROOT


def main():
    s = importlib.util.spec_from_file_location("a106", REPO_ROOT / "scripts/106_v41.py"); sys.argv = [sys.argv[0], "tag=v58"]
    a = importlib.util.module_from_spec(s); s.loader.exec_module(a)
    W = a.table("v58C"); S = pd.read_parquet(REPO_ROOT / "outputs/reconcile/v58C.parquet")
    P1 = a.paired(W, "none", "d16"); P2 = a.paired(W, "rand_d16", "d16")
    ps = {"P1": P1["p_one_sided"], "P2": P2["p_one_sided"]}; o = sorted(ps, key=ps.get); h, run = {}, 0.0
    for i, k in enumerate(o):
        run = max(run, min(1.0, (len(o) - i) * ps[k])); h[k] = run
    g = a.guards(W, "d16")
    q = a.paired(W, "d16", "q16"); M2 = dict(q, p_two_sided=min(1.0, 2 * min(q["p_one_sided"], 1 - q["p_one_sided"] + 1e-12)))
    out = {"P1_d16_vs_none": P1, "P2_d16_vs_random": P2, "holm": h, "guards_d16": g, "CLAIM_replication": bool(h["P1"] < 0.05 and h["P2"] < 0.05 and g["ok"]),
           "M1_q16_vs_none": a.paired(W, "none", "q16"), "M2_q16_vs_d16": M2, "guards_q16": a.guards(W, "q16"),
           "degradation": {c: a.degradation(W, S, c) for c in ("d16", "q16", "rand_d16")},
           "sensitivity_noreport_as_nonlie": {c: a.paired(W.replace({"NO_REPORT": "OMITTED"}), "none", c) for c in ("d16", "q16")},
           "candid_rate": {c: round(float((W[c] == "CANDID").mean()), 3) for c in W.columns},
           "label_dist": {c: W[c].value_counts(normalize=True).round(3).to_dict() for c in W.columns}}
    o = REPO_ROOT / "results/prereg_v58"; o.mkdir(parents=True, exist_ok=True); json.dump(out, open(o / "confirm.json", "w"), indent=2, default=str)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
