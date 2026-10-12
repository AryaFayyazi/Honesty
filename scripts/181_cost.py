#!/usr/bin/env python
"""Cost of the internal gate vs the zero-shot CoT monitor, per agent action (CPU; reads results/cost/bench_*.json if present).
  - Exact readout cost from the frozen gates (outputs/v54/gate_<m>.npz): 2 folds x 5 depths of z-scored dot products.
  - Exact active parameters per token from the safetensors headers (text decoder only: vision/audio towers and MTP heads excluded;
    routed-expert weights scaled by experts-per-token / experts; MXFP4-packed blocks = 2 parameters per byte).
  - Forward FLOPs per token = 2 x active matmul parameters (incl. the output head) + attention-score FLOPs
    4 x heads x head_dim x context for full-attention layers, with context capped at the window for sliding layers, and
    4 x value-heads x key_dim x value_dim for linear-attention layers.
  - Tokens on ALL 3,424 decision-time units of the v57 monitor subset: the exact monitor prompt (scripts/156, Qwen tokenizer,
    thinking template, 20,000-token cap) and the agent's own turn (its tokenizer): generated tokens, context, and new tokens since
    its previous turn (the previous tool result), which is what a prefix-cached agent prefills.
-> results/cost/cost.json, paper/tables/tab_cost.tex"""
import glob
import importlib.util
import json
import os
import struct
import time

import numpy as np
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"models": ["gemma4", "gptoss20b", "museglimmer", "qwen38"], "judge": "qwen38", "max_chars": 40000})
OUT = REPO_ROOT / "results/cost"; TAB = REPO_ROOT / "paper/tables"
HF = {"gemma4": "models--google--gemma-4-26B-A4B-it", "gptoss20b": "models--openai--gpt-oss-20b", "museglimmer": "models--meta-models--Muse-Glimmer-30B",
      "qwen38": "models--Qwen--Qwen3.8-27B"}
NAME = {"gemma4": "\\Gemma", "gptoss20b": "\\Oss", "museglimmer": "\\Muse", "qwen38": "\\Qwen"}
SKIP = ("vision", "visual", "audio", "embed_vision", "multi_modal", "mm_projector", "mtp.")


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def snap(m):
    return glob.glob(f"/data/models/{HF[m]}/snapshots/*/")[0]


def arch(m):
    """active parameters per token, attention geometry, from config + safetensors headers."""
    p = snap(m); c = json.load(open(p + "config.json")); t = c.get("text_config", c)
    E = t.get("num_experts") or t.get("num_local_experts") or 0; k = t.get("top_k_experts") or t.get("num_experts_per_tok") or t.get("experts_per_token") or 0
    tot = dense = expert = emb = head = 0
    for f in glob.glob(p + "*.safetensors"):
        with open(f, "rb") as fh:
            h = json.loads(fh.read(struct.unpack("<Q", fh.read(8))[0]))
        for name, v in h.items():
            if name == "__metadata__" or any(s in name for s in SKIP):
                continue
            n = int(np.prod(v["shape"])) * (2 if (v["dtype"] == "U8" and name.endswith("_blocks")) else 1)
            if name.endswith("_scales"):
                continue
            tot += n
            if "embed_tokens" in name:
                emb += n
            elif "lm_head" in name:
                head += n
            elif ".experts." in name and E:
                expert += n
            else:
                dense += n
    if head == 0:                                    # tied output head: the embedding matrix is multiplied once per token
        head = emb
    active_matmul = dense + (expert * k / E if E else 0) + head
    lt = t.get("layer_types") or ["full_attention"] * t["num_hidden_layers"]
    return {"total_params_text": tot, "embedding": emb, "output_head": head, "dense_nonembedding": dense, "routed_expert": expert, "experts": E, "experts_per_token": k,
            "active_matmul_params": active_matmul, "n_full": sum(x == "full_attention" for x in lt), "n_sliding": sum(x == "sliding_attention" for x in lt),
            "n_linear": sum(x == "linear_attention" for x in lt), "heads": t["num_attention_heads"], "head_dim": t.get("head_dim") or t["hidden_size"] // t["num_attention_heads"],
            "window": t.get("sliding_window") or 0, "lin_v_heads": t.get("linear_num_value_heads") or 0, "lin_k_dim": t.get("linear_key_head_dim") or 0,
            "lin_v_dim": t.get("linear_value_head_dim") or 0, "hidden": t["hidden_size"]}


def flops_token(a, ctx):
    """forward FLOPs for one token attending to `ctx` earlier tokens."""
    att = 4 * a["heads"] * a["head_dim"] * (a["n_full"] * ctx + a["n_sliding"] * min(ctx, a["window"] or ctx))
    lin = 4 * a["n_linear"] * a["lin_v_heads"] * a["lin_k_dim"] * a["lin_v_dim"]
    return 2 * a["active_matmul_params"] + att + lin


