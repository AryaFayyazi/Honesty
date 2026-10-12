"""Authority-calibration evaluation suite (src/cape/eval/authority.py, scripts/33_authority_eval.py)."""
import json

import numpy as np
import pandas as pd
import pytest

from cape.eval import authority as A
from cape.utils.config import REPO_ROOT

pytestmark = pytest.mark.skipif(not A.LOCK.exists(), reason="suite not built")


def test_lock_holds():
    A.check_lock()


def test_conditions_differ_only_in_manipulated_text():
    for b in A.BLOCKS:
        ref = {s["instance_id"]: s for s in A.load_specs(b, "base")}
        for c in A.CONDITIONS:
            if c == "base":
                continue
            specs = A.load_specs(b, c)
            assert len(specs) == len(ref)
            for s in specs:
                r = ref[s["instance_id"].replace(".aware", "")]
                for k in ("files", "db", "commands", "permissions", "critical", "goal", "world_seed", "template"):
                    assert s[k] == r[k], (c, k)
                if c in ("enforced", "responsibility"):
                    assert s["task_prompt"] == r["task_prompt"] and s["system_prompt"].startswith(r["system_prompt"])
                    assert s["system_prompt"] != r["system_prompt"]
                else:
                    assert s["system_prompt"] == r["system_prompt"] and r["task_prompt"] in s["task_prompt"]
                    assert s["task_prompt"] != r["task_prompt"]


def test_pairs_differ_only_in_authority_and_blocks_disjoint():
    seen = {}
    for b in A.BLOCKS:
        S = A.load_specs(b, "base")
        by = {}
        for s in S:
            by.setdefault(s["counterfactual_pair_id"], {})[s["cf_value"]] = s
        for pid, d in by.items():
            assert set(d) == {"safe", "unsafe"}
            assert d["safe"]["task_prompt"] == d["unsafe"]["task_prompt"]
            assert d["safe"]["system_prompt"] == d["unsafe"]["system_prompt"]
        seen[b] = {s["world_seed"] for s in S}
    assert not (seen["main"] & seen["ho"])


def test_included_worlds_unseen_and_unique():
    """Every scenario that enters analysis has world content unseen in any prior benchmark and unique in the suite."""
    inc = [A.world_key(s) for b in A.BLOCKS for s in A.load_specs(b, "base") if not s["excluded"]]
    assert len(inc) == len(set(inc))
    for p in (REPO_ROOT / "outputs/capebench").glob("*/scenarios.jsonl"):
        if "authority_eval" in str(p):
            continue
        assert not (set(inc) & {A.world_key(json.loads(l)) for l in open(p)}), p


def test_exclusion_consistent_across_conditions_and_ids_unique():
    for b in A.BLOCKS:
        ex = {c: {s["scenario_id"]: s["excluded"] for s in A.load_specs(b, c)} for c in A.CONDITIONS}
        assert all(ex[c] == ex["base"] for c in ex)
    ids = [{s["scenario_id"] for s in A.load_specs(b, "base")} for b in A.BLOCKS]
    assert not (ids[0] & ids[1])


