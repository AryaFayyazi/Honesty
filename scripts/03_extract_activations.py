#!/usr/bin/env python
"""Replay saved rollouts through HF Transformers and store event-boundary activations.

python scripts/03_extract_activations.py model=Qwen/Qwen3.8-27B trajectories=outputs/rollouts/pilot.parquet \
    layers='[15,31,47,63]' pooling=pre_action_last

pooling may be a single name, a list, or "all". layers may be a list or "all" (all 64 blocks).
Optional: out=<dir> check_episodes=8 (replay-equivalence check vs vLLM logprobs on the first N episodes).
Resumable: episodes already present in the output shards are skipped.
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from omegaconf import OmegaConf

from cape.activations.event_pooling import ALL_POOLINGS
from cape.activations.replay import compare_logprobs, replay_episode
from cape.activations.storage import ShardWriter
from cape.models.load import discover_transformer_blocks, load_hf_model
from cape.utils.config import REPO_ROOT, load_config
from cape.utils.repro import snapshot, write_json

DEFAULTS = OmegaConf.create({"trajectories": "outputs/rollouts/pilot.parquet", "layers": [15, 31, 47, 63],
                             "pooling": "pre_action_last", "out": None, "check_episodes": 8, "shard_size": 100})


def main():
    cfg = OmegaConf.merge(DEFAULTS, load_config(None))
    mcfg = cfg.model
    traj = REPO_ROOT / cfg.trajectories if not str(cfg.trajectories).startswith("/") else Path(cfg.trajectories)
    stem = traj.stem
    layers = list(range(mcfg.num_layers)) if cfg.layers == "all" else [int(l) for l in cfg.layers]
    pools = ALL_POOLINGS if cfg.pooling == "all" else ([cfg.pooling] if isinstance(cfg.pooling, str) else list(cfg.pooling))
    out = Path(cfg.out) if cfg.out else REPO_ROOT / "outputs" / "activations" / stem / (
        f"L{'all' if cfg.layers == 'all' else '-'.join(map(str, layers))}_{cfg.pooling if isinstance(cfg.pooling, str) else 'multi'}")
    out.mkdir(parents=True, exist_ok=True)
    snapshot(out, cfg, model_revision=mcfg.get("revision"))
    write_json(out / "meta.json", {"layers": layers, "poolings": pools, "trajectories": str(traj),
                                   "model": mcfg.name, "revision": mcfg.get("revision")})

    eps = pd.read_parquet(traj)
    toks = pd.read_parquet(str(traj).replace(".parquet", "_tokens.parquet")).set_index("episode_id")
    model = load_hf_model(mcfg)
    blocks, _ = discover_transformer_blocks(model, expected=mcfg.num_layers)
    w = ShardWriter(out, cfg.shard_size)
    done = w.done_episodes()
    checks = []
    t0 = time.time()
    for i, ep in enumerate(eps.itertuples()):
        if ep.episode_id in done:
            continue
        events = list(ep.events)
        tk = toks.loc[ep.episode_id]
        ids = list(tk.input_ids)
        check = None
        if i < cfg.check_episodes:
            gm = np.asarray(tk.gen_mask)
            check = [int(p) for p in np.nonzero(gm)[0] if p > 0]
        acts, lp = replay_episode(model, blocks, ids, events, layers, pools, check_positions=check)
        if lp is not None:
            ref = np.asarray(tk.logprobs, dtype=np.float64)[check]
            c = compare_logprobs(ref, lp)
            c["episode_id"] = ep.episode_id
            checks.append(c)
            print("replay check", json.dumps(c))
        w.add(ep.episode_id, [e["event_id"] for e in events],
              {f"{p}.L{l}": acts[p][l] for p in pools for l in layers})
        if (i + 1) % 20 == 0:
            print(f"{i + 1}/{len(eps)} episodes, {time.time() - t0:.0f}s, "
                  f"mem {torch.cuda.max_memory_allocated() / 1e9:.1f}GB")
    w.flush()
    if checks:
        df = pd.DataFrame(checks)
        write_json(out / "replay_check.json", {"episodes": checks,
                                               "mean_abs": float(df.mean_abs.mean()), "p99_abs": float(df.p99_abs.max()),
                                               "min_corr": float(df["corr"].min())})
    print("done ->", out, f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
