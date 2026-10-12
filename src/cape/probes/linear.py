"""Linear (logistic) probes with validation-only model selection."""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from cape.eval.statistics import auroc


def fit_logistic(Xtr, ytr, Xva, yva, Cs=(1e-4, 1e-3, 1e-2, 1e-1), max_iter: int = 2000, seed: int = 0):
    """Pick C by validation AUROC (never test). Returns (fitted pipeline, chosen C, val AUROC)."""
    best = (None, None, -np.inf)
    for C in Cs:
        m = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=max_iter, class_weight="balanced",
                                                               random_state=seed))
        m.fit(Xtr, ytr)
        a = auroc(yva, m.decision_function(Xva)) if len(np.unique(yva)) == 2 else -np.inf
        if np.isnan(a):
            a = -np.inf
        if a > best[2]:
            best = (m, C, a)
    if best[0] is None:  # degenerate validation labels: fall back to middle C
        m = make_pipeline(StandardScaler(), LogisticRegression(C=Cs[len(Cs) // 2], max_iter=max_iter,
                                                               class_weight="balanced", random_state=seed))
        best = (m.fit(Xtr, ytr), Cs[len(Cs) // 2], np.nan)
    return best


def score(model, X):
    return model.decision_function(X)


class TorchLogistic:
    """GPU L2-logistic regression with the SAME objective as sklearn's LogisticRegression(class_weight='balanced'):
        min_w,b  0.5*||w||^2 + C * sum_i s_i * logloss(y_i, x_i.w + b),  s_i = n / (2 n_{y_i}),  intercept unpenalised,
    on features standardised with training mean/std (as in the sklearn StandardScaler pipeline). Convex => same optimum
    up to solver tolerance; verified against sklearn in tests/test_torch_logistic.py."""

    def __init__(self, C: float, device: str = "cuda", max_iter: int = 500):
        self.C, self.device, self.max_iter = C, device, max_iter

    def fit(self, X, y):
        import torch
        X = torch.as_tensor(X, dtype=torch.float32, device=self.device)
        y = torch.as_tensor(y, dtype=torch.float32, device=self.device)
        self.mu, self.sd = X.mean(0), X.std(0, unbiased=False).clamp_min(1e-8)
        Z = (X - self.mu) / self.sd
        n, n1 = len(y), y.sum()
        s = torch.where(y > 0, n / (2 * n1), n / (2 * (n - n1)))
        w = torch.zeros(Z.shape[1], device=self.device, requires_grad=True)
        b = torch.zeros(1, device=self.device, requires_grad=True)
        opt = torch.optim.LBFGS([w, b], lr=1, max_iter=self.max_iter, tolerance_grad=1e-6, tolerance_change=1e-9,
                                history_size=20, line_search_fn="strong_wolfe")
        lf = torch.nn.functional.binary_cross_entropy_with_logits

        def closure():
            opt.zero_grad()
            loss = 0.5 * (w * w).sum() + self.C * (s * lf(Z @ w + b, y, reduction="none")).sum()
            loss.backward()
            return loss
        opt.step(closure)
        self.w, self.b = w.detach(), b.detach()
        return self

    def decision_function(self, X):
        import torch
        X = torch.as_tensor(X, dtype=torch.float32, device=self.device)
        return (((X - self.mu) / self.sd) @ self.w + self.b).cpu().numpy()


def fit_logistic_torch(Xtr, ytr, Xva, yva, Cs=(1e-4, 1e-3, 1e-2, 1e-1), device="cuda", seed: int = 0):
    """Same model selection as fit_logistic (C by validation AUROC), GPU solver."""
    best = (None, None, -np.inf)
    for C in Cs:
        m = TorchLogistic(C, device=device).fit(Xtr, ytr)
        a = auroc(yva, m.decision_function(Xva)) if len(np.unique(yva)) == 2 else -np.inf
        a = -np.inf if np.isnan(a) else a
        if a > best[2] or best[0] is None:
            best = (m, C, a)
    return best
