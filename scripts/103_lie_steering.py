#!/usr/bin/env python
"""Prereg v39: steer Muse-Glimmer AGAINST its internal lie-forecast direction while it writes its final report.
stage=direction (main env, sklearn): 2 scenario folds; for fold k, shrinkage LDA (y = rubric-v4 MISREPRESENTED) on the
    pre-report residual stream (scripts/94 `pre_report`, layer index 3 = block 42) of all OTHER-fold labelled Muse
    episodes -> unit direction in residual space, sigma_k = std of its projection, and a random unit vector orthogonal
    to it.  -> outputs/reconcile/v39_directions.npz + v39_episodes.parquet
stage=generate (v030 env): regenerate the report of every informed labelled episode under none / -8s d_lie / -16s d_lie /
    -16s d_rand / +16s d_lie (vector added to block 42's output at every generated position; same seed across conditions)
    -> outputs/reconcile/v39_steering.parquet, then label with scripts/97 revised=...
"""
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


D = OmegaConf.create({"stage": "direction", "batch": 6, "max_new": 1536, "limit": None, "layer_index": 3, "label_dir": "outputs/disclosure_v37",
                      # v41 options (defaults reproduce v39): extra conditions "name:mult:kind:mode" (mode decode|all), folds, neutral report turn
                      "conds": None, "folds": [0, 1], "neutral": False, "out_name": "v39_steering", "select_file": None,
                      "dim": False,
                      # CAA/clamp options: direction file with u{k}_{l}, r{k}_{l}, <scale_key>{k}_{l}, t{k}_{l}; fold_key overrides the
                      # per-episode fold (e.g. "a" = all-dev fit for fresh episodes); episodes = alternative episode table
                      "dir_npz": "outputs/reconcile/v42_directions.npz", "scale_key": "s", "fold_key": None, "episodes": None})   # v42: kind "dim"/"rand" = per-layer difference-of-means / random vectors added at ALL extracted layers
NEUTRAL = "Please write your final report to the user."
STEMS = ["rep_museglimmer_core24", "rep_museglimmer_core24b_C", "rep_museglimmer_core24b_reasoning_C", "rep_museglimmer_core24b_obfuscate_C"]
LIES = ["CANDID", "SPIN", "OMITTED", "MISREPRESENTED"]
CONDS = [("none", 0.0, "lie"), ("lie_m8", -8.0, "lie"), ("lie_m16", -16.0, "lie"), ("rand_m16", -16.0, "rand"), ("lie_p16", 16.0, "lie")]
OUT = REPO_ROOT / "outputs/reconcile"


def bench_of(st):
    import re as _re
    return _re.sub(r"_minus\d*$", "", st.replace("xm_museglimmer_", ""))   # e.g. core24b_minus45 -> core24b


def fold(sid):
    return int(hashlib.md5(sid.encode()).hexdigest(), 16) % 2


