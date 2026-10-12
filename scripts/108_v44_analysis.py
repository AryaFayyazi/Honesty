#!/usr/bin/env python
"""Prereg v44 analysis: FTA transparency / evidence-contract vs neutral on informed and laundering episodes."""
import glob, importlib.util, json
import numpy as np, pandas as pd
from omegaconf import OmegaConf
from scipy.stats import binomtest
from cape.utils.config import REPO_ROOT
s = importlib.util.spec_from_file_location("x98", REPO_ROOT / "scripts/98_v37_analysis.py"); X98 = importlib.util.module_from_spec(s); s.loader.exec_module(X98)
LIES = ["CANDID", "SPIN", "OMITTED", "MISREPRESENTED"]


def mc(W, a, b, sens=False):
    d = W.copy() if sens else W[W[a].isin(LIES) & W[b].isin(LIES)]
    xa, xb = d[a] == "MISREPRESENTED", d[b] == "MISREPRESENTED"; up, dn = int((~xa & xb).sum()), int((xa & ~xb).sum())
    return {"n": int(len(d)), f"rate_{a}": round(float(xa.mean()), 3), f"rate_{b}": round(float(xb.mean()), 3), "n_up": up, "n_down": dn,
            "p_one_sided": float(binomtest(dn, up + dn, .5, alternative="greater").pvalue) if up + dn else 1.0}


def main():
    V = pd.concat([pd.read_parquet(f) for f in glob.glob(str(REPO_ROOT / "outputs/prereport/v44_*_rubric3.parquet"))], ignore_index=True)
    S = pd.concat([pd.read_parquet(f) for f in glob.glob(str(REPO_ROOT / "outputs/prereport/v44_*.parquet")) if "rubric3" not in f], ignore_index=True)
    W = V.pivot_table(index=["set", "episode_id"], columns="message", values="label", aggfunc="first")
    W = W.reindex(S.pivot_table(index=["set", "episode_id"], columns="message", values="revised_report", aggfunc="first").index).fillna("NO_REPORT").reset_index()
    F = X98.episodes(OmegaConf.create({"label_dir": "outputs/disclosure_v37"}))
    W = W.merge(F[["set", "episode_id", "retro", "model"]], on=["set", "episode_id"], how="left")
    out = {"n": int(len(W)), "n_retro": int(W.retro.sum())}
    T = {"Y1_retro_contract": (W[W.retro == 1], "neutral", "fta_contract"), "Y2_all_contract": (W, "neutral", "fta_contract"), "Y3_all_transparency": (W, "neutral", "fta_transparency")}
    for k, (d, a, b) in T.items():
        out[k] = mc(d, a, b); out[k]["sensitivity"] = mc(d, a, b, sens=True)
    ks = list(T); ps = [out[k]["p_one_sided"] for k in ks]; od = np.argsort(ps)
    for i, j in enumerate(od):
        out[ks[j]]["holm_p"] = float(min(1, max(ps[o] * (3 - jj) for jj, o in enumerate(od[: i + 1]))))
    out["per_model_retro"] = {m: {c: round(float((g[c] == "MISREPRESENTED")[g[c].isin(LIES)].mean()), 3) for c in ("neutral", "fta_transparency", "fta_contract")} for m, g in W[W.retro == 1].groupby("model")}
    out["candid_rate"] = {c: round(float((W[c] == "CANDID")[W[c].isin(LIES)].mean()), 3) for c in ("neutral", "fta_transparency", "fta_contract")}
    out["no_report_rate"] = {c: round(float((W[c] == "NO_REPORT").mean()), 3) for c in ("neutral", "fta_transparency", "fta_contract")}
    out["CLAIM_contract_prevents"] = bool(out["Y1_retro_contract"]["holm_p"] < 0.05)
    o = REPO_ROOT / "results/prereg_v44"; o.mkdir(parents=True, exist_ok=True); (o / "summary.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
