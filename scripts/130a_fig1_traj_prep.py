#!/usr/bin/env python
"""Figure 1(a) prep (CPU, main env): rebuild the CONFIRMATORY pre-report lie forecasters (v37 F2a; scripts/98 confirm path:
frozen per-model position/layer from results/v37_explore/f2_selection.json, StandardScaler + shrinkage LDA fit on development
informed episodes, applied to the fresh confirmation set C) and verify they reproduce the locked F2a AUROC (0.7446) before use.
Saves each model's forecaster as a raw-space linear readout (w, b) plus the C-set z-score constants.
-> outputs/reconcile/fig1_traj_prep.npz, fig1_traj_episodes.parquet"""
import importlib.util, json
import numpy as np, pandas as pd
from omegaconf import OmegaConf
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.preprocessing import StandardScaler
from cape.utils.config import REPO_ROOT, load_config
s = importlib.util.spec_from_file_location("a98", REPO_ROOT / "scripts/98_v37_analysis.py"); a98 = importlib.util.module_from_spec(s); s.loader.exec_module(a98)
F = a98.episodes(OmegaConf.merge(a98.D, load_config(None))); sel = json.load(open(REPO_ROOT / "results/v37_explore/f2_selection.json"))
out, parts, eps = {}, [], []
for model, sm in sel.items():
    J = a98.joined(F, model)
    if J is None or "position" not in sm:
        continue
    J = J[J.informed == 1]; Dv, Cv = J[~J.C], J[J.C]
    if not len(Cv):
        continue
    li, pos = sm["layer_index"], sm["position"]
    Xd = np.stack([a[li] for a in Dv[f"_{pos}"]]); Xc = np.stack([a[li] for a in Cv[f"_{pos}"]])
    sc = StandardScaler().fit(Xd); m = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(sc.transform(Xd), Dv.y.values)
    w = m.coef_[0] / sc.scale_; b = float(m.intercept_[0] - (m.coef_[0] * sc.mean_ / sc.scale_).sum()); s_c = Xc @ w + b
    assert np.allclose(s_c, m.decision_function(sc.transform(Xc)), atol=1e-3)
    out.update({f"{model}_w": w.astype(np.float32), f"{model}_b": np.float32(b), f"{model}_li": li, f"{model}_pos": pos,
                f"{model}_mu": np.float32(s_c.mean()), f"{model}_sd": np.float32(s_c.std() + 1e-9)})
    z = (s_c - s_c.mean()) / (s_c.std() + 1e-9)
    parts.append(Cv[["model", "template", "scenario_id", "y"]].assign(f2=z)); eps.append(Cv[["set", "episode_id", "model", "template", "y", "retro"]])
P = pd.concat(parts, ignore_index=True); auc = a98.strat_auc(P.y, P.f2, P.model + "|" + P.template)
locked = json.load(open(REPO_ROOT / "results/prereg_v37/summary_full.json"))["F2"]["F2a"]["within_template_auroc"]
print("reproduced F2a", round(float(auc), 4), "locked", locked, "n", len(P), "lies", int(P.y.sum()))
assert abs(auc - locked) < 1e-3, "does not reproduce the confirmatory F2a; do not use"
np.savez(REPO_ROOT / "outputs/reconcile/fig1_traj_prep.npz", **out); pd.concat(eps).to_parquet(REPO_ROOT / "outputs/reconcile/fig1_traj_episodes.parquet")
print({k: v for k, v in out.items() if k.endswith(("_li", "_pos"))})
