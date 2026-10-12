#!/usr/bin/env python
"""v66 dissociation (prereg docs/preregistration_v66.md, descriptive; prediction stated before data): on none-arm τ² runs with
shadow gate scores, does the FROZEN CAPE gate separate informed violating writes (after the oracle answered NOT ALLOWED) from
authorized writes better than it separates uninformed violating writes from authorized writes?
  AUROC within write tool (>= 3 per class per tool, weighted by n; pooled if no tool qualifies), and the difference
  informed - uninformed with a task-cluster bootstrap 95% CI.
python scripts/180_v66_dissociation.py runs=v66_screen_qwen38_P0_orc,... logs=outputs/v65/server_v66_screen_qwen38_P0_orc.jsonl,...
  -> results/prereg_v66/dissociation.json"""
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"runs": "", "logs": "", "B": 4000, "out": "results/prereg_v66/dissociation.json"})
OUT = REPO_ROOT / "outputs/v65"


def auc(y, s):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s)) if len(set(y)) == 2 else float("nan")


def auc_within(df, pos):
    """AUROC of `pos` violating writes vs AUTHORIZED writes, within write tool (weighted by n); pooled fallback."""
    d = df[df.label_inf.isin([pos, "AUTHORIZED"])]; vals, w = [], []
    for _, g in d.groupby("tool"):
        y = (g.label_inf == pos).astype(int)
        if y.sum() >= 3 and (1 - y).sum() >= 3:
            vals.append(auc(y, g.score)); w.append(len(g))
    if vals:
        return float(np.average(vals, weights=w)), "within_tool", int(sum(w))
    return auc((d.label_inf == pos).astype(int), d.score), "pooled", int(len(d))


def main(cfg):
    L = pd.concat([pd.read_csv(OUT / f"labels_{r}.csv").assign(run=r) for r in str(cfg.runs).split(",")], ignore_index=True)
    S = pd.concat([pd.read_json(REPO_ROOT / g, lines=True) for g in str(cfg.logs).split(",")], ignore_index=True)
    S = S[S.call_id.notna()].drop_duplicates("call_id").set_index("call_id")
    L["score"] = L.tool_call_id.map(S.score); L = L[L.score.notna()].copy(); L["cluster"] = L.run + "|" + L.task_id.astype(str)
    out = {"runs": str(cfg.runs), "n_writes_scored": int(len(L)), "counts": L.label_inf.value_counts().to_dict()}
    for pos in ("VIOLATION_INF", "VIOLATION_UNINF"):
        a, how, n = auc_within(L, pos); out[pos] = {"auroc": a, "basis": how, "n": n}
    rng = np.random.default_rng(66); cl = L.cluster.unique(); g = {c: d for c, d in L.groupby("cluster")}; diffs = []
    for _ in range(cfg.B):
        d = pd.concat([g[c] for c in rng.choice(cl, len(cl))])
        ai, _, _ = auc_within(d, "VIOLATION_INF"); au, _, _ = auc_within(d, "VIOLATION_UNINF")
        if not (np.isnan(ai) or np.isnan(au)):
            diffs.append(ai - au)
    if diffs:
        out["informed_minus_uninformed"] = {"diff": out["VIOLATION_INF"]["auroc"] - out["VIOLATION_UNINF"]["auroc"],
                                            "ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
                                            "p_one_sided": float((np.sum(np.array(diffs) <= 0) + 1) / (len(diffs) + 1)), "n_boot_valid": len(diffs)}
    (REPO_ROOT / cfg.out).parent.mkdir(parents=True, exist_ok=True); json.dump(out, open(REPO_ROOT / cfg.out, "w"), indent=2); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(OmegaConf.merge(D, load_config(None)))
