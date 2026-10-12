#!/usr/bin/env python
"""EXPLORATORY (post-confirmatory) diagnosis of the v29 failures on core24. Not confirmatory: any fix found here must be
preregistered (v31) and confirmed on fresh data.

python scripts/80_explore_fixes.py actor=gemma4
(i)  In distribution (same grouped folds as H2): ECG vs mono vs ECG-m = P_crit * OR(P_mono, P_unv); within-fold TPR@1%
     over compliant actions, overall and per epistemic stratum.
(ii) Zero-shot v2fresh -> core24 unseen templates: AUROC, and TPR / realized FPR at (a) the transferred source
     threshold and (b) a LABEL-FREE target threshold = 99th percentile of the gate score over ALL target actions
     (unlabeled; violations are rare, so this approximates the compliant quantile).
Output: results/xm/explore_fixes_<actor>.json
"""
import importlib.util
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.eval.statistics import auroc
from cape.utils.config import REPO_ROOT, load_config

spec = importlib.util.spec_from_file_location("ecg", REPO_ROOT / "scripts/65_epistemic_gate.py")
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
V2T = {"auth_repo_access", "con_ci_green", "con_cloud_cost", "cons_service_restart", "own_dataset_upload",
       "prov_meeting_notes", "rev_config_overwrite", "tp_billing_correction"}
D = OmegaConf.create({"actor": "gemma4"})


def log_or(a, b):
    x = np.minimum(G.ls(-a) + G.ls(-b), -1e-300)
    return np.where(x > -np.log(2), np.log(-np.expm1(x)), np.log1p(-np.exp(x)))


def scores(Xtr, Mtr, Xte):
    g = Mtr.scenario_id.values
    c = G.lda(Xtr, Mtr.crit.values, g)(Xte)
    ci = (Mtr.crit.values == 1) & (Mtr.informed.values == 1)
    a = G.lda(Xtr[ci], Mtr.harm.values[ci], g[ci])(Xte)
    cm = Mtr.crit.values == 1
    u = G.lda(Xtr[cm], 1 - Mtr.informed.values[cm], g[cm])(Xte)
    m = G.lda(Xtr, Mtr.harm.values, g)(Xte)
    return {"ecg": G.ls(c) + log_or(a, u), "mono": m, "ecg_m": G.ls(c) + log_or(m, u),
            "br_auth_mono": G.ls(c) + G.ls(m), "br_auth": G.ls(c) + G.ls(a), "br_unv": G.ls(c) + G.ls(u)}


def strata(M):
    y = M.harm.values == 1; inf = M.informed.values == 1; crit = M.crit.values == 1
    return y, inf, (~y) & ((~crit) | inf), (~y) & crit & inf


def main():
    cfg = OmegaConf.merge(D, load_config(None)); G.SEEDS = [0, 1]; out = {"actor": cfg.actor, "EXPLORATORY": True}
    M, X = G.load(cfg.actor, "core24", "mean8", 2)
    scen = M.scenario_id.values; u = np.array(sorted(set(scen)))
    f = {s: i % 5 for i, s in enumerate(np.random.default_rng(0).permutation(u))}; folds = np.array([f[s] for s in scen])
    S = {}
    for k in range(5):
        tr, te = folds != k, folds == k
        for a_, v in scores(X[tr], M[tr].reset_index(drop=True), X[te]).items():
            S.setdefault(a_, np.zeros(len(M)))[te] = v
    y, inf, comp, hard = strata(M); out["in_dist"] = {}
    for a_, s in [(k, v) for k, v in S.items() if not k.startswith("br_")]:
        h = np.zeros(len(M), bool); hh = np.zeros(len(M), bool)
        for k in range(5):
            fk = folds == k; h[fk] = s[fk] >= np.quantile(s[fk & comp], .99); hh[fk] = s[fk] >= np.quantile(s[fk & hard], .99)
        out["in_dist"][a_] = {"TPR@1%": round(float(h[y].mean()), 3), "TPR@1%hard": round(float(hh[y].mean()), 3),
                              "informed": round(float(h[y & inf].mean()), 3), "uninformed": round(float(h[y & ~inf].mean()), 3)}
    # split-conformal union: fire if (auth branch >= its (1-a/2) compliant quantile) OR (unv branch >= its (1-a/2) quantile)
    for nm, ab in (("union_mono", "br_auth_mono"), ("union_auth", "br_auth")):
        h = np.zeros(len(M), bool)
        for k in range(5):
            fk = folds == k
            h[fk] = (S[ab][fk] >= np.quantile(S[ab][fk & comp], .995)) | (S["br_unv"][fk] >= np.quantile(S["br_unv"][fk & comp], .995))
        out["in_dist"][nm] = {"TPR@1%": round(float(h[y].mean()), 3), "realized_FPR_compliant": round(float(h[comp].mean()), 4),
                              "FPR_hard": round(float(h[hard].mean()), 4), "informed": round(float(h[y & inf].mean()), 3),
                              "uninformed": round(float(h[y & ~inf].mean()), 3)}
    # zero-shot transfer
    Mv, Xv = G.load(cfg.actor, "v2fresh", "mean8", 2)
    new = ~M.template.isin(V2T).values; Mc, Xc = M[new].reset_index(drop=True), X[new]
    sv = Mv.scenario_id.values; trs = np.array(sorted(set(sv))); cal = set(np.random.default_rng(10).permutation(trs)[: len(trs) // 4])
    ic = np.isin(sv, list(cal)); _, _, comp_v, _ = strata(Mv)
    sc = scores(Xv[~ic], Mv[~ic].reset_index(drop=True), np.concatenate([Xv[ic], Xc])); nc = ic.sum()
    yc, infc, compc, hardc = strata(Mc); out["transfer"] = {}
    for nm, ab in (("union_mono", "br_auth_mono"),):
        A_, U_ = sc[ab][nc:], sc["br_unv"][nc:]
        hlf = (A_ >= np.quantile(A_, .995)) | (U_ >= np.quantile(U_, .995))      # label-free target thresholds
        out.setdefault("transfer", {})[nm + "_labelfree"] = {"TPR": round(float(hlf[yc].mean()), 3), "FPR": round(float(hlf[compc].mean()), 4)}
    for a_, s in sc.items():
        if a_.startswith("br_"):
            continue
        s_cal, s_te = s[:nc], s[nc:]
        thr_src = np.quantile(s_cal[comp_v[ic]], .99); thr_lf = np.quantile(s_te, .99)   # label-free target threshold
        out["transfer"][a_] = {"auroc": round(float(auroc(np.r_[np.ones(yc.sum()), np.zeros(compc.sum())], np.r_[s_te[yc], s_te[compc]])), 4),
                               "src_thr": {"TPR": round(float((s_te[yc] >= thr_src).mean()), 3), "FPR": round(float((s_te[compc] >= thr_src).mean()), 4)},
                               "labelfree_thr": {"TPR": round(float((s_te[yc] >= thr_lf).mean()), 3), "FPR": round(float((s_te[compc] >= thr_lf).mean()), 4),
                                                 "TPR_hard_FPR": round(float((s_te[hardc] >= thr_lf).mean()), 4)}}
    print(json.dumps(out, indent=1))
    (REPO_ROOT / f"results/xm/explore_fixes_{cfg.actor}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
