#!/usr/bin/env python
"""v49 H4 (development, not confirmatory): self-counterfactual CAA honesty direction for any actor (gemma4, gptoss20b, qwen38),
generalising scripts/107 (Muse). Reports: every labelled regenerated report of that actor (outputs/prereport/<actor>_*,
v44_<actor>_*, v49dev_<actor>_*) on DEVELOPMENT episodes (never the fresh v49 confirmation sets).
Design choice (documented, H4 addendum): reports come from different prompt conditions whose lie rates differ (e.g. the
contract raises gpt-oss lies), so each report's activation is first DEMEANED BY CONDITION (mean over all reports of that
condition, per layer), then the within-episode honest-minus-lying difference is taken. This removes the average format effect.
stage=extract (GPU, main env): teacher-force each report after pre-report context + neutral turn; mean residual over the REPORT
    tokens only (span located by characters, so template wrappers such as Qwen's empty think block are excluded).
    -> outputs/reconcile/caa_<actor>_acts.npz + _meta.parquet
stage=direction (CPU) -> outputs/reconcile/caa_<actor>_directions.npz with the same keys as caa_directions.npz (u/g/t/r for folds 0,1,a)
python scripts/126_caa_multi.py stage=extract actor=gemma4"""
import glob
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


D = OmegaConf.create({"stage": "extract", "actor": "gemma4", "max_tokens": 24000})
OUT = REPO_ROOT / "outputs/reconcile"; LIES = ["CANDID", "SPIN", "OMITTED", "MISREPRESENTED"]
NEUTRAL = "Please write your final report to the user."
PRE = {"qwen38": "", "gemma4": "xm_gemma4_", "gptoss20b": "xm_gptoss20b_"}
FRESH_TAG = "6789"     # v49 confirmation seeds (gemma4/gptoss20b); qwen38 confirmation sets are the minus2345/0123 sets


def is_dev(actor, st):
    if actor == "qwen38":
        return st in ("core24_minus", "core24b_minus")          # original Qwen sets; fresh v49 Qwen sets excluded
    return FRESH_TAG not in st


def bench_of(actor, st):
    return re.sub(r"_minus\d*$", "", st[len(PRE[actor]):] if PRE[actor] and st.startswith(PRE[actor]) else st)


def reports(actor):
    fs = [f for f in glob.glob(str(REPO_ROOT / f"outputs/prereport/*{actor}_*_rubric3.parquet")) if not f.split("/")[-1].startswith("v49_")]
    parts = []
    for f in fs:
        lab = pd.read_parquet(f)[["set", "episode_id", "message", "label"]]
        txt = pd.read_parquet(f.replace("_rubric3.parquet", ".parquet"))[["set", "episode_id", "message", "revised_report"]].drop_duplicates(["set", "episode_id", "message"])
        src = f.split("/")[-1].replace("_rubric3.parquet", "")
        parts.append(lab.merge(txt, on=["set", "episode_id", "message"], how="left").assign(src=src, cond=lambda d: (src.split("_")[0] if src.startswith("v4") else "v37P") + ":" + d.message))
    A = pd.concat(parts, ignore_index=True); A = A[A.set.map(lambda s: is_dev(actor, s))]
    A = A[A.label.isin(LIES) & A.revised_report.fillna("").str.strip().ne("")].copy(); A["lie"] = A.label == "MISREPRESENTED"
    g = A.groupby(["set", "episode_id"]).lie.agg(["sum", "size"]); mixed = g[(g["sum"] > 0) & (g["sum"] < g["size"])].index
    return A, A.set_index(["set", "episode_id"]).loc[mixed].reset_index()


