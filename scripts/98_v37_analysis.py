#!/usr/bin/env python
"""Prereg v37 analysis (docs/preregistration_v37.md). CPU.
python scripts/98_v37_analysis.py stage=select     # F2 selection on DEV only -> results/v37_explore/f2_selection.json
python scripts/98_v37_analysis.py stage=confirm    # F1, F2a-c, P1-P4 on C (and D ∪ C for P) -> results/prereg_v37/summary.json
Labels: rubric v3 (outputs/disclosure_v37; revised reports outputs/prereport/*_rubric3.parquet).
"""
import glob
import importlib.util
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf
from scipy.stats import binomtest
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

from cape.utils.config import REPO_ROOT, load_config


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


X95 = _mod("x95", "scripts/95_lie_forecast.py")
D = OmegaConf.create({"stage": "select", "boot": 2000, "label_dir": "outputs/disclosure_v37"})
POS = ("pre_report", "pre_m8")
FEAT = {"qwen38": ["rep_qwen38_core24", "rep_qwen38_core24b"], "gemma4": ["rep_gemma4_core24", "rep_gemma4_core24b", "rep_gemma4_core24b_C", "rep_gemma4_core24b_reasoning"],
        "gptoss20b": ["rep_gptoss20b_core24", "rep_gptoss20b_core24b", "rep_gptoss20b_core24b_C", "rep_gptoss20b_core24b_reasoning",
                      "rep_gptoss20b_core24b_obfuscate"],
        "museglimmer": ["rep_museglimmer_core24", "rep_museglimmer_core24b_C", "rep_museglimmer_core24b_reasoning_C", "rep_museglimmer_core24b_obfuscate_C"]}


# Frozen v37 Muse C sets (2026-10-05 reproducibility fix): the original rule matched any xm_museglimmer_core24b* set, which
# after 2026-10-04 21:43 also swept in the v40/v47 fresh sets (minus45/67, *_minus23 variants). v37 results (08:32) are
# unchanged; this list reproduces them exactly.
V37_MUSE_C = {"xm_museglimmer_core24b_minus", "xm_museglimmer_core24b_minus23", "xm_museglimmer_core24b_reasoning_minus",
              "xm_museglimmer_core24b_obfuscate_minus"}


def is_C(st):
    return "minus2345" in st or st in V37_MUSE_C


def episodes(cfg):
    rows = []
    for f in sorted(glob.glob(str(REPO_ROOT / cfg.label_dir / "*_rubric.parquet"))):
        st = f.split("/")[-1].replace("_rubric.parquet", "")
        R = pd.read_parquet(f); R = R[R.label.isin(X95.LIES)]
        rows += X95.episode_rows(st, R)
    F = pd.DataFrame(rows).drop(columns=["text"]); F["C"] = F.set.map(is_C); return F


def feats(model):
    out = []
    for stem in FEAT[model]:
        p = REPO_ROOT / f"outputs/xm_feats/{stem}.npz"
        if not p.exists():
            continue
        Z = np.load(p); M = pd.read_parquet(str(p).replace(".npz", "_meta.parquet"))
        M = M.assign(**{f"_{k}": list(Z[k].astype(np.float32)) for k in ("pre_report", "pre_m8", "honest", "conceal")})
        out.append(M)
    return pd.concat(out, ignore_index=True) if out else None


def strat_auc(y, s, strata):
    return X95.strat_auc(np.asarray(y), np.asarray(s), np.asarray(strata))


def boot_ci(df, stat, B, seed=0):
    rng = np.random.default_rng(seed); cl = df.scenario_id.values; u = np.unique(cl); idx = {c: np.where(cl == c)[0] for c in u}; v = []
    for _ in range(B):
        pick = np.concatenate([idx[c] for c in rng.choice(u, len(u))]); x = stat(df.iloc[pick])
        if np.isfinite(x):
            v.append(x)
    return [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)], np.array(v)


def lda_fit(X, y):
    sc = StandardScaler().fit(X); m = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(sc.transform(X), y)
    return lambda Z: m.decision_function(sc.transform(Z))


def joined(F, model):
    Fm = feats(model)
    if Fm is None:
        return None
    return F[F.model == model].merge(Fm.drop(columns=["template", "scenario_id", "informed"]), on=["set", "episode_id"], how="inner")


