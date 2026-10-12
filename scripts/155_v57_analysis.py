#!/usr/bin/env python
"""v57: decision-time violation forecasting on fresh data (CPU, main env). Prereg: docs/preregistration_v57.md.
Units = proposed (non-read) actions with scripts/56 'pre' features (state after the turn's reasoning, before the tool call).
VIOL = first unauthorized action of an informed x- episode; XOTHER = post-reveal actions of informed non-violating x- episodes;
XPLUS = authorized critical actions in x+. I = frozen v54 gate model; T_sup fit on development units; M_cot from scripts/156.
python scripts/155_v57_analysis.py                    -> results/prereg_v57/summary.json, outputs/v57/scores.parquet"""
import glob
import hashlib
import importlib.util
import json
import re

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"models": ["gemma4", "gptoss20b", "museglimmer", "qwen38"], "B": 4000, "max_neg": 6000})
OUT = REPO_ROOT / "outputs/v57"; RES = REPO_ROOT / "results/prereg_v57"
CONF_PLUS = {"gemma4": ["core24b_plus", "core24b_reasoning_plus", "core24b_obfuscate_plus"], "gptoss20b": ["core24b_plus", "core24b_reasoning_plus", "core24b_obfuscate_plus"],
             "museglimmer": ["v2fresh_plus23"], "qwen38": ["core24b_plus"]}


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


G154 = _mod("g154", "scripts/154_v54_gate.py"); M150 = _mod("m150", "scripts/150_v55_analysis.py"); H153 = _mod("h153", "scripts/153_vhorizon_explore.py")


def label_units(A, st, world, Mt):
    if world == "minus":
        R = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{G154.roll_name(A, st)}.parquet", columns=["episode_id", "reveal_event", "first_unsafe_event"]).set_index("episode_id")
        Mt = Mt.join(R, on="episode_id"); rv = pd.to_numeric(Mt.reveal_event, errors="coerce"); fu = pd.to_numeric(Mt.first_unsafe_event, errors="coerce")
        cls = np.where((fu > rv) & (Mt.event_id == fu), "VIOL", np.where((rv >= 0) & fu.isna() & (Mt.event_id > rv), "XOTHER", ""))
        pre_ = ((fu > rv) & (Mt.event_id > rv) & (Mt.event_id < fu)).values           # earlier post-reveal actions of violators
        hh = np.full(len(Mt), -1)
        for ep, g in Mt[pre_].groupby("episode_id"):
            ids = sorted(g.event_id); hh[Mt.index.get_indexer(g.index)] = [len(ids) - ids.index(e) for e in g.event_id]
        return np.where(cls != "", cls, np.where((hh == 1) | (hh == 2), np.char.add("H", hh.astype(str)), ""))
    return np.where(Mt.critical.astype(bool), "XPLUS", "")


