#!/usr/bin/env python
"""v49 H4: self-counterfactual CAA steering of the final report for any actor (gemma4, gptoss20b, qwen38); the Muse protocol of
scripts/103 (dir 'caa', 5 layers, + mult * g_l * u_l at generated positions after a delay of d tokens; random control 'rand').
Episodes: an episode table (set, episode_id, label, fold). Development episodes use the OTHER fold's direction (cross-fit);
fresh confirmation episodes use fold_key=a (all development). Same seed across conditions within a batch.
Report extraction per actor: gpt-oss = Harmony final channel; gemma4 = text after the thought channel; qwen38 = text after
</think>. A generation that calls a tool or never reaches the final message is NO_REPORT (revised_has_tool_call=True).
Output schema = scripts/103 (labelled by scripts/97 revised=...).
python scripts/127_steer_multi.py actor=gemma4 episodes=outputs/reconcile/h4_gemma4_dev_episodes.parquet out_name=h4dev_gemma4 \
    'conds=[none:0:caa:d16,caa_p4_d16:4:caa:d16,caa_p8_d16:8:caa:d16]'"""
import hashlib
import importlib.util
import json
import re

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.envs.base import TOOLS
from cape.utils.config import REPO_ROOT, load_config


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


D = OmegaConf.create({"actor": "gemma4", "episodes": None, "out_name": None, "conds": ["none:0:caa:d16"], "fold_key": None,
                      "batch": 6, "max_new": 3072, "max_prompt": 24000})
OUT = REPO_ROOT / "outputs/reconcile"; NEUTRAL = "Please write your final report to the user."
TOOLMARK = {"gemma4": "<|tool_call>", "gptoss20b": "to=functions", "qwen38": "<tool_call>"}


def final_report(actor, txt):
    """-> (report or None). None = no user-facing report (tool call, or the final message never started)."""
    if TOOLMARK[actor] in txt:
        return None
    if actor == "gptoss20b":
        seg = txt.split("<|channel|>final<|message|>")
        return re.split(r"<\|return\|>|<\|end\|>|<\|start\|>", seg[-1])[0].strip() if len(seg) > 1 else None
    if actor == "qwen38":
        if "</think>" not in txt:
            return None
        return txt.split("</think>")[-1].split("<|im_end|>")[0].strip() or None
    if actor == "gemma4":
        body = txt.split("<channel|>")[-1] if "<|channel>" in txt else txt
        if "<|channel>" in txt and "<channel|>" not in txt:
            return None                                  # thought never closed: no report
        return body.split("<turn|>")[0].strip() or None
    raise ValueError(actor)


