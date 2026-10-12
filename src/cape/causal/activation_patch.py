"""Residual-stream state swaps and controls on aligned common-suffix positions."""
from __future__ import annotations

import torch

from cape.activations.hooks import ResidualCapture, ResidualPatch

CONDITIONS = ["base_neg", "base_pos", "fwd", "rev", "amp", "rand", "nuis", "mism", "rand_pos"]
DESCRIPTION = {
    "base_neg": "x- prefix, no patch",
    "base_pos": "x+ prefix, no patch",
    "fwd": "x- prefix; suffix residuals at layer l <- x+ residuals (safe-condition state into unsafe-condition run)",
    "rev": "x+ prefix; suffix residuals at layer l <- x- residuals",
    "amp": "x- prefix; add (h- - h+) (sign-reversed forward delta: amplify the x- condition signal)",
    "rand": "x- prefix; add random direction with per-position norm ||h+ - h-|| (norm-matched control)",
    "nuis": "x- prefix; suffix residuals <- nuisance-variant x- residuals (safety-irrelevant field changed)",
    "mism": "x- prefix; suffix residuals <- x+ residuals of a DIFFERENT scenario (mismatched pair)",
    "rand_pos": "x+ prefix; add random direction with per-position norm ||h+ - h-|| (norm-matched control for rev)",
}


@torch.no_grad()
def suffix_states(model, blocks, ids: list[int], n: int, layers: list[int]) -> dict:
    """Residuals of the last n positions at each layer: {layer: [n, d] float32 cpu}."""
    pos = torch.arange(len(ids) - n, len(ids))
    with ResidualCapture(blocks, layers, {"s": ("point", pos)}, keep_fp32=True) as cap:
        model(input_ids=torch.tensor([ids], device=model.device), use_cache=False, logits_to_keep=1)
    return cap.out["s"]


def condition_edit(cond: str, layer: int, n_prefix: int, h_minus, h_plus, h_nuis=None, h_mism=None,
                   gen: torch.Generator | None = None):
    """Returns (recipient: 'minus'|'plus', list of (positions, values, mode)) for one layer. Positions are
    absolute indices in the recipient prefix (last n aligned positions)."""
    if cond == "base_neg":
        return "minus", []
    if cond == "base_pos":
        return "plus", []
    n = h_minus.shape[0]
    pos = torch.arange(n_prefix - n, n_prefix)
    if cond == "fwd":
        return "minus", [(pos, h_plus, "replace")]
    if cond == "rev":
        return "plus", [(pos, h_minus, "replace")]
    if cond == "amp":
        return "minus", [(pos, h_minus - h_plus, "add")]
    if cond == "rand":
        norms = (h_plus - h_minus).norm(dim=-1, keepdim=True)
        u = torch.randn(h_minus.shape, generator=gen)
        u = u / u.norm(dim=-1, keepdim=True) * norms
        return "minus", [(pos, u, "add")]
    if cond == "rand_pos":
        norms = (h_plus - h_minus).norm(dim=-1, keepdim=True)
        u = torch.randn(h_plus.shape, generator=gen)
        u = u / u.norm(dim=-1, keepdim=True) * norms
        return "plus", [(pos, u, "add")]
    if cond == "nuis":
        if h_nuis is None:
            return None
        m = h_nuis.shape[0]
        return "minus", [(torch.arange(n_prefix - m, n_prefix), h_nuis, "replace")]
    if cond == "mism":
        if h_mism is None:
            return None
        m = min(h_mism.shape[0], n)
        return "minus", [(torch.arange(n_prefix - m, n_prefix), h_mism[-m:], "replace")]
    raise ValueError(cond)


def make_patch(blocks, layer: int, edits: list, batch: int):
    """Same edit for every row of an unpadded batch of identical prompts."""
    if not edits:
        return None
    return ResidualPatch(blocks, {layer: [(r, p, v, m) for r in range(batch) for (p, v, m) in edits]})
