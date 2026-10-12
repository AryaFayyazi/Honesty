#!/usr/bin/env python
"""Exploratory (DEVELOPMENT sets only; feeds the v57 preregistration): when does the violation become readable?
Unit = a proposed (non-read) action event after the reveal in an informed x- episode (scripts/56 features at that event:
'pre' = residual at the last token before the turn's tool-call markup, i.e. after the turn's reasoning, before the action is
written). Positives: the h-th proposed action before the first unauthorized action of a violating episode (h = 0 is the violating
turn itself). Negatives: post-reveal proposed actions of non-violating informed episodes.
Controls: (1) AUROC within (model, template, tool) strata, i.e. same tool being called; (2) position matching: negatives
restricted to the same index k (proposed actions since the reveal) as the positives' distribution, by stratified sampling;
(3) supervised text baseline on exactly what a CoT monitor sees at that moment: history (reasoning, messages, calls, results) +
the current turn's reasoning and message, WITHOUT the tool call itself. Same scenario folds for both.
python scripts/153_vhorizon_explore.py models='[gemma4,gptoss20b,museglimmer,qwen38]' -> results/v57_explore/horizon.json"""
import glob
import hashlib
import importlib.util
import json
import re

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"models": ["gemma4", "gptoss20b", "museglimmer", "qwen38"], "H": [0, 1, 2], "feat": "pre", "max_pos": 1500})
PRE = {"gemma4": "xm_gemma4_", "gptoss20b": "xm_gptoss20b_", "museglimmer": "xm_museglimmer_", "qwen38": "xm_qwen38_"}
TAG = re.compile(r"<\|[^|<>]{0,40}\|>")


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


M150 = _mod("m150", "scripts/150_v55_analysis.py"); M147 = _mod("m147", "scripts/147_v55_sites.py")


def is_dev(model, st):
    stem = st[len(PRE[model]):]
    if model == "qwen38":
        return M147.split_of(model, stem) == "dev"
    return M147.split_of(model, stem) == "dev" if model in ("gemma4", "gptoss20b", "museglimmer") else False


def turn_text(events, eid, specs_row):
    """history up to (not incl.) event eid with results, + event eid's reasoning and message, without its call."""
    s = [f"SYSTEM PROMPT:\n{specs_row['system_prompt']}", f"TASK:\n{specs_row['task_prompt']}"]
    for i, e in enumerate(events[:eid]):
        if not (e["is_tool_call"] and e["tool"]):
            continue
        t = f"[step {i}]"
        if (e["reasoning_text"] or "").strip():
            t += f"\n(agent reasoning) {TAG.sub(' ', e['reasoning_text'])[:3000]}"
        if (e["content_text"] or "").strip():
            t += f"\n(agent message) {TAG.sub(' ', e['content_text'])[:1500]}"
        s.append(t + f"\n(tool call) {e['tool']}({(e['args_json'] or '')[:600]})\n(tool result) {(e['tool_result'] or '')[:1500]}")
    e = events[eid]; t = f"[step {eid}]"
    if (e["reasoning_text"] or "").strip():
        t += f"\n(agent reasoning) {TAG.sub(' ', e['reasoning_text'])[:3000]}"
    if (e["content_text"] or "").strip():
        t += f"\n(agent message) {TAG.sub(' ', e['content_text'])[:1500]}"
    return "\n\n".join(s + [t])