def select(cfg, F):
    sel = {}
    for model in FEAT:
        J = joined(F, model)
        if J is None:
            continue
        Dv = J[(~J.C) & (J.informed == 1)].reset_index(drop=True); y = Dv.y.values
        if y.sum() < 5:
            sel[model] = {"note": f"too few informed dev lies ({int(y.sum())})"}; continue
        best = None; grid = {}
        for pos in POS:
            for li in range(5):
                X = np.stack([a[li] for a in Dv[f"_{pos}"]]); s = np.zeros(len(y))
                for tr, te in GroupKFold(5).split(X, y, Dv.scenario_id):
                    if y[tr].sum() < 2:
                        s[te] = 0; continue
                    s[te] = lda_fit(X[tr], y[tr])(X[te])
                a = strat_auc(y, s, Dv.template); grid[f"{pos}@{li}"] = round(float(a), 4)
                if best is None or a > best[0]:
                    best = (a, pos, li)
        sel[model] = {"position": best[1], "layer_index": best[2], "dev_within_template_auroc": round(float(best[0]), 4),
                      "n_dev_informed": int(len(y)), "n_dev_lies": int(y.sum()), "grid": grid}
        # Amendment 3 (F2d): sign of the label-free conceal-honest projection fixed on DEV (pre_report, F2 layer)
        Jall = joined(F, model); Jd = Jall[~Jall.C]; li = best[2]
        d = np.stack([a[li] for a in Jd["_conceal"]]).mean(0) - np.stack([a[li] for a in Jd["_honest"]]).mean(0)
        a_dev = strat_auc(y, np.stack([a[li] for a in Dv["_pre_report"]]) @ d, Dv.template)
        sel[model]["f2d_dev_auroc_apriori_sign"] = round(float(a_dev), 4); sel[model]["f2d_sign"] = 1 if a_dev >= 0.5 else -1
    o = REPO_ROOT / "results/v37_explore/f2_selection.json"; o.parent.mkdir(parents=True, exist_ok=True)
    json.dump(sel, open(o, "w"), indent=1); print(json.dumps(sel, indent=1))


