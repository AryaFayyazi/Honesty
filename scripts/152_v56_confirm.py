#!/usr/bin/env python
"""v56 report-anchored steering (CPU, main env). Prereg: docs/preregistration_v56.md.
stage=check run=<name>: built-in validity check: with the same seed and batch, each steered r0 generation must equal the unsteered
    one up to and including the report marker (reasoning untouched). Valid if >= 80% of episodes with a report marker in both.
stage=confirm: S1 lie(r0) < none, S2 lie(r0) < random (exact one-sided McNemar, complete case, Holm), guards, degradation guard;
    secondary d16 replication, r0 vs d16, NO_REPORT sensitivity, CANDID rate. -> results/prereg_v56/confirm.json
python scripts/152_v56_confirm.py stage=check run=v56devA"""
import importlib.util
import json
import sys

import pandas as pd

from cape.utils.config import REPO_ROOT

MARK = "to=user<|message|>"; RES = REPO_ROOT / "results/prereg_v56"


def arg(k, d=None):
    return next((a.split("=", 1)[1] for a in sys.argv if a.startswith(k + "=")), d)


def check(run):
    R = pd.read_parquet(REPO_ROOT / f"outputs/reconcile/{run}.parquet"); key = ["set", "episode_id", "fold"]
    base = R[R.message == "none"].set_index(key).raw_generation; out = {}
    for m in sorted(R.message.unique()):
        if m == "none" or "_r0" not in m and not m.startswith(("chosen", "rand_chosen")):
            continue
        g = R[R.message == m].set_index(key).raw_generation; n = same = 0
        for k, t in g.items():
            b = base.get(k)
            if b is None or MARK not in t or MARK not in b:
                continue
            n += 1; same += t[: t.index(MARK) + len(MARK)] == b[: b.index(MARK) + len(MARK)]
        out[m] = {"n_with_marker": n, "identical_prefix_share": round(same / n, 3) if n else None, "valid": bool(n and same / n >= 0.8)}
    RES.mkdir(parents=True, exist_ok=True); json.dump(out, open(RES / f"check_{run}.json", "w"), indent=2); print(out)
    assert all(v["valid"] for v in out.values()), "v56 validity check failed: reasoning changed under report-anchored steering"


def confirm():
    s = importlib.util.spec_from_file_location("a106", next((REPO_ROOT / "scripts").glob("106*.py")))
    sys.argv = [a for a in sys.argv if not a.startswith("tag=")] + ["tag=v56"]; a = importlib.util.module_from_spec(s); s.loader.exec_module(a)
    from scipy.stats import binomtest  # noqa: F401  (used inside a106.paired)
    W = a.table("v56C"); S = pd.read_parquet(REPO_ROOT / "outputs/reconcile/v56C.parquet")
    S1 = a.paired(W, "none", "chosen"); S2 = a.paired(W, "rand_chosen", "chosen")
    ps = {"S1": S1["p_one_sided"], "S2": S2["p_one_sided"]}; o = sorted(ps, key=ps.get); h, run = {}, 0.0
    for i, k in enumerate(o):
        run = max(run, min(1.0, (len(o) - i) * ps[k])); h[k] = run
    g = a.guards(W, "chosen"); d = a.degradation(W, S, "chosen")
    Wn = W.replace({"NO_REPORT": "OMITTED"})
    out = {"S1_vs_none": S1, "S2_vs_random": S2, "holm": h, "guards": g, "degradation": d,
           "CLAIM": bool(h["S1"] < 0.05 and h["S2"] < 0.05 and g["ok"] and d["ok"]),
           "secondary": {"d16_replication_vs_none": a.paired(W, "none", "v46rep") if "v46rep" in W else None,
                         "r0_vs_d16": a.paired(W, "v46rep", "chosen") if "v46rep" in W else None,
                         "d16_degradation": a.degradation(W, S, "v46rep") if "v46rep" in W else None,
                         "sensitivity_noreport_as_nonlie": a.paired(Wn, "none", "chosen"),
                         "candid_rate": {c: round(float((W[c] == "CANDID").mean()), 3) for c in W.columns}}}
    RES.mkdir(parents=True, exist_ok=True); json.dump(out, open(RES / "confirm.json", "w"), indent=2, default=str); print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    {"check": lambda: check(arg("run")), "confirm": confirm}[arg("stage")]()