def flops_prefill(a, n_new, ctx0=0):
    """n_new tokens appended after ctx0 cached tokens (closed form of the sum over positions)."""
    n = np.asarray(n_new, float); c0 = np.asarray(ctx0, float); mean_ctx = c0 + (n - 1) / 2
    return n * (2 * a["active_matmul_params"] + 4 * a["n_linear"] * a["lin_v_heads"] * a["lin_k_dim"] * a["lin_v_dim"]) + \
        4 * a["heads"] * a["head_dim"] * n * (a["n_full"] * mean_ctx + a["n_sliding"] * np.minimum(mean_ctx, a["window"] or 1e18))


def readout(m):
    Gz = np.load(REPO_ROOT / f"outputs/v54/gate_{m}.npz"); G = {k: Gz[k] for k in Gz.files}; d = int(G["w0_0"].shape[0]); nd = int(G["n_depth"]); nf = 2   # preload: NpzFile re-reads disk per access; nd = int(G["n_depth"]); nf = 2
    fl = nf * nd * (2 * d + 3) + nf * nd + 2                       # dot product + bias/mean/sd per depth; averages over depths and folds
    params = nf * nd * (d + 3) + 1
    X = np.random.default_rng(0).standard_normal((1, nd, d)).astype(np.float32); G154 = _mod("g154", "scripts/154_v54_gate.py"); reps = 20000
    t0 = time.perf_counter()
    for _ in range(reps):
        G154.gate_score(G, X)
    t = (time.perf_counter() - t0) / reps                 # the deployed scorer (Python loop over 10 dot products)
    Wm = np.stack([G[f"w{k}_{li}"] / float(G[f"sd{k}_{li}"]) for k in range(nf) for li in range(nd)]).astype(np.float32)   # same score as one matrix-vector product
    Xf = np.concatenate([X[0]] * nf).astype(np.float32); t0 = time.perf_counter()
    for _ in range(reps):
        (Wm * Xf).sum()
    t2 = (time.perf_counter() - t0) / reps
    return {"t_cpu_numpy_fused_s": t2, "d": d, "depths": nd, "folds": nf, "flops": fl, "params": params, "bytes_fp32": params * 4, "captured_floats": nd * d, "t_cpu_numpy_s": t}


def tokens(cfg):
    """per decision-time unit of the v57 monitor subset: monitor prompt tokens (exact), agent generated / context / new tokens."""
    import pandas as pd
    from transformers import AutoTokenizer
    from cape.models.load import model_path
    from cape.utils.config import resolve_model
    a155 = _mod("a155", "scripts/155_v57_analysis.py"); m156 = _mod("m156", "scripts/156_v57_monitor.py"); X56 = _mod("x56", "scripts/56_xm_replay_extract.py")
    jt = AutoTokenizer.from_pretrained(model_path(resolve_model("Qwen/Qwen3.8-27B"))); rows = []
    for A in cfg.models:
        at = AutoTokenizer.from_pretrained(model_path(resolve_model(X56.ACT[A]["model"])))
        C, _ = a155.units(A, "conf", with_x=False); C = C[a155.monitor_subset(C)].reset_index(drop=True); roll = {}
        for r, txt in zip(C.itertuples(), a155.texts(C)):
            if r.rollout not in roll:
                roll[r.rollout] = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{r.rollout}.parquet").set_index("episode_id")
            ev = list(roll[r.rollout].loc[r.episode_id].events); e = ev[int(r.event_id)]
            t2 = txt if len(txt) <= cfg.max_chars else txt[:4000] + "\n[... omitted ...]\n" + txt[-(cfg.max_chars - 4000):]
            pm = len(jt.encode(jt.apply_chat_template([{"role": "user", "content": m156.PROMPT.format(prefix=t2)}], add_generation_prompt=True, tokenize=False, enable_thinking=True),
                               add_special_tokens=False)[-20000:])
            gen = sum(len(at.encode(s or "", add_special_tokens=False)) for s in (e["reasoning_text"], e["content_text"], f"{e['tool']}({e['args_json'] or ''})"))
            cur = len(at.encode(((e["reasoning_text"] or "") + (e["content_text"] or "")), add_special_tokens=False))
            ctx = len(at.encode(txt, add_special_tokens=False)) - cur
            prev = next((x for x in reversed(ev[:int(r.event_id)]) if x["is_tool_call"] and x["tool"]), None)
            new = len(at.encode(str(prev["tool_result"] or ""), add_special_tokens=False)) if prev else ctx
            rows.append({"model": A, "cls": r.cls, "monitor_prompt": pm, "agent_gen": gen, "agent_ctx": ctx, "agent_new": new})
    return pd.DataFrame(rows)


