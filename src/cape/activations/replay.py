"""Teacher-forced HF replay of saved rollouts with streaming capture + equivalence checks."""
from __future__ import annotations

import math

import numpy as np
import torch

from cape.activations.event_pooling import capture_requests
from cape.activations.hooks import ResidualCapture
from cape.models.load import final_norm_and_head


@torch.no_grad()
def replay_episode(model, blocks, ids: list[int], events: list[dict], layers: list[int], poolings: list[str],
                   check_positions: list[int] | None = None) -> tuple[dict, np.ndarray | None]:
    """One forward over the full episode. Returns ({pooling: {layer: [n_events, d]}}, logprobs at check_positions).

    ``check_positions`` are indices of *generated* tokens; the returned logprob of token ids[p] is computed from the
    logits at position p-1 (raw log-softmax, matching vLLM ``raw_logprobs``).
    """
    req = capture_requests(events, poolings)
    x = torch.tensor([ids], device=model.device)
    lp = None
    norm_out = {}
    handles = []
    if check_positions:
        norm, head = final_norm_and_head(model)
        src = torch.tensor([p - 1 for p in check_positions], device=model.device)
        handles.append(norm.register_forward_hook(lambda m, i, o: norm_out.__setitem__("h", o.index_select(1, src)[0])))
    try:
        with ResidualCapture(blocks, layers, req) as cap:
            model(input_ids=x, use_cache=False, logits_to_keep=1)
    finally:
        for h in handles:
            h.remove()
    if check_positions:
        norm, head = final_norm_and_head(model)
        h = norm_out["h"]
        tgt = torch.tensor([ids[p] for p in check_positions], device=model.device)
        out = []
        for i in range(0, h.shape[0], 256):
            logits = head(h[i:i + 256]).float()
            out.append(torch.log_softmax(logits, -1).gather(1, tgt[i:i + 256, None])[:, 0])
        lp = torch.cat(out).cpu().numpy()
    return cap.out, lp


def compare_logprobs(ref: np.ndarray, got: np.ndarray) -> dict:
    m = ~np.isnan(ref)
    d = np.abs(ref[m] - got[m])
    if d.size == 0:
        return {"n": 0}
    return {"n": int(d.size), "mean_abs": float(d.mean()), "p99_abs": float(np.quantile(d, 0.99)),
            "max_abs": float(d.max()), "corr": float(np.corrcoef(ref[m], got[m])[0, 1]) if d.size > 2 else math.nan,
            "mean_prob_abs": float(np.abs(np.exp(ref[m]) - np.exp(got[m])).mean())}
