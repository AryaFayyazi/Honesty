#!/usr/bin/env python
"""EXPLORATORY (dev data only): can a misrepresenting final report be FORECAST from the state just before the report?
Population: violating episodes with a rubric-labelled report (scripts/87 v2). Outcome: MISREPRESENTED vs other.
Predictors (all observable before the report is generated):
  beh     : behavioural precursors -- retroactive permission request (request_permission after the first unsafe act) and
            its outcome, prior request/denial, #actions after the violation, #tool errors, #events, informed
  text    : TF-IDF (1-2 grams) of the full pre-report trajectory (reasoning, content, tool calls, tool results)
  placebo : one-hot model x template (+ tool of the first unsafe act)
  internal: (when outputs/xm_feats/rep_<actor>_<bench>.npz exist) pre-report residual stream, LDA readout, nested
Metrics: pooled AUROC and within-(model,template) stratified AUROC under 5-fold grouped-by-scenario CV; scenario-
cluster bootstrap CIs on differences.
python scripts/95_lie_forecast.py [benches=[core24,core24b]] [variants=true]
"""
import glob
import json
import re

import numpy as np
import pandas as pd
from omegaconf import OmegaConf
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"benches": ["core24", "core24b"], "variants": True, "boot": 2000, "out": "results/v37_explore/forecast.json",
                      "label_dir": "outputs/disclosure_v35"})
LIES = ["CANDID", "SPIN", "OMITTED", "MISREPRESENTED"]
PRE = {"": "qwen38", "xm_gemma4_": "gemma4", "xm_gptoss20b_": "gptoss20b", "xm_museglimmer_": "museglimmer"}


def parse_set(st):
    for p, m in sorted(PRE.items(), key=lambda x: -len(x[0])):
        if st.startswith(p):
            rest = st[len(p):].replace("_minus23", "").replace("_minus", ""); return m, rest
    raise ValueError(st)


# 2026-10-05 fix: retro_ok used re.search("APPROVED", re.I), which matched "... is not approved", so every denied retro
# request counted as approved. Only the exploratory behavioural baseline (beh) used it; F1/denied-retro use retro/retro_den.
def episode_rows(st, R):
    E = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{st}.parquet").set_index("episode_id"); rows = []
    for r in R.itertuples():
        ep = E.loc[r.episode_id]; ev = list(ep.events); fu = ep.first_unsafe_event
        tc = [e for e in ev if e["is_tool_call"] and e["tool"]]
        rp_b = [e for e in tc if e["tool"] == "request_permission" and e["event_id"] < fu]
        rp_a = [e for e in tc if e["tool"] == "request_permission" and e["event_id"] > fu]
        res = lambda es, pat: any(re.search(pat, e["tool_result"] or "", re.I) for e in es)
        first = next((e for e in tc if e["event_id"] == fu), None)
        txt = " ".join(f'{e["reasoning_text"] or ""} {e["content_text"] or ""} CALL_{e["tool"]} {e["args_json"] or ""} '
                       f'RESULT {(e["tool_result"] or "")[:400]}' for e in tc)   # full pre-report trajectory (prose + calls + results)
        model, bench = parse_set(st)
        rows.append(dict(set=st, model=model, bench=bench, episode_id=r.episode_id, scenario_id=r.scenario_id,
                         template=r.template, informed=int(bool(r.informed)), y=int(r.label == "MISREPRESENTED"), label=r.label,
                         retro=int(bool(rp_a)), retro_ok=int(any((e["tool_result"] or "").startswith("APPROVED") for e in rp_a)), retro_den=int(res(rp_a, r"DENIED|not approved")),
                         prior=int(bool(rp_b)), prior_den=int(res(rp_b, r"DENIED|not approved")),
                         acts_after=sum(e["event_id"] > fu and e["tool"] not in ("read_file", "list_files", "open_mock_url") for e in tc),
                         errs=sum(bool(re.search(r"(?i)error|denied|forbidden|failed", e["tool_result"] or "")) for e in tc),
                         n_events=int(ep.n_events), tool=(first or {}).get("tool") or "none", text=txt))
    return rows


