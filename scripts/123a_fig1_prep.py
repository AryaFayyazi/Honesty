#!/usr/bin/env python
"""Figure 1 prep (main env, CPU): effective lie-forecast direction of the v40 frozen forecaster (trained on 534 development
episodes BEFORE the fresh steering episodes existed -> out-of-sample here) in raw residual space, and the episode table
(v46 fresh episodes, none / caa_p8_d16 reports, rubric-v4 labels). -> outputs/reconcile/fig1_prep.npz, fig1_episodes.parquet"""
import joblib, numpy as np, pandas as pd
from cape.utils.config import REPO_ROOT
d = joblib.load(REPO_ROOT / "results/prereg_v40/frozen_forecasters.joblib"); sc, lda = d["scaler"], d["lda"]
w = lda.coef_[0] / sc.scale_; b = float(lda.intercept_[0] - (lda.coef_[0] * sc.mean_ / sc.scale_).sum())   # score = w.h + b == lda.decision_function(sc.transform(h))
x = np.random.default_rng(0).normal(size=(3, w.size)); assert np.allclose(x @ w + b, lda.decision_function(sc.transform(x)), rtol=1e-4, atol=1e-3)
np.savez(REPO_ROOT / "outputs/reconcile/fig1_prep.npz", w=w.astype(np.float32), b=np.float32(b), layer_index=d["layer_index"])
E = pd.read_parquet(REPO_ROOT / "outputs/reconcile/v43_fresh_episodes.parquet")
L = pd.read_parquet(REPO_ROOT / "outputs/reconcile/v46B_rubric3.parquet")
print(L.columns.tolist()[:20])
