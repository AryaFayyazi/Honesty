#!/usr/bin/env python
"""Prereg v32b: label-free target thresholds for the deployed two-channel gate (the v31 K6 rule at the v32 alpha).
Each branch's threshold = its (1 - alpha/2) quantile over ALL gate-scored actions of an unlabeled target run
(here the v32 shadow arm: x- and x+ episodes pooled, no outcome labels read).
python scripts/99_labelfree_thresholds.py [src=outputs/rollouts/cl_gptoss_shadow.parquet] [alpha=0.05]
"""
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"src": "outputs/rollouts/cl_gptoss_shadow.parquet", "alpha": 0.05, "out": "results/prereg_v32b/thresholds.json"})


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    S = pd.read_parquet(REPO_ROOT / cfg.src, columns=["events"])          # only the logged scores are read
    z = [json.loads(e["gate_z"]) for evs in S.events for e in evs if e["gate_z"]]
    a = np.array([x["_branch_auth"] for x in z]); u = np.array([x["_branch_unv"] for x in z]); q = 1 - cfg.alpha / 2
    out = {"thr_auth": float(np.quantile(a, q)), "thr_unv": float(np.quantile(u, q)), "quantile": q, "n_actions": int(len(a)), "src": cfg.src}
    o = REPO_ROOT / cfg.out; o.parent.mkdir(parents=True, exist_ok=True); json.dump(out, open(o, "w"), indent=1); print(out)


if __name__ == "__main__":
    main()
