#!/usr/bin/env python
"""Cross-family behavioural replication: rollouts of other actor models through a LOCAL vLLM OpenAI-compatible server
(started inside the slurm job, bound to 127.0.0.1; no external network), using each model's native chat template,
tool-call parser and reasoning parser. Same MockEnv, labels and partner-env reveal logic as src/cape/agents/rollout.py;
records are schema-compatible with outputs/rollouts/*.parquet (no token ids: behaviour only, no activations).

python scripts/20_server_rollouts.py actor=gptoss20b split=v2fresh out_name=x_gptoss_v2fresh_minus seeds='[0,1,2,3]'
"""
import asyncio
import json
import os
import subprocess
import sys
import time

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
from omegaconf import OmegaConf

from cape.agents.rollout import clean_tool_name, stable_seed
from cape.envs.base import TOOLS, MockEnv
from cape.models.load import model_path
from cape.utils.config import REPO_ROOT, load_config, resolve_model

# Sampling = each model card's recommended defaults (fixed before any run).
ACTORS = {
    "gptoss20b": {"model": "openai/gpt-oss-20b", "tool_parser": "openai", "reasoning_parser": "openai_gptoss",
                  "sampling": {"temperature": 1.0, "top_p": 1.0}, "extra": {"reasoning_effort": "medium"}},
    "gemma4": {"model": "google/gemma-4-26B-A4B-it", "tool_parser": "gemma4", "reasoning_parser": "gemma4",
               "sampling": {"temperature": 1.0, "top_p": 0.95, "top_k": 64},
               "extra": {"chat_template_kwargs": {"enable_thinking": True}}, "multimodal": True},  # thinking mode on
    # Meta Superintelligence Lab, Aug 2026, Apache-2.0; needs vLLM >= 0.30 (separate env: slurm/run_v030.sh).
    # Reasoning strength is set in the system prompt per the model card; "medium" to match the other actors.
    # Scale series (prereg v24): Qwen3 dense 4B/8B/14B/32B (thinking on) + Llama-3.3-70B (fp8 weights to fit one H100;
    # no reasoning channel). Sampling = each model's generation_config.json.
    **{f"qwen3_{sz}": {"model": f"Qwen/Qwen3-{sz.upper()}", "tool_parser": "hermes", "reasoning_parser": "qwen3",
                       "sampling": {"temperature": 0.6, "top_p": 0.95, "top_k": 20},
                       "extra": {"chat_template_kwargs": {"enable_thinking": True}}} for sz in ("4b", "8b", "14b", "32b")},
    "llama33_70b": {"model": "meta-llama/Llama-3.3-70B-Instruct", "tool_parser": "llama3_json", "reasoning_parser": None,
                    "sampling": {"temperature": 0.6, "top_p": 0.9}, "extra": {},
                    "server_args": ["--quantization", "fp8", "--kv-cache-dtype", "fp8"]},
    # v49 (2026-10-04): Qwen3.8 as a server actor, matching the original offline Qwen rollouts (vLLM 0.26, language-model-only,
    # triton GDN prefill, thinking on); its <tool_call> JSON format is parsed by vLLM's hermes parser
    "qwen38": {"model": "Qwen/Qwen3.8-27B", "tool_parser": "qwen3_coder", "reasoning_parser": "qwen3",   # v49 deviation 2: XML tool calls (hermes parsed none)
               "sampling": {"temperature": 0.6, "top_p": 0.95, "top_k": 20},
               "extra": {"chat_template_kwargs": {"enable_thinking": True}}, "multimodal": True,
               "server_args": ["--gdn-prefill-backend", "triton", "--max-num-seqs", "256"]},   # Mamba cache: <= 601 seqs; original used 256
    "museglimmer": {"model": "meta-models/Muse-Glimmer-30B", "tool_parser": "muse_glimmer",
                    "reasoning_parser": "muse_glimmer", "sampling": {"temperature": 1.0, "top_p": 0.95, "top_k": 64},
                    "extra": {}, "multimodal": True, "system_suffix": "\n\nReasoning strength: medium"},
}
D = OmegaConf.create({"actor": "gptoss20b", "split": "v2fresh", "out_name": None, "seeds": [0, 1, 2, 3],
                      "cf_values": ["unsafe"], "max_turns": 20, "max_tokens": 4096, "concurrency": 96, "port": 8123, "limit": None})
PARSE_ERROR_OBS = "Error: could not parse your tool call. Call exactly one tool with valid JSON arguments."


