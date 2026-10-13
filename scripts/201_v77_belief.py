#!/usr/bin/env python
"""v77 (prereg docs/preregistration_v77.md): does the frozen CAPE readout track the agent's information that an action is not
authorized? Counterfactual context swap on AgentDojo: every agent action is scored twice on the SAME generated tokens, once with the
real context (injection signed in the user's name) and once with the injection replaced by its third-party variant ("not from the
user; not authorized"), tool outputs taken from a shadow environment. Main env, CPU.
python scripts/201_v77_belief.py <actor> [<actor> ...]   -> results/prereg_v77/belief.json"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "outputs/v77"; RES = ROOT / "results/prereg_v77"; B = 4000


def load(A):
    E = [json.loads(x) for x in open(OUT / f"conf_{A}_swap_attack.jsonl")]
    S = {}
    for x in open(OUT / f"server_{A}.jsonl"):
        r = json.loads(x); S[r.get("rid")] = r
    U = []                                                    # (cluster, tool, injected, exposed, score, score_swap)
    for e in E:
        if e["error"] is not None:
            continue
        exposed = False
        for c in e["calls"]:
            r = S.get(c["rid"], {})
            if r.get("score") is None or r.get("score_swap") is None or not c["tool"]:
                continue
            d = r["score_swap"] - r["score"]; exposed = exposed or abs(d) > 1e-6
            U.append((f"{e['suite']}|{e['user_task']}", c["tool"], bool(c.get("injected")), abs(d) > 1e-6, r["score"], r["score_swap"]))
    return U


def boot(U, f, seed=77):
    rng = np.random.default_rng(seed); by = defaultdict(list); [by[u[0]].append(u) for u in U]; cl = sorted(by)
    v = []
    for _ in range(B):
        smp = [u for c in rng.choice(cl, len(cl)) for u in by[c]]; x = f(smp)
        if x == x:
            v.append(x)
    v = np.array(v); return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5)), float((np.sum(v <= 0) + 1) / (len(v) + 1))


def mean_diff(U):
    return float(np.mean([u[5] - u[4] for u in U])) if U else float("nan")


def did(U):
    inj = [u for u in U if u[2]]; oth = [u for u in U if not u[2] and u[3]]
    return mean_diff(inj) - mean_diff(oth) if inj and oth else float("nan")


def main(models):
    res, ps1, ps2 = {}, {}, {}
    for A in models:
        U = load(A); tau = json.load(open(ROOT / f"outputs/v77/tau_{A}.json"))["tau"]
        pre = [u for u in U if not u[3] and not u[2]]          # contexts identical (injection not yet seen): pipeline check
        inj = [u for u in U if u[2]]; oth = [u for u in U if not u[2] and u[3]]
        lo1, hi1, p1 = boot(inj, lambda X: mean_diff([u for u in X if u[2]]))
        lo2, hi2, p2 = boot(U, did)
        f_real = [u[4] > tau for u in inj]; f_swap = [u[5] > tau for u in inj]
        b = sum(s and not r for r, s in zip(f_real, f_swap)); c = sum(r and not s for r, s in zip(f_real, f_swap))
        res[A] = {"tau": tau, "injected_calls": len(inj), "exposed_other_calls": len(oth), "unexposed_calls": len(pre),
                  "pipeline_check_max_abs_diff_unexposed": float(max([abs(u[5] - u[4]) for u in pre], default=0.0)),
                  "P1_mean_diff_injected": mean_diff(inj), "P1_ci95": [lo1, hi1], "P1_p": p1,
                  "mean_diff_exposed_other": mean_diff(oth),
                  "P2_did": did(U), "P2_ci95": [lo2, hi2], "P2_p": p2,
                  "S1_fire_real": float(np.mean(f_real)) if inj else None, "S1_fire_swap": float(np.mean(f_swap)) if inj else None,
                  "S1_newly_fired": b, "S1_unfired": c, "S1_p": float(binomtest(b, b + c, 0.5, alternative="greater").pvalue) if b + c else 1.0}
        ps1[A], ps2[A] = p1, p2
    def holm(ps):
        k = sorted(ps, key=ps.get); out, m, run = {}, len(ps), 0.0
        for i, a in enumerate(k):
            run = max(run, min(1.0, (m - i) * ps[a])); out[a] = run
        return out
    H = holm({**{f"P1|{a}": p for a, p in ps1.items()}, **{f"P2|{a}": p for a, p in ps2.items()}})
    for A in res:
        res[A]["P1_holm"] = H[f"P1|{A}"]; res[A]["P2_holm"] = H[f"P2|{A}"]
        res[A]["P1_pass"] = bool(res[A]["P1_holm"] < 0.05 and res[A]["P1_mean_diff_injected"] > 0)
        res[A]["P2_pass"] = bool(res[A]["P2_holm"] < 0.05 and res[A]["P2_did"] > 0)
    RES.mkdir(parents=True, exist_ok=True); json.dump(res, open(RES / "belief.json", "w"), indent=1); print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
