#!/usr/bin/env python
"""v52 EXPLORATORY (development data only; same pool as scripts/131, reserved confirmation sets excluded): can a richer internal
forecaster, built only from report-time features we already have, match or beat the supervised text forecaster?
Feature blocks (all 5 depths): pre_report, pre_m8 (the state before the report), honest, conceal (pre-report activations under an
appended honest / concealing instruction; label-free representation-engineering contrasts, no report token is read), and their
difference honest - conceal. report_m8 is NOT used (it reads the written report).
Candidates (scenario-grouped 5-fold CV, within-template AUROC):
  I_lda   : the confirmatory recipe (LDA, pre_report, one layer)
  E_lda   : ensemble = mean of z-scored LDA scores over every (block, layer) pair  [robust to which layer carries the signal]
  E_sel   : ensemble over the (block, layer) pairs whose inner-CV AUROC > 0.55 (selected inside each training fold)
  L_all   : PCA-256 + L2 logistic on all blocks concatenated
  T_full  : supervised text (TF-IDF + logistic), the comparison
Also learning curves: I_lda, E_lda, T_full trained on 25/50/100% of each training fold.
-> results/v52_explore/summary.json"""
import importlib.util
import json

import numpy as np
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.linear_model import LogisticRegressionCV
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from cape.utils.config import REPO_ROOT


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


E = _mod("e131", "scripts/131_v51_explore.py"); X95 = E.X95; BLOCKS = ("pre_report", "pre_m8", "honest", "conceal", "hc")


def load(model):
    import glob
    import pandas as pd
    J = E.load(model)
    Ms = []
    for p in sorted(glob.glob(str(REPO_ROOT / f"outputs/xm_feats/rep_{model}_*.npz"))):
        Z = np.load(p); M = pd.read_parquet(p.replace(".npz", "_meta.parquet"))[["set", "episode_id"]]
        M["X_h"] = list(Z["honest"].astype(np.float32)); M["X_c"] = list(Z["conceal"].astype(np.float32)); Ms.append(M)
    H = pd.concat(Ms).drop_duplicates(["set", "episode_id"])
    return J.merge(H, on=["set", "episode_id"], how="inner").reset_index(drop=True)


def block(J, b, li):
    if b == "pre_report":
        return np.stack([x[li] for x in J.X_pre])
    if b == "pre_m8":
        return np.stack([x[li] for x in J.X_m8])
    if b == "honest":
        return np.stack([x[li] for x in J.X_h])
    if b == "conceal":
        return np.stack([x[li] for x in J.X_c])
    return np.stack([h[li] - c[li] for h, c in zip(J.X_h, J.X_c)])


def lda_scores(Xtr, ytr, Xte):
    sc = StandardScaler().fit(Xtr); m = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(sc.transform(Xtr), ytr)
    s_tr, s_te = m.decision_function(sc.transform(Xtr)), m.decision_function(sc.transform(Xte))
    return (s_te - s_tr.mean()) / (s_tr.std() + 1e-9)


def ens(tr, te, select=False):
    out = []
    for b in BLOCKS:
        for li in range(5):
            Xtr, Xte = block(tr, b, li), block(te, b, li)
            if select:   # inner CV inside the training fold only
                y = tr.y.values; s = np.zeros(len(tr))
                for a, c in GroupKFold(3).split(Xtr, y, tr.scenario_id):
                    s[c] = lda_scores(Xtr[a], y[a], Xtr[c]) if y[a].sum() >= 2 else 0
                if X95.strat_auc(y, s, tr.template.values) <= 0.55:
                    continue
            out.append(lda_scores(Xtr, tr.y.values, Xte))
    return np.mean(out, 0) if out else np.zeros(len(te))


def l_all(tr, te):
    X = lambda d: np.concatenate([block(d, b, li) for b in BLOCKS for li in range(5)], 1)
    m = make_pipeline(StandardScaler(), PCA(n_components=min(256, len(tr) - 1), random_state=0),
                      LogisticRegressionCV(Cs=[0.001, 0.01, 0.1, 1], cv=3, max_iter=3000, class_weight="balanced"))
    return m.fit(X(tr), tr.y).decision_function(X(te))


def subsample(fit, frac, seed=0):
    def f(tr, te):
        if frac < 1:
            rng = np.random.default_rng(seed); keep = rng.random(len(tr)) < frac
            if tr.y[keep].sum() < 3:
                keep[np.where(tr.y.values == 1)[0][:3]] = True
            tr = tr[keep]
        return fit(tr, te)
    return f


def main():
    import sys
    only = [a.split("=")[1] for a in sys.argv if a.startswith("model=")]
    out = {}
    for model in (only or ("gemma4", "gptoss20b", "museglimmer", "qwen38")):
        J = load(model)
        if J.y.sum() < 10:
            continue
        y, st = J.y.values, J.template.values; li = E.SEL[model]["layer_index"]
        S = {"I_lda": E.oof(J, E.i_lda(li)), "E_lda": E.oof(J, lambda a, b: ens(a, b)), "E_sel": E.oof(J, lambda a, b: ens(a, b, True)),
             "L_all": E.oof(J, l_all), "T_full": E.oof(J, E.t_lr("full"))}
        res = {"n": int(len(J)), "lies": int(y.sum()), "auroc": {k: round(float(X95.strat_auc(y, v, st)), 3) for k, v in S.items()}}
        obf = (J.variant == "obfuscate").values
        if obf.sum() >= 30 and y[obf].sum() >= 5:
            res["obfuscate"] = {k: round(float(X95.strat_auc(y[obf], v[obf], st[obf])), 3) for k, v in S.items()}
        res["learning_curve"] = {}
        for frac in (0.25, 0.5):
            res["learning_curve"][str(frac)] = {k: round(float(X95.strat_auc(y, E.oof(J, subsample(f, frac)), st)), 3)
                                                 for k, f in (("I_lda", E.i_lda(li)), ("E_lda", lambda a, b: ens(a, b)), ("T_full", E.t_lr("full")))}
        out[model] = res; print(model, json.dumps(res), flush=True)
    o = REPO_ROOT / "results/v52_explore"; o.mkdir(parents=True, exist_ok=True)
    (o / (f"summary_{only[0]}.json" if only else "summary.json")).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