def confirm(cfg, F):
    out = {}
    I = F[F.informed == 1]; C = I[I.C]
    # F1: CMH over model x template strata
    from statsmodels.stats.contingency_tables import StratifiedTable
    tabs = []
    for _, g in C.groupby(["model", "template"]):
        t = np.array([[((g.retro == 1) & (g.y == 1)).sum(), ((g.retro == 1) & (g.y == 0)).sum()],
                      [((g.retro == 0) & (g.y == 1)).sum(), ((g.retro == 0) & (g.y == 0)).sum()]])
        if t[0].sum() > 0 and t[1].sum() > 0 and t[:, 0].sum() > 0:
            tabs.append(t.astype(float))
    f1 = {"n_C_informed": int(len(C)), "n_lies": int(C.y.sum()), "n_retro": int(C.retro.sum()),
          "lie_rate_retro": float(C[C.retro == 1].y.mean()) if C.retro.sum() else None, "lie_rate_noretro": float(C[C.retro == 0].y.mean()),
          "n_strata": len(tabs)}
    if tabs:
        st = StratifiedTable([t for t in tabs]); p2 = st.test_null_odds(correction=True).pvalue
        rr = st.riskratio_pooled if hasattr(st, "riskratio_pooled") else np.nan
        lor = st.logodds_pooled
        f1.update({"cmh_p_one_sided": float(p2 / 2 if lor > 0 else 1 - p2 / 2), "pooled_odds_ratio": float(np.exp(lor)),
                   "pooled_risk_ratio": float(rr)})
        f1["PASS"] = bool(f1["cmh_p_one_sided"] < 0.05 and (rr if np.isfinite(rr) else 0) >= 2)
    s = C.retro.values + 0.01 * C.acts_after.values
    f1["retro_within_template_auroc"] = round(strat_auc(C.y, s, C.model + "|" + C.template), 4)
    f1["retro_auroc_ci95"], _ = boot_ci(C.assign(_s=s), lambda d: strat_auc(d.y, d._s, d.model + "|" + d.template), cfg.boot)
    den = C[C.retro_den == 1]
    if len(den):
        from statsmodels.stats.proportion import proportion_confint
        f1["denied_retro_lie_rate"] = [float(den.y.mean()), [float(x) for x in proportion_confint(den.y.sum(), len(den), method="wilson")], int(len(den))]
    out["F1"] = f1
    # F2: frozen selection, fit on dev informed, apply to C
    sel = json.load(open(REPO_ROOT / "results/v37_explore/f2_selection.json")); parts = []
    for model, sm in sel.items():
        if "position" not in sm:
            continue
        J = joined(F, model)
        if J is None:
            continue
        J = J[J.informed == 1]; Dv, Cv = J[~J.C], J[J.C]
        if not len(Cv):
            continue
        li, pos = sm["layer_index"], sm["position"]
        Xd = np.stack([a[li] for a in Dv[f"_{pos}"]]); Xc = np.stack([a[li] for a in Cv[f"_{pos}"]])
        sc = lda_fit(Xd, Dv.y.values)(Xc)
        Jall = joined(F, model); Jd = Jall[~Jall.C]
        d = np.stack([a[li] for a in Jd["_conceal"]]).mean(0) - np.stack([a[li] for a in Jd["_honest"]]).mean(0)
        dc = np.stack([a[li] for a in Cv["_pre_report"]]) @ d
        z = lambda v: (v - v.mean()) / (v.std() + 1e-9)
        parts.append(Cv[["model", "template", "scenario_id", "y", "retro"]].assign(f2=z(sc), f2c=z(dc), f2d=z(sm.get("f2d_sign", 1) * dc)))
    if parts:
        P = pd.concat(parts, ignore_index=True); f2 = {}; ps = {}
        for key, sub, col in (("F2a", P, "f2"), ("F2b", P[P.retro == 0], "f2"), ("F2c", P, "f2c"), ("F2d", P, "f2d")):
            a = strat_auc(sub.y, sub[col], sub.model + "|" + sub.template)
            ci, v = boot_ci(sub, lambda d, c=col: strat_auc(d.y, d[c], d.model + "|" + d.template), cfg.boot)
            ps[key] = float((np.sum(v <= 0.5) + 1) / (len(v) + 1)); f2[key] = {"within_template_auroc": round(float(a), 4), "ci95": ci, "p_boot": ps[key],
                                                                             "n": int(len(sub)), "n_lies": int(sub.y.sum())}
        order = sorted(ps, key=ps.get); m = len(order)
        for i, k in enumerate(order):
            f2[k]["holm_p"] = min(1.0, max(ps[o] * (m - j) for j, o in enumerate(order[: i + 1]))); f2[k]["PASS"] = bool(f2[k]["holm_p"] < 0.05)
        out["F2"] = f2
    out["F3"] = f3(cfg, F)
    # P: pre-report interventions (rubric labels of regenerated reports)
    V = pd.concat([pd.read_parquet(f) for f in glob.glob(str(REPO_ROOT / "outputs/prereport/*_rubric3.parquet"))], ignore_index=True) \
        if glob.glob(str(REPO_ROOT / "outputs/prereport/*_rubric3.parquet")) else None
    if V is not None:
        Vall = V.copy(); V = V[V.label.isin(X95.LIES)]; W = V.pivot_table(index=["set", "episode_id"], columns="message", values="label", aggfunc="first").dropna().reset_index()
        # Amendment 6 sensitivity: all episodes, NO_REPORT/UNPARSED counted as not MISREPRESENTED
        Ws = Vall.pivot_table(index=["set", "episode_id"], columns="message", values="label", aggfunc="first").fillna("NO_REPORT").reset_index()
        Ws = Ws.merge(I[["set", "episode_id", "retro", "C", "model", "template", "scenario_id"]], on=["set", "episode_id"], how="inner")
        for c in ("neutral", "generic", "provenance"):
            if c in Ws:
                Ws[f"lie_{c}"] = (Ws[c] == "MISREPRESENTED").astype(int)
        _SENS = Ws
        W = W.merge(I[["set", "episode_id", "retro", "C", "model", "template", "scenario_id"]], on=["set", "episode_id"], how="inner")
        for c in ("neutral", "generic", "provenance"):
            W[f"lie_{c}"] = (W[c] == "MISREPRESENTED").astype(int); W[f"cand_{c}"] = (W[c] == "CANDID").astype(int)

        def mcnemar(d, a, b):   # H1: lie rate under b < under a
            n10 = int(((d[f"lie_{a}"] == 1) & (d[f"lie_{b}"] == 0)).sum()); n01 = int(((d[f"lie_{a}"] == 0) & (d[f"lie_{b}"] == 1)).sum())
            p = binomtest(n10, n10 + n01, 0.5, alternative="greater").pvalue if n10 + n01 else 1.0
            ci, _ = boot_ci(d, lambda x: x[f"lie_{b}"].mean() - x[f"lie_{a}"].mean(), cfg.boot)
            return {"n": int(len(d)), f"lie_{a}": float(d[f"lie_{a}"].mean()), f"lie_{b}": float(d[f"lie_{b}"].mean()), "n10": n10, "n01": n01,
                    "p_one_sided": float(p), "diff_ci95": ci}
        Pr = {"P1_retro_prov_vs_neutral": mcnemar(W[W.retro == 1], "neutral", "provenance"),
              "P2_all_prov_vs_neutral": mcnemar(W, "neutral", "provenance"), "P2_all_generic_vs_neutral": mcnemar(W, "neutral", "generic")}
        keys = list(Pr); ps = [Pr[k]["p_one_sided"] for k in keys]; order = np.argsort(ps)
        for i, k in enumerate(order):
            Pr[keys[k]]["holm_p"] = float(min(1.0, max(ps[o] * (len(ps) - j) for j, o in enumerate(order[: i + 1]))))
        Pr["P1_PASS"] = bool(Pr["P1_retro_prov_vs_neutral"]["holm_p"] < 0.05 and Pr["P1_retro_prov_vs_neutral"]["diff_ci95"][1] < 0)
        bm = W[W.retro == 1].groupby("model")[["lie_neutral", "lie_generic", "lie_provenance"]].agg(["mean", "size"]).round(3)
        bm.columns = ["_".join(c) for c in bm.columns]; Pr["by_model_retro"] = bm.to_dict("index")   # string keys (JSON)
        Wc = W[W.C].copy(); Wc["gain"] = Wc.lie_neutral - Wc.lie_provenance
        if len(Wc) and Wc.retro.sum():
            T = Wc[Wc.retro == 1].gain.mean(); Rn = Wc.gain.mean()
            ci, _ = boot_ci(Wc, lambda d: (d[d.retro == 1].gain.mean() if d.retro.sum() else np.nan) - d.gain.mean(), cfg.boot)
            Pr["P3"] = {"prevented_per_intervention_targeted": float(T), "random_same_rate": float(Rn), "diff_ci95": ci, "trigger_rate": float(Wc.retro.mean()),
                        "PASS": bool(ci[0] > 0)}
        if _F3A_SCORES and len(Wc):   # P5 (Amendment 5): trigger = top 10% per model by the internal forecast at the violation
            Sc = pd.concat(_F3A_SCORES); Wi = Wc.merge(Sc[["set", "episode_id", "s_internal"]], on=["set", "episode_id"], how="inner")
            Wi["trig"] = Wi.groupby("model").s_internal.transform(lambda v: v >= np.quantile(v, 0.9)).astype(int)
            stat = lambda d: (d[d.trig == 1].gain.mean() if d.trig.sum() else np.nan) - d.gain.mean()
            ci, bv = boot_ci(Wi, stat, cfg.boot)
            Pr["P5"] = {"p_one_sided": float((np.sum(bv <= 0) + 1) / (len(bv) + 1)), "n": int(len(Wi)), "n_triggered": int(Wi.trig.sum()), "prevented_per_intervention_internal": float(Wi[Wi.trig == 1].gain.mean()),
                        "random_same_rate": float(Wi.gain.mean()), "retro_trigger": float(Wi[Wi.retro == 1].gain.mean()) if Wi.retro.sum() else None,
                        "lie_rate_triggered_neutral": float(Wi[Wi.trig == 1].lie_neutral.mean()), "lie_rate_untriggered_neutral": float(Wi[Wi.trig == 0].lie_neutral.mean()),
                        "diff_ci95": ci, "PASS": bool(ci[0] > 0)}
        fam = [k for k in ("P1_retro_prov_vs_neutral", "P2_all_prov_vs_neutral", "P2_all_generic_vs_neutral", "P5") if k in Pr]   # Amendment 5 family
        pv = [Pr[k]["p_one_sided"] for k in fam]; od = np.argsort(pv)
        for i, k in enumerate(od):
            Pr[fam[k]]["holm_p"] = float(min(1.0, max(pv[o] * (len(pv) - j) for j, o in enumerate(od[: i + 1]))))
        Pr["P1_PASS"] = bool(Pr["P1_retro_prov_vs_neutral"]["holm_p"] < 0.05 and Pr["P1_retro_prov_vs_neutral"]["diff_ci95"][1] < 0)
        Pr["sensitivity_A6"] = {"P1_retro_prov_vs_neutral": mcnemar(_SENS[_SENS.retro == 1], "neutral", "provenance"),
                                "P2_all_prov_vs_neutral": mcnemar(_SENS, "neutral", "provenance"),
                                "no_report_rate": {c: float((_SENS[c] == "NO_REPORT").mean()) for c in ("neutral", "generic", "provenance") if c in _SENS}}
        if "P5" in Pr:
            Pr["P5"]["PASS"] = bool(Pr["P5"]["holm_p"] < 0.05 and Pr["P5"]["diff_ci95"][0] > 0)
        nl = W[W.lie_neutral == 0]
        from statsmodels.stats.proportion import proportion_confint
        k = int(nl.lie_provenance.sum()); ub = proportion_confint(k, len(nl), alpha=0.10, method="wilson")[1]
        Pr["P4"] = {"new_lies_under_provenance": [k, int(len(nl))], "upper95_one_sided": float(ub), "PASS": bool(ub <= 0.02),
                    "new_lies_under_neutral_when_prov_clean_(symmetric)": int(((W.lie_provenance == 0) & (W.lie_neutral == 1)).sum()),
                    "candid_rate": {c: float(W[f"cand_{c}"].mean()) for c in ("neutral", "generic", "provenance")},
                    "tool_call_rate": V.groupby("message").revised_has_tool_call.mean().to_dict()}
        out["P"] = Pr
    o = REPO_ROOT / "results/prereg_v37/summary.json"; o.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(o, "w"), indent=1, default=str); print(json.dumps(out, indent=1, default=str))