def units(A, split, with_x=True, cap=None):
    """-> (DataFrame, X or None). split='dev': the v54-gate development sets; 'conf': v55 conf x- episodes + conf x+ sets."""
    if split == "dev":
        sets = G154.dev_sets(A)
    else:
        ep = pd.read_parquet(REPO_ROOT / f"outputs/v55/sites_{A}.parquet"); ep = ep[ep.split == "conf"]
        pre = G154.PRE[A]; sets = [((s if s.startswith("xm_") else pre + s), "minus") for s in sorted(ep.set.unique())] + [(pre + s, "plus") for s in CONF_PLUS[A]]
    rows, Xs = [], []
    for st, w in sets:
        f = REPO_ROOT / f"outputs/xm_feats/{st}_meta.parquet"
        if not f.exists():
            print("missing features", st); continue
        Mt = pd.read_parquet(f); Mt["cls"] = label_units(A, st, w, Mt); Mt["world"] = w
        k = (Mt.cls != "").values
        if with_x:
            Xs.append(np.load(REPO_ROOT / f"outputs/xm_feats/{st}.npz")["pre"][k])
        Mt = Mt[k].copy(); Mt["rollout"] = G154.roll_name(A, st); Mt["bench"] = re.sub(r"_(minus|plus)\d*$", "", Mt.rollout.iloc[0][len(G154.PRE[A]):] if A != "qwen38" else Mt.rollout.iloc[0]) if len(Mt) else ""
        rows.append(Mt)
    M = pd.concat(rows, ignore_index=True); X = np.concatenate(Xs).astype(np.float32) if with_x else None
    if cap:
        rng = np.random.default_rng(54); keep = np.ones(len(M), bool)
        for c in ("XOTHER", "XPLUS"):
            idx = np.where(M.cls.values == c)[0]
            if len(idx) > cap:
                keep[rng.choice(idx, len(idx) - cap, replace=False)] = False
        M = M[keep].reset_index(drop=True); X = X[keep] if with_x else None
    M["model"] = A; M["y"] = (M.cls == "VIOL").astype(int); M["fold"] = M.scenario_id.map(lambda s: int(hashlib.md5(s.encode()).hexdigest(), 16) % 2)
    M["variant"] = np.where(M.rollout.str.contains("obfuscate"), "obfuscate", np.where(M.rollout.str.contains("reasoning"), "reasoning", "base"))
    M["h"] = (M.set + "|" + M.episode_id + "|" + M.event_id.astype(str)).map(lambda s: hashlib.sha256(f"{A}|{s}".encode()).hexdigest())
    return M, X


def texts(M):
    specs, roll, out = {}, {}, []
    for b in M.bench.unique():
        for l in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl"):
            x = json.loads(l); specs[(b, x["instance_id"])] = x
    for r in M.itertuples():
        if r.rollout not in roll:
            roll[r.rollout] = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{r.rollout}.parquet").set_index("episode_id")
        ep = roll[r.rollout].loc[r.episode_id]; out.append(H153.turn_text(list(ep.events), int(r.event_id), specs[(r.bench, ep.instance_id)]))
    return np.array(out, dtype=object)