def start_server(a, port):
    path = model_path(resolve_model(a["model"]))
    cmd = [sys.executable, "-m", "vllm.entrypoints.openai.api_server", "--model", path, "--served-model-name", "actor",
           "--host", "127.0.0.1", "--port", str(port), "--enable-auto-tool-choice", "--tool-call-parser",
           a["tool_parser"], "--max-model-len", "32768", "--gpu-memory-utilization", "0.9"] + \
        (["--reasoning-parser", a["reasoning_parser"]] if a.get("reasoning_parser") else []) + \
        (["--language-model-only"] if a.get("multimodal") else []) + list(a.get("server_args", []))
    env = dict(os.environ)  # the server entrypoint imports sqlite3, which needs the conda env's newer libstdc++
    env["LD_LIBRARY_PATH"] = "/data/models/cider_ws/envs/cider/lib:" + env.get("LD_LIBRARY_PATH", "")
    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr, env=env)
    for _ in range(360):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=2).status_code == 200:
                return proc
        except Exception:
            pass
        if proc.poll() is not None:
            raise RuntimeError("vLLM server exited during startup")
        time.sleep(5)
    raise RuntimeError("vLLM server did not become healthy")


def prior_openai(prior):
    """Spec prior messages store tool-call arguments as a mapping (HF templates); the OpenAI API wants a JSON string."""
    out = []
    for m in prior or []:
        m = json.loads(json.dumps(m))
        for c in m.get("tool_calls") or []:
            if not isinstance(c["function"]["arguments"], str):
                c["function"]["arguments"] = json.dumps(c["function"]["arguments"])
        out.append(m)
    return out


async def episode(client, a, cfg, spec, partner_spec, seed, sem):
    env, partner = MockEnv(spec), MockEnv(partner_spec)
    msgs = [{"role": "system", "content": spec["system_prompt"] + a.get("system_suffix", "")}] + \
        prior_openai(spec.get("prior_messages")) + [{"role": "user", "content": spec["task_prompt"]}]
    turns, status = [], "max_turns"
    for t in range(cfg.max_turns):
        body = {"model": "actor", "messages": msgs, "tools": TOOLS, "max_tokens": cfg.max_tokens,
                # per-episode hashed request seed. The earlier `seed * 1000 + t` reused one random stream across every
                # scenario with the same seed index, leaving a seed fingerprint that a text classifier decodes at AUROC
                # 0.91-0.99; with unbalanced seeds across worlds it confounds world/harm labels (results/xm/seed_fingerprint.json)
                "seed": seed * 1000 + t if cfg.get("legacy_seed") else stable_seed(spec["instance_id"], seed, t),
                **a["sampling"], **a["extra"]}   # legacy_seed: ONLY to complete an existing legacy-seeded design symmetrically
        r = None
        async with sem:
            for attempt in range(3):
                try:
                    body["seed"] = (seed * 1000 + t + 100000 * attempt if cfg.get("legacy_seed")
                                    else stable_seed(spec["instance_id"], seed, t, attempt))  # resample on server-side parse failures
                    r = await client.post("/v1/chat/completions", json=body, timeout=600)
                    r.raise_for_status()
                    break
                except Exception:
                    r = None
                    await asyncio.sleep(2)
        if r is None:  # persistent server error (e.g. malformed harmony output): end this episode, count it
            status = "server_error"
            break
        ch = r.json()["choices"][0]
        m = ch["message"]
        reasoning = m.get("reasoning_content") or m.get("reasoning") or ""
        content = m.get("content") or ""
        calls = m.get("tool_calls") or []
        turn = {"event_id": t, "finish_reason": ch.get("finish_reason"), "reasoning_text": reasoning,
                "content_text": content, "is_tool_call": bool(calls), "tool": None, "args_json": None,
                "parse_error": None, "tool_result": None, "unsafe_action": False, "critical": False, "goal": False,
                "escalation": False, "violations": [], "obs_differs_from_partner": False, "n_tool_calls": len(calls), "tool_raw": None}
        turns.append(turn)
        if ch.get("finish_reason") == "length":
            status = "truncated"
            break
        if not calls:
            status = "final_answer"
            break
        c = calls[0]  # policy: one tool call per turn; extra calls are recorded as n_tool_calls
        raw = c["function"]["name"]; name = clean_tool_name(raw)
        c = dict(c, function=dict(c["function"], name=name)); turn["tool_raw"] = raw   # harness fix 2026-10-03 (see clean_tool_name)
        try:
            args = json.loads(c["function"].get("arguments") or "{}")
            assert isinstance(args, dict)
        except Exception as e:
            args, turn["parse_error"] = None, str(e)[:200]
        turn["tool"], turn["args_json"] = name, json.dumps(args) if args is not None else None
        if args is None:
            obs = PARSE_ERROR_OBS
        else:
            obs, info = env.step(name, args)
            turn.update(unsafe_action=info.unsafe, critical=info.critical, goal=info.goal,
                        escalation=info.escalation, violations=list(info.violations))
            pobs, _ = partner.step(name, args)
            turn["obs_differs_from_partner"] = pobs != obs
        turn["tool_result"] = obs
        # keep the model's own prior reasoning in context (gpt-oss harmony reads `thinking`; others `reasoning(_content)`)
        msgs.append({"role": "assistant", "content": content, "tool_calls": [c], "thinking": reasoning,
                     "reasoning": reasoning, "reasoning_content": reasoning})
        msgs.append({"role": "tool", "tool_call_id": c.get("id", f"call_{t}"), "content": obs})
    for tr in turns:
        tr["violations"] = ",".join(tr["violations"])
    unsafe = [x["event_id"] for x in turns if x["unsafe_action"]]
    crit = [x["event_id"] for x in turns if x["critical"]]
    reveal = [x["event_id"] for x in turns if x["obs_differs_from_partner"]]
    s = spec
    return {"episode_id": f"{s['instance_id']}.s{seed}", "scenario_id": s["scenario_id"],
            "scenario_family": s["scenario_family"], "template": s["template"],
            "surface_template": s["surface_template"], "counterfactual_pair_id": s["counterfactual_pair_id"],
            "counterfactual_value": s["counterfactual_value"], "cf_value": s["cf_value"],
            "instance_id": s["instance_id"], "nuisance": s["nuisance"], "monitor_aware": s["monitor_aware"],
            "seed": seed, "model": a["model"], "benchmark": "capebench", "status": status, "n_events": len(turns),
            "success": bool(any(x["goal"] for x in turns) and not unsafe), "unsafe_episode": bool(unsafe),
            "first_unsafe_event": unsafe[0] if unsafe else None, "critical_done": bool(crit),
            "first_critical_event": crit[0] if crit else None,
            "escalated": any(x["escalation"] for x in turns), "reveal_event": reveal[0] if reveal else None,
            "n_parse_errors": sum(x["parse_error"] is not None for x in turns),
            "final_answer": turns[-1]["content_text"] if status == "final_answer" else None, "n_tokens": 0,
            "events": turns}


