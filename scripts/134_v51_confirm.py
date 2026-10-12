#!/usr/bin/env python
"""Prereg v51 confirmation (docs/preregistration_v51.md).
stage=episodes model=<m> : informed labelled fresh episodes with a report -> results/v51/episodes_<m>.parquet (input of scripts/132)
stage=analyze            : C1 I > M_cot, C2 S > T_sup (Holm), C3 obfuscation, C4/C5 per model -> results/prereg_v51/summary.json"""
import importlib.util
import json
import sys

import joblib
import numpy as np
import pandas as pd

from cape.utils.config import REPO_ROOT


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


E = _mod("e131", "scripts/131_v51_explore.py"); X95 = E.X95; LIES = E.LIES
FRESH = {"museglimmer": {"sets": [f"xm_museglimmer_core24b_minus{s}" for s in ("89", "1011", "1213", "1415")] +
                                 [f"xm_museglimmer_core24b_{v}_minus{s}" for v in ("reasoning", "obfuscate") for s in ("45", "67")], "tag": "_G"},
         "qwen38": {"sets": ["core24b_minus2345", "core24b_reasoning_minus0123", "core24b_obfuscate_minus0123"], "tag": "_H"},
         "gemma4": {"sets": ["xm_gemma4_core24b_minus10111213", "xm_gemma4_core24b_obfuscate_minus10111213"], "tag": "_K"},
         "gptoss20b": {"sets": ["xm_gptoss20b_core24b_minus10111213", "xm_gptoss20b_core24b_obfuscate_minus10111213"], "tag": "_K"}}
V = REPO_ROOT / "results/v51"; O = REPO_ROOT / "results/prereg_v51"


def fresh(model):
    rows = []
    for st in FRESH[model]["sets"]:
        f = REPO_ROOT / f"outputs/disclosure_v37/{st}_rubric.parquet"
        if f.exists():
            R = pd.read_parquet(f); rows.append(R[R.label.isin(LIES) & R.informed.astype(bool)][["episode_id", "scenario_id", "template", "label"]].assign(set=st))
    return pd.concat(rows, ignore_index=True) if rows else None


def episodes(model):
    F = fresh(model); V.mkdir(parents=True, exist_ok=True); F[["set", "episode_id"]].to_parquet(V / f"episodes_{model}.parquet"); print(model, len(F))


def scores(model):
    F = fresh(model)
    if F is None:
        return None
    Ms = []
    for st in FRESH[model]["sets"]:
        bench = st.replace(f"xm_{model}_", "").rsplit("_minus", 1)[0]; stem = f"rep_{model}_{bench}{FRESH[model]['tag']}"
        p = REPO_ROOT / f"outputs/xm_feats/{stem}.npz"
        if p.exists():
            Z = np.load(p); M = pd.read_parquet(str(p).replace(".npz", "_meta.parquet")); M["X_pre"] = list(Z["pre_report"].astype(np.float32)); M["X_m8"] = list(Z["pre_m8"].astype(np.float32)); Ms.append(M)
    if not Ms:
        return None
    J = F.merge(pd.concat(Ms).drop_duplicates(["set", "episode_id"])[["set", "episode_id", "X_pre", "X_m8"]], on=["set", "episode_id"], how="inner")
    T = {}
    for st, g in J.groupby("set"):
        T.update({(st, k): v for k, v in E.texts(st, g.episode_id.tolist()).items()})
    J["full"] = [T[(s, e)][0] + " " + T[(s, e)][1] for s, e in zip(J.set, J.episode_id)]
    Fz = joblib.load(O / f"frozen_{model}.joblib"); I = Fz["I"]
    if I["kind"] == "I_lda":
        s_i = I["model"].decision_function(I["scaler"].transform(np.stack([x[I["layer_index"]] for x in J.X_pre])))
    else:
        s_i = I["model"].decision_function(np.concatenate([np.stack(list(J.X_pre)).reshape(len(J), -1), np.stack(list(J.X_m8)).reshape(len(J), -1)], 1))
    s_t = Fz["T"]["model"].decision_function(Fz["T"]["tfidf"].transform(J.full))
    zi, zt = (s_i - Fz["zc"]["i"][0]) / Fz["zc"]["i"][1], (s_t - Fz["zc"]["t"][0]) / Fz["zc"]["t"][1]
    J = J.assign(I=s_i, T_sup=s_t, S=Fz["S"].decision_function(np.stack([zi, zt], 1)), y=(J.label == "MISREPRESENTED").astype(int), model=model,
                 variant=J.set.map(lambda s: "obfuscate" if "obfuscate" in s else ("monitored" if "reasoning" in s else "base")))
    cm = V / f"cotmon_{model}.parquet"
    if cm.exists():
        C = pd.read_parquet(cm).pivot_table(index=["set", "episode_id"], columns="variant", values="prob").reset_index().rename(columns={"cot": "M_cot", "act": "M_act"})
        J = J.merge(C, on=["set", "episode_id"], how="left")
    return J.drop(columns=["X_pre", "X_m8", "full"])


