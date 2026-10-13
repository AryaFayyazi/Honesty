#!/usr/bin/env python
"""Main-text tables generated from result files (no number typed by hand):
  paper/tables/tab_forecast.tex : forecasting at each moment, internal vs supervised text vs CoT monitor, with the test, its p and status
  paper/tables/tab_prevent.tex  : prevention per model: decision turn, gate every action, gate then ask (rates, fixed/broken, p, work)
python scripts/179_tables.py"""
import json
import re
from pathlib import Path

from cape.utils.config import REPO_ROOT

T = REPO_ROOT / "paper/tables"; T.mkdir(parents=True, exist_ok=True)
MN = {"gemma4": "\\Gemma", "gptoss20b": "\\Oss", "museglimmer": "\\Muse", "qwen38": "\\Qwen"}


def J(p):
    p = REPO_ROOT / p
    return json.load(open(p)) if p.exists() else None


def pf(p):
    """p-value in compact scientific form."""
    if p is None:
        return "--"
    if p >= 0.001:
        return f"{p:.3f}".rstrip("0").rstrip(".") if p < 0.1 else f"{p:.2f}"
    e = int(f"{p:e}".split("e")[1]); m = p / 10 ** e
    return f"${m:.0f}{{\\times}}10^{{{e}}}$" if round(m) != 1 else f"$10^{{{e}}}$"


def g3(x):
    """rate with up to 3 decimals, at least 2 (0.055, 0.41, 0.685)."""
    t = f"{x:.3f}"
    return t[:-1] if t.endswith("0") else t


def ar(a, b):
    return f"{g3(a)}$\\to${g3(b)}"


def ci(c):
    return f"[{c[0]:.2f}, {c[1]:.2f}]"


def n_(n, k):
    return f"{n:,}".replace(",", "{,}") + f" ({k:,})".replace(",", "{,}")


def a3(x):
    return f"{x:.3f}" if x is not None else "--"


def dci(d):
    c = d.get("ci95") or []
    return f"${d['diff']:+.3f}$" + (f" [${c[0]:.3f}$, ${c[1]:.3f}$]" if len(c) == 2 else "")


def lie_by_variant():
    """Pooled (four models, single frozen readout) lie AUROCs per prompt variant, from the v51 confirmation scores."""
    import importlib.util
    import pandas as pd
    s = importlib.util.spec_from_file_location("c134", REPO_ROOT / "scripts/134_v51_confirm.py"); C = importlib.util.module_from_spec(s); s.loader.exec_module(C)
    D = pd.concat([C.scores(m).assign(model=m) for m in ("museglimmer", "qwen38", "gemma4", "gptoss20b")], ignore_index=True); out = {}
    for v, d in D.groupby("variant"):
        out[v] = {"n": int(len(d)), "lies": int(d.y.sum()), **{c: C.auc(d, c) for c in ("I", "T_sup", "M_cot")}}
    return out