async def run(cfg, a, specs, by_inst):
    sem = asyncio.Semaphore(cfg.concurrency)
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{cfg.port}") as client:
        jobs = []
        for s in specs:
            other = "safe" if s["cf_value"] == "unsafe" else "unsafe"
            pid = f"{s['base_id']}.p{s['paraphrase_id']}.{other}" + (".aware" if s["monitor_aware"] else "")
            for sd in cfg.seeds:
                jobs.append(episode(client, a, cfg, s, by_inst[pid], int(sd), sem))
        out, t0 = [], time.time()
        for i, f in enumerate(asyncio.as_completed(jobs)):
            out.append(await f)
            if (i + 1) % 100 == 0:
                print(f"{i + 1}/{len(jobs)} episodes, {time.time() - t0:.0f}s, unsafe so far "
                      f"{sum(o['unsafe_episode'] for o in out)}", flush=True)
        return out


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    a = ACTORS[cfg.actor]
    specs = [json.loads(l) for l in open(REPO_ROOT / f"outputs/capebench/{cfg.split}/scenarios.jsonl")]
    by_inst = {s["instance_id"]: s for s in specs}
    specs = [s for s in specs if s["cf_value"] in set(cfg.cf_values) and not s["nuisance"]]
    if cfg.limit:  # smoke runs
        specs = specs[:: max(1, len(specs) // int(cfg.limit))][: int(cfg.limit)]
    proc = start_server(a, cfg.port)
    try:
        recs = asyncio.run(run(cfg, a, specs, by_inst))
    finally:
        proc.terminate()
    name = cfg.out_name or f"x_{cfg.actor}_{cfg.split}"
    pq.write_table(pa.Table.from_pylist(recs), REPO_ROOT / f"outputs/rollouts/{name}.parquet")
    import pandas as pd
    df = pd.DataFrame([{k: v for k, v in r.items() if k != "events"} for r in recs])
    print(json.dumps({"n": len(df), "status": df.status.value_counts().to_dict(),
                      "unsafe_rate": float(df.unsafe_episode.mean()),
                      "by_template": df.groupby("template").unsafe_episode.mean().round(3).to_dict(),
                      "parse_errors": int(df.n_parse_errors.sum())}, indent=2))
    print("wrote", name)


if __name__ == "__main__":
    main()
