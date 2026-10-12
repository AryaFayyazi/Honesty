#!/usr/bin/env python
"""Paper table for AgentDojo (v74 undefended, v75 spotlighting): development diagnostics per model and, where the go rule passed,
the preregistered confirmation. -> paper/tables/tab_agentdojo.tex"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = {"gptoss20b": r"\Oss", "gemma4": r"\Gemma", "qwen38": r"\Qwen", "museglimmer": r"\Muse"}
COND = [("v74", "", "none", "gate", "frozen, undefended"), ("v75", "_spot", "spot", "spotgate", "frozen, spotlighting"), ("v76", "", "none", "gate", "refit, undefended")]


def load(p):
    p = ROOT / p
    return json.load(open(p)) if p.exists() else None


def f2(x):
    return "--" if x is None or x != x else f"{x:.2f}"


def pval(p):
    return "--" if p is None else (f"{p:.3f}" if p >= 0.001 else f"$<$0.001")


def main():
    lines = []
    for v, tag, a0, a1, label in COND:
        S = load(f"results/prereg_{v}/summary{tag}.json") or {}
        for A in NAMES:                                   # single-model interim summaries (v76 Addendum 2) where the full one is absent
            if A not in S and load(f"results/prereg_{v}/summary_interim_{A}.json"):
                S[A] = load(f"results/prereg_{v}/summary_interim_{A}.json")[A]
        for A, nm in NAMES.items():
            c = load(f"results/prereg_{v}/calibration_{A}{tag}.json")
            if c is None:
                continue
            s = S.get(A)
            conf = (f"{f2(s['asr_none'])} $\\to$ {f2(s['asr_gate'])} ({s['fixed']}/{s['broken']}) & {pval(s['holm_A1'])} & "
                    f"{s['A2_diff']:+.2f} [{s['A2_lower']:+.2f}]") if s else (r"\multicolumn{3}{c}{go rule not met}" if not c.get("go") else r"\multicolumn{3}{c}{pending}")
            lines.append(f"{label} & {nm} & {f2(c['asr_none'])} & {f2(c['fire_on_injected'])} ({c['injected_calls']}) & {f2(c['auroc_injected_vs_benign'])} & {conf} \\\\")
            label = ""
        if lines and lines[-1] != r"\midrule":
            lines.append(r"\midrule")
    if lines and lines[-1] == r"\midrule":
        lines.pop()
    tex = r"""\begin{table}[t]
\centering\scriptsize
\caption{\textbf{AgentDojo prompt injections.} Readout: frozen (trained on CAPE-Bench only) or refit on the 29 development tasks (out-of-fold scores); steering always frozen. Development: attack success (ASR), share of injected calls on which the gate fires at 10\% benign false alarms, AUROC of injected vs benign calls. Confirmation (68 unseen tasks): ASR without $\to$ with the gate (fixed/broken pairs), Holm $p$, benign utility change [one-sided 95\% lower bound].}
\label{tab:agentdojo}
\setlength{\tabcolsep}{3pt}
\begin{tabular}{@{}llcccccc@{}}
\toprule
 & & \multicolumn{3}{c}{Development} & \multicolumn{3}{c}{Confirmation} \\
\cmidrule(lr){3-5}\cmidrule(lr){6-8}
Readout, defense & Agent & ASR & fires (n) & AUROC & ASR (fixed/broken) & Holm $p$ & utility \\
\midrule
""" + "\n".join(lines) + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    (ROOT / "paper/tables/tab_agentdojo.tex").write_text(tex); print(tex)


if __name__ == "__main__":
    main()
