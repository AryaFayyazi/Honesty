#!/usr/bin/env python
"""Architecture-aware causal test: transplant Gated-DeltaNet recurrent/conv states between matched prefixes.

python scripts/06b_deltanet_state_patch.py model=Qwen/Qwen3.8-27B [max_sites=24 continuations_per_patch=8]
then:  python scripts/06_causal_patching.py stage=continue model=Qwen/Qwen3.8-27B out=outputs/patching/pilot_dn
       python scripts/06_causal_patching.py stage=analyze out=outputs/patching/pilot_dn

Motivation: residual patches at the decision positions left behaviour unchanged. In Qwen3.8, 48/64 layers are
linear-attention blocks whose fixed-size recurrent state has already absorbed the safety-relevant metadata before the
decision positions, so a residual patch cannot reach it. Recurrent states are fixed-size, so a state transplant needs
no token alignment. Each prefix is run to its second-to-last token with caching; the recipient cache's linear-layer
states (in a layer set S) are replaced by the donor's; the decision turn is then sampled from the recipient prefix.
Full-attention KV is never modified (it still encodes the recipient's own metadata).
"""
import copy
import json
import time

import numpy as np
import pandas as pd
import torch
from omegaconf import OmegaConf

from cape.agents.actor import ChatFormatter
from cape.agents.rollout import stable_seed
from cape.models.load import discover_transformer_blocks, load_hf_model, load_tokenizer
from cape.utils.config import REPO_ROOT, load_config
from cape.utils.repro import snapshot

D = OmegaConf.create({"trajectories": "outputs/rollouts/pilot.parquet", "pairs": "outputs/capebench/pilot/pairs.parquet",
                      "scenarios": "outputs/capebench/pilot/scenarios.jsonl", "max_sites": 24,
                      "continuations_per_patch": 8, "max_new_tokens": 4096, "temperature": 0.6, "top_p": 0.95,
                      "top_k": 20, "out": "outputs/patching/pilot_dn", "seed": 0})


def prefill(model, ids, K):
    """Prefill K identical rows so every cache layer (incl. linear-attention states) is natively batch-K
    (LinearAttentionLayer has no batch_repeat_interleave)."""
    from transformers import DynamicCache
    cache = DynamicCache(config=model.config.get_text_config())
    with torch.no_grad():
        model(input_ids=torch.tensor([ids[:-1]] * K, device=model.device), past_key_values=cache, use_cache=True,
              logits_to_keep=1)
    return cache