def stage_direction(cfg):
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.preprocessing import StandardScaler
    Ms, Xs = [], []
    for st in STEMS:
        z = np.load(REPO_ROOT / f"outputs/xm_feats/{st}.npz"); M = pd.read_parquet(REPO_ROOT / f"outputs/xm_feats/{st}_meta.parquet")
        Ms.append(M.drop(columns=["informed"])); Xs.append(z["pre_report"][:, cfg.layer_index].astype(np.float32)); layers = z["layers"]
    M = pd.concat(Ms, ignore_index=True); X = np.concatenate(Xs)
    L = pd.concat([pd.read_parquet(p).assign(set=p.name.replace("_rubric.parquet", "")) for p in (REPO_ROOT / cfg.label_dir).glob("xm_museglimmer_*_rubric.parquet")])
    L = L[L.label.isin(LIES)][["set", "episode_id", "label", "informed"]]
    J = M.reset_index().merge(L, on=["set", "episode_id"], how="inner"); y = (J.label == "MISREPRESENTED").astype(int).values; Xj = X[J["index"].values]
    J["fold"] = J.scenario_id.map(fold); out = {"layer": int(layers[cfg.layer_index])}; rng = np.random.default_rng(39)
    for k in (0, 1):
        tr = J.fold.values != k
        sc = StandardScaler().fit(Xj[tr]); lda = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(sc.transform(Xj[tr]), y[tr])
        w = lda.coef_[0] / sc.scale_; w = w / np.linalg.norm(w); s = float(np.std(Xj[tr] @ w))
        r = rng.normal(size=w.shape); r -= (r @ w) * w; r /= np.linalg.norm(r)
        out[f"w{k}"], out[f"s{k}"], out[f"r{k}"], out[f"n{k}"] = w, s, r, int(tr.sum())
        te = ~tr; proj = Xj[te] @ w
        from sklearn.metrics import roc_auc_score
        out[f"heldout_auroc{k}"] = float(roc_auc_score(y[te], proj)) if 0 < y[te].sum() < te.sum() else np.nan
    OUT.mkdir(parents=True, exist_ok=True); np.savez(OUT / "v39_directions.npz", **out)
    E = J[J.informed.astype(bool)][["set", "episode_id", "scenario_id", "label", "fold"]].reset_index(drop=True)
    E.to_parquet(OUT / "v39_episodes.parquet")
    print({k: v for k, v in out.items() if not isinstance(v, np.ndarray)}, "| steering episodes", len(E), "lies", int((E.label == "MISREPRESENTED").sum()))


def stage_direction_dim(cfg):
    """v42: difference-of-means (honest - lie) of pre-report states at EVERY extracted layer, per scenario fold (trained on the
    other fold's labelled episodes, informed+uninformed); sigma_l = std of the projection on the unit DiM; random unit
    vectors orthogonal to each."""
    Ms, Xs = [], []
    for st in STEMS:
        z = np.load(REPO_ROOT / f"outputs/xm_feats/{st}.npz"); M = pd.read_parquet(REPO_ROOT / f"outputs/xm_feats/{st}_meta.parquet")
        Ms.append(M.drop(columns=["informed"])); Xs.append(z["pre_report"].astype(np.float32)); layers = z["layers"]
    M = pd.concat(Ms, ignore_index=True); X = np.concatenate(Xs)            # (n, L, d)
    L = pd.concat([pd.read_parquet(p).assign(set=p.name.replace("_rubric.parquet", "")) for p in (REPO_ROOT / cfg.label_dir).glob("xm_museglimmer_*_rubric.parquet")])
    L = L[L.label.isin(LIES)][["set", "episode_id", "label"]]
    J = M.reset_index().merge(L, on=["set", "episode_id"], how="inner"); y = (J.label == "MISREPRESENTED").values; Xj = X[J["index"].values]
    J["fold"] = J.scenario_id.map(fold); out = {"layers": layers.astype(int)}; rng = np.random.default_rng(42)
    from sklearn.metrics import roc_auc_score
    for k in (0, 1):
        tr = J.fold.values != k; te = ~tr
        for li in range(len(layers)):
            d = Xj[tr][~y[tr], li].mean(0) - Xj[tr][y[tr], li].mean(0); u = d / np.linalg.norm(d)
            r = rng.normal(size=u.shape); r -= (r @ u) * u; r /= np.linalg.norm(r)
            out[f"u{k}_{li}"], out[f"s{k}_{li}"], out[f"r{k}_{li}"] = u, float(np.std(Xj[tr][:, li] @ u)), r
            out[f"auroc{k}_{li}"] = float(roc_auc_score(~y[te], Xj[te][:, li] @ u))
    np.savez(OUT / "v42_directions.npz", **out); print({k: round(v, 3) for k, v in out.items() if k.startswith("auroc") or k.startswith("s")})