def auc(d, col):
    d = d.dropna(subset=[col])
    return float(X95.strat_auc(d.y.values, d[col].values, (d.model + "|" + d.template).values))


def boot_diff(D, a, b, B=4000, seed=51):
    D = D.dropna(subset=[a, b]); rng = np.random.default_rng(seed); cl = (D.model + "|" + D.scenario_id).values; u = np.unique(cl)
    idx = {c: np.where(cl == c)[0] for c in u}; v = []
    for _ in range(B):
        pick = np.concatenate([idx[c] for c in rng.choice(u, len(u))]); d = D.iloc[pick]; v.append(auc(d, a) - auc(d, b))
    v = np.array(v); return {"diff": round(auc(D, a) - auc(D, b), 4), "ci95": [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)],
                             "p_one_sided": float((np.sum(v <= 0) + 1) / (len(v) + 1)), "n": int(len(D)), "lies": int(D.y.sum())}


def analyze():
    parts = {m: scores(m) for m in FRESH}; have = {m: d for m, d in parts.items() if d is not None and len(d)}
    D = pd.concat(list(have.values()), ignore_index=True)
    for c in ("I", "T_sup", "S", "M_cot", "M_act"):           # per-model z-scoring
        if c in D:
            D[c] = D.groupby("model")[c].transform(lambda v: (v - v.mean()) / (v.std() + 1e-9))
    out = {"models": {m: {"n": int(len(d)), "lies": int(d.y.sum())} for m, d in have.items()}}
    out["auroc_pooled"] = {c: round(auc(D, c), 4) for c in ("I", "T_sup", "S", "M_cot", "M_act") if c in D}
    if "M_cot" in D:
        out["C1_I_vs_Mcot"] = boot_diff(D, "I", "M_cot")
    out["C2_S_vs_Tsup"] = boot_diff(D, "S", "T_sup")
    ps = {k: out[k]["p_one_sided"] for k in ("C1_I_vs_Mcot", "C2_S_vs_Tsup") if k in out}; order = sorted(ps, key=ps.get); run = 0
    for i, k in enumerate(order):
        run = max(run, min(1.0, ps[k] * (len(order) - i))); out[k]["holm_p"] = round(run, 5)
    if "M_cot" in D:
        Ob, Ba = D[D.variant == "obfuscate"], D[D.variant == "base"]
        out["C3"] = {"obfuscate_I_vs_Mcot": boot_diff(Ob, "I", "M_cot"),
                     "drop_base_to_obf": {"I": round(auc(Ba, "I") - auc(Ob, "I"), 4), "M_cot": round(auc(Ba, "M_cot") - auc(Ob, "M_cot"), 4)}}
        out["C5_I_vs_Mact"] = boot_diff(D, "I", "M_act")
    out["C4_per_model"] = {m: {c: round(auc(d.assign(model=m), c), 4) for c in ("I", "T_sup", "S", "M_cot", "M_act") if c in d} for m, d in have.items()}
    out["COMPLETE"] = len(have) == 4 and "M_cot" in D
    O.mkdir(parents=True, exist_ok=True); (O / "summary.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    st = next(a.split("=")[1] for a in sys.argv if a.startswith("stage="))
    episodes(next(a.split("=")[1] for a in sys.argv if a.startswith("model="))) if st == "episodes" else analyze()