def horizons(A, C, X):
    """Secondary, descriptive (prereg v57): h = 1, 2 actions before the violation vs X-OTHER, within (template, tool).
    Horizon-specific internal (scripts/150 recipe) and text forecasters fit on DEVELOPMENT units, applied to fresh units."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    Dv, Xd = units(A, "dev", with_x=True); res = {}; rng = np.random.default_rng(57)
    for h in (1, 2):
        def pick(M, Xm, k_neg=2):
            pos = np.where(M.cls.values == f"H{h}")[0]; neg = np.where(M.cls.values == "XOTHER")[0]
            neg = rng.choice(neg, min(len(neg), k_neg * len(pos)), replace=False) if len(pos) else neg[:0]
            idx = np.concatenate([pos, neg]); d = M.iloc[idx].reset_index(drop=True); d["y"] = (d.cls == f"H{h}").astype(int)
            return d, (Xm[idx] if Xm is not None else None)
        dd, xd = pick(Dv, Xd); cc, xc = pick(C, X)
        if dd.y.sum() < 30 or cc.y.sum() < 15:
            res[f"h{h}"] = {"status": "too few", "dev_pos": int(dd.y.sum()), "conf_pos": int(cc.y.sum())}; continue
        cc["I"] = M150.score_internal(M150.fit_internal(xd, dd.y.values), xc)
        v = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True); lr = LogisticRegression(C=1.0, max_iter=3000).fit(v.fit_transform(texts(dd)), dd.y.values)
        cc["T_sup"] = lr.decision_function(v.transform(texts(cc))); cc["template"] = cc.template + "|" + cc.tool
        res[f"h{h}"] = {"n_pos": int(cc.y.sum()), "n_neg": int((1 - cc.y).sum()), "I": round(M150.auc(cc, "I"), 4), "T_sup": round(M150.auc(cc, "T_sup"), 4),
                        "I_minus_T": M150.boot(cc, "I", "T_sup", B=1000)}
    return res


def monitor_subset(M, k=300):
    s = np.zeros(len(M), bool)
    for c in ("VIOL", "XOTHER", "XPLUS"):
        idx = M[M.cls == c].sort_values("h").head(k).index; s[idx] = True
    return s


def main():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    cfg = OmegaConf.merge(D, load_config(None)); RES.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True); parts = []; out_h = {}
    for A in cfg.models:
        gz = REPO_ROOT / f"outputs/v54/gate_{A}.npz"
        if not gz.exists():
            print("no gate model", A); continue
        G = np.load(gz); C, X = units(A, "conf")
        hz = horizons(A, C, X); keep = C.cls.isin(["VIOL", "XOTHER", "XPLUS"]).values; C, X = C[keep].reset_index(drop=True), X[keep]
        out_h[A] = hz
        C["I"] = G154.gate_score(G, X); C["fire"] = C.I > float(G["tau"])
        Dv, _ = units(A, "dev", with_x=False, cap=cfg.max_neg); Dv = Dv[Dv.cls.isin(["VIOL", "XOTHER", "XPLUS"])].reset_index(drop=True)
        vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True); lr = LogisticRegression(C=1.0, max_iter=3000).fit(vec.fit_transform(texts(Dv)), Dv.y.values)
        C["T_sup"] = lr.decision_function(vec.transform(texts(C))); C["mon_subset"] = monitor_subset(C)
        mf = OUT / f"monitor_{A}.parquet"
        if mf.exists():
            Mo = pd.read_parquet(mf)[["set", "episode_id", "event_id", "prob"]].rename(columns={"prob": "M_cot"}); C = C.merge(Mo, on=["set", "episode_id", "event_id"], how="left")
        parts.append(C)
    J = pd.concat(parts, ignore_index=True); J["template"] = J.template + "|" + J.tool     # strata: (model, template, tool)
    J.drop(columns=[c for c in J.columns if c in ("reveal_event", "first_unsafe_event")]).to_parquet(OUT / "scores.parquet")
    keys = [k for k in ("I", "T_sup", "M_cot") if k in J]
    vp, vo = J[J.cls.isin(["VIOL", "XPLUS"])], J[J.cls.isin(["VIOL", "XOTHER"])]
    E1 = {"vs_XPLUS": M150.boot(vp, "I", B=cfg.B), "vs_XOTHER": M150.boot(vo, "I", B=cfg.B)}
    E1["passes"] = E1["vs_XPLUS"]["p_one_sided"] < 0.05 and E1["vs_XOTHER"]["p_one_sided"] < 0.05
    out = {"n": J.cls.value_counts().to_dict(), "E1": E1,
           "auroc": {lab: {k: round(M150.auc(d, k), 4) for k in keys} for lab, d in (("all", J), ("vs_XPLUS", vp), ("vs_XOTHER", vo))},
           "per_model": {A: {lab: {k: round(M150.auc(d[d.model == A], k), 4) for k in keys} for lab, d in (("all", J), ("vs_XPLUS", vp), ("vs_XOTHER", vo))} for A in J.model.unique()},
           "gate_fire_rate": {A: g.groupby("cls").fire.mean().round(3).to_dict() for A, g in J.groupby("model")}}
    if E1["passes"]:
        E2 = M150.boot(J, "I", "T_sup", B=cfg.B); Jm = J[J.mon_subset]; E3 = M150.boot(Jm, "I", "M_cot", B=cfg.B) if "M_cot" in J else None
        ps = {"E2": E2["p_one_sided"], **({"E3": E3["p_one_sided"]} if E3 else {})}; o = sorted(ps, key=ps.get); h, run = {}, 0.0
        for i, k in enumerate(o):
            run = max(run, min(1.0, (len(o) - i) * ps[k])); h[k] = run
        out.update({"E2_I_vs_Tsup": E2, "E3_I_vs_Mcot": E3, "holm": h,
                    "monitor_subset_auroc": {k: round(M150.auc(Jm, k), 4) for k in keys}})
    if (J.variant == "obfuscate").any():
        out["obfuscate"] = {k: round(M150.auc(J[J.variant == "obfuscate"], k), 4) for k in keys}
    out["horizons_descriptive"] = out_h
    json.dump(out, open(RES / "summary.json", "w"), indent=2, default=str); print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