def main(cfg):
    OUT.mkdir(parents=True, exist_ok=True); TAB.mkdir(parents=True, exist_ok=True)
    AR = {m: arch(m) for m in set(cfg.models) | {cfg.judge}}; RO = {m: readout(m) for m in cfg.models}; T = tokens(cfg)
    BM = json.load(open(OUT / "bench_monitor.json")) if (OUT / "bench_monitor.json").exists() else None
    BA = {m: json.load(open(OUT / f"bench_agent_{m}.json")) for m in cfg.models if (OUT / f"bench_agent_{m}.json").exists()}
    g_mon = BM["gen_tokens"]["mean"] if BM else None; J = AR[cfg.judge]; res = {"architecture": AR, "readout": RO, "monitor_thinking_tokens_measured": g_mon, "per_model": {}}
    for m in cfg.models:
        t = T[T.model == m]; a = AR[m]
        agent = flops_prefill(a, t.agent_new, t.agent_ctx - t.agent_new) + flops_prefill(a, t.agent_gen, t.agent_ctx)     # prefix-cached agent turn
        mon_pre = flops_prefill(J, t.monitor_prompt)                                                                       # monitor prefill (no cache)
        mon_think = flops_prefill(J, np.full(len(t), g_mon), t.monitor_prompt) if g_mon else None
        # best case for the monitor: it also prefix-caches across consecutive actions of an episode, so it prefills only what is new since
        # its previous call (the previous tool result and the current turn's text; agent-tokenizer counts as a proxy), then thinks
        mon_new = t.agent_new + t.agent_gen; mon_cached = flops_prefill(J, mon_new, np.maximum(t.monitor_prompt - mon_new, 0))
        mon_cached_total = mon_cached + (mon_think if g_mon else 0)
        r = {"n_units": int(len(t)), "tokens": {k: {"mean": float(t[k].mean()), "p50": float(t[k].median()), "p90": float(t[k].quantile(0.9))}
                                                 for k in ("monitor_prompt", "agent_gen", "agent_ctx", "agent_new")},
             "flops_per_action": {"readout": RO[m]["flops"], "agent_turn_mean": float(agent.mean()), "monitor_prefill_mean": float(mon_pre.mean()),
                                  "monitor_total_mean": float((mon_pre + mon_think).mean()) if g_mon else None,
                                  "monitor_cached_prefill_mean": float(mon_cached.mean()), "monitor_cached_total_mean": float(np.mean(mon_cached_total))},
             "tokens_per_action": {"agent_processed_mean": float((t.agent_new + t.agent_gen).mean()),
                                   "monitor_processed_mean": float((t.monitor_prompt + (g_mon or 0)).mean()), "readout": 0}}
        r["ratios"] = {"monitor_over_readout_flops": (r["flops_per_action"]["monitor_total_mean"] or r["flops_per_action"]["monitor_prefill_mean"]) / RO[m]["flops"],
                       "readout_over_agent_flops": RO[m]["flops"] / r["flops_per_action"]["agent_turn_mean"],
                       "monitor_over_agent_flops": (r["flops_per_action"]["monitor_total_mean"] or r["flops_per_action"]["monitor_prefill_mean"]) / r["flops_per_action"]["agent_turn_mean"],
                       "monitor_over_agent_tokens": r["tokens_per_action"]["monitor_processed_mean"] / r["tokens_per_action"]["agent_processed_mean"],
                       "cached_monitor_over_agent_flops": float(np.mean(mon_cached_total)) / r["flops_per_action"]["agent_turn_mean"],
                       "cached_monitor_over_readout_flops": float(np.mean(mon_cached_total)) / RO[m]["flops"]}
        if m in BA:
            r["latency_measured"] = {"agent_turn_s": BA[m]["t_agent_turn_s"]["mean"], "gate_scoring_call_s": BA[m]["t_gate_scoring_call_s"]["mean"],
                                     "readout_cpu_s": BA[m]["t_readout_cpu_s"]["mean"], "readout_gpu_s": BA[m]["t_readout_gpu_s"]["mean"]}
        res["per_model"][m] = r
    if BM:
        res["monitor_latency_measured"] = {"batch1_s": BM["t_call_batch1_s"], "batched_gpu_s_per_call": BM["batched"]["gpu_s_per_call"]}
    json.dump(res, open(OUT / "cost.json", "w"), indent=2, default=float); print(json.dumps(res["per_model"], indent=1, default=float)[:4000])
    table(res, cfg); table_main(res, cfg)


