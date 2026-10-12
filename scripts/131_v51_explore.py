#!/usr/bin/env python
"""v51 EXPLORATORY (development data only; no confirmatory claim): where and why does a text forecaster beat the internal one?
Per model, all labelled informed episodes that have report-time features (outputs/xm_feats/rep_*), EXCLUDING sets reserved for
confirmation (v47 Muse stage-1/2 sets, Qwen v49 sets; none of them have features yet anyway).
Scenario-grouped 5-fold cross-validated forecasts of the lie (rubric v4 MISREPRESENTED); within-template AUROC overall and by
prompt variant (base / monitored / obfuscate).
  internal: I_lda  = shrinkage LDA, pre_report at the F2-selected layer (the confirmatory recipe)
            I_lr   = pre_report + pre_m8 at all 5 depths -> standardise -> PCA(256) -> L2 logistic (C by inner CV)
  text    : T_full = TF-IDF(1-2 gram) + L2 logistic on reasoning + messages + tool calls + results
            T_cot  = reasoning (chain of thought) only;  T_act = messages + tool calls + results only (no reasoning)
  combo   : I_lr + T_full (logistic stack on out-of-fold scores; inner CV)
-> results/v51_explore/summary.json"""
import glob
import importlib.util
import json
import re

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from cape.utils.config import REPO_ROOT


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


X95 = _mod("x95", "scripts/95_lie_forecast.py")
LIES = ["CANDID", "SPIN", "OMITTED", "MISREPRESENTED"]
RESERVED = re.compile(r"museglimmer_core24b(_reasoning|_obfuscate)?_minus(89|1011|1213|1415|45|67)$|^core24b(_reasoning|_obfuscate)?_minus(2345|0123)$|_minus10111213$")   # + v51 fresh Gemma/gpt-oss
SEL = json.load(open(REPO_ROOT / "results/v37_explore/f2_selection.json"))
TAG = re.compile(r"<\|[^|<>]{0,40}\|>")


def texts(st, eids):
    E = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{st}.parquet").set_index("episode_id"); out = {}
    for e in eids:
        cot, act = [], []
        for ev in E.loc[e].events:
            if not (ev["is_tool_call"] and ev["tool"]):
                continue
            cot.append(TAG.sub(" ", ev["reasoning_text"] or ""))
            act.append(f'{TAG.sub(" ", ev["content_text"] or "")} CALL_{ev["tool"]} {ev["args_json"] or ""} RESULT {(ev["tool_result"] or "")[:400]}')
        out[e] = (" ".join(cot), " ".join(act))
    return out


def load(model):
    Ms = []
    for p in sorted(glob.glob(str(REPO_ROOT / f"outputs/xm_feats/rep_{model}_*.npz"))):
        if p.endswith("_meta.parquet"):
            continue
        Z = np.load(p); M = pd.read_parquet(p.replace(".npz", "_meta.parquet"))
        M["X_pre"] = list(Z["pre_report"].astype(np.float32)); M["X_m8"] = list(Z["pre_m8"].astype(np.float32)); Ms.append(M)
    M = pd.concat(Ms, ignore_index=True).drop_duplicates(["set", "episode_id"])
    M = M[~M.set.map(lambda s: bool(RESERVED.search(s)))]
    labs = []
    for st in M.set.unique():
        f = REPO_ROOT / f"outputs/disclosure_v37/{st}_rubric.parquet"
        if f.exists():
            R = pd.read_parquet(f); labs.append(R[R.label.isin(LIES) & R.informed.astype(bool)][["episode_id", "label"]].assign(set=st))
    L = pd.concat(labs); J = M.drop(columns=[c for c in ("informed",) if c in M]).merge(L, on=["set", "episode_id"], how="inner")
    J["y"] = (J.label == "MISREPRESENTED").astype(int)
    J["variant"] = J.set.map(lambda s: "obfuscate" if "obfuscate" in s else ("monitored" if "reasoning" in s else "base"))
    T = {}
    for st, g in J.groupby("set"):
        T.update({(st, k): v for k, v in texts(st, g.episode_id.tolist()).items()})
    J["cot"] = [T[(s, e)][0] for s, e in zip(J.set, J.episode_id)]; J["act"] = [T[(s, e)][1] for s, e in zip(J.set, J.episode_id)]
    J["full"] = J.cot + " " + J.act
    return J.reset_index(drop=True)


def oof(J, fit_predict):
    s = np.zeros(len(J)); y = J.y.values
    for tr, te in GroupKFold(5).split(J, y, J.scenario_id):
        s[te] = fit_predict(J.iloc[tr], J.iloc[te]) if y[tr].sum() >= 2 else 0
    return s


def i_lda(li):
    def f(tr, te):
        Xtr = np.stack([x[li] for x in tr.X_pre]); Xte = np.stack([x[li] for x in te.X_pre])
        sc = StandardScaler().fit(Xtr); m = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(sc.transform(Xtr), tr.y)
        return m.decision_function(sc.transform(Xte))
    return f


def i_lr(tr, te):
    X = lambda d: np.concatenate([np.stack(list(d.X_pre)).reshape(len(d), -1), np.stack(list(d.X_m8)).reshape(len(d), -1)], 1)
    m = make_pipeline(StandardScaler(), PCA(n_components=min(256, len(tr) - 1), random_state=0),
                      LogisticRegressionCV(Cs=[0.001, 0.01, 0.1, 1], cv=3, max_iter=3000, class_weight="balanced"))
    return m.fit(X(tr), tr.y).decision_function(X(te))


def t_lr(col):
    def f(tr, te):
        v = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=50000, sublinear_tf=True)
        m = LogisticRegressionCV(Cs=[0.1, 1, 10], cv=3, max_iter=3000, class_weight="balanced")
        return m.fit(v.fit_transform(tr[col]), tr.y).decision_function(v.transform(te[col]))
    return f


def main():
    out = {}
    for model in ("gemma4", "gptoss20b", "museglimmer", "qwen38"):
        J = load(model)
        if J.y.sum() < 10:
            out[model] = {"n": int(len(J)), "lies": int(J.y.sum()), "note": "too few lies"}; continue
        S = {"I_lda": oof(J, i_lda(SEL[model]["layer_index"])), "I_lr": oof(J, i_lr), "T_full": oof(J, t_lr("full")),
             "T_cot": oof(J, t_lr("cot")), "T_act": oof(J, t_lr("act"))}
        z = lambda v: (v - v.mean()) / (v.std() + 1e-9)
        S["combo_avg"] = z(S["I_lr"]) + z(S["T_full"])
        res = {"n": int(len(J)), "lies": int(J.y.sum()), "variants": J.variant.value_counts().to_dict()}
        for sub in ("all", "base", "monitored", "obfuscate"):
            idx = np.ones(len(J), bool) if sub == "all" else (J.variant == sub).values
            if idx.sum() < 30 or J.y[idx].sum() < 5 or (1 - J.y[idx]).sum() < 5:
                continue
            res[sub] = {k: round(float(X95.strat_auc(J.y.values[idx], v[idx], J.template.values[idx])), 3) for k, v in S.items()}
            res[sub]["n"], res[sub]["lies"] = int(idx.sum()), int(J.y[idx].sum())
        out[model] = res; print(model, json.dumps(res), flush=True)
    o = REPO_ROOT / "results/v51_explore"; o.mkdir(parents=True, exist_ok=True); (o / "summary.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
