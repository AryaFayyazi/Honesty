"""Small temporal probe: GRU over the sequence of event-level representations of one episode.

Causal by construction (a unidirectional GRU): the score at event t depends only on events <= t.
"""
from __future__ import annotations

import numpy as np
import torch
from torch import nn

from cape.eval.statistics import auroc


class GRUProbe(nn.Module):
    def __init__(self, d_in: int, d_proj: int = 128, d_hidden: int = 128):
        super().__init__()
        self.proj = nn.Sequential(nn.LayerNorm(d_in), nn.Linear(d_in, d_proj), nn.GELU(), nn.Dropout(0.2))
        self.gru = nn.GRU(d_proj, d_hidden, batch_first=True)
        self.head = nn.Linear(d_hidden, 1)

    def forward(self, x):  # x [B, T, d]
        h, _ = self.gru(self.proj(x))
        return self.head(h).squeeze(-1)


def _seqs(X, df):
    """Group rows of X by episode in event order. Returns list of (row_indices, tensor)."""
    out = []
    for _, g in df.groupby("episode_id", sort=False):
        idx = g.sort_values("event_id").index.values
        out.append(idx)
    return out


def _batch(X, seqs, y=None):
    T = max(len(s) for s in seqs)
    B = len(seqs)
    xb = torch.zeros(B, T, X.shape[1])
    mb = torch.zeros(B, T, dtype=torch.bool)
    yb = torch.zeros(B, T)
    for i, s in enumerate(seqs):
        xb[i, :len(s)] = torch.as_tensor(X[s])
        mb[i, :len(s)] = True
        if y is not None:
            yb[i, :len(s)] = torch.as_tensor(y[s], dtype=torch.float32)
    return xb, mb, yb


def fit_gru(X, y, df, tr_idx, va_idx, epochs: int = 60, lr: float = 1e-3, seed: int = 0, device="cpu"):
    """X, y indexed by df row position; tr_idx/va_idx are row positions (whole episodes)."""
    torch.manual_seed(seed)
    dtr, dva = df.iloc[tr_idx], df.iloc[va_idx]
    str_, sva = _seqs(X, dtr), _seqs(X, dva)
    m = GRUProbe(X.shape[1]).to(device)
    opt = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=1e-2)
    pos_w = torch.tensor((len(y[tr_idx]) - y[tr_idx].sum()) / max(y[tr_idx].sum(), 1), device=device)
    lossf = nn.BCEWithLogitsLoss(pos_weight=pos_w, reduction="none")
    rng = np.random.default_rng(seed)
    best, best_state, bad = -np.inf, None, 0
    for ep in range(epochs):
        m.train()
        order = rng.permutation(len(str_))
        for i in range(0, len(order), 32):
            xb, mb, yb = _batch(X, [str_[j] for j in order[i:i + 32]], y)
            xb, mb, yb = xb.to(device), mb.to(device), yb.to(device)
            opt.zero_grad()
            l = (lossf(m(xb), yb) * mb).sum() / mb.sum()
            l.backward()
            opt.step()
        sc = score_gru(m, X, dva, device)
        a = auroc(y[va_idx], _align(sc, dva))  # df index == row position (event_table resets the index)
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


def _align(scores: dict, dsub):
    return np.array([scores[i] for i in dsub.index.values])


@torch.no_grad()
def score_gru(m, X, dsub, device="cpu") -> dict:
    """Returns {row_index: score} for all rows of dsub."""
    m.eval()
    out = {}
    seqs = _seqs(X, dsub)
    for i in range(0, len(seqs), 64):
        chunk = seqs[i:i + 64]
        xb, mb, _ = _batch(X, chunk)
        s = m(xb.to(device)).cpu().numpy()
        for b, idx in enumerate(chunk):
            for t, r in enumerate(idx):
                out[r] = float(s[b, t])
    return out