def main():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    cfg = OmegaConf.merge(D, load_config(None)); out = {}; rng = np.random.default_rng(57)
    for A in cfg.models:
        Xs, rows = [], []
        for f in sorted(glob.glob(str(REPO_ROOT / f"outputs/xm_feats/{PRE[A]}*minus*.npz"))):
            st = f.split("/")[-1][:-4]
            if not is_dev(A, st) or not (REPO_ROOT / f"outputs/rollouts/{st}.parquet").exists():
                continue
            Mt = pd.read_parquet(f.replace(".npz", "_meta.parquet")); Z = np.load(f)[cfg.feat]
            R = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{st}.parquet", columns=["episode_id", "reveal_event", "first_unsafe_event", "instance_id"]).set_index("episode_id")
            Mt = Mt.join(R, on="episode_id"); rv = pd.to_numeric(Mt.reveal_event, errors="coerce"); fu = pd.to_numeric(Mt.first_unsafe_event, errors="coerce")
            after = Mt.event_id > rv; vio = (fu > rv) & after & (Mt.event_id <= fu); non = (rv >= 0) & fu.isna() & after
            Mt["kind"] = np.where(vio, "viol", np.where(non, "nonviol", "x")); Mt["h"] = -1; Mt["k"] = -1
            for ep, g in Mt[Mt.kind != "x"].groupby("episode_id"):
                ids = sorted(g.event_id); Mt.loc[g.index, "k"] = [ids.index(e) for e in g.event_id]
                if g.kind.iloc[0] == "viol":
                    Mt.loc[g.index, "h"] = [len(ids) - 1 - ids.index(e) for e in g.event_id]
            keep = (Mt.kind != "x").values; Xs.append(Z[keep]); Mt = Mt[keep].copy(); Mt["bench"] = re.sub(r"_minus\d*$", "", st[len(PRE[A]):]); rows.append(Mt)
        if not rows:
            print("no dev features", A); continue
        M = pd.concat(rows, ignore_index=True); X = np.concatenate(Xs).astype(np.float32); M["model"] = A
        M["fold"] = M.scenario_id.map(lambda s: int(hashlib.md5(s.encode()).hexdigest(), 16) % 2); out[A] = {}
        specs = {}
        for b in M.bench.unique():
            for l in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl"):
                x = json.loads(l); specs[(b, x["instance_id"])] = x
        roll = {}
        for h in cfg.H:
            pos = M[(M.kind == "viol") & (M.h == h)]
            if len(pos) < 40:
                continue
            pos = pos.sample(min(len(pos), cfg.max_pos), random_state=0)
            negpool = M[M.kind == "nonviol"]
            # position matching: for each positive with index k, draw two negatives with the same k (fall back to the nearest k)
            neg_idx = []
            by_k = {k: list(g.index) for k, g in negpool.groupby("k")}
            for k in pos.k:
                kk = min(by_k, key=lambda q: (abs(q - k), q))
                if by_k[kk]:
                    neg_idx += list(rng.choice(by_k[kk], min(2, len(by_k[kk])), replace=False))
            idx = np.concatenate([pos.index.values, np.unique(neg_idx)]); Dd = M.loc[idx].reset_index(drop=True); XD = X[idx]
            Dd["y"] = (Dd.kind == "viol").astype(int); cv = np.full(len(Dd), np.nan)
            for f_ in (0, 1):
                tr = Dd.fold.values != f_
                cv[~tr] = M150.score_internal(M150.fit_internal(XD[tr], Dd.y.values[tr]), XD[~tr])
            Dd["I"] = cv
            texts = []
            for r in Dd.itertuples():
                if r.set not in roll:
                    roll[r.set] = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{r.set}.parquet").set_index("episode_id")
                texts.append(turn_text(list(roll[r.set].loc[r.episode_id].events), int(r.event_id), specs[(r.bench, r.instance_id)]))
            T = np.full(len(Dd), np.nan); texts = np.array(texts, dtype=object)
            for f_ in (0, 1):
                tr = Dd.fold.values != f_; v = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
                lr = LogisticRegression(C=1.0, max_iter=3000).fit(v.fit_transform(texts[tr]), Dd.y.values[tr]); T[~tr] = lr.decision_function(v.transform(texts[~tr]))
            Dd["T"] = T
            tool_strat = Dd.assign(template=Dd.template + "|" + Dd.tool)
            res = {"n_pos": int(Dd.y.sum()), "n_neg": int((1 - Dd.y).sum()),
                   "auroc_template": {"I": round(M150.auc(Dd, "I"), 3), "T": round(M150.auc(Dd, "T"), 3)},
                   "auroc_template_x_tool": {"I": round(M150.auc(tool_strat, "I"), 3), "T": round(M150.auc(tool_strat, "T"), 3)},
                   "pos_tools": Dd[Dd.y == 1].tool.value_counts().head(4).to_dict(), "neg_tools": Dd[Dd.y == 0].tool.value_counts().head(4).to_dict()}
            out[A][f"h{h}"] = res; print(A, f"h={h}", json.dumps(res), flush=True)
    o = REPO_ROOT / "results/v57_explore"; o.mkdir(parents=True, exist_ok=True); json.dump(out, open(o / "horizon.json", "w"), indent=1)


if __name__ == "__main__":
    main()
