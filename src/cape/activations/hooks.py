"""Streaming residual-stream hooks.

``ResidualCapture`` pools the output of selected decoder blocks at requested positions/windows *inside the hook*
(on GPU) so that full ``[T, d]`` hidden states are never materialised or stored (no ``output_hidden_states=True``).

``ResidualPatch`` edits a block's output at given (row, position) sites: replace with a vector, or add a delta.
Positions are absolute indices into the current forward's sequence; the hook only fires for positions present in
that forward call (prefill), which makes a patch of a prompt prefix persist through KV-cached decoding.
"""
from __future__ import annotations

from contextlib import contextmanager

import torch


def _hidden(out):
    return out[0] if isinstance(out, tuple) else out


def _replace_hidden(out, h):
    if isinstance(out, tuple):
        return (h,) + tuple(out[1:])
    return h


class ResidualCapture:
    """Capture pooled block outputs.

    requests: {name: spec} where spec is either
        ("point", LongTensor[P])                      -> [P, d]
        ("window", list[(start, end_inclusive)])      -> [W, d] mean over each window (clipped at 0)
    Results: self.out[name][layer] -> float16 CPU tensor.
    """

    def __init__(self, blocks, layers: list[int], requests: dict, keep_fp32: bool = False):
        self.blocks, self.layers, self.requests = blocks, list(layers), requests
        self.out: dict[str, dict[int, torch.Tensor]] = {k: {} for k in requests}
        self.handles = []
        self.dtype = torch.float32 if keep_fp32 else torch.float16

    def _hook(self, layer):
        def fn(mod, inp, out):
            h = _hidden(out)[0]  # batch size 1
            for name, (kind, spec) in self.requests.items():
                if kind == "point":
                    v = h.index_select(0, spec.to(h.device))
                else:
                    v = torch.stack([h[max(s, 0):e + 1].float().mean(0) for s, e in spec]) if len(spec) else \
                        h.new_zeros((0, h.shape[-1]))
                self.out[name][layer] = v.to(self.dtype).cpu()
        return fn

    def __enter__(self):
        for l in self.layers:
            self.handles.append(self.blocks[l].register_forward_hook(self._hook(l)))
        return self

    def __exit__(self, *a):
        for h in self.handles:
            h.remove()
        self.handles = []


class ResidualPatch:
    """Patch block outputs.

    edits: {layer: list of (row, positions LongTensor[P], values Tensor[P, d], mode)} with mode in {"replace", "add"}.
    Positions >= current sequence length are ignored (they belong to a later forward).
    """

    def __init__(self, blocks, edits: dict):
        self.blocks, self.edits, self.handles = blocks, edits, []
        self.n_applied = 0

    def _hook(self, layer):
        def fn(mod, inp, out):
            h = _hidden(out)
            T = h.shape[1]
            if T == 1:  # decode step: prefix positions already patched in the cached prefill
                return out
            h = h.clone()
            for row, pos, val, mode in self.edits[layer]:
                keep = pos < T
                if not bool(keep.any()):
                    continue
                p = pos[keep].to(h.device)
                v = val[keep].to(h.device, h.dtype)
                if mode == "replace":
                    h[row, p] = v
                else:
                    h[row, p] = h[row, p] + v
                self.n_applied += int(keep.sum())
            return _replace_hidden(out, h)
        return fn

    def __enter__(self):
        for l in self.edits:
            self.handles.append(self.blocks[l].register_forward_hook(self._hook(l)))
        return self

    def __exit__(self, *a):
        for h in self.handles:
            h.remove()
        self.handles = []


@contextmanager
def hooks(*managers):
    for m in managers:
        m.__enter__()
    try:
        yield managers
    finally:
        for m in reversed(managers):
            m.__exit__()
