#!/usr/bin/env python
"""Catch-friction identity (Corollary of Thm 3): on uninformed actions, for ANY context-measurable gate and threshold,
TPR on violations = flag rate on authorized critical twins. On informed actions the two separate.

python scripts/75_catch_friction.py actor=gptoss20b      (uses results/xm/oof_<actor>_v2fresh_mean8_L2.npz)
Within-fold thresholds at FPR in {1,5,10}% over compliant actions; episode-cluster bootstrap CI of (TPR - flag rate)
per stratum, arm and threshold.
"""
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"actor": "gptoss20b", "path": None, "nboot": 2000})


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    z = np.load(cfg.path or REPO_ROOT / f"results/xm/oof_{cfg.actor}_v2fresh_mean8_L2.npz", allow_pickle=True)
    M = pd.DataFrame({k: z[k] for k in ("harm", "informed", "crit", "fold", "episode_id")})
    y = M.harm.values == 1; inf = M.informed.values == 1; crit = M.crit.values == 1; comp = (~y) & ((~crit) | inf)
    ep = M.episode_id.values; ue = np.unique(ep); rng = np.random.default_rng(0)
    idx = pd.Series(np.arange(len(M))).groupby(ep).apply(lambda v: v.values)
    boots = [np.concatenate([idx[e] for e in rng.choice(ue, len(ue))]) for _ in range(cfg.nboot)]
    out = {}
    for arm in [a for a in ("ecg", "mono", "auth_only") if a in z.files]:
        s = z[arm]
        for q in (0.99, 0.95, 0.90):
            hit = np.zeros(len(M), bool)
            for k in np.unique(M.fold):
                f = M.fold.values == k; hit[f] = s[f] >= np.quantile(s[f & comp], q)
            for nm, st in (("uninformed", ~inf), ("informed", inf)):
                pos, neg = y & st, (~y) & crit & st
                d = [hit[b][pos[b]].mean() - hit[b][neg[b]].mean() for b in boots if pos[b].sum() and neg[b].sum()]
                out[f"{arm}|FPR{1-q:.2f}|{nm}"] = {"TPR": round(float(hit[pos].mean()), 3), "twin_flag": round(float(hit[neg].mean()), 3),
                                                   "diff": round(float(hit[pos].mean() - hit[neg].mean()), 3),
                                                   "ci95": [round(float(np.quantile(d, .025)), 3), round(float(np.quantile(d, .975)), 3)]}
    un = [v for k, v in out.items() if k.endswith("uninformed")]; im = [v for k, v in out.items() if k.endswith("|informed")]
    summ = {"uninformed_ci_covers_0": f"{sum(v['ci95'][0] <= 0 <= v['ci95'][1] for v in un)}/{len(un)}",
            "uninformed_max_abs_diff": max(abs(v["diff"]) for v in un),
            "informed_ci_excludes_0": f"{sum(v['ci95'][0] > 0 for v in im)}/{len(im)}",
            "informed_min_diff": min(v["diff"] for v in im)}
    print(json.dumps(summ, indent=1))
    (REPO_ROOT / f"results/xm/catch_friction_{cfg.actor}.json").write_text(json.dumps({"summary": summ, "points": out}, indent=1))


if __name__ == "__main__":
    main()