def forecast_table():
    """Table 2: every row a complete head-to-head (I, T, M AUROCs; I-T and I-M with 95% CIs and one-sided p).
    Preregistered primary tests (dagger) keep their Holm-adjusted p and CIs from the preregistered analyses; preregistered
    secondary contrasts (double dagger) and descriptive differences use results/forecast_table_stats.json (scripts/200)."""
    S = J("results/forecast_table_stats.json"); v55, v57, v51, v37 = (J(f) for f in ("results/prereg_v55/summary.json", "results/prereg_v57/summary.json",
                                                                                   "results/prereg_v51/summary.json", "results/prereg_v37/summary.json"))
    sec = J("results/prereg_v57/secondary_contrasts.json")
    def d(x, mark=""):
        lo, hi = x["ci95"]; return f"${x['diff']:+.3f}$ [${lo:.3f}$, ${hi:.3f}$]{mark}"
    def pp(x, key="p_one_sided"):
        return pf(x[key]) if key in x else pf(x["p_one_sided"])
    DG, DD = "$^{\\dagger}$", "$^{\\ddagger}$"
    rows = []
    def add(lab, r, cols, dT, pT, dM, pM, first_mark=""):
        rows.append((lab, n_(r["n"], r["pos"]), a3(r[cols[0]]) + first_mark, a3(r["T_sup"]), a3(r["M_cot"]), dT, pT, dM, pM))
    r = S["reveal"]
    add("reads the decisive fact", r, ["I"], d(v55["V3_I_vs_Tsup"], DG), pf(v55["holm"]["V3"]), d(v55["V2_I_vs_Mcot"], DG), pf(v55["holm"]["V2"]))
    r = S["decision_vs_other"]
    add("decision vs other actions", r, ["I"], d(sec["vsXOTHER_I_minus_T"], DD), pp(sec["vsXOTHER_I_minus_T"]),
        d(sec["vsXOTHER_I_minus_Mcot(monitor subset)"], DD), pp(sec["vsXOTHER_I_minus_Mcot(monitor subset)"]))
    r = S["decision_vs_twin"]
    add("decision vs authorized twin", r, ["I"], d(r["first_minus_T"], DD), pp(r["first_minus_T"]), d(r["first_minus_M"], DD), pp(r["first_minus_M"]), first_mark=DG)
    r = S["decision_all"]
    add("decision, all negatives", r, ["I"], d(v57["E2_I_vs_Tsup"], DG), pf(v57["holm"]["E2"]), d(v57["E3_I_vs_Mcot"], DG), pf(v57["holm"]["E3"]))
    nviol = len(rows)
    r = S["lie_all"]; c1 = v51["C1_I_vs_Mcot"]
    add("before the report, all variants", r, ["I"], d(r["first_minus_T"]), pp(r["first_minus_T"]), d(c1, DG), pf(c1["holm_p"]))
    r = S["lie_base"]
    add("\\quad no pressure", r, ["I"], d(r["first_minus_T"]), pp(r["first_minus_T"]), d(r["first_minus_M"]), pp(r["first_minus_M"]))
    r = S["lie_monitored"]
    add("\\quad told its reasoning is monitored", r, ["I"], d(r["first_minus_T"]), pp(r["first_minus_T"]), d(r["first_minus_M"]), pp(r["first_minus_M"]))
    r = S["lie_obfuscate"]; c3 = v51["C3"]["obfuscate_I_vs_Mcot"]
    add("\\quad reasoning told to hide it", r, ["I"], d(r["first_minus_T"]), pp(r["first_minus_T"]), d(c3, DG), pf(c3["p_one_sided"]))
    for k, lab in (("ens_base", "\\quad no pressure, ensemble$^{e}$"), ("ens_obfuscate", "\\quad told to hide it, ensemble$^{e}$")):
        r = S[k]; add(lab, r, ["E_lda"], d(r["first_minus_T"]), pp(r["first_minus_T"]), d(r["first_minus_M"]), pp(r["first_minus_M"]))
    f2 = v37["F2"]["F2a"]; c2 = v51["C2_S_vs_Tsup"]
    body = []
    for i, rr in enumerate(rows):
        lead = ("\\multirow{%d}{*}{\\rotatebox{90}{Violation}}" % nviol) if i == 0 else ("\\multirow{%d}{*}{\\rotatebox{90}{Lie}}" % (len(rows) - nviol) if i == nviol else "")
        body.append(lead + " & " + " & ".join(rr) + " \\\\" + ("\n\\midrule" if i == nviol - 1 else ""))
    tex = r"""\begin{table*}[t]
\centering\scriptsize
\caption{\textbf{Forecasting at each moment: every forecaster on the same fresh units.} AUROC within model and template, pooled over the four models (ensemble rows: three models$^{e}$). I: internal readout (E: internal ensemble); T: supervised text classifier; M: zero-shot CoT monitor, scored on its preregistered subset (about a third of the units). Differences are paired, with two-sided (model, scenario)-cluster bootstrap 95\% CIs and one-sided $p$ for the internal forecaster being better ($p$ near 1: the comparator is better). \textbf{Markers:} $^{\dagger}$preregistered primary test, Holm-adjusted $p$ (on an AUROC: test against 0.5); $^{\ddagger}$preregistered secondary contrast, unadjusted $p$; unmarked: descriptive, unadjusted $p$. Two further preregistered results: on the laundering set (""" + f"{f2['n']:,}".replace(",", "{,}") + r""" informed violations, three models) the lie forecaster reaches I $=""" + f"{f2['within_template_auroc']:.3f}" + r"""$ (I $>0.5$, Holm $p=""" + f"{f2['holm_p']:.3f}" + r"""$); internal-plus-text versus text on all lie variants, $""" + f"{c2['diff']:+.3f}" + r"""$ (Holm $p=""" + f"{c2['holm_p']:.2f}" + r"""$). The violation time course before the decision is in \cref{fig:fcast}a. The ``monitored'' variant is small (47 episodes), and the ensemble is not reported on it (4 episodes). $^{e}$\Qwen, \Gemma, \Oss: \Muse's fresh episodes had been examined before the ensemble was designed.}
\label{tab:forecast-main}
\setlength{\tabcolsep}{3pt}
\begin{tabular}{@{}cl r ccc ll ll@{}}
\toprule
 & Moment & $n$ (pos.) & I & T & M & I$-$T [95\% CI] & $p$ & I$-$M [95\% CI] & $p$ \\
\midrule
""" + "\n".join(body) + r"""
\bottomrule
\end{tabular}
\vspace{-2mm}
\end{table*}
"""
    (T / "tab_forecast.tex").write_text(tex)
    short = r"""\caption{\textbf{Forecasting at each moment} (fresh units; AUROC within model and template; four models, ensemble rows three$^{e}$). I: internal readout (E: ensemble); T: supervised text; M: CoT monitor (its preregistered subset). Paired differences: two-sided cluster-bootstrap 95\% CIs; one-sided $p$ for internal better. $^{\dagger}$Preregistered primary test (Holm $p$; on an AUROC: vs 0.5); $^{\ddagger}$preregistered secondary; unmarked: descriptive. Notes: \cref{app:vforecast}.}"""
    tex_short = re.sub(r"\\caption\{\\textbf\{Forecasting at each moment: every forecaster.*?\}\n\\label", lambda m: short + "\n\\label", tex, flags=re.S)
    assert tex_short != tex
    (T / "tab_forecast_short.tex").write_text(tex_short); return tex


