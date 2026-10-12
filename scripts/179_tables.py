#!/usr/bin/env python
"""Main-text tables generated from result files (no number typed by hand):
  paper/tables/tab_forecast.tex : forecasting at each moment, internal vs supervised text vs CoT monitor, with the test, its p and status
  paper/tables/tab_prevent.tex  : prevention per model: decision turn, gate every action, gate then ask (rates, fixed/broken, p, work)
python scripts/179_tables.py"""
import json
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
    tc, v55, v57, v51, v37 = (J(f) for f in ("results/prereg_v57/timecourse.json", "results/prereg_v55/summary.json", "results/prereg_v57/summary.json",
                                             "results/prereg_v51/summary.json", "results/prereg_v37/summary.json"))
    fm = J("paper/figures/fig_forecast_main_stats.json")["lie"]
    Y, N, D = "\\yes", "\\no", "desc."
    rows = []
    r = tc["reveal"]
    rows.append(("\\multirow{6}{*}{\\rotatebox{90}{Violation}}", "reads the decisive fact", n_(r["I"]["n"], r["I"]["violators"]), a3(r["I"]["auroc"]), a3(r["T_sup"]["auroc"]), a3(r["M_cot"]["auroc"]) + "$^{s}$",
                 "I$-$T " + dci(v55["V3_I_vs_Tsup"]) + "; I$-$M " + dci(v55["V2_I_vs_Mcot"]), pf(v55["holm"]["V3"]), Y))
    for h, lab in (("h2", "two actions before"), ("h1", "one action before")):
        r = tc[h]
        rows.append(("", lab, n_(r["I"]["n"], r["I"]["violators"]), a3(r["I"]["auroc"]), a3(r["T_sup"]["auroc"]), "--", "I$-$T " + dci(r["I_minus_T"]), "--", D))
    au = v57["auroc"]; e1 = v57["E1"]
    r = tc["decision"]
    rows.append(("", "decision vs other actions", n_(e1["vs_XOTHER"]["n"], e1["vs_XOTHER"]["violators"]), a3(au["vs_XOTHER"]["I"]), a3(au["vs_XOTHER"]["T_sup"]), a3(au["vs_XOTHER"]["M_cot"]) + "$^{s}$",
                 "I$-$T " + dci(r["I_minus_T"]), "--", D))
    rows.append(("", "decision vs authorized twin", n_(e1["vs_XPLUS"]["n"], e1["vs_XPLUS"]["violators"]), a3(au["vs_XPLUS"]["I"]), a3(au["vs_XPLUS"]["T_sup"]), a3(au["vs_XPLUS"]["M_cot"]) + "$^{s}$",
                 "I$-$0.5 " + dci(e1["vs_XPLUS"]), pf(e1["vs_XPLUS"]["p_one_sided"]), Y))
    nn = v57["n"]; ntot = nn["XOTHER"] + nn["XPLUS"] + nn["VIOL"]
    rows.append(("", "decision, all negatives", n_(ntot, nn["VIOL"]), a3(au["all"]["I"]), a3(au["all"]["T_sup"]), a3(au["all"]["M_cot"]) + "$^{s}$",
                 f"I$-$T ${v57['E2_I_vs_Tsup']['diff']:+.3f}$; I$-$M ${v57['E3_I_vs_Mcot']['diff']:+.3f}$", f"{pf(v57['holm']['E2'])}; {pf(v57['holm']['E3'])}", N))
    f2 = v37["F2"]["F2a"]; c1, c2, c3 = v51["C1_I_vs_Mcot"], v51["C2_S_vs_Tsup"], v51["C3"]["obfuscate_I_vs_Mcot"]; ap = v51["auroc_pooled"]
    b, o = fm["base"], fm["obfuscate"]
    rows.append(("\\multirow{6}{*}{\\rotatebox{90}{Lie}}", "before the report", n_(f2["n"], f2["n_lies"]), a3(f2["within_template_auroc"]), "--", "--",
                 f"I$-$0.5 ${f2['within_template_auroc'] - 0.5:+.3f}$ [${f2['ci95'][0] - 0.5:.3f}$, ${f2['ci95'][1] - 0.5:.3f}$]", pf(f2["holm_p"]), Y))
    PV = lie_by_variant()
    rows.append(("", "all prompt variants", n_(c1["n"], c1["lies"]), a3(ap["I"]), a3(ap["T_sup"]), a3(ap["M_cot"]),
                 f"I$-$M ${c1['diff']:+.3f}$; S$-$T ${c2['diff']:+.3f}$", f"{c1['holm_p']:.2f}; {c2['holm_p']:.2f}", N))
    q = PV["base"]
    rows.append(("", "no pressure", n_(q["n"], q["lies"]), a3(q["I"]), a3(q["T_sup"]), a3(q["M_cot"]), "--", "--", D))
    q = PV["obfuscate"]
    rows.append(("", "reasoning told to hide it", n_(c3["n"], c3["lies"]), a3(q["I"]), a3(q["T_sup"]), a3(q["M_cot"]), "I$-$M " + dci(c3), pf(c3["p_one_sided"]), Y))
    rows.append(("", "no pressure, ensemble$^{e}$", n_(b["E_lda"]["n"], b["E_lda"]["lies"]), a3(b["E_lda"]["auroc"]), a3(b["T_sup"]["auroc"]), a3(b["M_cot"]["auroc"]), "--", "--", D))
    rows.append(("", "told to hide it, ensemble$^{e}$", n_(o["E_lda"]["n"], o["E_lda"]["lies"]), a3(o["E_lda"]["auroc"]), a3(o["T_sup"]["auroc"]), a3(o["M_cot"]["auroc"]), "--", "--", D))
    body = "\n".join(" & ".join(map(str, r)) + " \\\\" + ("\n\\midrule" if i == 5 else "") for i, r in enumerate(rows))
    tex = r"""\begin{table*}[t]
\centering\scriptsize
\caption{\textbf{Forecasting at each moment.} Fresh data; frozen forecasters; AUROC within model and template. I: internal readout; T: supervised text; M: CoT monitor ($^{s}$on its preregistered subset); S: internal + text. Paired differences with cluster-bootstrap 95\% CIs; $p$ one-sided, Holm-corrected. \yes/\no: preregistered, passed/failed; desc.: descriptive. $^{e}$\Qwen, \Gemma, \Oss; other rows pool four models.}
\label{tab:forecast-main}
\setlength{\tabcolsep}{3.6pt}
\begin{tabular}{@{}cl r ccc l l c@{}}
\toprule
 & Moment & $n$ (pos.) & I & T & M & Test: difference [95\% CI] & $p$ & status \\
\midrule
""" + body + r"""
\bottomrule
\end{tabular}
\vspace{-2mm}
\end{table*}
"""
    (T / "tab_forecast.tex").write_text(tex); return tex


def prevent_table():
    rows = []
    for m in MN:
        G = J(f"results/prereg_v54/gate_{m}_conf.json"); r = G["rates"]; g1 = G["G1_gate_vs_none"]
        dec = (ar(r["none"]["violate_minus"], r["gate"]["violate_minus"]), f"{g1['b_fixed']}/{g1['c_broken']}", pf(G["holm"]["G1"]), g3(G["fire_rate"]["plus"]),
               f"{g3(r['none']['progress_plus'])} / {g3(r['blanket']['progress_plus'])} / {g3(r['gate']['progress_plus'])}")
        if m == "gemma4":
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
\caption{\textbf{Prevention per model.} Fresh, paired sites (decision turn: about 200 unauthorized + 200 authorized; episodes: 100 + 200, 12 more turns); exact one-sided McNemar, Holm-corrected. Violations: unauthorized sites with a violation, without$\to$with the policy; fix/brk: sites fixed / broken; alarm: gate fires on authorized turns; progress (none / blanket / gate) and completion (none / policy): authorized work done; asks: approver calls per authorized episode. $^{a}$6 more turns. $^{b}$First 100 sites of the end-to-end run; unadjusted $p$.}
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