def main():
    import torch
    from transformers import AutoModelForCausalLM, AutoModelForImageTextToText, AutoTokenizer
    from cape.models.load import discover_transformer_blocks, model_path
    from cape.utils.config import resolve_model
    cfg = OmegaConf.merge(D, load_config(None)); X56 = _mod("x56", "scripts/56_xm_replay_extract.py"); C126 = _mod("c126", "scripts/126_caa_multi.py")
    torch.backends.cuda.enable_cudnn_sdp(False)
    E = pd.read_parquet(REPO_ROOT / cfg.episodes); Zd = np.load(OUT / f"caa_{cfg.actor}_directions.npz")
    a = X56.ACT[cfg.actor]; p = model_path(resolve_model(a["model"])); tok = AutoTokenizer.from_pretrained(p); tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    try:
        model = AutoModelForCausalLM.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    except Exception:
        model = AutoModelForImageTextToText.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    blocks, _ = discover_transformer_blocks(model); dl = [int(x) for x in Zd["layers"]]; assert dl == X56.layers_for(len(blocks))
    st = {"vecs": None, "delay": 0, "step": 0}

    def mk(li):
        def h(mod, inp, out):
            x = out[0] if isinstance(out, tuple) else out
            if li == 0:
                st["step"] = 0 if x.shape[1] > 1 else st["step"] + 1
            if st["vecs"] is None or x.shape[1] != 1 or st["step"] <= st["delay"]:
                return out
            x = x + st["vecs"][li]
            return (x,) + tuple(out[1:]) if isinstance(out, tuple) else x
        return h
    for li, bl in enumerate(dl):
        blocks[bl].register_forward_hook(mk(li))
    specs = {}
    for b in sorted(set(E.set.map(lambda s: C126.bench_of(cfg.actor, s)))):
        for l in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl"):
            s = json.loads(l); specs[(b, s["instance_id"])] = s
    roll = {s_: pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{s_}.parquet").set_index("episode_id") for s_ in E.set.unique()}
    prompts, keep = [], []
    for i, r in enumerate(E.itertuples()):
        ep = roll[r.set].loc[r.episode_id]
        msgs = X56.messages_upto(specs[(C126.bench_of(cfg.actor, r.set), ep.instance_id)], list(ep.events), 10**9, a["suffix"]) + [{"role": "user", "content": NEUTRAL}]
        t = tok.apply_chat_template(msgs, tools=TOOLS, tokenize=False, add_generation_prompt=True, **a["kwargs"])
        if len(tok(t, add_special_tokens=False)["input_ids"]) <= cfg.max_prompt:
            prompts.append(t); keep.append(i)
    E = E.iloc[keep].reset_index(drop=True); print("episodes", len(E), flush=True)
    ck = OUT / f"{cfg.out_name}.parquet"; rows = pd.read_parquet(ck).to_dict("records") if ck.exists() else []; done = {r["message"] for r in rows}
    for spec in cfg.conds:
        name, mult, kind, mode = spec.split(":"); mult = float(mult)
        if name in done:
            print("skip done", name, flush=True); continue
        st["delay"] = int(re.fullmatch(r"d(\d+)", mode).group(1))
        for fold in sorted(E.fold.unique()):
            fk = cfg.fold_key if cfg.fold_key is not None else int(fold)       # cross-fit: direction k of scripts/126 is fit on folds != k
            vk = "u" if kind == "caa" else "r"
            st["vecs"] = None if mult == 0 else [torch.tensor(mult * float(Zd[f"g{fk}_{li}"]) * Zd[f"{vk}{fk}_{li}"], dtype=torch.bfloat16, device="cuda") for li in range(len(dl))]
            idx = list(E.index[E.fold == fold])
            for j0 in range(0, len(idx), cfg.batch):
                bi = idx[j0:j0 + cfg.batch]; enc = tok([prompts[i] for i in bi], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
                torch.manual_seed(int(hashlib.md5(f"{fold}-{j0}".encode()).hexdigest(), 16) % 2**31)
                samp = {"temperature": 1.0, "top_p": 0.95, "top_k": 64} if cfg.actor == "gemma4" else ({"temperature": 0.6, "top_p": 0.95, "top_k": 20} if cfg.actor == "qwen38" else {"temperature": 1.0, "top_p": 1.0})
                with torch.no_grad():
                    o = model.generate(**enc, max_new_tokens=cfg.max_new, do_sample=True, **samp)
                for k, seq in enumerate(o):
                    gen = seq[enc["input_ids"].shape[1]:]; txt = tok.decode(gen, skip_special_tokens=False); r = E.iloc[bi[k]]
                    rep = final_report(cfg.actor, txt)
                    rows.append({"set": r.set, "episode_id": r.episode_id, "orig_label": r.label, "message": name, "fold": int(fold),
                                 "revised_report": rep or "", "revised_has_tool_call": rep is None, "raw_generation": txt[:6000],
                                 "n_gen_tokens": int((gen != tok.pad_token_id).sum())})
                print(name, fold, j0 + len(bi), "/", len(idx), flush=True)
        pd.DataFrame(rows).to_parquet(ck)
    pd.DataFrame(rows).to_parquet(ck); print("wrote", len(rows))


if __name__ == "__main__":
    main()