def prevent_table():
    rows = []
    for m in MN:
        G = J(f"results/prereg_v54/gate_{m}_conf.json"); r = G["rates"]; g1 = G["G1_gate_vs_none"]
        dec = (ar(r["none"]["violate_minus"], r["gate"]["violate_minus"]), f"{g1['b_fixed']}/{g1['c_broken']}", pf(G["holm"]["G1"]), g3(G["fire_rate"]["plus"]),
               f"{g3(r['none']['progress_plus'])} / {g3(r['blanket']['progress_plus'])} / {g3(r['gate']['progress_plus'])}")
        if m == "gemma4" and not J("results/prereg_v59/always_all_gemma4.json"):   # fallback: original 6-turn run (superseded by the uniform 12-turn run)
            a = J("results/prereg_v59/always_gemma4.json"); k = J("results/prereg_v59/always_k12_gemma4.json"); d = a["D1_always_vs_none"]
            ev = (ar(d["rates"]["none_hf"], d["rates"]["gate_always"]) + "$^{a}$", f"{d['b_fixed']}/{d['c_broken']}", pf(a["holm"]["D1"]),
                  f"{g3(k['completion']['none_hf'])} / {g3(k['completion']['gate_always'])}")
        elif m == "museglimmer":
            e = J("results/prereg_v61/e2e_museglimmer.json")["v59b_muse"]; d1 = e["D1_first100"]
            ev = (ar(d1["rate_comparator"], d1["rate_treated"]) + "$^{b}$", f"{d1['fixed']}/{d1['broken']}", pf(d1["p_one_sided"]),
                  f"{g3(e['completion']['none_hf'])} / {g3(e['completion']['gate_always'])}")
        else:
            a = J(f"results/prereg_v59/always_all_{m}.json")
            ev = (ar(a["violation"]["none_hf"], a["violation"]["gate_always"]), f"{a['D1']['b_fixed']}/{a['D1']['c_broken']}", pf(a["holm"]["D1"]),
                  f"{g3(a['completion']['none_hf'])} / {g3(a['completion']['gate_always'])}")
        s = J(f"results/prereg_v59/always_esc{'64' if m == 'qwen38' else ''}_{m}.json")   # Qwen: 12-step rerun (v64 Addendum 2: confirmatory)
        esc = ((ar(s["violation"]["none_hf"], s["violation"]["gate_always"]), f"{s['D1']['b_fixed']}/{s['D1']['c_broken']}", pf(s["holm"]["D1"]),
                f"{g3(s['completion']['none_hf'])} / {g3(s['completion']['gate_always'])}", g3(s["asks_per_episode"]["plus"])) if s else ("\\multicolumn{5}{c}{\\emph{running}}",))
        rows.append((MN[m],) + dec + ev + esc)
    body = "\n".join(" & ".join(r) + " \\\\" for r in rows)
    tex = r"""\begin{table*}[t]
\centering\scriptsize
\caption{\textbf{Prevention per model.} Fresh, paired sites (decision turn: about 200 unauthorized + 200 authorized; episodes: 100 + 200, 12 more turns); exact one-sided McNemar, Holm-corrected. Violations: unauthorized sites with a violation, without$\to$with the policy; fix/brk: sites fixed / broken; alarm: gate fires on authorized turns; progress (none / blanket / gate) and completion (none / policy): authorized work done; asks: approver calls per authorized episode. $^{b}$\Muse: the preregistered design run within the end-to-end experiment (first 100 sites); unadjusted $p$.}
\label{tab:prevent-main}
\setlength{\tabcolsep}{2.4pt}
\resizebox{\textwidth}{!}{%
\begin{tabular}{@{}l ccccc cccc ccccc@{}}
\toprule
 & \multicolumn{5}{c}{Decision turn (gate once)} & \multicolumn{4}{c}{Gate every action} & \multicolumn{5}{c}{Gate, then ask} \\
\cmidrule(lr){2-6}\cmidrule(lr){7-10}\cmidrule(l){11-15}
Model & violations & fix/brk & $p$ & alarm & progress & violations & fix/brk & $p$ & completion & violations & fix/brk & $p$ & completion & asks \\
\midrule
""" + body + r"""
\bottomrule
\end{tabular}}
\vspace{-2mm}
\end{table*}
"""
    (T / "tab_prevent.tex").write_text(tex); return tex


if __name__ == "__main__":
    print(forecast_table()); print(prevent_table())