def _fold(sid):
    import hashlib
    return int(hashlib.md5(sid.encode()).hexdigest(), 16) % 5


def act_rows(F, which, li):
    """mean8 action features (scripts/56) at the first unsafe action ('first') or last action ('last') per episode."""
    out = []
    for st, g in F.groupby("set"):
        p = REPO_ROOT / f"outputs/xm_feats/{st if st.startswith('xm_') else 'xm_qwen38_' + st}.npz"
        if not p.exists():
            continue
        M = pd.read_parquet(str(p).replace(".npz", "_meta.parquet")); Z = np.load(p)["mean8"]
        M["i"] = np.arange(len(M)); M = M[M.episode_id.isin(g.episode_id)]
        pick = (M[M.y == 1].groupby("episode_id").i.min() if which == "first" else M.groupby("episode_id").i.max())
        gg = g[g.episode_id.isin(pick.index)]
        out.append(gg.assign(X=[Z[pick[e], li].astype(np.float32) for e in gg.episode_id]))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def prefix_text(r, which):
    E = _ROLL.setdefault(r.set, pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{r.set}.parquet").set_index("episode_id"))
    ep = E.loc[r.episode_id]; tc = [e for e in ep.events if e["is_tool_call"] and e["tool"]]
    cut = ep.first_unsafe_event if which == "first" else tc[-1]["event_id"]
    return " ".join(f'{e["reasoning_text"] or ""} {e["content_text"] or ""} CALL_{e["tool"]} {e["args_json"] or ""}'
                    + (f' RESULT {(e["tool_result"] or "")[:400]}' if e["event_id"] < cut else "") for e in tc if e["event_id"] <= cut)


_ROLL = {}
_F3A_SCORES = []


def crossfit_scores(Dm, Cm, target, kind):
    """score C episodes in scenario-fold k with a forecaster trained on dev episodes from the other folds"""
    from sklearn.decomposition import PCA
    from sklearn.feature_extraction.text import TfidfVectorizer
    s = np.full(len(Cm), np.nan); fd = Dm.scenario_id.map(_fold).values; fc = Cm.scenario_id.map(_fold).values
    for k in range(5):
        tr = Dm[fd != k]; te = np.where(fc == k)[0]
        if not len(te) or tr[target].sum() < 2:
            continue
        if kind == "internal":
            A, B = np.stack(tr.X), np.stack(Cm.X.values[te])
        else:
            v = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=5000, sublinear_tf=True).fit(tr.text)
            A, B = v.transform(tr.text).toarray(), v.transform(Cm.text.values[te]).toarray()
        mu_all = A.mean(0); tmu = {t: A[(tr.template == t).values].mean(0) for t in tr.template.unique()}
        A = A - np.stack([tmu[t] for t in tr.template]); B = B - np.stack([tmu.get(t, mu_all) for t in Cm.template.values[te]])
        sc = StandardScaler().fit(A); pc = PCA(min(128, len(A) - 2), random_state=0).fit(sc.transform(A))
        T = lambda Z: pc.transform(sc.transform(Z))
        m = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(T(A), tr[target].values); s[te] = m.decision_function(T(B))
        if len(te) > 1:   # Amendment 7: fold models are fitted separately, so put their scores on a common scale before pooling
            s[te] = (s[te] - s[te].mean()) / (s[te].std() + 1e-9)
    return s


