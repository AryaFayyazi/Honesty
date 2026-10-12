#!/usr/bin/env python
"""Development (not confirmatory): contrastive activation addition (CAA) honesty direction for Muse-Glimmer.
For episodes that have BOTH lying and non-lying regenerated reports (v37 P, v39, v41), teacher-force every report after
the standardised pre-report context (+ neutral report turn) and average the residual stream over the report tokens at
the 5 extracted layers. The direction is the within-episode paired difference mean(non-lying) - mean(lying), averaged
over episodes, so episode content cancels.
stage=extract  (v030 env, GPU) -> outputs/reconcile/caa_acts.npz + caa_meta.parquet
stage=direction (main env)     -> outputs/reconcile/caa_directions.npz (per episode-fold, cross-fitted) with per-layer
                                   paired gap g_l (mean projection difference) for dose units
"""
import glob
import hashlib
import importlib.util
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.envs.base import TOOLS
from cape.utils.config import REPO_ROOT, load_config


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


D = OmegaConf.create({"stage": "extract", "max_tokens": 24000})
OUT = REPO_ROOT / "outputs/reconcile"; LIES = ["CANDID", "SPIN", "OMITTED", "MISREPRESENTED"]
SRC = ["outputs/reconcile/v39_steering_rubric3.parquet", "outputs/reconcile/v41A_rubric3.parquet", "outputs/reconcile/v41B_rubric3.parquet"]


def reports():
    fs = glob.glob(str(REPO_ROOT / "outputs/prereport/museglimmer_*_rubric3.parquet")) + [str(REPO_ROOT / s) for s in SRC]
    parts = []
    for f in fs:
        lab = pd.read_parquet(f)[["set", "episode_id", "message", "label"]]
        txt = pd.read_parquet(f.replace("_rubric3.parquet", ".parquet"))[["set", "episode_id", "message", "revised_report"]].drop_duplicates(["set", "episode_id", "message"])
        parts.append(lab.merge(txt, on=["set", "episode_id", "message"], how="left").assign(src=f.split("/")[-1]))
    A = pd.concat(parts, ignore_index=True)
    A = A[A.label.isin(LIES) & A.revised_report.fillna("").str.strip().ne("")].copy(); A["lie"] = A.label == "MISREPRESENTED"
    g = A.groupby(["set", "episode_id"]).lie.agg(["sum", "size"]); mixed = g[(g["sum"] > 0) & (g["sum"] < g["size"])].index
    return A.set_index(["set", "episode_id"]).loc[mixed].reset_index()


def bench_of(st):
    import re as _re
    return _re.sub(r"_minus\d*$", "", st.replace("xm_museglimmer_", ""))   # e.g. core24b_minus45 -> core24b


