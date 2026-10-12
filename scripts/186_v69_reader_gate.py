#!/usr/bin/env python
"""v69 (prereg docs/preregistration_v69.md): reader gate on frontier agents' τ²-bench airline trajectories.
  stage=build   (τ² env, CPU): for every v38-labelled write, the frontier agent's context up to the write (τ² LLMAgent system
                prompt with the published policy, airline tool schemas, messages before the write, and the write turn's own text
                without the tool call) -> outputs/v69/prefixes.jsonl
  stage=score   (main env, GPU): Qwen3.8 reads each prefix (chat template, thinking off); residual stream at the last token at the
                5 CAPE layers (vLLM hooks, scripts/174 Steer.features); frozen CAPE gate score -> outputs/v69/scores.parquet (+ feats.npz)
  stage=analyze (CPU): R1, R2 (task-cluster bootstrap), descriptive refit CV -> results/prereg_v69/summary.json"""
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path("/home/arya/new_safety/cape"); OUT = REPO / "outputs/v69"; RES = REPO / "results/prereg_v69"
FINAL = "/data/models/cape_ws/datasets/tau2-bench/data/tau2/results/final"
AGENTS = ["claude-3-7-sonnet-20250219", "gpt-4.1-2025-04-14", "gpt-4.1-mini-2025-04-14", "o4-mini-2025-04-16"]


def stage_build():
    import pandas as pd
    from tau2.agent.llm_agent import AGENT_INSTRUCTION, SYSTEM_PROMPT
    from tau2.domains.airline.environment import get_environment
    env = get_environment(); tools = [t.openai_schema for t in env.get_tools()]
    L = pd.read_json(OUT / "labels.json"); L = L[L.label.isin(["NOT_ALLOWED", "ALLOWED", "CONDITIONAL"])]   # exported from results/v38/tau2_disclosure.parquet (τ² env has no pyarrow)
    OUT.mkdir(parents=True, exist_ok=True); n = 0
    with open(OUT / "prefixes.jsonl", "w") as fo:
        for ag in AGENTS:
            import glob; d = json.load(open(sorted(glob.glob(f"{FINAL}/{ag}_airline_*_4trials.json"))[0]))   # gpt-4.1-mini file is named _airline_base_ (as v38 used)
            sysmsg = SYSTEM_PROMPT.format(domain_policy=d["info"]["environment_info"]["policy"], agent_instruction=AGENT_INSTRUCTION)
            sims = {s["id"]: s for s in d["simulations"]}
            for r in L[L.model == ag].itertuples():
                s = sims.get(r.sim_id)
                if s is None:
                    continue
                msgs = [{"role": "system", "content": sysmsg}]
                for m in s["messages"][:int(r.msg_idx)]:
                    role = m.get("role")
                    if role == "assistant":
                        tc = [{"id": c.get("id"), "type": "function", "function": {"name": c["name"], "arguments": c.get("arguments") or {}}} for c in (m.get("tool_calls") or [])]
                        msgs.append({"role": "assistant", "content": m.get("content") or "", **({"tool_calls": tc} if tc else {})})
                    elif role == "tool":
                        msgs.append({"role": "tool", "tool_call_id": m.get("id"), "content": str(m.get("content") or "")})
                    elif role == "user":
                        msgs.append({"role": "user", "content": m.get("content") or ""})
                w = s["messages"][int(r.msg_idx)]
                fo.write(json.dumps({"key": f"{ag}|{r.sim_id}|{r.tool_call_id}", "agent": ag, "task_id": str(r.task_id), "trial": int(r.trial) if r.trial == r.trial and r.trial is not None else -1,
                                     "tool": r.tool, "label": r.label, "knowing": bool(r.false_justification_before) if r.false_justification_before == r.false_justification_before else False,
                                     "final_text": w.get("content") or "", "messages": msgs, "tools": tools}) + "\n"); n += 1
    print("prefixes", n)


def stage_score():
    import pandas as pd
    from omegaconf import OmegaConf
    sys.path.insert(0, str(REPO / "src"))
    s = importlib.util.spec_from_file_location("v174", REPO / "scripts/174_vllm_steer.py"); V = importlib.util.module_from_spec(s); s.loader.exec_module(V)
    cfg = OmegaConf.create({"max_model_len": 32768, "gpu_mem": 0.88}); S = V.Steer("qwen38", cfg)
    Gz = np.load(REPO / "outputs/v54/gate_qwen38.npz"); G = {k: Gz[k] for k in Gz.files}
    rows, feats = [], {}
    for l in open(OUT / "prefixes.jsonl"):
        x = json.loads(l); msgs = list(x["messages"])
        if x["final_text"].strip():
            msgs.append({"role": "assistant", "content": x["final_text"]})
            txt = S.tok.apply_chat_template(msgs, tools=x["tools"], tokenize=False, continue_final_message=True, enable_thinking=False)
        else:
            txt = S.tok.apply_chat_template(msgs, tools=x["tools"], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        ids = S.tok(txt, add_special_tokens=False)["input_ids"]
        if len(ids) > 30000:
            ids = ids[:2000] + ids[-28000:]
        f = S.features(ids); feats[x["key"]] = f.astype(np.float16)
        sc = float(S.G154.gate_score(G, f[None].astype(np.float32))[0])
        rows.append({k: x[k] for k in ("key", "agent", "task_id", "trial", "tool", "label", "knowing")} | {"n_tokens": len(ids), "score": sc})
        if len(rows) % 100 == 0:
            print(len(rows), flush=True)
    pd.DataFrame(rows).to_parquet(OUT / "scores.parquet"); np.savez_compressed(OUT / "feats.npz", **feats); print("scored", len(rows), flush=True)
    os._exit(0)


def auc(y, s):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s)) if len(set(y)) == 2 else float("nan")


