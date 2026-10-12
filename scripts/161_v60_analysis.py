#!/usr/bin/env python
"""v60 analysis (CPU, main env). Prereg: docs/preregistration_v60.md. VIOL vs XOTHER on the new seed-14-17 sets, with the frozen v57
forecasters (scripts/155 machinery). -> results/prereg_v60/summary.json"""
import importlib.util
import json

import numpy as np
import pandas as pd

from cape.utils.config import REPO_ROOT

MODELS = ["gemma4", "gptoss20b", "museglimmer", "qwen38"]; SETS = {A: f"xm_{A}_core24b_minus14151617" for A in MODELS}


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


A155 = _mod("a155", "scripts/155_v57_analysis.py"); G154 = A155.G154; M150 = A155.M150


def units_new(A):
    st = SETS[A]; Mt = pd.read_parquet(REPO_ROOT / f"outputs/xm_feats/{st}_meta.parquet"); X = np.load(REPO_ROOT / f"outputs/xm_feats/{st}.npz")["pre"]
    roll = st if A != "qwen38" else st[len("xm_qwen38_"):]
    R = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{roll}.parquet", columns=["episode_id", "reveal_event", "first_unsafe_event"]).set_index("episode_id")
    Mt = Mt.join(R, on="episode_id"); rv = pd.to_numeric(Mt.reveal_event, errors="coerce"); fu = pd.to_numeric(Mt.first_unsafe_event, errors="coerce")
    cls = np.where((fu > rv) & (Mt.event_id == fu), "VIOL", np.where((rv >= 0) & fu.isna() & (Mt.event_id > rv), "XOTHER", ""))
    k = cls != ""; Mt = Mt[k].copy(); Mt["cls"] = cls[k]; Mt["rollout"] = roll; Mt["bench"] = "core24b"; Mt["model"] = A
    Mt["y"] = (Mt.cls == "VIOL").astype(int); Mt["h"] = (Mt.set + "|" + Mt.episode_id + "|" + Mt.event_id.astype(str)).map(lambda s: __import__("hashlib").sha256(f"{A}|{s}".encode()).hexdigest())
    return Mt.reset_index(drop=True), X[k].astype(np.float32)


def monitor_subset(M):
    s = np.zeros(len(M), bool)
    for c, k in (("VIOL", 300), ("XOTHER", 600)):
        s[M[M.cls == c].sort_values("h").head(k).index] = True
    return s


def main():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    parts = []
    for A in MODELS:
        if not (REPO_ROOT / f"outputs/xm_feats/{SETS[A]}.npz").exists():
            print("missing", A); continue
        C, X = units_new(A); G = np.load(REPO_ROOT / f"outputs/v54/gate_{A}.npz"); C["I"] = G154.gate_score(G, X)
        Dv, _ = A155.units(A, "dev", with_x=False, cap=6000); Dv = Dv[Dv.cls.isin(["VIOL", "XOTHER", "XPLUS"])].reset_index(drop=True)   # identical to v57 T_sup
        vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True); lr = LogisticRegression(C=1.0, max_iter=3000).fit(vec.fit_transform(A155.texts(Dv)), Dv.y.values)
        C["T_sup"] = lr.decision_function(vec.transform(A155.texts(C))); C["mon_subset"] = monitor_subset(C)
        mf = REPO_ROOT / f"outputs/v60/monitor_{A}.parquet"
        if mf.exists():
            Mo = pd.read_parquet(mf)[["set", "episode_id", "event_id", "prob"]].rename(columns={"prob": "M_cot"}); C = C.merge(Mo, on=["set", "episode_id", "event_id"], how="left")
        parts.append(C)
    J = pd.concat(parts, ignore_index=True); J["template"] = J.template + "|" + J.tool; Jm = J[J.mon_subset]
    F1 = M150.boot(J, "I", "T_sup", B=4000); F2 = M150.boot(Jm, "I", "M_cot", B=4000) if "M_cot" in J else None
    ps = {"F1": F1["p_one_sided"], **({"F2": F2["p_one_sided"]} if F2 else {})}; o = sorted(ps, key=ps.get); h, run = {}, 0.0
    for i, k in enumerate(o):
        run = max(run, min(1.0, (len(o) - i) * ps[k])); h[k] = run
    keys = [k for k in ("I", "T_sup", "M_cot") if k in J]
    out = {"n": J.groupby(["model", "cls"]).size().astype(int).to_dict(), "auroc": {k: round(M150.auc(J, k), 4) for k in keys},
           "auroc_monitor_subset": {k: round(M150.auc(Jm, k), 4) for k in keys},
           "per_model": {A: {k: round(M150.auc(g, k), 4) for k in keys} for A, g in J.groupby("model")}, "F1_I_vs_Tsup": F1, "F2_I_vs_Mcot": F2, "holm": h}
    o_ = REPO_ROOT / "results/prereg_v60"; o_.mkdir(parents=True, exist_ok=True); json.dump(out, open(o_ / "summary.json", "w"), indent=2, default=str); print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
