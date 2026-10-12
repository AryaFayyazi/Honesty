#!/usr/bin/env python
"""Prereg v29 S4 placebo: the identical gate pipeline (scripts/65 gate/evaluate) with residual-stream features replaced by
one-hot(template) + one-hot(tool name) + one-hot(seed). Bounds how much gate TPR is template/tool base rate or seed.

python scripts/74_placebo_gate.py actor=gptoss20b bench=v2fresh
"""
import importlib.util
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config

spec = importlib.util.spec_from_file_location("ecg", REPO_ROOT / "scripts/65_epistemic_gate.py")
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
D = OmegaConf.create({"actor": "gptoss20b", "bench": "v2fresh"})


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    G.SEEDS = [0, 1]
    M, _ = G.load(cfg.actor, cfg.bench, "mean8", 2)
    sd = M.episode_id.str.extract(r"\.s(\d+)$")[0]
    X = pd.get_dummies(pd.DataFrame({"t": M.template, "tool": M.tool, "seed": sd})).values.astype(np.float32)
    X = X + np.random.default_rng(0).normal(0, 1e-3, X.shape).astype(np.float32)   # break exact collinearity for LDA
    scen = M.scenario_id.values; u = np.array(sorted(set(scen)))
    f = {s: i % 5 for i, s in enumerate(np.random.default_rng(0).permutation(u))}; folds = np.array([f[s] for s in scen])
    S = {}
    for k in range(5):
        tr, te = folds != k, folds == k
        g = G.gate(X[tr], M[tr].reset_index(drop=True), X[te])
        for a, v in g.items():
            S.setdefault(a, np.zeros(len(M)))[te] = v
    r = G.evaluate(S, M, folds)
    out = {"actor": cfg.actor, "bench": cfg.bench, "n_harm": int(M.harm.sum()),
           **{a: {"all": r[a]["all"], "informed": r[a]["informed"], "uninformed": r[a]["uninformed"],
                  "auroc": r[a]["auroc_harm_vs_compliant"]} for a in ("ecg", "mono")}}
    print(json.dumps(out, indent=1))
    p = REPO_ROOT / ("results/prereg_v29" if cfg.bench == "core24" else "results/prereg_v29_dry")
    p.mkdir(parents=True, exist_ok=True)
    (p / f"S4_placebo_{cfg.actor}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