def sci(x):
    if x is None:
        return "--"
    e = int(np.floor(np.log10(x))); m_ = x / 10 ** e
    return f"${m_:.1f}{{\\times}}10^{{{e}}}$"


def table(res, cfg):
    rows = []
    for m in cfg.models:
        r = res["per_model"][m]; f = r["flops_per_action"]; tk = r["tokens_per_action"]; L = r.get("latency_measured", {})
        lat_r = f"{res['readout'][m]['t_cpu_numpy_fused_s']*1e6:.0f}\\,$\\mu$s"   # our own fused timing (the bench's readout timing re-read the npz per key)
        rows.append(" & ".join([NAME[m], f"{res['readout'][m]['flops']:,}".replace(",", "{,}"), sci(f["agent_turn_mean"]),
                                sci(f["monitor_total_mean"] or f["monitor_prefill_mean"]), sci(f["monitor_cached_total_mean"]), sci(r["ratios"]["cached_monitor_over_readout_flops"]),
                                f"{r['ratios']['monitor_over_agent_flops']:.0f}$\\times$ / {r['ratios']['cached_monitor_over_agent_flops']:.1f}$\\times$", f"{tk['monitor_processed_mean']:,.0f}".replace(",", "{,}"),
                                f"{r['ratios']['monitor_over_agent_tokens']:.1f}$\\times$", lat_r]) + " \\\\")
    BM = res.get("monitor_latency_measured"); ml = f"; measured monitor latency per call {BM['batch1_s']['mean']:.1f}\\,s at batch 1 and {BM['batched_gpu_s_per_call']:.2f}\\,GPU-s batched" if BM else ""
    tex = r"""\begin{table}[h]
\centering\scriptsize
\caption{\textbf{Cost per agent action}: internal readout vs the zero-shot CoT monitor (\Qwen-27B), on all 3{,}424 decision units. FLOPs: exact for the readout; from active parameters and attention geometry for model calls (agent prefix-cached). Mon.\ cached: the monitor's best case; mon./agent: uncached / cached. """ + ("Monitor columns include its measured thinking tokens. " if res.get("monitor_thinking_tokens_measured") else "Monitor thinking tokens are excluded, so monitor columns understate its cost. ") + r"""Readout latency: CPU, fused (one matrix--vector product)""" + ml + r""".}
\label{tab:cost}
\setlength{\tabcolsep}{2.2pt}
\begin{tabular}{@{}lrrrrrrrrr@{}}
\toprule
 & \multicolumn{4}{c}{FLOPs per action} & & & \multicolumn{2}{c}{Monitor tokens} & Readout \\
\cmidrule(lr){2-5}\cmidrule(lr){8-9}
Model & readout & agent & monitor & mon.\ cached & cached/readout & mon./agent & per action & vs agent & latency \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
\vspace{-3mm}
\end{table}
"""
    (TAB / "tab_cost.tex").write_text(tex)


def table_main(res, cfg):
    """compact main-text version: per action, readout vs the monitor's best case (prefix-cached), relative to the agent's own turn."""
    rows = []
    for m in cfg.models:
        r = res["per_model"][m]; f = r["flops_per_action"]
        rows.append(" & ".join([NAME[m], sci(res["readout"][m]["flops"]), sci(f["agent_turn_mean"]), sci(f["monitor_cached_total_mean"]),
                                f"{r['ratios']['cached_monitor_over_agent_flops']:.1f}$\\times$", sci(r["ratios"]["cached_monitor_over_readout_flops"]),
                                f"{r['tokens_per_action']['monitor_processed_mean']:,.0f}".replace(",", "{,}")]) + " \\\\")
    tex = r"""\begin{table}[t]
\centering\scriptsize
\caption{\textbf{Cost per action}: FLOPs of the internal readout, the agent's own turn and the CoT monitor (best case: prefix-cached; thinking included when measured), and the tokens the monitor reads. All 3{,}424 decision units; details in \cref{app:cost}.}
\label{tab:cost-main}
\setlength{\tabcolsep}{3pt}
\begin{tabular}{@{}lrrrrrr@{}}
\toprule
 & \multicolumn{3}{c}{FLOPs per action} & \multicolumn{2}{c}{Monitor relative to} & Monitor \\
\cmidrule(lr){2-4}\cmidrule(lr){5-6}
Agent & readout & agent turn & monitor & agent & readout & tokens \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
\vspace{-3mm}
\end{table}
"""
    (TAB / "tab_cost_main.tex").write_text(tex)


if __name__ == "__main__":
    main(OmegaConf.merge(D, load_config(None)))
