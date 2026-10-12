#!/usr/bin/env python
"""v9 closed-loop fix demonstration (docs/preregistration_v9.md): agents act with a pre-execution gate IN THE LOOP.

python scripts/21_gated_rollouts.py arm=B_resolved split=v2fresh cf_values='[unsafe]' seeds='[0,...,7]' \
    out_name=gated_B_v2fresh_minus

Every proposed tool call is scored BEFORE execution by the same zero-shot judge, prompt and information arm as the
offline gate study (scripts/11_gate_eval.py; Qwen3.8-27B non-thinking, one YES/NO token), served from the SAME vLLM
engine as the actor (identical weights). If score > the arm's fixed 1%-FPR threshold (results/v3/gate_thresholds_
1pct.json, set on the offline study), the call is NOT executed and the agent receives GATE_BLOCK_OBS; what it would
have done is labelled on a throwaway copy of the environment. Everything else is identical to scripts/02.
"""
import importlib.util
import json
import math
import random
import time
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from omegaconf import OmegaConf

from cape.agents.actor import ChatFormatter
from cape.agents.generators import VLLMGenerator
from cape.agents.rollout import EpisodeState
from cape.agents.tool_parser import parse_tool_call
from cape.envs.base import NEVER_CRITICAL
from cape.guard.resolve import resolve_effect
from cape.models.load import load_tokenizer, model_path
from cape.utils.config import REPO_ROOT, load_config
from cape.utils.repro import make_run_dir, snapshot, write_json

