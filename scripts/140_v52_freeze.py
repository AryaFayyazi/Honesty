#!/usr/bin/env python
"""Prereg v52 (stronger internal forecaster): freeze, on DEVELOPMENT data only, the internal recipe chosen per model by the rule fixed
before the exploration finished: highest development-CV within-template AUROC among {I_lda, E_lda, E_sel, L_all}
(results/v52_explore/summary_<model>.json; ties -> simpler: I_lda < E_lda < E_sel < L_all).
Refits the chosen recipe on all development episodes and stores what is needed to score fresh episodes.
-> results/prereg_v52/frozen_<model>.joblib, results/prereg_v52/choice.json
Confirmation (scripts/134-style, on the v51 fresh sets): chosen internal vs T_sup (v51 frozen) pooled within-template AUROC, one-sided
paired cluster bootstrap; stack vs T_sup."""
import importlib.util
import json

import joblib
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


X = _mod("x137", "scripts/137_v52_explore.py"); E = X.E; X95 = E.X95
ORDER = ["I_lda", "E_lda", "E_sel", "L_all"]; O = REPO_ROOT / "results/prereg_v52"


def fit_lda(Xtr, y):
    """Compact linear readout (2026-10-06 fix: storing sklearn LDA objects kept a d x d covariance per part and filled the disk).
    score = X @ w + b equals lda.decision_function(scaler.transform(X)) exactly."""
    sc = StandardScaler().fit(Xtr); m = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(sc.transform(Xtr), y)
    w = (m.coef_[0] / sc.scale_).astype(np.float32); b = float(m.intercept_[0] - (m.coef_[0] * sc.mean_ / sc.scale_).sum())
    s = Xtr @ w + b; return {"w": w, "b": b, "mu": float(s.mean()), "sd": float(s.std() + 1e-9)}


def main():
    O.mkdir(parents=True, exist_ok=True); choice = {}
    for model in ("gemma4", "gptoss20b", "museglimmer", "qwen38"):
        f = REPO_ROOT / f"results/v52_explore/summary_{model}.json"
        if not f.exists():
            continue
        r = json.load(open(f))[model]["auroc"]; best = max(ORDER, key=lambda k: (round(r[k], 3), -ORDER.index(k)))
        J = X.load(model); y = J.y.values; li = E.SEL[model]["layer_index"]; art = {"kind": best}
        if best == "I_lda":
            art["parts"] = [("pre_report", li, fit_lda(X.block(J, "pre_report", li), y))]
        elif best in ("E_lda", "E_sel"):
            parts = []
            for b in X.BLOCKS:
                for l in range(5):
                    Xb = X.block(J, b, l)
                    if best == "E_sel":
                        s = np.zeros(len(J))
                        for a, c in GroupKFold(3).split(Xb, y, J.scenario_id):
                            s[c] = X.lda_scores(Xb[a], y[a], Xb[c]) if y[a].sum() >= 2 else 0
                        if X95.strat_auc(y, s, J.template.values) <= 0.55:
                            continue
                    parts.append((b, l, fit_lda(Xb, y)))
            art["parts"] = parts
        else:
            Xa = np.concatenate([X.block(J, b, l) for b in X.BLOCKS for l in range(5)], 1)
            art["model"] = make_pipeline(StandardScaler(), PCA(n_components=min(256, len(J) - 1), random_state=0),
                                         LogisticRegressionCV(Cs=[0.001, 0.01, 0.1, 1], cv=3, max_iter=3000, class_weight="balanced")).fit(Xa, y)
        # low-label versions (V2): the identical 25% development subsample as scripts/137 (rng seed 0), chosen recipe and T_sup
        rng = np.random.default_rng(0); keep = rng.random(len(J)) < 0.25
        if J.y[keep].sum() < 3:
            keep[np.where(y == 1)[0][:3]] = True
        Jl = J[keep].reset_index(drop=True); yl = Jl.y.values; low = {"kind": best, "n": int(len(Jl)), "lies": int(yl.sum())}
        if best == "L_all":
            Xl = np.concatenate([X.block(Jl, b, l) for b in X.BLOCKS for l in range(5)], 1)
            low["model"] = make_pipeline(StandardScaler(), PCA(n_components=min(256, len(Jl) - 1), random_state=0),
                                         LogisticRegressionCV(Cs=[0.001, 0.01, 0.1, 1], cv=3, max_iter=3000, class_weight="balanced")).fit(Xl, yl)
        else:
            low["parts"] = [(b, l, fit_lda(X.block(Jl, b, l), yl)) for (b, l, _) in art["parts"]]
        from sklearn.feature_extraction.text import TfidfVectorizer
        v = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=50000, sublinear_tf=True).fit(Jl.full)
        low["T"] = {"tfidf": v, "model": LogisticRegressionCV(Cs=[0.1, 1, 10], cv=3, max_iter=3000, class_weight="balanced").fit(v.transform(Jl.full), yl)}
        art["low"] = low
        joblib.dump(art, O / f"frozen_{model}.joblib"); choice[model] = {"chosen": best, "dev_cv": r, "n_parts": len(art.get("parts", [])), "low_label_n": low["n"], "low_label_lies": low["lies"]}
        print(model, choice[model], flush=True)
    (O / "choice.json").write_text(json.dumps(choice, indent=1))


if __name__ == "__main__":
    main()
