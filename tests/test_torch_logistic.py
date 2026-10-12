"""GPU logistic solver must reproduce sklearn's balanced L2-logistic (same objective) — run on CPU here."""
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from cape.probes.linear import TorchLogistic


def test_matches_sklearn_objective():
    rng = np.random.default_rng(0)
    n, d = 1500, 64
    X = rng.standard_normal((n, d)).astype(np.float32)
    w = rng.standard_normal(d)
    y = (X @ w + rng.standard_normal(n) * 2 > 1.5).astype(int)  # imbalanced
    for C in (1e-3, 1e-2, 1e-1):
        sc = StandardScaler().fit(X)
        sk = LogisticRegression(C=C, class_weight="balanced", max_iter=5000, tol=1e-8).fit(sc.transform(X), y)
        tl = TorchLogistic(C, device="cpu").fit(X, y)
        s_sk, s_t = sk.decision_function(sc.transform(X)), tl.decision_function(X)
        assert np.corrcoef(s_sk, s_t)[0, 1] > 0.9999, C
        assert np.abs(s_sk - s_t).max() < 1e-2, (C, np.abs(s_sk - s_t).max())
