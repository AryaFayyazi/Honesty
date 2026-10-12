#!/usr/bin/env python
"""Descriptive per-model breakdown of the v37 F1 endpoint (same episodes and labels as scripts/98 stage=confirm).
Not a new test: the preregistered F1 is pooled CMH. Output: results/prereg_v37/f1_by_model.json"""
import importlib.util, json
import numpy as np
from omegaconf import OmegaConf
from statsmodels.stats.proportion import proportion_confint
from cape.utils.config import REPO_ROOT, load_config
s = importlib.util.spec_from_file_location("a98", REPO_ROOT / "scripts/98_v37_analysis.py"); a98 = importlib.util.module_from_spec(s); s.loader.exec_module(a98)
F = a98.episodes(OmegaConf.merge(a98.D, load_config(None))); C = F[(F.informed == 1) & F.C]
def rate(g):
    k, n = int(g.y.sum()), len(g)
    return {"k": k, "n": n, "rate": round(k / n, 3) if n else None, "wilson95": [round(x, 3) for x in proportion_confint(k, n, method="wilson")] if n else None}
out = {"pooled": {"retro": rate(C[C.retro == 1]), "noretro": rate(C[C.retro == 0])}}
for m, g in C.groupby("model"):
    out[m] = {"n_informed": len(g), "retro_share": round(float(g.retro.mean()), 3), "retro": rate(g[g.retro == 1]), "noretro": rate(g[g.retro == 0])}
json.dump(out, open(REPO_ROOT / "results/prereg_v37/f1_by_model.json", "w"), indent=1); print(json.dumps(out, indent=1))