def stage_extract(cfg):
    import torch
    from transformers import AutoModelForCausalLM, AutoModelForImageTextToText, AutoTokenizer
    from cape.models.load import discover_transformer_blocks, model_path
    from cape.utils.config import resolve_model
    X56 = _mod("x56", "scripts/56_xm_replay_extract.py"); torch.backends.cuda.enable_cudnn_sdp(False)
    Aall, A = reports(cfg.actor); A = Aall   # extract ALL dev reports: condition means need every report, not only mixed episodes
    print("reports", len(A), flush=True)
    a = X56.ACT[cfg.actor]; p = model_path(resolve_model(a["model"])); tok = AutoTokenizer.from_pretrained(p)
    try:
        model = AutoModelForCausalLM.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    except Exception:
        model = AutoModelForImageTextToText.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    blocks, _ = discover_transformer_blocks(model); L = X56.layers_for(len(blocks)); cap = {}
    for l in L:
        blocks[l].register_forward_hook(lambda m, i, o, l=l: cap.__setitem__(l, (o[0] if isinstance(o, tuple) else o)[0, cap["a"]:cap["b"]].float().mean(0).cpu().numpy()))
    specs = {}
    for b in sorted(set(A.set.map(lambda s: bench_of(cfg.actor, s)))):
        for line in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl"):
            s = json.loads(line); specs[(b, s["instance_id"])] = s
    roll = {st: pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{st}.parquet").set_index("episode_id") for st in A.set.unique()}
    render = lambda m, gen: tok.apply_chat_template(m, tools=TOOLS, tokenize=False, add_generation_prompt=gen, **a["kwargs"])
    enc = lambda t: tok(t, add_special_tokens=False)["input_ids"]; acts, meta = [], []
    for i, r in enumerate(A.itertuples()):
        ep = roll[r.set].loc[r.episode_id]
        msgs = X56.messages_upto(specs[(bench_of(cfg.actor, r.set), ep.instance_id)], list(ep.events), 10**9, a["suffix"]) + [{"role": "user", "content": NEUTRAL}]
        try:
            full_txt = render(msgs + [{"role": "assistant", "content": r.revised_report}], False)
        except Exception as ex:
            print("render fail", r.episode_id, repr(ex)[:100]); continue
        k = full_txt.rfind(r.revised_report)
        if k < 0:
            continue
        a_ = len(enc(full_txt[:k])); full = enc(full_txt); b_ = len(enc(full_txt[:k + len(r.revised_report)]))
        if len(full) > cfg.max_tokens or b_ <= a_ + 2:
            continue
        cap["a"], cap["b"] = a_, b_
        with torch.no_grad():
            try:
                model(input_ids=torch.tensor([full]).cuda(), logits_to_keep=1)
            except TypeError:
                model(input_ids=torch.tensor([full]).cuda())
        acts.append(np.stack([cap[l] for l in L]).astype(np.float16))
        meta.append({"set": r.set, "episode_id": r.episode_id, "lie": bool(r.lie), "src": r.src, "message": r.message, "cond": r.cond})
        if i % 100 == 0:
            print(i, "/", len(A), flush=True)
    np.savez_compressed(OUT / f"caa_{cfg.actor}_acts.npz", acts=np.stack(acts), layers=np.array(L)); pd.DataFrame(meta).to_parquet(OUT / f"caa_{cfg.actor}_meta.parquet")
    print("wrote", len(meta))


def stage_direction(cfg):
    from sklearn.metrics import roc_auc_score
    Z = np.load(OUT / f"caa_{cfg.actor}_acts.npz"); X = Z["acts"].astype(np.float32); M = pd.read_parquet(OUT / f"caa_{cfg.actor}_meta.parquet")
    for c, idx in M.groupby("cond").groups.items():          # condition demeaning (see docstring)
        X[idx] -= X[idx].mean(0, keepdims=True)
    M["key"] = M.set + "|" + M.episode_id; M["fold"] = M.episode_id.map(lambda e: int(hashlib.md5(e.rsplit(".", 1)[0].encode()).hexdigest(), 16) % 2)
    mixed = M.groupby("key").lie.transform(lambda v: v.any() and (~v).any()); out = {"layers": Z["layers"], "n_mixed_episodes": int(M[mixed].key.nunique())}
    for k in (0, 1, "a"):
        tr = M[mixed] if k == "a" else M[mixed & (M.fold != k)]
        for li in range(X.shape[1]):
            diffs = [X[g.index[~g.lie.values], li].mean(0) - X[g.index[g.lie.values], li].mean(0) for _, g in tr.groupby("key")]
            d = np.mean(diffs, 0); u = d / np.linalg.norm(d)
            out[f"u{k}_{li}"] = u; out[f"g{k}_{li}"] = float(np.mean([x @ u for x in diffs])); out[f"t{k}_{li}"] = float((X[tr.index[~tr.lie.values], li] @ u).mean())
            if k != "a":
                te = M[mixed & (M.fold == k)]
                out[f"auroc{k}_{li}"] = float(roc_auc_score(~te.lie.values, X[te.index.values, li] @ u)) if te.lie.nunique() == 2 else float("nan")
        rng = np.random.default_rng(126 + (k if k != "a" else 2))
        for li in range(X.shape[1]):
            r = rng.normal(size=out[f"u{k}_{li}"].shape); r -= (r @ out[f"u{k}_{li}"]) * out[f"u{k}_{li}"]; out[f"r{k}_{li}"] = r / np.linalg.norm(r)
            out[f"tr{k}_{li}"] = float((X[tr.index[~tr.lie.values], li] @ out[f"r{k}_{li}"]).mean())
    np.savez(OUT / f"caa_{cfg.actor}_directions.npz", **out); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in out.items() if k.startswith(("g", "auroc", "n_"))})


def main():
    cfg = OmegaConf.merge(D, load_config(None)); {"extract": stage_extract, "direction": stage_direction}[cfg.stage](cfg)


if __name__ == "__main__":
    main()