def transplant(recipient, donor, layers, noise_like=None, gen=None):
    """Copy of recipient cache with linear-layer states in `layers` replaced by donor's (or, for noise, recipient +
    norm-matched random perturbation where the norm is ||donor - recipient|| per state tensor)."""
    c = copy.deepcopy(recipient)
    for i in layers:
        L, Ld = c.layers[i], donor.layers[i]
        for attr in ("recurrent_states", "conv_states"):
            r, d = getattr(L, attr)[0], getattr(Ld, attr)[0]
            if noise_like:  # norm-matched per sample row
                u = torch.randn(r.shape, generator=gen, dtype=torch.float32).to(r.device)
                dims = tuple(range(1, r.dim()))
                target = (d.float() - r.float()).flatten(1).norm(dim=1).view(-1, *[1] * (r.dim() - 1))
                u = u / u.flatten(1).norm(dim=1).view(-1, *[1] * (r.dim() - 1)) * target
                getattr(L, attr)[0] = (r.float() + u).to(r.dtype)
            else:
                getattr(L, attr)[0] = d.clone()
    return c


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    mcfg = cfg.model
    import importlib.util
    spec = importlib.util.spec_from_file_location("p06", REPO_ROOT / "scripts/06_causal_patching.py")
    p06 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p06)
    out = REPO_ROOT / cfg.out
    out.mkdir(parents=True, exist_ok=True)
    snapshot(out, cfg, model_revision=mcfg.get("revision"))
    tok = load_tokenizer(mcfg)
    fmt = ChatFormatter(tok, reasoning_effort=mcfg.chat.reasoning_effort)
    eps = pd.read_parquet(REPO_ROOT / cfg.trajectories)
    toks = pd.read_parquet(str(REPO_ROOT / cfg.trajectories).replace(".parquet", "_tokens.parquet")).set_index("episode_id")
    specs = {json.loads(l)["instance_id"]: json.loads(l) for l in open(REPO_ROOT / cfg.scenarios)}
    sites = p06.select_sites(OmegaConf.merge(p06.DEFAULTS, {"max_sites": cfg.max_sites}), fmt, eps, toks, specs,
                             pd.read_parquet(REPO_ROOT / cfg.pairs))
    model = load_hf_model(mcfg)
    blocks, types = discover_transformer_blocks(model, expected=mcfg.num_layers)
    lin = [i for i, t in enumerate(types) if t == "linear_attention"]
    quarters = {f"q{k + 1}": [i for i in lin if 16 * k <= i < 16 * (k + 1)] for k in range(4)}
    conds = {"base_neg": ("minus", None, []), "base_pos": ("plus", None, []),
             "dn_all": ("minus", "plus", lin), **{f"dn_{q}": ("minus", "plus", ls) for q, ls in quarters.items()},
             "dn_all_rand": ("minus", "rand", lin), "dn_all_nuis": ("minus", "nuis", lin),
             "dn_all_mism": ("minus", "mism", lin),
             "rev_dn_all": ("plus", "minus", lin), "rev_dn_all_rand": ("plus", "rand", lin)}
    I = fmt.ids
    stop = [I.tool_call_end, I.im_end, I.eot]
    K = int(cfg.continuations_per_patch)
    rows, t0 = [], time.time()
    for si, s in enumerate(sites):
        K = int(cfg.continuations_per_patch)
        caches = {"minus": prefill(model, s.minus, K), "plus": prefill(model, s.plus, K)}
        if s.nuis is not None:
            caches["nuis"] = prefill(model, s.nuis, K)
        other = sites[(si + 1) % len(sites)]
        if other.scenario_id != s.scenario_id:
            caches["mism"] = prefill(model, other.plus, K)
        for cond, (recip, donor, layers) in conds.items():
            if donor in ("nuis", "mism") and donor not in caches:
                continue
            if donor is None:
                cache = copy.deepcopy(caches[recip])
            elif donor == "rand":
                g = torch.Generator().manual_seed(stable_seed(s.site_id, cond))
                other_side = "plus" if recip == "minus" else "minus"
                cache = transplant(caches[recip], caches[other_side], layers, noise_like=True, gen=g)
            else:
                cache = transplant(caches[recip], caches[donor], layers)
            prefix = s.minus if recip == "minus" else s.plus
            torch.manual_seed(stable_seed(s.site_id, "crn"))
            with torch.no_grad():
                o = model.generate(torch.tensor([prefix] * K, device=model.device), past_key_values=cache,
                                   max_new_tokens=cfg.max_new_tokens, do_sample=True, temperature=cfg.temperature,
                                   top_p=cfg.top_p, top_k=cfg.top_k, eos_token_id=stop, pad_token_id=I.eot)
            for k in range(K):
                gen = o[k, len(prefix):].tolist()
                cut = next((j for j, t in enumerate(gen) if t in stop), None)
                rows.append({"site_id": s.site_id, "condition": cond, "layer": -1, "sample": k, "recipient": recip,
                             "gen_ids": gen[:cut + 1] if cut is not None else gen,
                             "finish": "stop" if cut is not None else "length"})
        pd.DataFrame(rows).to_parquet(out / "turn_samples.parquet")
        print(f"site {si + 1}/{len(sites)} {s.site_id} done, {time.time() - t0:.0f}s", flush=True)
    pd.DataFrame([{"site_id": s.site_id, "episode_id": s.episode_id, "pair_id": s.pair_id, "scenario_id": s.scenario_id,
                   "family": s.family, "t_star": s.t_star, "T_harm": s.T_harm, "unsafe_episode": s.unsafe_episode,
                   "suffix_len": s.suffix_len, "diff_tokens": s.diff_tokens} for s in sites]).to_parquet(out / "sites.parquet")
    with open(out / "sites.jsonl", "w") as f:
        for s in sites:
            f.write(json.dumps({"site_id": s.site_id, "minus": [int(x) for x in s.minus], "plus": [int(x) for x in s.plus],
                                "spec_minus": s.spec_minus, "spec_plus": s.spec_plus, "actions": s.actions,
                                "t_star": s.t_star}) + "\n")
    print("done ->", out)


if __name__ == "__main__":
    main()