def auc_within(d, pos_mask):
    """AUROC positives (pos_mask) vs ALLOWED within write tool (>=3 per class, weighted by n); pooled if none qualifies."""
    dd = d[pos_mask | (d.label == "ALLOWED")]; y = pos_mask[dd.index].astype(int); vals, w = [], []
    for _, g in dd.groupby("tool"):
        yy = y[g.index]
        if yy.sum() >= 3 and (1 - yy).sum() >= 3:
            vals.append(auc(yy.values, g.score.values)); w.append(len(g))
    return (float(np.average(vals, weights=w)), "within_tool") if vals else (auc(y.values, dd.score.values), "pooled")


def stage_analyze():
    import pandas as pd
    D = pd.read_parquet(OUT / "scores.parquet"); D = D[D.label.isin(["NOT_ALLOWED", "ALLOWED"])].reset_index(drop=True)
    viol = D.label == "NOT_ALLOWED"; know = viol & D.knowing; other = viol & ~D.knowing
    a1, b1 = auc_within(D, viol); ak, _ = auc_within(D, know); ao, _ = auc_within(D, other)
    D["cl"] = D.agent + "|" + D.task_id; cl = D.cl.unique(); g = {c: d.index.values for c, d in D.groupby("cl")}; rng = np.random.default_rng(69); r1, r2 = [], []
    for _ in range(10000):
        idx = np.concatenate([g[c] for c in rng.choice(cl, len(cl))]); d = D.loc[idx].reset_index(drop=True)
        v = d.label == "NOT_ALLOWED"; x1, _ = auc_within(d, v); xk, _ = auc_within(d, v & d.knowing); xo, _ = auc_within(d, v & ~d.knowing)
        r1.append(x1); r2.append(xk - xo)
    r1, r2 = np.array(r1), np.array(r2); r1 = r1[~np.isnan(r1)]; r2 = r2[~np.isnan(r2)]
    p1 = float((np.sum(r1 <= 0.5) + 1) / (len(r1) + 1)); p2 = float((np.sum(r2 <= 0) + 1) / (len(r2) + 1))
    holm = {"R1": min(1.0, 2 * min(p1, p2)) if p1 <= p2 else min(1.0, max(2 * p2, p1)), "R2": min(1.0, 2 * min(p1, p2)) if p2 < p1 else min(1.0, max(2 * p1, p2))}
    out = {"n": int(len(D)), "violating": int(viol.sum()), "knowing": int(know.sum()), "allowed": int((~viol).sum()),
           "R1_auroc": a1, "R1_basis": b1, "R1_ci95": [float(np.percentile(r1, 2.5)), float(np.percentile(r1, 97.5))], "R1_p": p1,
           "R2_knowing_auroc": ak, "R2_other_auroc": ao, "R2_diff": ak - ao, "R2_ci95": [float(np.percentile(r2, 2.5)), float(np.percentile(r2, 97.5))], "R2_p": p2,
           "holm": holm, "per_agent": {}}
    for ag, d in D.groupby("agent"):
        d = d.reset_index(drop=True); out["per_agent"][ag] = {"n": int(len(d)), "auroc": auc_within(d, d.label == "NOT_ALLOWED")[0]}
    # descriptive: refit of the readout recipe with task-grouped 5-fold CV (is the information there?)
    try:
        from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
        F = np.load(OUT / "feats.npz"); X = np.stack([F[k].astype(np.float32) for k in D.key]); y = viol.astype(int).values
        tasks = D.task_id.unique(); fold = {t: int(hashlib.md5(t.encode()).hexdigest(), 16) % 5 for t in tasks}; fo = D.task_id.map(fold).values; oof = np.zeros(len(D))
        for k in range(5):
            tr, te = fo != k, fo == k; zz = []
            for li in range(X.shape[1]):
                lda = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(X[tr, li], y[tr]); s_tr = lda.decision_function(X[tr, li])
                zz.append((lda.decision_function(X[te, li]) - s_tr.mean()) / (s_tr.std() + 1e-8))
            oof[te] = np.mean(zz, 0)
        D2 = D.assign(score=oof); out["refit_cv_auroc"] = auc_within(D2, D2.label == "NOT_ALLOWED")[0]
        out["refit_cv_knowing_vs_allowed"] = auc_within(D2, (D2.label == "NOT_ALLOWED") & D2.knowing)[0]
    except Exception as e:
        out["refit_error"] = str(e)
    RES.mkdir(parents=True, exist_ok=True); json.dump(out, open(RES / "summary.json", "w"), indent=2); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    {"build": stage_build, "score": stage_score, "analyze": stage_analyze}[sys.argv[1]]()
