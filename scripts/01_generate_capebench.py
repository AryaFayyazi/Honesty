#!/usr/bin/env python
"""Generate CAPE-Bench matched counterfactual scenarios.

python scripts/01_generate_capebench.py --num-base-scenarios 50 --num-paraphrases 2 --seed 0 [--name pilot]
"""
import argparse
import collections
import json
from pathlib import Path

import pandas as pd

from cape.envs.capebench.generator import generate
from cape.utils.config import REPO_ROOT
from cape.utils.repro import snapshot, write_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--num-base-scenarios", type=int, default=50)
    ap.add_argument("--num-paraphrases", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--name", default="pilot")
    ap.add_argument("--monitor-aware", action="store_true")
    ap.add_argument("--aware-style", default="hidden", choices=["hidden", "reasoning", "internal", "obfuscate", "responsibility", "enforced"])
    ap.add_argument("--policy-style", default="explicit", choices=["explicit", "handbook"])
    ap.add_argument("--escalation", default="normal", choices=["normal", "unavailable"])
    ap.add_argument("--pressure", default="none", choices=["none", "high"])
    ap.add_argument("--suite", default="core", choices=["core", "lh", "scope"])
    ap.add_argument("--request-style", default="", choices=["", "assert", "conditional"])
    ap.add_argument("--templates", default=None, help="comma-separated template names to keep (after generation)")
    ap.add_argument("--variant", default="", help="suffix appended to scenario ids (to combine configurations)")
    ap.add_argument("--out", default=str(REPO_ROOT / "outputs" / "capebench"))
    a = ap.parse_args()

    specs = generate(a.num_base_scenarios, a.num_paraphrases, a.seed, nuisance=True, monitor_aware=a.monitor_aware,
                     policy_style=a.policy_style, escalation=a.escalation, pressure=a.pressure, variant=a.variant,
                     suite=a.suite, aware_style=a.aware_style, request_style=a.request_style)
    if a.templates:
        keep = set(a.templates.split(","))
        specs = [s for s in specs if s["template"] in keep]
        assert specs, "no specs left after template filter"
    out = Path(a.out) / a.name
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "scenarios.jsonl", "w") as f:
        for s in specs:
            f.write(json.dumps(s) + "\n")
    rows = []
    by_pair = collections.defaultdict(dict)
    for s in specs:
        if not s["nuisance"]:
            by_pair[s["counterfactual_pair_id"]][s["cf_value"]] = s["instance_id"]
    for pid, d in by_pair.items():
        base = next(s for s in specs if s["counterfactual_pair_id"] == pid)
        rows.append({"counterfactual_pair_id": pid, "scenario_id": base["scenario_id"],
                     "scenario_family": base["scenario_family"], "template": base["template"],
                     "surface_template": base["surface_template"], "safe_instance": d["safe"],
                     "unsafe_instance": d["unsafe"], "nuisance_instance": d["unsafe"] + ".nuis"})
    pairs = pd.DataFrame(rows)
    pairs.to_parquet(out / "pairs.parquet")
    if a.name == "pilot":  # alias referenced by the brief's patching command (never overwritten by other benches)
        pairs.to_parquet(Path(a.out) / "test_pairs.parquet")
    manifest = {"n_specs": len(specs), "n_pairs": len(pairs), "n_base": a.num_base_scenarios,
                "families": dict(collections.Counter(p for p in pairs.scenario_family)), "seed": a.seed,
                "suite": a.suite, "policy_style": a.policy_style, "escalation": a.escalation, "pressure": a.pressure}
    write_json(out / "manifest.json", manifest)
    snapshot(out, vars(a), seed=a.seed)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
