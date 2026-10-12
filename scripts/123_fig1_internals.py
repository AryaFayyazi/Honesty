#!/usr/bin/env python
"""Figure 1 data (GPU, v030 env): per-token internal readouts of Muse-Glimmer on the 110 fresh steering-confirmation episodes.
For each episode (prompt = full trajectory + neutral report turn, exactly as in scripts/103):
  pass "none"  : teacher-force prompt + the unsteered generated report (v46 'none'), no hook
  pass "p8"    : teacher-force prompt + the +8 steered report (v46 'caa_p8_d16') WITH the identical steering hook
                 (+8 * g_l * u_l at the 5 CAA blocks, generated positions >= 16), recording projections BEFORE the addition
  pass "p8nat" : the steered report text WITHOUT the hook (the model's natural reading of the text it wrote)
Recorded per token: projection on u_l (5 layers; all-development CAA direction 'ua', the one used for fresh episodes) and the
v40 frozen forecaster score (layer index 3, out-of-sample). Event anchors (token offsets): reveal, violation, retro request,
report start. Nothing is generated.  -> outputs/reconcile/fig1_internals.npz + fig1_internals_meta.parquet
"""
import importlib.util
import json

import numpy as np
import pandas as pd

from cape.envs.base import TOOLS
from cape.utils.config import REPO_ROOT


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


X56 = _mod("x56", "scripts/56_xm_replay_extract.py"); S103 = _mod("s103", "scripts/103_lie_steering.py")
OUT = REPO_ROOT / "outputs/reconcile"; DELAY, MULT = 16, 8.0


def main():
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer
    from cape.models.load import discover_transformer_blocks, model_path
    from cape.utils.config import resolve_model
    torch.backends.cuda.enable_cudnn_sdp(False)
    E = pd.read_parquet(OUT / "v43_fresh_episodes.parquet"); G = pd.read_parquet(OUT / "v46B.parquet")
    Zd = np.load(OUT / "caa_directions.npz"); P = np.load(OUT / "fig1_prep.npz")
    p = model_path(resolve_model("meta-models/Muse-Glimmer-30B")); tok = AutoTokenizer.from_pretrained(p)
    model = AutoModelForImageTextToText.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    blocks, _ = discover_transformer_blocks(model); dl = [int(x) for x in Zd["layers"]]; assert dl == X56.layers_for(len(blocks))
    U = [torch.tensor(Zd[f"ua_{i}"], dtype=torch.float32, device="cuda") for i in range(5)]
    V = [torch.tensor(MULT * float(Zd[f"ga_{i}"]) * Zd[f"ua_{i}"], dtype=torch.bfloat16, device="cuda") for i in range(5)]
    W = torch.tensor(P["w"], dtype=torch.float32, device="cuda"); bW = float(P["b"]); lw = int(P["layer_index"])
    st = {"steer_from": None, "rec": {}}

    def mk(li):
        def h(mod, inp, out):
            x = out[0] if isinstance(out, tuple) else out
            xf = x[0].float(); st["rec"][f"u{li}"] = (xf @ U[li]).cpu().numpy()
            if li == lw:
                st["rec"]["lda"] = (xf @ W + bW).cpu().numpy()
            if st["steer_from"] is not None:   # identical to generation: add only at generated positions >= DELAY
                x = x.clone(); x[:, st["steer_from"]:] += V[li]
                return (x,) + tuple(out[1:]) if isinstance(out, tuple) else x
            return out
        return h
    for li, bl in enumerate(dl):
        blocks[bl].register_forward_hook(mk(li))
    specs = {}
    for b in sorted(set(E.set.map(S103.bench_of))):
        for l in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl"):
            s = json.loads(l); specs[(b, s["instance_id"])] = s
    roll = {s_: pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{s_}.parquet").set_index("episode_id") for s_ in E.set.unique()}
    suffix = X56.ACT["museglimmer"]["suffix"]; render = lambda m, gen: tok.apply_chat_template(m, tools=TOOLS, tokenize=False, add_generation_prompt=gen)
    enc = lambda t: tok(t, add_special_tokens=False)["input_ids"]
    arrays, meta = {}, []
    for n, r in enumerate(E.itertuples()):
        ep = roll[r.set].loc[r.episode_id]; ev = list(ep.events); spec = specs[(S103.bench_of(r.set), ep.instance_id)]
        msgs = X56.messages_upto(spec, ev, 10**9, suffix) + [{"role": "user", "content": S103.NEUTRAL}]
        ids_p = enc(render(msgs, True)); fu = int(ep.first_unsafe_event)
        rev = int(ep.reveal_event) if pd.notna(ep.reveal_event) else None
        retro = next((e["event_id"] for e in ev if e["is_tool_call"] and e["tool"] == "request_permission" and e["event_id"] > fu), None)
        anchor = lambda k: len(enc(render(X56.messages_upto(spec, ev, k, suffix), False))) if k is not None else -1
        m = {"set": r.set, "episode_id": r.episode_id, "template": ep.template, "orig_label": r.label, "prompt_len": len(ids_p),
             "a_reveal": anchor(rev), "a_violation": anchor(fu), "a_retro": anchor(retro), "has_retro": retro is not None}
        g = G[(G.set == r.set) & (G.episode_id == r.episode_id)].set_index("message")
        for pas, msg, steer in (("none", "none", False), ("p8", "caa_p8_d16", True), ("p8nat", "caa_p8_d16", False)):
            gen = enc(g.loc[msg, "raw_generation"]); ids = ids_p + gen
            st["steer_from"] = len(ids_p) + DELAY if steer else None; st["rec"] = {}
            with torch.no_grad():
                try:
                    model(input_ids=torch.tensor([ids], device="cuda"), logits_to_keep=1)
                except TypeError:
                    model(input_ids=torch.tensor([ids], device="cuda"))
            for k, v in st["rec"].items():
                arrays[f"{n}_{pas}_{k}"] = v.astype(np.float16)
            m[f"len_{pas}"] = len(ids)
        meta.append(m); print(n, r.episode_id, m["prompt_len"], m["len_none"], flush=True)
    np.savez_compressed(OUT / "fig1_internals.npz", **arrays); pd.DataFrame(meta).to_parquet(OUT / "fig1_internals_meta.parquet")
    print("wrote", len(meta))


if __name__ == "__main__":
    main()