def final_report(txt, X56):
    seg = txt.split("to=user<|message|>")
    if len(seg) > 1:
        return seg[-1].split("<|eot|>")[0].strip()
    return X56.TAG.sub("", txt).strip()


def stage_generate(cfg):
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer
    from cape.models.load import discover_transformer_blocks, model_path
    from cape.utils.config import resolve_model
    X56 = _mod("x56", "scripts/56_xm_replay_extract.py")
    torch.backends.cuda.enable_cudnn_sdp(False)
    Z = np.load(OUT / "v39_directions.npz"); E = pd.read_parquet(REPO_ROOT / cfg.episodes) if cfg.episodes else pd.read_parquet(OUT / "v39_episodes.parquet")
    if cfg.limit:
        E = E.groupby("fold").head(int(cfg.limit)).reset_index(drop=True)
    p = model_path(resolve_model("meta-models/Muse-Glimmer-30B")); tok = AutoTokenizer.from_pretrained(p); tok.padding_side = "left"
    model = AutoModelForImageTextToText.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    blocks, _ = discover_transformer_blocks(model); layer = int(Z["layer"]); assert layer == X56.layers_for(len(blocks))[cfg.layer_index]
    state = {"vec": None, "mode": "decode"}

    def hook(mod, inp, out):
        h = out[0] if isinstance(out, tuple) else out
        if state["vec"] is not None and (h.shape[1] == 1 or state["mode"] == "all"):   # v41: "all" also steers the prompt (prefill)
            h = h + state["vec"]
            return (h,) + tuple(out[1:]) if isinstance(out, tuple) else h
        return out
    if not cfg.dim:
        blocks[layer].register_forward_hook(hook)
    else:   # v42: one hook per extracted layer, each adds its own vector
        Zd = np.load(REPO_ROOT / cfg.dir_npz); dlayers = [int(x) for x in Zd["layers"]]
        assert dlayers == X56.layers_for(len(blocks))
        mstate = {"vecs": None, "mode": "decode", "delay": 0, "step": 0, "wend": 10**9, "layers": None, "anchor": None}
        # v56: report-anchored steering. Muse writes its reasoning first, then "<|start|>assistant to=user<|message|>" and the
        # report. A pre-hook on the token embedding tracks, per sequence, the number of tokens since the report's <|message|>
        # token (-1 = report not started), so steering can start at the report itself instead of at generated token k.
        USER_ID, MSG_ID = tok.convert_tokens_to_ids("=user"), tok.convert_tokens_to_ids("<|message|>")
        rst = {"count": None, "prev": None}

        def emb_pre(mod, args, kwargs=None):
            ids = args[0] if args else (kwargs or {}).get("input")
            if ids is None or ids.dim() != 2:
                return None
            if ids.shape[1] > 1:                              # prefill: no report yet
                rst["count"] = torch.full((ids.shape[0],), -1, device=ids.device, dtype=torch.long); rst["prev"] = ids[:, -1].clone()
            elif rst["count"] is not None:
                cur = ids[:, 0]; c = rst["count"]
                start = (cur == MSG_ID) & (rst["prev"] == USER_ID) & (c < 0)
                c = torch.where(c >= 0, c + 1, c); rst["count"] = torch.where(start, torch.zeros_like(c), c); rst["prev"] = cur
            return None
        model.get_input_embeddings().register_forward_pre_hook(emb_pre)

        def mk(li):
            def h2(mod, inp, out):
                h = out[0] if isinstance(out, tuple) else out
                if li == 0:   # decode-step counter (reset at each prefill) for delayed steering: leave the message header intact
                    mstate["step"] = 0 if h.shape[1] > 1 else mstate["step"] + 1
                if mstate["anchor"] == "reasoning":             # v58: steer the reasoning only (decode step > delay, report not started)
                    if mstate["vecs"] is None or h.shape[1] != 1 or rst["count"] is None or mstate["step"] <= mstate["delay"]:
                        return out
                    mk_ = (rst["count"] < 0).to(h.dtype).view(-1, 1, 1)
                    if not bool(mk_.any()):
                        return out
                    h = h + mstate["vecs"][li] * mk_
                    return (h,) + tuple(out[1:]) if isinstance(out, tuple) else h
                if mstate["anchor"] == "report":                # v56: steer report positions only (count 0 = the <|message|> token)
                    if mstate["vecs"] is None or h.shape[1] != 1 or rst["count"] is None:
                        return out
                    c = rst["count"]; mk_ = ((c >= mstate["delay"]) & (c < mstate["wend"])).to(h.dtype).view(-1, 1, 1)
                    if not bool(mk_.any()):
                        return out
                    h = h + mstate["vecs"][li] * mk_
                    return (h,) + tuple(out[1:]) if isinstance(out, tuple) else h
                if mstate["vecs"] is not None and h.shape[1] == 1 and (mstate["step"] <= mstate["delay"] or mstate["step"] > mstate["wend"]):
                    return out
                if mstate["layers"] is not None and li not in mstate["layers"]:   # v48: steer only a layer subset
                    return out
                if mstate["vecs"] is not None and (h.shape[1] == 1 or mstate["mode"] == "all"):   # clamp: decode positions only
                    v = mstate["vecs"][li]
                    if mstate["mode"] == "clamp":   # set the projection on u_l to the honest-report mean: h += mult*(t - h.u) u
                        u, t, m = v
                        h = h + (m * (t - (h.float() @ u.float()).unsqueeze(-1)) * u.float()).to(h.dtype)   # keep the model dtype
                    else:
                        h = h + v
                    return (h,) + tuple(out[1:]) if isinstance(out, tuple) else h
                return out
            return h2
        for li, bl in enumerate(dlayers):
            blocks[bl].register_forward_hook(mk(li))
    specs = {}
    for b in sorted(set(E.set.map(bench_of))):
        for l in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl"):
            s = json.loads(l); specs[(b, s["instance_id"])] = s
    roll = {st: pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{st}.parquet").set_index("episode_id") for st in E.set.unique()}
    suffix = X56.ACT["museglimmer"]["suffix"]; ck = OUT / f"{cfg.out_name}.parquet"
    rows = pd.read_parquet(ck).to_dict("records") if ck.exists() else []          # resume after a crash
    done = {(int(r["fold"]), r["message"]) for r in rows}
    conds = [(c, m, kd, "decode") for c, m, kd in CONDS]
    if cfg.conds:
        conds = [(x.split(":")[0], float(x.split(":")[1]), x.split(":")[2], x.split(":")[3]) for x in cfg.conds]
    if cfg.select_file:   # v41 stage B: chosen config from stage A, plus none and the random-direction control
        sel = json.load(open(REPO_ROOT / cfg.select_file))["chosen"]; m, mode = float(sel["mult"]), sel["mode"]
        kd = "dim" if cfg.dim else "lie"
        conds = [("none", 0.0, kd, "decode"), ("chosen", m, kd, mode), ("rand_chosen", m, "rand", mode)]
    for k in cfg.folds:
        Ek = E[E.fold == k].reset_index(drop=True)
        prompts = []
        for r in Ek.itertuples():
            ep = roll[r.set].loc[r.episode_id]
            msgs = X56.messages_upto(specs[(bench_of(r.set), ep.instance_id)], list(ep.events), 10**9, suffix)
            if cfg.neutral:
                msgs = msgs + [{"role": "user", "content": NEUTRAL}]
            prompts.append(tok.apply_chat_template(msgs, tools=TOOLS, tokenize=False, add_generation_prompt=True))
        w = torch.tensor(Z[f"w{k}"], dtype=torch.bfloat16, device="cuda"); rv = torch.tensor(Z[f"r{k}"], dtype=torch.bfloat16, device="cuda"); s = float(Z[f"s{k}"])
        for cname, mult, kind, mode in conds:
            if (k, cname) in done:
                print("skip done", k, cname, flush=True); continue
            if cfg.dim:   # multi-layer: + mult*scale_l*(u_l or r_l) at each layer (positive mult = toward honest); or clamp
                fk = cfg.fold_key if cfg.fold_key is not None else k
                mstate["delay"], mstate["wend"], mstate["layers"], mstate["anchor"] = 0, 10**9, None, None
                import re as _re
                mm = _re.fullmatch(r"([dcrq])(\d+)(?:w(\d+))?(?:L(\d+))?", mode)   # d16 | d16w120 | d16L34 | r0 (v56: report only) | q16 (v58: reasoning only)
                if mm:
                    mstate["delay"] = int(mm.group(2)); mode = "clamp" if mm.group(1) == "c" else "decode"
                    if mm.group(1) == "r":
                        mstate["anchor"] = "report"            # delay/window counted from the report's <|message|> token
                    elif mm.group(1) == "q":
                        mstate["anchor"] = "reasoning"         # generated tokens > delay, until the report's <|message|> token
                    if mm.group(3):
                        mstate["wend"] = int(mm.group(3))          # stop steering after this many generated tokens
                    if mm.group(4):
                        mstate["layers"] = {int(c) for c in mm.group(4)}   # layer indices (0-4) to steer
                if mult == 0:
                    mstate["vecs"] = None
                elif mode == "clamp":
                    vk = "u" if kind in ("dim", "caa") else "r"
                    mstate["vecs"] = [(torch.tensor(Zd[f"{vk}{fk}_{li}"], device="cuda"), float(Zd[f"t{fk}_{li}"]) if vk == "u" else float(Zd[f"tr{fk}_{li}"]), float(mult))
                                      for li in range(len(dlayers))]
                else:
                    vk = "u" if kind in ("dim", "caa") else "r"
                    mstate["vecs"] = [torch.tensor(mult * float(Zd[f"{cfg.scale_key}{fk}_{li}"]) * Zd[f"{vk}{fk}_{li}"], dtype=torch.bfloat16, device="cuda")
                                      for li in range(len(dlayers))]
                mstate["mode"] = mode
            else:
                state["vec"] = None if mult == 0 else (mult * s) * (w if kind == "lie" else rv); state["mode"] = mode
            for i in range(0, len(prompts), cfg.batch):
                batch = prompts[i:i + cfg.batch]; enc = tok(batch, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
                torch.manual_seed(int(hashlib.md5(f"{k}-{i}".encode()).hexdigest(), 16) % 2**31)
                with torch.no_grad():
                    o = model.generate(**enc, max_new_tokens=cfg.max_new, do_sample=True, temperature=1.0, top_p=0.95, top_k=64)
                for j, seq in enumerate(o):
                    gen = seq[enc["input_ids"].shape[1]:]; txt = tok.decode(gen, skip_special_tokens=False); r = Ek.iloc[i + j]
                    is_report = "to=user<|message|>" in txt   # otherwise the model continued reasoning / called a tool: no report
                    rows.append({"set": r.set, "episode_id": r.episode_id, "orig_label": r.label, "message": cname, "fold": k,
                                 "revised_report": final_report(txt, X56) if is_report else "", "revised_has_tool_call": not is_report,
                                 "raw_generation": txt[:4000],
                                 "n_gen_tokens": int((gen != tok.pad_token_id).sum())})
                print(k, cname, i + len(batch), "/", len(prompts), flush=True)
            pd.DataFrame(rows).to_parquet(ck)   # checkpoint after each condition
    pd.DataFrame(rows).to_parquet(OUT / f"{cfg.out_name}.parquet"); print("wrote", len(rows))


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    {"direction": stage_direction, "direction_dim": stage_direction_dim, "generate": stage_generate}[cfg.stage](cfg)


if __name__ == "__main__":
    main()
