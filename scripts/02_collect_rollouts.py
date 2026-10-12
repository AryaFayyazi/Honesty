#!/usr/bin/env python
"""Bulk rollout generation with vLLM (token-in/token-out, exact ids saved for HF replay).

python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B benchmark=capebench split=pilot \
    generation.temperature=0.6 generation.top_p=0.95 seeds='[0,1,2,3]'

Optional: scenarios=<path to scenarios.jsonl> limit_pairs=N families='[...]' include_nuisance=false
          reasoning_effort=medium max_turns=20 out_name=pilot
Writes outputs/rollouts/<out_name>.parquet (episodes, nested events) and <out_name>_tokens.parquet.
"""
import json
import random
import time
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from omegaconf import OmegaConf

from cape.agents.actor import ChatFormatter
from cape.agents.generators import VLLMGenerator
from cape.agents.rollout import EpisodeState, run_lockstep
from cape.models.load import load_tokenizer, model_path
from cape.utils.config import REPO_ROOT, load_config
from cape.utils.repro import make_run_dir, snapshot, write_json

DEFAULTS = OmegaConf.create({
    "benchmark": "capebench", "split": "pilot", "scenarios": None, "seeds": [0, 1, 2, 3],
    "generation": {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "max_tokens": 4096},
    "reasoning_effort": None, "max_turns": 20, "max_model_len": 32768, "max_context": 30000,
    "limit_pairs": None, "families": None, "include_nuisance": False, "out_name": None, "shuffle_seed": 0,
    "gpu_memory_utilization": 0.9, "cf_values": None,
})


def main():
    cfg = OmegaConf.merge(DEFAULTS, load_config(None))
    mcfg = cfg.model
    effort = cfg.reasoning_effort or mcfg.chat.reasoning_effort
    scen = Path(cfg.scenarios or REPO_ROOT / "outputs" / "capebench" / cfg.split / "scenarios.jsonl")
    specs = [json.loads(l) for l in open(scen)]
    by_inst = {s["instance_id"]: s for s in specs}
    if cfg.get("cf_values"):
        specs = [s for s in specs if s["cf_value"] in set(cfg.cf_values)]
    if cfg.families:
        specs = [s for s in specs if s["scenario_family"] in set(cfg.families)]
    if not cfg.include_nuisance:
        specs = [s for s in specs if not s["nuisance"]]
    if cfg.limit_pairs:
        pids = sorted({s["counterfactual_pair_id"] for s in specs})
        random.Random(cfg.shuffle_seed).shuffle(pids)
        keep = set(pids[: int(cfg.limit_pairs)])
        specs = [s for s in specs if s["counterfactual_pair_id"] in keep]

    out_name = cfg.out_name or cfg.split
    run = make_run_dir(f"rollouts_{out_name}")
    snapshot(run, cfg, model_revision=mcfg.get("revision"))
    tok = load_tokenizer(mcfg)
    fmt = ChatFormatter(tok, enable_thinking=mcfg.chat.enable_thinking, reasoning_effort=effort)

    def partner(s):
        other = "safe" if s["cf_value"] == "unsafe" else "unsafe"
        pid = f"{s['base_id']}.p{s['paraphrase_id']}.{other}" + (".aware" if s["monitor_aware"] else "")
        return by_inst[pid]

    eps = [EpisodeState(spec=s, seed=int(sd), fmt=fmt, partner_spec=partner(s), max_turns=cfg.max_turns,
                        max_context=cfg.max_context) for s in specs for sd in cfg.seeds]
    print(f"{len(specs)} instances x {len(cfg.seeds)} seeds = {len(eps)} episodes; reasoning_effort={effort}")
    gen = VLLMGenerator(model_path(mcfg), max_model_len=cfg.max_model_len,
                        gpu_memory_utilization=cfg.gpu_memory_utilization, seed=0,
                        **OmegaConf.to_container(cfg.generation))
    t0 = time.time()
    run_lockstep(eps, gen)
    dt = time.time() - t0

    recs = [e.record(mcfg.name) for e in eps]
    for r in recs:
        for ev in r["events"]:
            ev["violations"] = ",".join(ev["violations"])
    out_dir = REPO_ROOT / "outputs" / "rollouts"
    out_dir.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(recs), out_dir / f"{out_name}.parquet")
    toks = pa.Table.from_pylist([{"episode_id": e.episode_id, "input_ids": e.ids, "gen_mask": e.gen_mask,
                                  "logprobs": e.logprobs} for e in eps])
    pq.write_table(toks, out_dir / f"{out_name}_tokens.parquet")

    df = pd.DataFrame([{k: v for k, v in r.items() if k != "events"} for r in recs])
    summ = {
        "n_episodes": len(df), "wall_s": round(dt), "gen_tokens": int(sum(sum(e.gen_mask) for e in eps)),
        "status": df.status.value_counts().to_dict(),
        "unsafe_rate_by_cf": df.groupby("cf_value").unsafe_episode.mean().round(3).to_dict(),
        "unsafe_rate_by_family_cf": {f"{a}|{b}": round(v, 3) for (a, b), v in
                                     df.groupby(["scenario_family", "cf_value"]).unsafe_episode.mean().items()},
        "critical_rate_by_cf": df.groupby("cf_value").critical_done.mean().round(3).to_dict(),
        "escalated_rate_by_cf": df.groupby("cf_value").escalated.mean().round(3).to_dict(),
        "success_rate_by_cf": df.groupby("cf_value").success.mean().round(3).to_dict(),
        "mean_events": round(df.n_events.mean(), 2), "mean_tokens": round(df.n_tokens.mean()),
        "reveal_rate": round(df.reveal_event.notna().mean(), 3),
        "parse_errors": int(df.n_parse_errors.sum()),
    }
    write_json(run / "metrics.json", summ)
    print(json.dumps(summ, indent=2))
    print("wrote", out_dir / f"{out_name}.parquet")


if __name__ == "__main__":
    main()
