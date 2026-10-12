#!/usr/bin/env python
"""Measured cost of the internal gate vs the zero-shot CoT monitor, on one H100 NVL (bf16, vLLM, eager, prefix caching).
  stage=agent actor=<m> : real CAPE decision sites (v54 confirmation sites, as scripts/174 validate). Per site, batch 1:
        (i) the agent's turn: generation latency and tokens (CAPE sampling, fixed seed);
        (ii) our gate's scoring call: prefill-only forward on prompt + turn up to the tool-call markup (prefix-cached), capturing
             the 5 residual vectors;
        (iii) the readout itself: 2 folds x 5 depths of z-scored dot products (numpy, CPU), and the same on the GPU (torch).
  stage=monitor : the zero-shot CoT monitor of scripts/156 (Qwen3.8-27B, thinking on, greedy, max 3000 thinking tokens) on a stratified
        sample of the exact v57 monitor prompts: batch-1 latency, prompt and generated tokens; then the whole sample batched (throughput).
-> results/cost/bench_agent_<m>.json, results/cost/bench_monitor.json"""
import hashlib
import importlib.util
import json
import os
import time

import numpy as np
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"stage": "agent", "actor": "qwen38", "n": 24, "n_monitor": 24, "max_model_len": 32768, "gpu_mem": 0.88, "n_val": 48,
                      "max_think": 3000, "judge_model": "Qwen/Qwen3.8-27B", "max_chars": 40000})
OUT = REPO_ROOT / "results/cost"


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def pct(v):
    v = np.asarray(v, float); return {"mean": float(v.mean()), "p50": float(np.percentile(v, 50)), "p90": float(np.percentile(v, 90)), "n": int(len(v))}


