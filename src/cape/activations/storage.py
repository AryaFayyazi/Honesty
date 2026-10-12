"""Sharded safetensors activation storage (hidden vectors never go into Parquet).

Layout:  <dir>/shard_00000.safetensors   tensors "<pooling>.L<layer>" -> [n_events_in_shard, d] fp16
         <dir>/shard_00000.index.parquet episode_id, event_id, row
         <dir>/meta.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from safetensors.numpy import load_file
from safetensors.torch import save_file


class ShardWriter:
    def __init__(self, out_dir, shard_size: int = 100):
        self.dir = Path(out_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.shard_size = shard_size
        self._buf: dict[str, list] = {}
        self._idx: list[dict] = []
        self._n_eps = 0
        self.shard = len(list(self.dir.glob("shard_*.safetensors")))

    def done_episodes(self) -> set:
        s = set()
        for f in self.dir.glob("shard_*.index.parquet"):
            s |= set(pd.read_parquet(f, columns=["episode_id"]).episode_id)
        return s

    def add(self, episode_id: str, event_ids: list[int], tensors: dict[str, torch.Tensor]):
        n0 = len(self._idx)
        for i, e in enumerate(event_ids):
            self._idx.append({"episode_id": episode_id, "event_id": int(e), "row": n0 + i})
        for k, v in tensors.items():
            assert v.shape[0] == len(event_ids), (k, v.shape, len(event_ids))
            self._buf.setdefault(k, []).append(v)
        self._n_eps += 1
        if self._n_eps >= self.shard_size:
            self.flush()

    def flush(self):
        if not self._idx:
            return
        name = f"shard_{self.shard:05d}"
        save_file({k: torch.cat(v).contiguous() for k, v in self._buf.items()}, str(self.dir / f"{name}.safetensors"))
        pd.DataFrame(self._idx).to_parquet(self.dir / f"{name}.index.parquet")
        self.shard += 1
        self._buf, self._idx, self._n_eps = {}, [], 0


def load_activations(act_dir, pooling: str, layers: list[int] | None = None) -> tuple[pd.DataFrame, dict]:
    """Returns (index with global row order, {layer: float32 array [N, d]})."""
    act_dir = Path(act_dir)
    idx_all, arrs = [], {}
    for f in sorted(act_dir.glob("shard_*.safetensors")):
        t = load_file(str(f))
        idx = pd.read_parquet(str(f).replace(".safetensors", ".index.parquet"))
        idx_all.append(idx)
        for k, v in t.items():
            p, l = k.rsplit(".L", 1)
            if p != pooling or (layers is not None and int(l) not in layers):
                continue
            arrs.setdefault(int(l), []).append(v)
    index = pd.concat(idx_all, ignore_index=True)
    index["row"] = np.arange(len(index))
    return index, {l: np.concatenate(v).astype(np.float32) for l, v in sorted(arrs.items())}


def available(act_dir) -> dict:
    meta = Path(act_dir) / "meta.json"
    return json.loads(meta.read_text()) if meta.exists() else {}