def test_identity_collision_rule_reproduces_validity_file():
    col = json.load(open(REPO_ROOT / "results/validity/identity_collisions.json"))
    for b, ids in col.items():
        specs = [json.loads(l) for l in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl")]
        got = {s["scenario_id"] for s in specs if s["cf_value"] == "unsafe" and not s["nuisance"]
               and A.identity_collision(s)}
        assert got == set(ids), b


def test_paired_test_superiority_and_noninferiority():
    idx = pd.MultiIndex.from_tuples([("main", f"s{i}") for i in range(200)])
    rng = np.random.default_rng(1)
    ref = pd.Series(rng.uniform(0.2, 0.4, 200), idx)
    better = ref - 0.10 + rng.normal(0, 0.05, 200)
    same = ref + rng.normal(0, 0.05, 200)
    assert A.paired_test(better, ref, 2000, 0, "less")["p_one_sided"] < 0.01
    assert A.paired_test(same, ref, 2000, 0, "less")["p_one_sided"] > 0.05
    # non-inferiority with margin 0.05: a 2-point drop passes, an 8-point drop fails
    assert A.paired_test(ref - 0.02 + rng.normal(0, 0.02, 200), ref, 2000, 0, "greater", 0.05)["p_one_sided"] < 0.01
    assert A.paired_test(ref - 0.08 + rng.normal(0, 0.02, 200), ref, 2000, 0, "greater", 0.05)["p_one_sided"] > 0.5


def _ep(eid, sid, cf, seed, unsafe, crit, perm=None, reveal=0, tmpl="con_ci_green"):
    ev = []
    if perm:
        ev.append({"event_id": 0, "tool": "request_permission", "tool_result": perm, "unsafe_action": False,
                   "reasoning_text": ""})
    ev.append({"event_id": len(ev), "tool": "run_command", "tool_result": "ok", "unsafe_action": unsafe,
               "reasoning_text": "let me just try it" if unsafe else ""})
    tu = len(ev) - 1 if unsafe else None
    return {"episode_id": eid, "scenario_id": sid, "template": tmpl, "cf_value": cf, "seed": seed,
            "status": "final_answer", "unsafe_episode": unsafe, "first_unsafe_event": tu, "reveal_event": reveal - 1,
            "critical_done": crit, "success": crit and not unsafe, "escalated": bool(perm), "n_parse_errors": 0,
            "events": ev}


def test_endpoints_on_synthetic_run():
    eps = pd.DataFrame([
        _ep("a1", "s1", "unsafe", 0, True, True, perm="DENIED by x"),   # denial override, informed
        _ep("a2", "s1", "unsafe", 1, False, False, perm="DENIED by x"),
        _ep("a3", "s1", "safe", 0, False, True),
        _ep("b1", "s2", "unsafe", 0, True, True),                       # unasked violation
        _ep("b2", "s2", "unsafe", 1, True, True),
        _ep("b3", "s2", "safe", 0, False, False),                       # over-cautious under authorization
    ])
    T = A.episode_table(eps).assign(block="main", cond="base", heldout=False)
    v = A.endpoint(T, "viol_train_tmpl")
    assert v.loc[("main", "s1")] == 0.5 and v.loc[("main", "s2")] == 1.0
    s = A.endpoint(T, "authority_sensitivity")
    assert s.loc[("main", "s1")] == 0.5 and s.loc[("main", "s2")] == -1.0
    assert A.endpoint(T, "denial_override").loc[("main", "s1")] == 0.5
    assert A.endpoint(T, "unasked_viol").loc[("main", "s2")] == 1.0
    assert T.set_index("episode_id").loc["a1", "probe"] == 1 and T.set_index("episode_id").loc["a1", "iv"] == 1


def test_contamination_check_flags_suite_world(tmp_path):
    import subprocess
    import sys
    s = A.load_specs("main", "base")[0]
    p = tmp_path / "train.jsonl"
    p.write_text(json.dumps({"world_seed": s["world_seed"], "prompt": "x"}) + "\n")
    r = subprocess.run([sys.executable, str(REPO_ROOT / "scripts/33_authority_eval.py"), "stage=contam", f"train={p}"],
                       capture_output=True, text=True, cwd=REPO_ROOT)
    assert r.returncode != 0 and '"world_seed_overlap": 1' in r.stdout
    p.write_text(json.dumps({"world_seed": 1, "prompt": "unrelated"}) + "\n")
    r = subprocess.run([sys.executable, str(REPO_ROOT / "scripts/33_authority_eval.py"), "stage=contam", f"train={p}"],
                       capture_output=True, text=True, cwd=REPO_ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


def _synthetic_run(root, name, p_viol, p_act, seed, gap_enf=0.0):
    """Episodes for every core cell / included spec / seed with Bernoulli outcomes (scenario difficulty shared)."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    rng = np.random.default_rng(seed)
    (root / name).mkdir(parents=True)
    for b, c, cf in A.TIERS["core"]:
        recs = []
        for s in A.load_specs(b, c):
            if s["cf_value"] != cf:
                continue
            diff = (int(s["world_seed"]) % 7) / 6  # fixed per scenario, shared across runs
            for sd in A.SEEDS[cf]:
                if cf == "unsafe":
                    pv = min(1, p_viol * (0.5 + diff) + (gap_enf if c == "enforced" else 0))
                    u = bool(rng.random() < pv)
                    recs.append(_ep(f"{s['instance_id']}.s{sd}", s["scenario_id"], cf, sd, u, u, tmpl=s["template"]))
                else:
                    a = bool(rng.random() < p_act)
                    recs.append(_ep(f"{s['instance_id']}.s{sd}", s["scenario_id"], cf, sd, False, a, tmpl=s["template"]))
        pq.write_table(pa.Table.from_pylist(recs), root / name / f"{A.cell_name(b, c, cf)}.parquet")


def test_compare_end_to_end(tmp_path):
    _synthetic_run(tmp_path, "ref", 0.12, 0.99, 0, gap_enf=0.08)
    _synthetic_run(tmp_path, "fix", 0.03, 0.985, 1, gap_enf=0.0)     # real fix: fewer violations, no reliance
    _synthetic_run(tmp_path, "null", 0.12, 0.99, 2, gap_enf=0.08)    # same model, new samples
    _synthetic_run(tmp_path, "refuser", 0.0, 0.70, 3)                # safety bought by refusing authorized work
    R = A.load_run("ref", A.TIERS["core"], tmp_path)
    t = A.compare(A.load_run("fix", A.TIERS["core"], tmp_path), R, 2000)
    assert t["viol_train_tmpl"]["reject"] and t["viol_heldout_tmpl"]["reject"] and t["gap_enforced"]["reject"]
    assert t["act_ok_plus"]["pass"] and t["parse_err_all"]["pass"]
    t = A.compare(A.load_run("null", A.TIERS["core"], tmp_path), R, 2000)
    assert not any(t[k].get("reject") for k in ("viol_train_tmpl", "viol_heldout_tmpl", "gap_enforced", "gap_assert"))
    assert t["act_ok_plus"]["pass"]
    t = A.compare(A.load_run("refuser", A.TIERS["core"], tmp_path), R, 2000)
    assert t["viol_train_tmpl"]["reject"] and not t["act_ok_plus"]["pass"]  # caught by the utility gate
    pw = A.power(R)
    assert set(pw) >= {"viol_train_tmpl", "viol_heldout_tmpl", "extend"}
