"""Two-layer MLP probe (small) with early stopping on validation AUROC."""
from __future__ import annotations

import numpy as np
import torch
from torch import nn

from cape.eval.statistics import auroc


class MLPProbe(nn.Module):
    def __init__(self, d_in: int, d_hidden: int = 256, dropout: float = 0.2):
        super().__init__()
        self.net = nn.Sequential(nn.LayerNorm(d_in), nn.Linear(d_in, d_hidden), nn.GELU(), nn.Dropout(dropout),
                                 nn.Linear(d_hidden, 1))

    def forward(self, x):
        return self.net(x).squeeze(-1)


def fit_mlp(Xtr, ytr, Xva, yva, epochs: int = 60, lr: float = 1e-3, wd: float = 1e-2, seed: int = 0,
            device: str = "cpu", d_hidden: int = 256):
    torch.manual_seed(seed)
    m = MLPProbe(Xtr.shape[1], d_hidden).to(device)
    opt = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=wd)
    Xt, yt = torch.tensor(Xtr, dtype=torch.float32, device=device), torch.tensor(ytr, dtype=torch.float32, device=device)
    Xv = torch.tensor(Xva, dtype=torch.float32, device=device)
    pos_w = torch.tensor((len(ytr) - ytr.sum()) / max(ytr.sum(), 1), device=device)
    lossf = nn.BCEWithLogitsLoss(pos_weight=pos_w)
    best, best_state, bad = -np.inf, None, 0
    g = torch.Generator(device="cpu").manual_seed(seed)
    for ep in range(epochs):
        m.train()
        perm = torch.randperm(len(Xt), generator=g)
        for i in range(0, len(perm), 256):
            b = perm[i:i + 256].to(device)
            opt.zero_grad()
            lossf(m(Xt[b]), yt[b]).backward()
            opt.step()
        m.eval()
        with torch.no_grad():
            a = auroc(yva, m(Xv).cpu().numpy())
        a = -np.inf if np.isnan(a) else a
        if a > best:
            best, best_state, bad = a, {k: v.clone() for k, v in m.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= 8:
                break
    if best_state is not None:
        m.load_state_dict(best_state)
    m.eval()
    return m, best


@torch.no_grad()
def score_mlp(m, X, device="cpu"):
    return m(torch.tensor(X, dtype=torch.float32, device=device)).cpu().numpy()
