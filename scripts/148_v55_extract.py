#!/usr/bin/env python
"""v55 decision states (GPU, HF; Muse in the v030 env). Prereg: docs/preregistration_v55.md.
For every v55 site: prefix = messages_upto(anchor_event) without the anchor turn's own assistant message (same construction and
renderer as v54, scripts/144 render_gen); one forward pass; residual at the last prompt token at the five depths of scripts/56.
-> outputs/v55/decision_<model>.npz (keys "<set>|<episode_id>", float16 [5, d]; plus "layers")
python scripts/148_v55_extract.py actor=gemma4"""
import importlib.util
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"actor": "gemma4", "max_tokens": 24000, "sites": None, "out": None})


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def main():
    import torch
    from transformers import AutoModelForCausalLM, AutoModelForImageTextToText, AutoTokenizer
    from cape.models.load import discover_transformer_blocks, model_path
    from cape.utils.config import resolve_model
    cfg = OmegaConf.merge(D, load_config(None)); A = cfg.actor; torch.backends.cuda.enable_cudnn_sdp(False)
    X56 = _mod("x56", "scripts/56_xm_replay_extract.py"); M144 = _mod("m144", "scripts/144_v54_steer.py"); a = X56.ACT[A]
    S = pd.read_parquet(REPO_ROOT / (cfg.sites or f"outputs/v55/sites_{A}.parquet"))
    out = REPO_ROOT / (cfg.out or f"outputs/v55/decision_{A}.npz")
    p = model_path(resolve_model(a["model"])); tok = AutoTokenizer.from_pretrained(p)
    try:
        model = AutoModelForCausalLM.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    except Exception:
        model = AutoModelForImageTextToText.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    blocks, _ = discover_transformer_blocks(model); L = X56.layers_for(len(blocks)); cap = {}

    def mk(li):
        def h(mod, inp, o):
            cap[li] = (o[0] if isinstance(o, tuple) else o)[0, -1].detach()
        return h
    for li, bl in enumerate(L):
        blocks[bl].register_forward_hook(mk(li))
    specs, roll = {}, {}
    for b in S.bench.unique():
        for l in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl"):
            x = json.loads(l); specs[(b, x["instance_id"])] = x
    for s_ in S.set.unique():
        roll[s_] = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{s_}.parquet").set_index("episode_id")
    feats, skipped = {}, {"render": 0, "long": 0}
    for i, r in enumerate(S.itertuples()):
        ev = list(roll[r.set].loc[r.episode_id].events)
        msgs = X56.messages_upto(specs[(r.bench, r.instance_id)], ev, int(r.anchor_event), a["suffix"])
        if msgs and msgs[-1]["role"] == "assistant":
            msgs = msgs[:-1]
        t = M144.render_gen(X56, tok, msgs, a["kwargs"])
        if t is None:
            skipped["render"] += 1; continue
        ids = tok(t, add_special_tokens=False)["input_ids"]
        if len(ids) > cfg.max_tokens:
            skipped["long"] += 1; continue
        with torch.no_grad():
            model(input_ids=torch.tensor([ids], device="cuda"), logits_to_keep=1, use_cache=False)
        feats[f"{r.set}|{r.episode_id}"] = np.stack([cap[li].float().cpu().numpy() for li in range(len(L))]).astype(np.float16)
        if i % 250 == 0:
            print(i, "/", len(S), flush=True)
    np.savez_compressed(out, layers=np.array(L), **feats); print("wrote", len(feats), "skipped", skipped)


if __name__ == "__main__":
    main()
