#!/usr/bin/env python
"""Figure 1(a) data (GPU): the CONFIRMATORY pre-report lie forecaster (v37 F2a, rebuilt and verified by scripts/130a) applied to the
agent's own residual stream along each fresh confirmation episode (set C, informed; 1,081 episodes, 3 models).
One teacher-forced pass per episode over the exact pre-report prompt of scripts/94 (rend with add_generation_prompt=True); per-token
score = w . h_l(t) + b at the forecaster's layer (pre_m8 forecasters: 8-token rolling mean, which is linear). Recorded: the score at
the end of every tool-call turn (state right after the agent issues action k) and at the final pre-report token (which equals the
confirmatory feature), plus the event index of the violation, reveal and retroactive request.
python scripts/130_fig1_traj.py actor=gemma4      -> outputs/reconcile/fig1_traj_<actor>.parquet"""
import importlib.util
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


D = OmegaConf.create({"actor": "gemma4", "max_tokens": 30000})


def main():
    import torch
    from transformers import AutoModelForCausalLM, AutoModelForImageTextToText, AutoTokenizer
    from cape.models.load import discover_transformer_blocks, model_path
    from cape.utils.config import resolve_model
    cfg = OmegaConf.merge(D, load_config(None)); A = cfg.actor
    X56 = _mod("x56", "scripts/56_xm_replay_extract.py"); X94 = _mod("x94", "scripts/94_report_feats.py"); torch.backends.cuda.enable_cudnn_sdp(False)
    P = np.load(REPO_ROOT / "outputs/reconcile/fig1_traj_prep.npz"); E = pd.read_parquet(REPO_ROOT / "outputs/reconcile/fig1_traj_episodes.parquet")
    E = E[E.model == A].reset_index(drop=True); a = X56.ACT[A]
    p = model_path(resolve_model(a["model"])); tok = AutoTokenizer.from_pretrained(p)
    try:
        model = AutoModelForCausalLM.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    except Exception:
        model = AutoModelForImageTextToText.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    blocks, _ = discover_transformer_blocks(model); L = X56.layers_for(len(blocks)); layer = L[int(P[f"{A}_li"])]
    w = torch.tensor(P[f"{A}_w"], dtype=torch.float32, device="cuda"); b = float(P[f"{A}_b"]); m8 = str(P[f"{A}_pos"]) == "pre_m8"
    cap = {}
    blocks[layer].register_forward_hook(lambda mod, i, o: cap.__setitem__("s", ((o[0] if isinstance(o, tuple) else o)[0].float() @ w + b).cpu().numpy()))
    specs = {}
    stems = {st: st.replace(X94.PRE[A], "", 1) if X94.PRE[A] else st for st in E.set.unique()}
    for st, stem in stems.items():
        bench = stem.rsplit("_minus", 1)[0]
        for l in open(REPO_ROOT / f"outputs/capebench/{bench}/scenarios.jsonl"):
            s = json.loads(l); specs[(st, s["instance_id"])] = s
    roll = {st: pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{st}.parquet").set_index("episode_id") for st in E.set.unique()}
    enc = lambda t: tok(t, add_special_tokens=False)["input_ids"]; rows = []
    for n, r in enumerate(E.itertuples()):
        ep = roll[r.set].loc[r.episode_id]; ev = list(ep.events); spec = specs[(r.set, ep.instance_id)]
        msgs = X56.messages_upto(spec, ev, 10**9, a["suffix"]); ids = enc(X94.rend(tok, msgs, a["kwargs"], True))
        if len(ids) > cfg.max_tokens:
            continue
        with torch.no_grad():
            try:
                model(input_ids=torch.tensor([ids], device="cuda"), logits_to_keep=1)
            except TypeError:
                model(input_ids=torch.tensor([ids], device="cuda"))
        s = cap["s"]
        if m8:
            c = np.cumsum(np.insert(s, 0, 0)); s = np.array([(c[t + 1] - c[max(0, t - 7)]) / (t + 1 - max(0, t - 7)) for t in range(len(s))])
        calls = [e["event_id"] for e in ev if e["is_tool_call"] and e["tool"]]
        pts = []
        for k in calls:   # state right after the agent issues action k (prefix ends with call k, before its result)
            try:
                off = len(enc(X94.rend(tok, X56.messages_upto(spec, ev, k, a["suffix"]), a["kwargs"], False)))
            except Exception:
                continue
            if 0 < off <= len(s):
                pts.append((k, float(s[off - 1])))
        fu = int(ep.first_unsafe_event); retro = next((k for k in calls if k > fu and next(e for e in ev if e["event_id"] == k)["tool"] == "request_permission"), None)
        rows.append({"set": r.set, "episode_id": r.episode_id, "model": A, "template": r.template, "y": int(r.y), "retro": int(r.retro),
                     "violation_event": fu, "reveal_event": int(ep.reveal_event) if pd.notna(ep.reveal_event) else -1, "retro_event": retro if retro is not None else -1,
                     "events": [k for k, _ in pts], "scores": [v for _, v in pts], "pre_report": float(s[-1])})
        if n % 50 == 0:
            print(n, "/", len(E), flush=True)
    pd.DataFrame(rows).to_parquet(REPO_ROOT / f"outputs/reconcile/fig1_traj_{A}.parquet"); print("wrote", len(rows))


if __name__ == "__main__":
    main()
