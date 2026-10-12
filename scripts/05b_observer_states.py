#!/usr/bin/env python
"""Observer hidden-state baseline (simplified TRACES / DreamGuard-style encoder).

python scripts/05b_observer_states.py trajectories=outputs/rollouts/pilot.parquet [observer=Qwen/Qwen3-8B]
    [layers='[18,27]']

A separate observer LLM reads the externally visible transcript (with and without the actor's CoT). For every
decision t we store the observer's residual state at the last token of the proposed-action line (so the observer has
seen exactly what the transcript/CoT monitors see). One forward pass per episode (causal => prefix-exact).
"""
import json
from pathlib import Path

import pandas as pd
import torch
from omegaconf import OmegaConf

from cape.activations.hooks import ResidualCapture
from cape.activations.storage import ShardWriter
from cape.models.load import discover_transformer_blocks, load_hf_model, load_tokenizer
from cape.utils.config import REPO_ROOT, load_config, resolve_model
from cape.utils.repro import snapshot, write_json

DEFAULTS = OmegaConf.create({"trajectories": "outputs/rollouts/pilot.parquet", "observer": "Qwen/Qwen3-8B",
                             "layers": [18, 27], "scenarios": "outputs/capebench/pilot/scenarios.jsonl",
                             "max_tokens": 32000, "variants": ["nocot", "cot"]})


def episode_text(ep, spec, with_cot, pre_action=False):
    """pre_action=True places the decision mark at the end of the agent's reasoning for step t, BEFORE the proposed
    action (matched information with the actor's pre_action_last representation)."""
    parts, marks = [f"Monitoring transcript of an operations agent.\nTASK: {spec['task_prompt']}\n"], []
    for e in ep.events:
        if with_cot:
            parts.append(f"AGENT REASONING: {e['reasoning_text']}\n")
        if pre_action:
            marks.append(sum(len(p) for p in parts))  # char offset at end of reasoning (action not yet visible)
        act = f"AGENT ACTION: {e['tool']}({e['args_json']})" if e["is_tool_call"] else \
            f"AGENT FINAL ANSWER: {e['content_text']}"
        parts.append(act)
        if not pre_action:
            marks.append(sum(len(p) for p in parts))  # char offset just after the action line
        parts.append("\n")
        if e["tool_result"] is not None:
            parts.append(f"OBSERVATION: {e['tool_result']}\n")
    return "".join(parts), marks


def main():
    cfg = OmegaConf.merge(DEFAULTS, load_config(None))
    ocfg = resolve_model(cfg.observer)
    traj = REPO_ROOT / cfg.trajectories
    eps = pd.read_parquet(traj)
    specs = {json.loads(l)["instance_id"]: json.loads(l) for l in open(REPO_ROOT / cfg.scenarios)}
    tok = load_tokenizer(ocfg)
    model = load_hf_model(ocfg)
    blocks, _ = discover_transformer_blocks(model)
    layers = [int(l) for l in cfg.layers]
    VAR = {"nocot": ("observer_nocot", False, False), "cot": ("observer_cot", True, False),
           "cotpre": ("observer_cotpre", True, True)}
    for vkey in cfg.variants:
        variant, with_cot, pre = VAR[vkey]
        out = REPO_ROOT / "outputs" / "activations" / traj.stem / f"{variant}_{Path(ocfg.hf_id).name}"
        snapshot(out, cfg)
        write_json(out / "meta.json", {"layers": layers, "poolings": ["observer"], "trajectories": str(traj),
                                       "model": ocfg.hf_id})
        w = ShardWriter(out, 200)
        done = w.done_episodes()
        for i, ep in enumerate(eps.itertuples()):
            if ep.episode_id in done:
                continue
            text, marks = episode_text(ep, specs[ep.instance_id], with_cot, pre)
            enc = tok(text, return_offsets_mapping=True, add_special_tokens=False)
            offs = enc["offset_mapping"]
            pos = []
            j = 0
            for m in marks:
                while j + 1 < len(offs) and offs[j + 1][1] <= m:
                    j += 1
                pos.append(j)
            ids = enc["input_ids"]
            if len(ids) > cfg.max_tokens:  # keep causal prefix exactness: truncate the tail only
                ids = ids[:cfg.max_tokens]
                pos = [min(p, cfg.max_tokens - 1) for p in pos]
            with ResidualCapture(blocks, layers, {"observer": ("point", torch.tensor(pos))}) as cap, torch.no_grad():
                model(input_ids=torch.tensor([ids], device=model.device), use_cache=False, logits_to_keep=1)
            w.add(ep.episode_id, [e["event_id"] for e in ep.events],
                  {f"observer.L{l}": cap.out["observer"][l] for l in layers})
            if (i + 1) % 100 == 0:
                print(variant, i + 1, "/", len(eps))
        w.flush()
        print("wrote", out)


if __name__ == "__main__":
    main()
