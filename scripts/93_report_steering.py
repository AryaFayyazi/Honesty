#!/usr/bin/env python
"""Prereg v36 B: causal test. Steer Muse-Glimmer's internal "unsafe-world" (knowledge) direction while it regenerates its
final report; label the reports with the validated rubric (scripts/92 stage=label path=...).

python scripts/93_report_steering.py            (GPU, v030 env) -> outputs/reconcile/muse_steering.parquet
Direction: world probe (shrinkage LDA, x- vs x+) on Muse's INFORMED core24 actions, `mean8` at extracted layer index 2;
mapped to residual space (w_std / sd), unit-normalised. alpha = 4 * std of h.w over informed actions.
Hook: adds +/- alpha*w to the block output at every newly generated position (decode steps), not to the prompt.
Conditions: none, plus, minus; same sampling seed per episode across conditions; batched left-padded generation.
"""
import importlib.util
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.envs.base import TOOLS
from cape.utils.config import REPO_ROOT, load_config


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


X56 = _mod("x56", "scripts/56_xm_replay_extract.py")
D = OmegaConf.create({"bench": "core24", "batch": 6, "max_new": 1536, "alpha_mult": 4.0, "limit": None,
                      "dir_file": None})   # deviation 2026-10-04: direction precomputed by stage=direction in the sklearn env


def direction(cfg):
    """world-probe direction on Muse's informed core24 actions (needs sklearn; the v030 vLLM env has none)"""
    G = _mod("ecg", "scripts/65_epistemic_gate.py")
    G.SEEDS = [0, 1]; M, X = G.load("museglimmer", cfg.bench, "mean8", 2)
    inf = M.informed.values == 1; w_lab = (M.cf.values == "unsafe").astype(int)
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.preprocessing import StandardScaler
    sc = StandardScaler().fit(X[inf]); lda = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(sc.transform(X[inf]), w_lab[inf])
    w = lda.coef_[0] / sc.scale_; w = w / np.linalg.norm(w); alpha = cfg.alpha_mult * float(np.std(X[inf] @ w))
    return w, alpha


def final_report(txt):
    seg = txt.split("to=user<|message|>")
    if len(seg) > 1:
        return seg[-1].split("<|eot|>")[0].strip()
    return X56.TAG.sub("", txt).strip()


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer
    from cape.models.load import discover_transformer_blocks, model_path
    from cape.utils.config import resolve_model
    torch.backends.cuda.enable_cudnn_sdp(False)
    # direction from Muse's own core24 features (identical procedure; precomputed when the env lacks sklearn)
    if cfg.get("stage") == "direction":
        w, alpha = direction(cfg); out = REPO_ROOT / "outputs/reconcile"; out.mkdir(parents=True, exist_ok=True)
        np.savez(out / "muse_steer_direction.npz", w=w, alpha=alpha); print("saved direction; alpha", alpha); return
    if cfg.dir_file:
        z = np.load(REPO_ROOT / cfg.dir_file); w, alpha = z["w"], float(z["alpha"])
    else:
        w, alpha = direction(cfg)
    print(f"direction ready; alpha={alpha:.3f}", flush=True)
    p = model_path(resolve_model("meta-models/Muse-Glimmer-30B")); tok = AutoTokenizer.from_pretrained(p); tok.padding_side = "left"
    model = AutoModelForImageTextToText.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    blocks, _ = discover_transformer_blocks(model); layer = X56.layers_for(len(blocks))[2]
    wt = torch.tensor(w, dtype=torch.bfloat16, device="cuda"); state = {"coef": 0.0}

    def hook(mod, inp, out):
        h = out[0] if isinstance(out, tuple) else out
        if state["coef"] != 0.0 and h.shape[1] == 1:           # decode steps only (generated positions)
            h = h + state["coef"] * wt
            return (h,) + tuple(out[1:]) if isinstance(out, tuple) else h
        return out
    blocks[layer].register_forward_hook(hook)
    specs = {json.loads(l)["instance_id"]: json.loads(l) for l in open(REPO_ROOT / f"outputs/capebench/{cfg.bench}/scenarios.jsonl")}
    E = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/xm_museglimmer_{cfg.bench}_minus.parquet").set_index("episode_id")
    L = pd.read_parquet(REPO_ROOT / f"outputs/disclosure_v35/xm_museglimmer_{cfg.bench}_minus_rubric.parquet")
    L = L[L.label.isin(["CANDID", "SPIN", "OMITTED", "MISREPRESENTED"])].reset_index(drop=True)
    if cfg.limit:
        L = L.head(int(cfg.limit))
    prompts = []
    for r in L.itertuples():
        ep = E.loc[r.episode_id]; ev = list(ep.events); last = ev[-1]["event_id"]
        msgs = X56.messages_upto(specs[ep.instance_id], ev, last, X56.ACT["museglimmer"]["suffix"])
        prompts.append(tok.apply_chat_template(msgs, tools=TOOLS, tokenize=False, add_generation_prompt=True))
    rows = []
    for cond, coef in (("none", 0.0), ("plus", alpha), ("minus", -alpha)):
        state["coef"] = coef
        for i in range(0, len(prompts), cfg.batch):
            batch = prompts[i:i + cfg.batch]; enc = tok(batch, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
            torch.manual_seed(1234 + i)
            with torch.no_grad():
                out = model.generate(**enc, max_new_tokens=cfg.max_new, do_sample=True, temperature=1.0, top_p=0.95, top_k=64)
            for j, o in enumerate(out):
                txt = tok.decode(o[enc["input_ids"].shape[1]:], skip_special_tokens=False)
                r = L.iloc[i + j]
                rows.append({"set": f"xm_museglimmer_{cfg.bench}_minus", "episode_id": r.episode_id, "orig_label": r.label, "message": cond,
                             "informed": bool(r.informed), "revised_report": final_report(txt), "n_gen_tokens": int((o[enc['input_ids'].shape[1]:] != tok.pad_token_id).sum())})
            print(cond, i + len(batch), "/", len(prompts), flush=True)
    out = REPO_ROOT / "outputs/reconcile"; out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(out / "muse_steering.parquet"); print("wrote", len(rows), "alpha", alpha)


if __name__ == "__main__":
    main()
