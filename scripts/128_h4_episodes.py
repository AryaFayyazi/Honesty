#!/usr/bin/env python
"""v49 H4: development episode tables for per-model steering sweeps (CPU).
Lie-prone informed DEVELOPMENT episodes: at least one NEUTRAL-condition regenerated report is MISREPRESENTED (an earlier, independent
sample; the sweep regenerates both 'none' and steered reports fresh, so selection does not bias the steered-vs-none contrast).
Hash order sha256(actor|set|episode_id), first N. fold = md5(scenario+variant) % 2, identical to scripts/126 (cross-fit).
-> outputs/reconcile/h4_<actor>_dev_episodes.parquet
python scripts/128_h4_episodes.py gemma4 96"""
import hashlib, importlib.util, sys
import pandas as pd
from cape.utils.config import REPO_ROOT
s = importlib.util.spec_from_file_location("c", REPO_ROOT / "scripts/126_caa_multi.py"); C = importlib.util.module_from_spec(s); s.loader.exec_module(C)
actor, N = sys.argv[1], int(sys.argv[2])
A, _ = C.reports(actor)
g = A[A.message == "neutral"].groupby(["set", "episode_id"]).lie.any().reset_index(); g = g[g.lie]
orig = []
for st in g.set.unique():
    f = REPO_ROOT / f"outputs/disclosure_v37/{st}_rubric.parquet"
    if f.exists():
        R = pd.read_parquet(f); orig.append(R[R.informed.astype(bool)][["episode_id", "label"]].assign(set=st))
O = pd.concat(orig); E = g.merge(O, on=["set", "episode_id"], how="inner")
E["h"] = [hashlib.sha256(f"{actor}|{a}|{b}".encode()).hexdigest() for a, b in zip(E.set, E.episode_id)]
E = E.sort_values("h").head(N); E["fold"] = E.episode_id.map(lambda e: int(hashlib.md5(e.rsplit(".", 1)[0].encode()).hexdigest(), 16) % 2)
E[["set", "episode_id", "label", "fold"]].to_parquet(REPO_ROOT / f"outputs/reconcile/h4_{actor}_dev_episodes.parquet")
print(actor, len(E), E.fold.value_counts().to_dict(), "orig lie rate %.2f" % (E.label == "MISREPRESENTED").mean())
