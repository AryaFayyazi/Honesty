"""Model/tokenizer loading and architecture introspection (no hard-coded module paths)."""
from __future__ import annotations

import os

import torch
from torch import nn

os.environ.setdefault("HF_HUB_CACHE", "/data/models")
os.environ.setdefault("HF_HUB_OFFLINE", "1")


def model_path(cfg) -> str:
    p = cfg.get("local_path") if hasattr(cfg, "get") else None
    if p:
        return p
    from huggingface_hub import snapshot_download
    return snapshot_download(cfg["hf_id"], revision=cfg.get("revision"), cache_dir=os.environ["HF_HUB_CACHE"],
                             local_files_only=True)


def load_tokenizer(cfg):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(model_path(cfg))


def load_hf_model(cfg, device: str = "cuda:0", dtype: str = "bfloat16", attn_implementation: str = "sdpa"):
    import transformers
    path = model_path(cfg)
    conf = transformers.AutoConfig.from_pretrained(path)
    kw = dict(dtype=getattr(torch, dtype), device_map=device, attn_implementation=attn_implementation)
    if getattr(conf, "model_type", "") == "qwen3_5":
        # checkpoint is the VLM wrapper; load it whole (vision tower is small and never called)
        model = transformers.AutoModelForImageTextToText.from_pretrained(path, **kw)
    else:
        model = transformers.AutoModelForCausalLM.from_pretrained(path, **kw)
    model.eval()
    model.requires_grad_(False)
    return model


def text_config(model):
    c = model.config
    return getattr(c, "text_config", None) or c


def discover_transformer_blocks(model: nn.Module, expected: int | None = None) -> tuple[list[nn.Module], list[str]]:
    """Find the language-model decoder layer stack by introspection.

    Picks the ``nn.ModuleList`` whose length equals the text config's ``num_hidden_layers`` and whose name does not
    belong to a vision tower / MTP head. Returns (blocks, layer_types) and validates the count.
    """
    tc = text_config(model)
    n = tc.num_hidden_layers
    cands = []
    for name, mod in model.named_modules():
        if isinstance(mod, nn.ModuleList) and len(mod) == n and not any(k in name for k in ("visual", "vision", "mtp")):
            cands.append((name, mod))
    if len(cands) != 1:
        raise RuntimeError(f"expected exactly one decoder stack of length {n}, found {[c[0] for c in cands]}")
    name, blocks = cands[0]
    if expected is not None and len(blocks) != expected:
        raise RuntimeError(f"expected {expected} language blocks, found {len(blocks)} at {name}")
    types = list(getattr(tc, "layer_types", None) or ["full_attention"] * n)
    return list(blocks), types


def final_norm_and_head(model):
    """Return (final_norm, lm_head) for logit reconstruction during replay checks."""
    lm = model.get_decoder() if hasattr(model, "get_decoder") else model.model
    norm = getattr(lm, "norm", None)
    if norm is None:
        for name, mod in model.named_modules():
            if name.endswith("language_model.norm") or name == "model.norm":
                norm = mod
    return norm, model.get_output_embeddings()
