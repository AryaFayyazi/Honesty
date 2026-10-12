#!/usr/bin/env python
"""Prereg v51: freeze every forecaster on DEVELOPMENT data before any confirmation label exists.
Per model (gemma4, gptoss20b, museglimmer, qwen38), using the development pool of scripts/131 (all labelled informed episodes with
report-time features, reserved confirmation sets excluded):
  I      : internal forecaster = the better of I_lda / I_lr by development CV within-template AUROC (ties -> I_lda); refit on all dev
  T_sup  : supervised text forecaster (TF-IDF + logistic, full pre-report text incl. reasoning); refit on all dev
  S      : stack = logistic regression on the z-scored OOF dev scores [I, T_sup] (standardisation constants frozen)
-> results/prereg_v51/frozen_<model>.joblib, results/prereg_v51/freeze_summary.json"""
import importlib.util
import json

import joblib
import numpy as np
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from cape.utils.config import REPO_ROOT


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


E = _mod("e131", "scripts/131_v51_explore.py"); X95 = E.X95
O = REPO_ROOT / "results/prereg_v51"; O.mkdir(parents=True, exist_ok=True)


def xi_lr(d):
    return np.concatenate([np.stack(list(d.X_pre)).reshape(len(d), -1), np.stack(list(d.X_m8)).reshape(len(d), -1)], 1)


def main():
    summ = {}
    for model in ("gemma4", "gptoss20b", "museglimmer", "qwen38"):
        J = E.load(model); li = E.SEL[model]["layer_index"]; y = J.y.values; st = J.template.values
        s_lda, s_lr, s_t = E.oof(J, E.i_lda(li)), E.oof(J, E.i_lr), E.oof(J, E.t_lr("full"))
        a_lda, a_lr, a_t = (float(X95.strat_auc(y, s, st)) for s in (s_lda, s_lr, s_t))
        kind = "I_lr" if a_lr > a_lda else "I_lda"; s_i = s_lr if kind == "I_lr" else s_lda
        if kind == "I_lda":
            Xd = np.stack([x[li] for x in J.X_pre]); sc = StandardScaler().fit(Xd)
            I = {"kind": kind, "layer_index": li, "scaler": sc, "model": LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(sc.transform(Xd), y)}
        else:
            I = {"kind": kind, "model": make_pipeline(StandardScaler(), PCA(n_components=min(256, len(J) - 1), random_state=0),
                                                       LogisticRegressionCV(Cs=[0.001, 0.01, 0.1, 1], cv=3, max_iter=3000, class_weight="balanced")).fit(xi_lr(J), y)}
        v = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=50000, sublinear_tf=True)
        T = {"tfidf": v.fit(J.full), "model": LogisticRegressionCV(Cs=[0.1, 1, 10], cv=3, max_iter=3000, class_weight="balanced").fit(v.transform(J.full), y)}
        zc = {"i": (float(s_i.mean()), float(s_i.std() + 1e-9)), "t": (float(s_t.mean()), float(s_t.std() + 1e-9))}
        Zs = np.stack([(s_i - zc["i"][0]) / zc["i"][1], (s_t - zc["t"][0]) / zc["t"][1]], 1)
        S = LogisticRegression(C=1.0, max_iter=1000).fit(Zs, y)
        a_s = float(X95.strat_auc(y, S.decision_function(Zs), st))
        joblib.dump({"I": I, "T": T, "S": S, "zc": zc, "n_dev": int(len(J)), "lies_dev": int(y.sum())}, O / f"frozen_{model}.joblib")
        summ[model] = {"n_dev": int(len(J)), "lies_dev": int(y.sum()), "dev_cv_auroc": {"I_lda": round(a_lda, 4), "I_lr": round(a_lr, 4), "T_sup": round(a_t, 4),
                       "stack_in_sample_on_oof": round(a_s, 4)}, "chosen_internal": kind, "stack_coef": [round(float(c), 3) for c in S.coef_[0]]}
        print(model, summ[model], flush=True)
    (O / "freeze_summary.json").write_text(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