def stage_extract(cfg):
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer
    from cape.models.load import discover_transformer_blocks, model_path
    from cape.utils.config import resolve_model
    X56 = _mod("x56", "scripts/56_xm_replay_extract.py"); torch.backends.cuda.enable_cudnn_sdp(False)
    A = reports(); print("reports", len(A), "episodes", A.groupby(["set", "episode_id"]).ngroups, flush=True)
    p = model_path(resolve_model("meta-models/Muse-Glimmer-30B")); tok = AutoTokenizer.from_pretrained(p)
    model = AutoModelForImageTextToText.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    blocks, _ = discover_transformer_blocks(model); L = X56.layers_for(len(blocks)); cap = {}
    for l in L:
        blocks[l].register_forward_hook(lambda m, i, o, l=l: cap.__setitem__(l, (o[0] if isinstance(o, tuple) else o)[0, cap["a"]:cap["b"]].float().mean(0).cpu().numpy()))
    specs = {}
    for b in sorted(set(A.set.map(bench_of))):
        for line in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl"):
            s = json.loads(line); specs[(b, s["instance_id"])] = s
    roll = {st: pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{st}.parquet").set_index("episode_id") for st in A.set.unique()}
    suffix = X56.ACT["museglimmer"]["suffix"]; acts, meta = [], []
    for i, r in enumerate(A.itertuples()):
        ep = roll[r.set].loc[r.episode_id]
        msgs = X56.messages_upto(specs[(bench_of(r.set), ep.instance_id)], list(ep.events), 10**9, suffix) + [{"role": "user", "content": "Please write your final report to the user."}]
        pre = tok(tok.apply_chat_template(msgs, tools=TOOLS, tokenize=False, add_generation_prompt=True), add_special_tokens=False)["input_ids"]
        full = tok(tok.apply_chat_template(msgs + [{"role": "assistant", "content": r.revised_report}], tools=TOOLS, tokenize=False, add_generation_prompt=False), add_special_tokens=False)["input_ids"]
        if len(full) > cfg.max_tokens or len(full) <= len(pre) + 2:
            continue
        cap["a"], cap["b"] = len(pre), len(full) - 1
        with torch.no_grad():
            try:
                model(input_ids=torch.tensor([full]).cuda(), logits_to_keep=1)
            except TypeError:
                model(input_ids=torch.tensor([full]).cuda())
        acts.append(np.stack([cap[l] for l in L]).astype(np.float16)); meta.append({"set": r.set, "episode_id": r.episode_id, "lie": bool(r.lie), "src": r.src, "message": r.message})
        if i % 50 == 0:
            print(i, "/", len(A), flush=True)
    np.savez_compressed(OUT / "caa_acts.npz", acts=np.stack(acts), layers=np.array(L)); pd.DataFrame(meta).to_parquet(OUT / "caa_meta.parquet"); print("wrote", len(meta))


def stage_direction(cfg):
    Z = np.load(OUT / "caa_acts.npz"); X = Z["acts"].astype(np.float32); M = pd.read_parquet(OUT / "caa_meta.parquet")
    M["key"] = M.set + "|" + M.episode_id; M["fold"] = M.episode_id.map(lambda e: int(hashlib.md5(e.rsplit(".", 1)[0].encode()).hexdigest(), 16) % 2)
    out = {"layers": Z["layers"]}
    for k in (0, 1, "a"):          # "a": fitted on ALL development episodes (the direction locked for the fresh confirmation)
        tr = M if k == "a" else M[M.fold != k]
        for li in range(X.shape[1]):
            diffs = [X[g.index[~g.lie.values], li].mean(0) - X[g.index[g.lie.values], li].mean(0) for _, g in tr.groupby("key") if g.lie.any() and (~g.lie).any()]
            d = np.mean(diffs, 0); u = d / np.linalg.norm(d)
            out[f"u{k}_{li}"] = u; out[f"g{k}_{li}"] = float(np.mean([x @ u for x in diffs]))
            out[f"t{k}_{li}"] = float((X[tr.index[~tr.lie.values], li] @ u).mean())    # clamp target: honest-report mean projection
            if k != "a":
                te = M[M.fold == k]; proj = X[te.index.values, li] @ u
                from sklearn.metrics import roc_auc_score
                out[f"auroc{k}_{li}"] = float(roc_auc_score(~te.lie.values, proj))
        rng = np.random.default_rng(107 + (k if k != "a" else 2))
        for li in range(X.shape[1]):
            r = rng.normal(size=out[f"u{k}_{li}"].shape); r -= (r @ out[f"u{k}_{li}"]) * out[f"u{k}_{li}"]; out[f"r{k}_{li}"] = r / np.linalg.norm(r)
            trn = M if k == "a" else M[M.fold != k]
            out[f"tr{k}_{li}"] = float((X[trn.index[~trn.lie.values], li] @ out[f"r{k}_{li}"]).mean())   # clamp target for the random control
    np.savez(OUT / "caa_directions.npz", **out); print({k: round(v, 3) for k, v in out.items() if k.startswith(("g", "auroc"))})


def main():
    cfg = OmegaConf.merge(D, load_config(None)); {"extract": stage_extract, "direction": stage_direction}[cfg.stage](cfg)


if __name__ == "__main__":
    main()