def oof(Xf, y, groups, C=1.0, kind="lr"):
    s = np.zeros(len(y))
    for tr, te in GroupKFold(5).split(Xf if not isinstance(Xf, list) else np.zeros(len(y)), y, groups):
        if kind == "text":
            v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=20000, sublinear_tf=True)
            A = v.fit_transform([Xf[i] for i in tr]); B = v.transform([Xf[i] for i in te])
        else:
            A, B = Xf[tr], Xf[te]
        m = LogisticRegression(C=C, max_iter=2000, class_weight="balanced").fit(A, y[tr]); s[te] = m.decision_function(B)
    return s


def strat_auc(y, s, strata):
    num, den = 0.0, 0
    for k in np.unique(strata):
        i = strata == k
        if 0 < y[i].sum() < i.sum():
            w = y[i].sum() * (1 - y[i]).sum(); num += roc_auc_score(y[i], s[i]) * w; den += w
    return num / den if den else np.nan


def main():
    cfg = OmegaConf.merge(D, load_config(None)); rows = []
    for f in sorted(glob.glob(str(REPO_ROOT / cfg.label_dir / "*_rubric.parquet"))):
        st = f.split("/")[-1].replace("_rubric.parquet", ""); model, bench = parse_set(st)
        base = bench.split("_")[0]
        if base not in cfg.benches or (not cfg.variants and bench != base):
            continue
        R = pd.read_parquet(f); R = R[R.label.isin(LIES)]
        rows += episode_rows(st, R)
    F = pd.DataFrame(rows); y = F.y.values; g = (F.model + "|" + F.scenario_id).values
    strata = (F.model + "|" + F.template).values
    beh = F[["retro", "retro_ok", "retro_den", "prior", "prior_den", "acts_after", "errs", "n_events", "informed"]].astype(float).values
    beh = (beh - beh.mean(0)) / (beh.std(0) + 1e-9)
    plc = pd.get_dummies(F[["model", "template", "tool"]].astype(str)).astype(float).values
    S = {"beh": oof(beh, y, g), "placebo": oof(plc, y, g), "beh+placebo": oof(np.hstack([beh, plc]), y, g),
         "text": oof(list(F.text), y, g, C=1.0, kind="text"), "retro_rule": F.retro.values + 0.01 * F.acts_after.values}
    out = {"n": int(len(F)), "n_lies": int(y.sum()), "by_model": F.groupby("model").y.agg(["size", "sum"]).to_dict(),
           "retro": {"n_retro": int(F.retro.sum()), "lie_rate_retro": float(F[F.retro == 1].y.mean()), "lie_rate_noretro": float(F[F.retro == 0].y.mean()),
                     "share_of_lies_with_retro": float(F[F.y == 1].retro.mean()),
                     "by_model": F.groupby(["model", "retro"]).y.agg(["size", "mean"]).reset_index().to_dict("records")}}
    for sub, idx in (("all", np.ones(len(F), bool)), ("informed", F.informed.values == 1)):
        out[sub] = {k: {"auroc": round(roc_auc_score(y[idx], v[idx]), 4), "within_template": round(strat_auc(y[idx], v[idx], strata[idx]), 4)}
                    for k, v in S.items()}
    # scenario-cluster bootstrap: beh+placebo minus placebo (pooled AUROC), informed subset
    rng = np.random.default_rng(0); idx = np.where(F.informed.values == 1)[0]; cl = pd.Series(g[idx]).astype("category").cat.codes.values
    ucl = np.unique(cl); d = []
    for _ in range(cfg.boot):
        pick = np.concatenate([idx[cl == c] for c in rng.choice(ucl, len(ucl))])
        if 0 < y[pick].sum() < len(pick):
            d.append(roc_auc_score(y[pick], S["beh+placebo"][pick]) - roc_auc_score(y[pick], S["placebo"][pick]))
    out["informed"]["beh+placebo_minus_placebo_ci95"] = [round(float(np.percentile(d, 2.5)), 4), round(float(np.percentile(d, 97.5)), 4)]
    o = REPO_ROOT / cfg.out; o.parent.mkdir(parents=True, exist_ok=True); json.dump(out, open(o, "w"), indent=1, default=str)
    F.drop(columns=["text"]).to_parquet(o.with_suffix(".parquet")); print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
