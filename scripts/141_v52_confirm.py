#!/usr/bin/env python
"""Prereg v52 confirmation (docs/preregistration_v52.md) on the v51 fresh sets (scripts/134 FRESH).
V1: chosen internal recipe (results/prereg_v52/frozen_<m>.joblib) vs the v51-frozen supervised text model T_sup (full development data).
V2: low-label versions (identical 25% development subsample): internal_low vs T_low.
Pooled within-(model, template) AUROC with per-model z-scoring; one-sided paired scenario-cluster bootstrap; Holm over V1, V2.
-> results/prereg_v52/summary.json"""
import importlib.util
import json

import joblib
import numpy as np
import pandas as pd

from cape.utils.config import REPO_ROOT


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


C = _mod("c134", "scripts/134_v51_confirm.py"); X = _mod("x137", "scripts/137_v52_explore.py"); E = C.E
O = REPO_ROOT / "results/prereg_v52"


def score_parts(parts, J):
    out = []
    for b, l, a in parts:
        s = X.block(J, b, l) @ a["w"] + a["b"]; out.append((s - a["mu"]) / a["sd"])
    return np.mean(out, 0)


def fresh(model):
    if not (O / f"frozen_{model}.joblib").exists():   # deviation 1: Muse is excluded by the prereg (no frozen recipe); skip it
        return None
    F = C.fresh(model)
    if F is None:
        return None
    Ms = []
    for st in C.FRESH[model]["sets"]:
        bench = st.replace(f"xm_{model}_", "").rsplit("_minus", 1)[0]; p = REPO_ROOT / f"outputs/xm_feats/rep_{model}_{bench}{C.FRESH[model]['tag']}.npz"
        if p.exists():
            Z = np.load(p); M = pd.read_parquet(str(p).replace(".npz", "_meta.parquet"))[["set", "episode_id"]]
            for k, c in (("pre_report", "X_pre"), ("pre_m8", "X_m8"), ("honest", "X_h"), ("conceal", "X_c")):
                M[c] = list(Z[k].astype(np.float32))
            Ms.append(M)
    if not Ms:
        return None
    J = F.merge(pd.concat(Ms).drop_duplicates(["set", "episode_id"]), on=["set", "episode_id"], how="inner").reset_index(drop=True)
    T = {}
    for st, g in J.groupby("set"):
        T.update({(st, k): v for k, v in E.texts(st, g.episode_id.tolist()).items()})
    J["full"] = [T[(s, e)][0] + " " + T[(s, e)][1] for s, e in zip(J.set, J.episode_id)]
    A = joblib.load(O / f"frozen_{model}.joblib"); V = joblib.load(REPO_ROOT / f"results/prereg_v51/frozen_{model}.joblib")
    Xa = lambda d: np.concatenate([X.block(d, b, l) for b in X.BLOCKS for l in range(5)], 1)
    I = A["model"].decision_function(Xa(J)) if A["kind"] == "L_all" else score_parts(A["parts"], J)
    low = A["low"]; Il = low["model"].decision_function(Xa(J)) if low["kind"] == "L_all" else score_parts(low["parts"], J)
    return J.assign(I=I, T_sup=V["T"]["model"].decision_function(V["T"]["tfidf"].transform(J.full)), I_low=Il,
                    T_low=low["T"]["model"].decision_function(low["T"]["tfidf"].transform(J.full)), y=(J.label == "MISREPRESENTED").astype(int),
                    model=model)[["set", "episode_id", "scenario_id", "template", "model", "y", "I", "T_sup", "I_low", "T_low"]]


def main():
    have = {m: d for m in C.FRESH if (d := fresh(m)) is not None and len(d)}
    D = pd.concat(list(have.values()), ignore_index=True)
    for c in ("I", "T_sup", "I_low", "T_low"):
        D[c] = D.groupby("model")[c].transform(lambda v: (v - v.mean()) / (v.std() + 1e-9))
    out = {"models": {m: {"n": int(len(d)), "lies": int(d.y.sum())} for m, d in have.items()},
           "auroc_pooled": {c: round(C.auc(D, c), 4) for c in ("I", "T_sup", "I_low", "T_low")},
           "V1_I_vs_Tsup": C.boot_diff(D, "I", "T_sup"), "V2_Ilow_vs_Tlow": C.boot_diff(D, "I_low", "T_low"),
           "per_model": {m: {c: round(C.auc(d.assign(model=m), c), 4) for c in ("I", "T_sup", "I_low", "T_low")} for m, d in have.items()}}
    ps = {k: out[k]["p_one_sided"] for k in ("V1_I_vs_Tsup", "V2_Ilow_vs_Tlow")}; order = sorted(ps, key=ps.get); run = 0
    for i, k in enumerate(order):
        run = max(run, min(1.0, ps[k] * (2 - i))); out[k]["holm_p"] = round(run, 5)
    out["COMPLETE"] = len(have) == 4
    O.mkdir(parents=True, exist_ok=True); (O / "summary.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
