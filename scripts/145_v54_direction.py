#!/usr/bin/env python
"""v54 direction data (development only). Prereg: docs/preregistration_v54.md (+ Clarification 2).
stage=sample  (GPU, vLLM): K unsteered decision turns per DEVELOPMENT site from the identical prefix (prompt string = the one
              scripts/144 builds), labelled by environment replay (scripts/144 label()). -> outputs/v54/samples_<actor>.parquet
stage=extract (GPU, HF): teacher-force prompt + each sampled turn; per sample, the mean residual (five depths) over the positions
              that PRODUCE the turn's tokens (last prompt position .. second-to-last turn token), for sites with >= 1 VIOLATE and
              >= 1 parsed non-VIOLATE sample; plus the decision state (last prompt token, five depths) of EVERY development site,
              x- and x+ (forecaster features). -> samples_<actor>_genmean.npz, decision_<actor>_dev.npz
stage=direction (CPU): u_l = normalised mean over mixed sites of [mean(non-violating) - mean(violating)]; g_l = mean projection of
              the within-site differences on u_l; folds k in {0, 1, a}: direction k uses sites with fold != k (a = all);
              r_l = random unit vector orthogonal to u_l (control); auroc_k = held-out within-site separation.
              -> outputs/v54/dir_<actor>.npz (keys as scripts/126: u{k}_{l}, g{k}_{l}, r{k}_{l}, layers)
python scripts/145_v54_direction.py stage=sample actor=gemma4"""
import importlib.util
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"stage": "sample", "actor": "gemma4", "K": 8, "max_new": 4096, "worlds_sample": ["minus"]})
OUT = REPO_ROOT / "outputs/v54"


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def build_prompts(A, split, tok):
    """Same prefix construction as scripts/144 (site call dropped; prompts > 24000 tokens skipped)."""
    X56 = _mod("x56", "scripts/56_xm_replay_extract.py"); M144 = _mod("m144", "scripts/144_v54_steer.py"); a = X56.ACT[A]
    S = pd.read_parquet(OUT / f"sites_{A}_{split}.parquet"); specs, roll = {}, {}
    for b in S.bench.unique():
        for l in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl"):
            s = json.loads(l); specs[(b, s["instance_id"])] = s
    for s_ in S.set.unique():
        roll[s_] = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{s_}.parquet").set_index("episode_id")
    ids, keep = [], []
    for i, r in enumerate(S.itertuples()):
        ep = roll[r.set].loc[r.episode_id]; msgs = X56.messages_upto(specs[(r.bench, r.instance_id)], list(ep.events), int(r.site_event), a["suffix"])
        if msgs and msgs[-1]["role"] == "assistant":
            msgs = msgs[:-1]
        t = M144.render_gen(X56, tok, msgs, a["kwargs"])
        if t is None:
            continue
        x = tok(t, add_special_tokens=False)["input_ids"]
        if len(x) <= 24000:
            ids.append(x); keep.append(i)
    return S.iloc[keep].reset_index(drop=True), ids, specs, roll


def stage_sample(cfg):
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    from vllm.inputs import TokensPrompt
    from cape.models.load import model_path
    from cape.utils.config import resolve_model
    A = cfg.actor; X56 = _mod("x56", "scripts/56_xm_replay_extract.py"); M144 = _mod("m144", "scripts/144_v54_steer.py")
    p = model_path(resolve_model(X56.ACT[A]["model"])); tok = AutoTokenizer.from_pretrained(p)
    S, ids, specs, roll = build_prompts(A, "dev", tok); sel = S.world.isin(list(cfg.worlds_sample)).values
    S = S[sel].reset_index(drop=True); ids = [x for x, k in zip(ids, sel) if k]; print("sites", len(S), flush=True)
    gc = json.load(open(f"{p}/generation_config.json")); eos = gc["eos_token_id"] if isinstance(gc["eos_token_id"], list) else [gc["eos_token_id"]]
    kw = {"language_model_only": True} if A in ("gemma4", "qwen38", "museglimmer") else {}
    if A == "qwen38":
        kw["gdn_prefill_backend"] = "triton"
    llm = LLM(model=p, dtype="bfloat16", max_model_len=24000 + cfg.max_new + 16, gpu_memory_utilization=0.9, max_num_seqs=128, seed=54, **kw)
    sp = SamplingParams(n=cfg.K, max_tokens=cfg.max_new, stop_token_ids=eos, skip_special_tokens=False, seed=54, **M144.SAMP[A])
    outs = llm.generate([TokensPrompt(prompt_token_ids=x) for x in ids], sp); rows = []
    for (i, r), o in zip(S.iterrows(), outs):
        ep = roll[r.set].loc[r.episode_id]
        for k, c in enumerate(o.outputs):
            g = list(c.token_ids); txt = tok.decode(g, skip_special_tokens=False); trunc = len(g) >= cfg.max_new and (not g or g[-1] not in eos)
            tool, args = M144.parse_call(A, txt)
            if trunc and tool == "__final__":
                tool, args = None, None
            rows.append({"set": r.set, "episode_id": r.episode_id, "world": r.world, "fold": int(r.fold), "sample": k, "tool": tool,
                         "args_json": json.dumps(args) if isinstance(args, dict) else None,
                         "category": M144.label(specs[(r.bench, r.instance_id)], list(ep.events), int(r.site_event), tool, args),
                         "gen_ids": g, "gen_text": txt[:6000], "n_gen_tokens": len(g), "truncated": bool(trunc)})
    R = pd.DataFrame(rows); R.to_parquet(OUT / f"samples_{A}.parquet")
    print("wrote", len(R), R.category.value_counts(normalize=True).round(3).to_dict())
    v = R.groupby(["set", "episode_id"]).category.agg(lambda c: (c == "VIOLATE").any() and ((c != "VIOLATE") & (c != "PARSE")).any())
    print("mixed sites", int(v.sum()), "/", len(v), "| per-site VIOLATE rate mean %.3f" % R.assign(v=R.category == "VIOLATE").groupby(["set", "episode_id"]).v.mean().mean())


