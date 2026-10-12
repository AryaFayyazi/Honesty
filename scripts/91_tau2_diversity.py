#!/usr/bin/env python
"""EXPLORATORY (tau2 results already known): does training-task diversity improve zero-shot transfer to published
frontier-agent trajectories (tau2-bench airline)? Theorem 2 / H4 predict OOD transfer improves with more task families.

python scripts/91_tau2_diversity.py
Same Qwen3.8-reader feature space (`mean8`, layer index 2). Training sets:
  A (8 templates):  v2fresh  qwen38 + rdqwen-{gemma4, gptoss20b, museglimmer}         (= v30 X1)
  B (24 templates): A + core24 qwen38 (own) + rdqwen-gptoss20b core24
Probes: v29 ECG / monolithic / auth-only (scripts/65 gate). Metric: AUROC NOT ALLOWED vs ALLOWED tau2 writes with a
task-cluster bootstrap; paired bootstrap of B - A.
"""
import importlib.util
import json

import numpy as np
import pandas as pd

from cape.eval.statistics import auroc
from cape.utils.config import REPO_ROOT

spec = importlib.util.spec_from_file_location("ecg", REPO_ROOT / "scripts/65_epistemic_gate.py")
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)


def pool(sets):
    Ms, Xs = [], []
    for a, b in sets:
        G.SEEDS = [0, 1]
        M, X = G.load(a, b, "mean8", 2); M["scenario_id"] = f"{a}|{b}|" + M.scenario_id; Ms.append(M); Xs.append(X)
    return pd.concat(Ms, ignore_index=True), np.concatenate(Xs)


def main():
    T = pd.read_parquet(REPO_ROOT / "outputs/xm_feats/tau2_rdqwen_meta.parquet")
    XT = np.load(REPO_ROOT / "outputs/xm_feats/tau2_rdqwen.npz")["mean8"][:, 2].astype(np.float32)
    k = T.label.isin(["NOT_ALLOWED", "ALLOWED"]).values; T, XT = T[k].reset_index(drop=True), XT[k]
    y = (T.label == "NOT_ALLOWED").values.astype(int); tasks = T.task_id.astype(str).values
    A = [("qwen38", "v2fresh"), ("rdqwen-gemma4", "v2fresh"), ("rdqwen-gptoss20b", "v2fresh"), ("rdqwen-museglimmer", "v2fresh")]
    B = A + [("qwen38", "core24"), ("rdqwen-gptoss20b", "core24")]
    S = {}
    for nm, sets in (("A_8tpl", A), ("B_24tpl", B)):
        M, X = pool(sets); g = G.gate(X, M, XT)
        S[nm] = {arm: g[arm] for arm in ("ecg", "mono", "auth_only")}
        print(nm, {arm: round(float(auroc(y, s)), 4) for arm, s in S[nm].items()}, "n_train", len(M), flush=True)
    rng = np.random.default_rng(0); u = np.unique(tasks); idx = {t: np.where(tasks == t)[0] for t in u}; out = {}
    for arm in ("ecg", "mono", "auth_only"):
        a, b = S["A_8tpl"][arm], S["B_24tpl"][arm]; d = []
        for _ in range(2000):
            p = np.concatenate([idx[t] for t in rng.choice(u, len(u))])
            if 0 < y[p].sum() < len(p):
                d.append(auroc(y[p], b[p]) - auroc(y[p], a[p]))
        out[arm] = {"A_8tpl": round(float(auroc(y, a)), 4), "B_24tpl": round(float(auroc(y, b)), 4), "B_minus_A": round(float(np.mean(d)), 4),
                    "ci95": [round(float(np.quantile(d, .025)), 4), round(float(np.quantile(d, .975)), 4)]}
    print(json.dumps(out, indent=1)); (REPO_ROOT / "results/v30/tau2_diversity_exploratory.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