def stage_agent(cfg):
    import pandas as pd
    import torch
    V174 = _mod("v174", "scripts/174_vllm_steer.py"); A = cfg.actor; S = V174.Steer(A, cfg); M144 = _mod("m144", "scripts/144_v54_steer.py")
    G = np.load(REPO_ROOT / f"outputs/v54/gate_{A}.npz")
    R = pd.read_parquet(REPO_ROOT / f"outputs/v54/v54conf_{A}.parquet"); R["key"] = R.set + "|" + R.episode_id
    Sx = pd.read_parquet(REPO_ROOT / f"outputs/v54/sites_{A}_conf.parquet"); Sx["key"] = Sx.set + "|" + Sx.episode_id
    Sx = Sx[Sx.key.isin(set(R.key))].groupby("world").head(int(cfg.n) // 2)
    specs, roll = {}, {}
    for b in Sx.bench.unique():
        for l in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl"):
            x = json.loads(l); specs[(b, x["instance_id"])] = x
    for s_ in Sx.set.unique():
        roll[s_] = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{s_}.parquet").set_index("episode_id")
    a = S.X56.ACT[A]; SAMP = {"qwen38": (0.6, 0.95, 20), "gemma4": (1.0, 0.95, 64), "gptoss20b": (1.0, 1.0, -1), "museglimmer": (1.0, 0.95, 64)}[A]
    # readout weights on the GPU for the torch timing
    W = {k: torch.tensor(G[k], dtype=torch.float32, device="cuda") for k in G.files if k.startswith("w")}
    rows = []
    # warm-up (CUDA graphs are off; first calls allocate)
    for _ in range(2):
        S.generate([[S.tok.eos_token_id or 0] * 8], [{"temperature": 1.0, "top_p": 1.0, "top_k": -1, "max_tokens": 4, "seed": 0}])
    for r in Sx.itertuples():
        ev = list(roll[r.set].loc[r.episode_id].events); spec = specs[(r.bench, r.instance_id)]
        base = S.X56.messages_upto(spec, ev, int(r.site_event), a["suffix"]); base = base[:-1] if base and base[-1]["role"] == "assistant" else base
        prompt = M144.render_gen(S.X56, S.tok, base, a["kwargs"]); pid = S.tok(prompt, add_special_tokens=False)["input_ids"]
        sd = int(hashlib.md5(r.key.encode()).hexdigest(), 16) % 2**31
        torch.cuda.synchronize(); t0 = time.perf_counter()
        (g, txt), = S.generate([pid], [{"temperature": SAMP[0], "top_p": SAMP[1], "top_k": SAMP[2], "max_tokens": 1536, "seed": sd}])
        torch.cuda.synchronize(); t_gen = time.perf_counter() - t0
        ids = S.pre_action_ids(pid, g)
        if ids is None:
            rows.append({"prompt_tokens": len(pid), "gen_tokens": len(g), "t_gen": t_gen, "t_score": np.nan, "t_readout_cpu": np.nan, "t_readout_gpu": np.nan}); continue
        torch.cuda.synchronize(); t0 = time.perf_counter(); f = S.features(ids); torch.cuda.synchronize(); t_score = time.perf_counter() - t0
        X = f[None].astype(np.float32); reps = 2000
        t0 = time.perf_counter()
        for _ in range(reps):
            S.G154.gate_score(G, X)
        t_cpu = (time.perf_counter() - t0) / reps
        Xg = torch.tensor(f, dtype=torch.float32, device="cuda"); torch.cuda.synchronize(); t0 = time.perf_counter()
        for _ in range(reps):
            s_ = sum(((Xg[li] @ W[f"w{k}_{li}"]) for k in (0, 1) for li in range(int(G["n_depth"]))))
        torch.cuda.synchronize(); t_gpu = (time.perf_counter() - t0) / reps
        rows.append({"prompt_tokens": len(pid), "gen_tokens": len(g), "pre_action_tokens": len(ids), "t_gen": t_gen, "t_score": t_score, "t_readout_cpu": t_cpu, "t_readout_gpu": t_gpu})
        print(len(rows), f"gen {t_gen:.2f}s ({len(g)} tok)  score {t_score*1e3:.1f} ms  readout cpu {t_cpu*1e6:.1f} us gpu {t_gpu*1e6:.1f} us", flush=True)
    Rw = pd.DataFrame(rows); ok = Rw.t_score.notna()
    out = {"actor": A, "n_sites": int(len(Rw)), "n_scored": int(ok.sum()), "gpu": torch.cuda.get_device_name(0),
           "prompt_tokens": pct(Rw.prompt_tokens), "gen_tokens": pct(Rw.gen_tokens),
           "t_agent_turn_s": pct(Rw.t_gen), "t_gate_scoring_call_s": pct(Rw.t_score[ok]),
           "t_readout_cpu_s": pct(Rw.t_readout_cpu[ok]), "t_readout_gpu_s": pct(Rw.t_readout_gpu[ok]),
           "overhead_scoring_call_vs_turn": pct((Rw.t_score / Rw.t_gen)[ok]),
           "note": "scoring call = our implementation (extra prefix-cached prefill to the tool-call markup); an in-line capture during decoding needs no extra forward pass, leaving only the readout."}
    OUT.mkdir(parents=True, exist_ok=True); json.dump(out, open(OUT / f"bench_agent_{A}.json", "w"), indent=2); print(json.dumps(out, indent=1), flush=True)
    os._exit(0)


def stage_monitor(cfg):
    import pandas as pd
    import torch
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    from vllm.inputs import TokensPrompt
    from cape.models.load import model_path
    from cape.utils.config import resolve_model
    a155 = _mod("a155", "scripts/155_v57_analysis.py"); m156 = _mod("m156", "scripts/156_v57_monitor.py")
    mp = model_path(resolve_model(cfg.judge_model)); tok = AutoTokenizer.from_pretrained(mp); prompts, meta = [], []
    per = int(cfg.n_monitor) // 4
    for A in ("gemma4", "gptoss20b", "museglimmer", "qwen38"):
        C, _ = a155.units(A, "conf", with_x=False); C = C[a155.monitor_subset(C)].reset_index(drop=True)
        C = C.assign(h=[hashlib.sha256(f"cost|{e}|{i}".encode()).hexdigest() for e, i in zip(C.episode_id, C.event_id)]).sort_values("h").head(per)
        for r, txt in zip(C.itertuples(), a155.texts(C)):
            txt = txt if len(txt) <= cfg.max_chars else txt[:4000] + "\n[... omitted ...]\n" + txt[-(cfg.max_chars - 4000):]
            ids = tok.encode(tok.apply_chat_template([{"role": "user", "content": m156.PROMPT.format(prefix=txt)}], add_generation_prompt=True, tokenize=False, enable_thinking=True), add_special_tokens=False)
            prompts.append(ids[-20000:]); meta.append({"model": A, "cls": r.cls})
    llm = LLM(model=mp, dtype="bfloat16", max_model_len=24000, gpu_memory_utilization=0.9, language_model_only=True, gdn_prefill_backend="triton", max_num_seqs=128)
    sp = SamplingParams(max_tokens=int(cfg.max_think) + 50, temperature=0.0)
    llm.generate([TokensPrompt(prompt_token_ids=prompts[0][:64])], SamplingParams(max_tokens=4), use_tqdm=False)        # warm-up
    rows = []
    for ids, m in zip(prompts, meta):                       # batch 1: the latency an action waits for
        torch.cuda.synchronize(); t0 = time.perf_counter(); o = llm.generate([TokensPrompt(prompt_token_ids=ids)], sp, use_tqdm=False)[0]
        torch.cuda.synchronize(); rows.append({**m, "prompt_tokens": len(ids), "gen_tokens": len(o.outputs[0].token_ids), "t": time.perf_counter() - t0})
        print(len(rows), f"{rows[-1]['t']:.2f}s prompt {len(ids)} gen {rows[-1]['gen_tokens']}", flush=True)
    llm.reset_prefix_cache()
    torch.cuda.synchronize(); t0 = time.perf_counter(); llm.generate([TokensPrompt(prompt_token_ids=i) for i in prompts], sp, use_tqdm=False); torch.cuda.synchronize()
    t_batch = time.perf_counter() - t0
    Rw = pd.DataFrame(rows)
    out = {"judge": cfg.judge_model, "gpu": torch.cuda.get_device_name(0), "n": int(len(Rw)), "prompt_tokens": pct(Rw.prompt_tokens), "gen_tokens": pct(Rw.gen_tokens),
           "t_call_batch1_s": pct(Rw.t), "batched": {"n": int(len(prompts)), "wall_s": t_batch, "gpu_s_per_call": t_batch / len(prompts)},
           "per_model": {k: {"prompt_tokens_mean": float(g.prompt_tokens.mean()), "gen_tokens_mean": float(g.gen_tokens.mean()), "t_mean": float(g.t.mean())} for k, g in Rw.groupby("model")}}
    OUT.mkdir(parents=True, exist_ok=True); json.dump(out, open(OUT / "bench_monitor.json", "w"), indent=2); print(json.dumps(out, indent=1), flush=True)
    os._exit(0)


if __name__ == "__main__":
    c = OmegaConf.merge(D, load_config(None)); {"agent": stage_agent, "monitor": stage_monitor}[c.stage](c)