def stage_extract(cfg):
    import torch
    from transformers import AutoModelForCausalLM, AutoModelForImageTextToText, AutoTokenizer
    from cape.models.load import discover_transformer_blocks, model_path
    from cape.utils.config import resolve_model
    A = cfg.actor; X56 = _mod("x56", "scripts/56_xm_replay_extract.py"); torch.backends.cuda.enable_cudnn_sdp(False)
    p = model_path(resolve_model(X56.ACT[A]["model"])); tok = AutoTokenizer.from_pretrained(p)
    try:
        model = AutoModelForCausalLM.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    except Exception:
        model = AutoModelForImageTextToText.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    blocks, _ = discover_transformer_blocks(model); L = X56.layers_for(len(blocks)); cap = {}

    def mk(li):
        def h(mod, inp, out):
            cap[li] = (out[0] if isinstance(out, tuple) else out)[0].detach()
        return h
    for li, bl in enumerate(L):
        blocks[bl].register_forward_hook(mk(li))
    S, ids, _, _ = build_prompts(A, "dev", tok); key = {f"{r.set}|{r.episode_id}": i for i, r in enumerate(S.itertuples())}
    dec = {}
    for i, r in enumerate(S.itertuples()):                     # decision state of every development site (x- and x+)
        with torch.no_grad():
            model(input_ids=torch.tensor([ids[i]], device="cuda"), logits_to_keep=1, use_cache=False)
        dec[f"{r.set}|{r.episode_id}"] = np.stack([cap[li][-1].float().cpu().numpy() for li in range(len(L))]).astype(np.float16)
        if i % 50 == 0:
            print("decision", i, "/", len(S), flush=True)
    np.savez_compressed(OUT / f"decision_{A}_dev.npz", layers=np.array(L), **dec)
    R = pd.read_parquet(OUT / f"samples_{A}.parquet"); R["key"] = R.set + "|" + R.episode_id
    mixed = R.groupby("key").category.transform(lambda c: (c == "VIOLATE").any() and ((c != "VIOLATE") & (c != "PARSE")).any())
    R = R[mixed & (R.category != "PARSE")]; gm = {}
    for j, r in enumerate(R.itertuples()):
        x = ids[key[r.key]]; g = list(r.gen_ids); n = len(g)
        with torch.no_grad():
            model(input_ids=torch.tensor([x + g[:n - 1]], device="cuda"), logits_to_keep=1, use_cache=False)
        gm[f"{r.key}|{r.sample}"] = np.stack([cap[li][-n:].float().mean(0).cpu().numpy() for li in range(len(L))]).astype(np.float16)
        if j % 100 == 0:
            print("genmean", j, "/", len(R), flush=True)
    np.savez_compressed(OUT / f"samples_{A}_genmean.npz", **gm); print("wrote", len(dec), "decision states,", len(gm), "turn means")


def stage_direction(cfg):
    from sklearn.metrics import roc_auc_score
    A = cfg.actor; R = pd.read_parquet(OUT / f"samples_{A}.parquet"); R["key"] = R.set + "|" + R.episode_id
    Z = np.load(OUT / f"samples_{A}_genmean.npz"); L = np.load(OUT / f"decision_{A}_dev.npz")["layers"]
    R["zk"] = R.key + "|" + R["sample"].astype(str); R = R[R.zk.isin(set(Z.files))].reset_index(drop=True)
    X = np.stack([Z[k] for k in R.zk]).astype(np.float32); R["viol"] = R.category == "VIOLATE"
    out = {"layers": L, "n_mixed_sites": int(R.key.nunique()), "n_samples": len(R)}
    for k in (0, 1, "a"):
        tr = R if k == "a" else R[R.fold != k]
        for li in range(X.shape[1]):
            diffs = [X[g.index[~g.viol.values], li].mean(0) - X[g.index[g.viol.values], li].mean(0) for _, g in tr.groupby("key")]
            d = np.mean(diffs, 0); u = d / np.linalg.norm(d)
            out[f"u{k}_{li}"] = u; out[f"g{k}_{li}"] = float(np.mean([x @ u for x in diffs]))
            if k != "a":       # held-out: within-site centred projections separate non-violating from violating samples
                te = R[R.fold == k]; pr = X[te.index.values, li] @ u
                pr = pr - pd.Series(pr, index=te.index).groupby(te.key).transform("mean").values
                out[f"auroc{k}_{li}"] = float(roc_auc_score(~te.viol.values, pr))
        rng = np.random.default_rng(145 + (k if k != "a" else 2))
        for li in range(X.shape[1]):
            r = rng.normal(size=out[f"u{k}_{li}"].shape); r -= (r @ out[f"u{k}_{li}"]) * out[f"u{k}_{li}"]; out[f"r{k}_{li}"] = r / np.linalg.norm(r)
    out["cos_fold01"] = np.array([float(out[f"u0_{li}"] @ out[f"u1_{li}"]) for li in range(X.shape[1])])
    np.savez(OUT / f"dir_{A}.npz", **out)
    print({k: (np.round(v, 3).tolist() if isinstance(v, np.ndarray) and v.ndim == 1 and k == "cos_fold01" else round(v, 3) if isinstance(v, float) else v)
           for k, v in out.items() if k.startswith(("g", "auroc", "n_", "cos"))})


if __name__ == "__main__":
    c = OmegaConf.merge(D, load_config(None)); {"sample": stage_sample, "extract": stage_extract, "direction": stage_direction}[c.stage](c)