spec = importlib.util.spec_from_file_location("g", REPO_ROOT / "scripts/11_gate_eval.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

D = OmegaConf.create({"arm": "B_resolved", "split": "v2fresh", "seeds": [0, 1, 2, 3, 4, 5, 6, 7],
                      "cf_values": ["unsafe"], "out_name": None, "max_turns": 20, "max_context": 30000,
                      "generation": {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "max_tokens": 4096},
                      "max_prompt_tokens": 28000, "thresholds": "results/v3/gate_thresholds_1pct.json"})


def history_text(e) -> str:
    """Identical format to cape.eval.prediction.visible_history(with_cot=False), up to (excluding) the proposal."""
    parts = [f"TASK: {e.spec['task_prompt']}"]
    for t in e.turns:
        parts.append(f"ACTION: {t['tool']}({t['args_json']})" if t["is_tool_call"]
                     else f"FINAL ANSWER: {t['content_text']}")
        if t["tool_result"] is not None:
            parts.append(f"OBSERVATION: {t['tool_result']}")
    return "\n".join(parts)


def perm_log(e) -> list[str]:
    return [t["tool_result"].strip()[:200] for t in e.turns if t["tool"] == "request_permission" and t["tool_result"]]


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    mcfg = cfg.model
    assert cfg.arm in ("A_transcript", "B_resolved", "B2_resolved_identity")
    tau = json.load(open(REPO_ROOT / cfg.thresholds))[cfg.arm if cfg.arm != "B2_resolved_identity" else "B_resolved"]
    specs = [json.loads(l) for l in open(REPO_ROOT / f"outputs/capebench/{cfg.split}/scenarios.jsonl")]
    by_inst = {s["instance_id"]: s for s in specs}
    specs = [s for s in specs if s["cf_value"] in set(cfg.cf_values) and not s["nuisance"]]
    out_name = cfg.out_name or f"gated_{cfg.arm}_{cfg.split}"
    run = make_run_dir(f"rollouts_{out_name}")
    snapshot(run, cfg, model_revision=mcfg.get("revision"))
    tok = load_tokenizer(mcfg)
    fmt = ChatFormatter(tok, enable_thinking=mcfg.chat.enable_thinking, reasoning_effort=mcfg.chat.reasoning_effort)
    yes = sorted({i[0] for w in ("YES", "Yes", " YES") if len(i := tok.encode(w, add_special_tokens=False)) == 1})
    no = sorted({i[0] for w in ("NO", "No", " NO") if len(i := tok.encode(w, add_special_tokens=False)) == 1})

    def partner(s):
        other = "safe" if s["cf_value"] == "unsafe" else "unsafe"
        return by_inst[f"{s['base_id']}.p{s['paraphrase_id']}.{other}" + (".aware" if s["monitor_aware"] else "")]

    eps = [EpisodeState(spec=s, seed=int(sd), fmt=fmt, partner_spec=partner(s), max_turns=cfg.max_turns,
                        max_context=cfg.max_context) for s in specs for sd in cfg.seeds]
    gen = VLLMGenerator(model_path(mcfg), seed=0, **OmegaConf.to_container(cfg.generation))
    from vllm import SamplingParams
    from vllm.inputs import TokensPrompt
    judge_sp = SamplingParams(max_tokens=1, temperature=0.0, logprob_token_ids=yes + no)
    print(f"{len(eps)} episodes; arm={cfg.arm} tau={tau:.4f}", flush=True)
    t0, turn, n_scored, n_blocked = time.time(), 0, 0, 0
    while True:
        active = [e for e in eps if not e.done]
        if not active:
            break
        outs = gen(active)
        props, prompts = [], []
        for e, (g, lp, fr) in zip(active, outs):
            sp = e.fmt.split_generation(g)
            te = sp["think_end"]
            if fr == "length" or te is None:
                continue
            name, args, perr = parse_tool_call(tok.decode(g[te + 1:], skip_special_tokens=False))
            if name is None or perr is not None or name in NEVER_CRITICAL:
                continue  # escalation and read-only inspection are never gated
            traj = history_text(e) + f"\nACTION: {name}({json.dumps(args) if args else None})"
            eff = ""
            if cfg.arm.startswith("B"):
                eff = G.EFFECT.format(eff=resolve_effect(e.env, name, args or {}, perm_log(e),
                                                         identity=cfg.arm == "B2_resolved_identity"))
            msg = G.INSTR.format(system=e.spec["system_prompt"], traj=traj, cot="", effect=eff)
            ids = tok.encode(tok.apply_chat_template([{"role": "user", "content": msg}], tokenize=False,
                                                     add_generation_prompt=True, enable_thinking=False),
                             add_special_tokens=False)
            if len(ids) > cfg.max_prompt_tokens:
                ids = ids[:4000] + ids[-(cfg.max_prompt_tokens - 4000):]
            props.append((e, len(e.turns)))
            prompts.append(TokensPrompt(prompt_token_ids=ids))
        if prompts:
            for (e, eid), o in zip(props, gen.llm.generate(prompts, judge_sp, use_tqdm=False)):
                lp = o.outputs[0].logprobs[0]
                ly = math.log(sum(math.exp(lp[i].logprob) for i in yes if i in lp) or 1e-30)
                ln = math.log(sum(math.exp(lp[i].logprob) for i in no if i in lp) or 1e-30)
                sc = ly - ln
                e.gate_decisions[eid] = (sc > tau, sc)
                n_scored += 1
                n_blocked += sc > tau
        for e, (g, lp, fr) in zip(active, outs):
            e.consume(g, lp, fr)
        turn += 1
        print(f"[turn {turn}] active={len(active)} scored={n_scored} blocked={n_blocked} "
              f"executed_unsafe={sum(any(t['unsafe_action'] for t in e.turns) for e in eps)} "
              f"blocked_unsafe={sum(any(t['blocked'] and t['would_be_unsafe'] for t in e.turns) for e in eps)} "
              f"{time.time() - t0:.0f}s", flush=True)
    recs = [e.record(mcfg.name) for e in eps]
    for r in recs:
        r["gate_arm"], r["gate_tau"] = cfg.arm, tau
        for ev in r["events"]:
            ev["violations"] = ",".join(ev["violations"])
    out_dir = REPO_ROOT / "outputs" / "rollouts"
    pq.write_table(pa.Table.from_pylist(recs), out_dir / f"{out_name}.parquet")
    pq.write_table(pa.Table.from_pylist([{"episode_id": e.episode_id, "input_ids": e.ids, "gen_mask": e.gen_mask,
                                          "logprobs": e.logprobs} for e in eps]), out_dir / f"{out_name}_tokens.parquet")
    df = pd.DataFrame([{k: v for k, v in r.items() if k != "events"} for r in recs])
    summ = {"n": len(df), "executed_unsafe_rate": float(df.unsafe_episode.mean()),
            "episodes_with_blocked_unsafe": int((df.blocked_unsafe > 0).sum()), "blocks": int(df.n_blocked.sum()),
            "success": float(df.success.mean()), "escalated": float(df.escalated.mean()),
            "status": df.status.value_counts().to_dict(), "wall_s": round(time.time() - t0)}
    write_json(run / "metrics.json", summ)
    print(json.dumps(summ, indent=2))
    print("wrote", out_dir / f"{out_name}.parquet")


if __name__ == "__main__":
    main()