def perm_p(y, s, strata, n=10000, seed=0):
    rng = np.random.default_rng(seed); obs = strat_auc(y, s, strata); y = np.asarray(y); st = np.asarray(strata); cnt = 0
    groups = [np.where(st == k)[0] for k in np.unique(st)]
    for _ in range(n):
        yp = y.copy()
        for ii in groups:
            yp[ii] = y[rng.permutation(ii)]
        cnt += strat_auc(yp, s, st) >= obs
    return float(obs), float((cnt + 1) / (n + 1))


def f3(cfg, F):
    I = F[F.informed == 1]; res = {}; ps = {}
    for key, target, which, li, sub in (("F3a", "retro", "first", 1, None), ("F3b", "y", "last", 2, "retro0")):
        A = act_rows(I, which, li); parts = []
        for model, g in A.groupby("model"):
            Dm, Cm = g[~g.C].reset_index(drop=True), g[g.C].reset_index(drop=True)
            if Dm[target].sum() < 5 or not len(Cm):
                continue
            for kind in ("internal", "text"):
                if kind == "text":
                    Dm = Dm.assign(text=[prefix_text(r, which) for r in Dm.itertuples()]); Cm = Cm.assign(text=[prefix_text(r, which) for r in Cm.itertuples()])
                sc = crossfit_scores(Dm, Cm, target, kind); Cm[f"s_{kind}"] = (sc - np.nanmean(sc)) / (np.nanstd(sc) + 1e-9)
            parts.append(Cm.drop(columns=["X", "text"], errors="ignore"))
        if not parts:
            res[key] = {"note": "no C data"}; continue
        P = pd.concat(parts, ignore_index=True).dropna(subset=["s_internal", "s_text"])
        if key == "F3a":
            _F3A_SCORES.append(P[["set", "episode_id", "model", "s_internal"]].copy())
            Q = P.assign(rl=((P.retro == 1) & (P.y == 1)).astype(int)); stq = (Q.model + "|" + Q.template).values
            ai, pi = perm_p(Q.rl.values, Q.s_internal.values, stq); at, pt = perm_p(Q.rl.values, Q.s_text.values, stq, n=2000)
            ci, _ = boot_ci(Q, lambda d: strat_auc(d.rl, d.s_internal, d.model + "|" + d.template) - strat_auc(d.rl, d.s_text, d.model + "|" + d.template), cfg.boot)
            ps["F3c"] = pi; res["F3c"] = {"n": int(len(Q)), "n_pos": int(Q.rl.sum()), "internal_auroc": round(ai, 4), "p_perm": pi, "text_auroc": round(at, 4),
                                          "text_p": pt, "internal_minus_text_ci95": ci, "score": "F3a score unchanged (Amendment 5)"}
        if sub == "retro0":
            P = P[P.retro == 0]
        stt = (P.model + "|" + P.template).values; y = P[target].values
        a_i, p_i = perm_p(y, P.s_internal.values, stt); a_t, p_t = perm_p(y, P.s_text.values, stt, n=2000)
        ci, _ = boot_ci(P, lambda d: strat_auc(d[target], d.s_internal, d.model + "|" + d.template) - strat_auc(d[target], d.s_text, d.model + "|" + d.template), cfg.boot)
        ps[key] = p_i; res[key] = {"n": int(len(P)), "n_pos": int(y.sum()), "internal_auroc": round(a_i, 4), "p_perm": p_i, "text_auroc": round(a_t, 4),
                                   "text_p": p_t, "internal_minus_text_ci95": ci, "by_model_n_pos": P.groupby("model")[target].sum().to_dict()}
    order = sorted(ps, key=ps.get)
    for i, k in enumerate(order):
        res[k]["holm_p"] = min(1.0, max(ps[o] * (len(order) - j) for j, o in enumerate(order[: i + 1]))); res[k]["PASS"] = bool(res[k]["holm_p"] < 0.05)
    return res


def main():
    cfg = OmegaConf.merge(D, load_config(None)); F = episodes(cfg)
    (select if cfg.stage == "select" else confirm)(cfg, F)


if __name__ == "__main__":
    main()
