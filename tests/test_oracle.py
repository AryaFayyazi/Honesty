"""Truthful authorization oracle (src/cape/envs/base.py check_authorization; docs/preregistration_v19.md)."""
import json

import pandas as pd
import pytest

from cape.envs.base import TOOLS, MockEnv, tools_for
from cape.utils.config import REPO_ROOT

V2 = REPO_ROOT / "outputs/rollouts/v2fresh_minus.parquet"


def _specs(bench):
    return {json.loads(l)["instance_id"]: json.loads(l) for l in open(REPO_ROOT / f"outputs/capebench/{bench}/scenarios.jsonl")}


@pytest.mark.skipif(not V2.exists(), reason="no v2 rollouts")
def test_existing_episodes_replay_identically():
    """Without the oracle flag, recorded actions give the same observations and labels as at rollout time."""
    specs = _specs("v2fresh")
    eps = pd.read_parquet(V2).sample(300, random_state=0)
    for ep in eps.itertuples():
        env = MockEnv(specs[ep.instance_id])
        for e in ep.events:
            if not e["is_tool_call"] or e["parse_error"] is not None:
                continue
            args = json.loads(e["args_json"]) if e["args_json"] else {}
            obs, info = env.step(e["tool"], args)
            # known, documented change after v2 was recorded: cluster-info became target-aware (labels unchanged)
            if not str(args.get("command", "")).startswith("cluster-info"):
                assert obs == e["tool_result"], (ep.episode_id, e["event_id"])
            assert info.unsafe == e["unsafe_action"] and info.critical == e["critical"]


def test_oracle_only_when_flagged():
    s = next(iter(_specs("v2fresh").values()))
    assert tools_for(s) == TOOLS
    obs, info = MockEnv(s).step("check_authorization", {"tool": "read_file", "arguments": {"path": "/x"}})
    assert info.error and obs.startswith("Error: unknown tool")


def test_oracle_truthful_and_side_effect_free():
    specs = _specs("v2fresh")
    n = 0
    for s in specs.values():
        if s["nuisance"] or not s["critical_example"]:
            continue
        tool, args = s["critical_example"][0], s["critical_example"][1]
        s = dict(s, oracle=True)
        env = MockEnv(s)
        before = json.dumps(env.state, sort_keys=True)
        obs, info = env.step("check_authorization", {"tool": tool, "arguments": args})
        assert json.dumps(env.state, sort_keys=True) == before and not info.unsafe and not info.critical
        _, real = MockEnv(s).step(tool, args)  # what would actually happen
        assert obs.startswith("NOT ALLOWED") == real.unsafe, (s["instance_id"], obs)
        n += 1
    assert n > 100


def test_oracle_reflects_approval():
    specs = _specs("v2fresh")
    s = next(v for v in specs.values() if v["cf_value"] == "unsafe" and not v["nuisance"] and
             v["permissions"].get("on_request") == "approved" and v["template"] == "auth_repo_access")
    s = dict(s, oracle=True)
    env = MockEnv(s)
    tool, args = s["critical_example"][0], s["critical_example"][1]
    assert env.step("check_authorization", {"tool": tool, "arguments": args})[0].startswith("NOT ALLOWED")
    env.step("request_permission", {"resource": "r", "action": "a", "justification": "j"})
    assert env.step("check_authorization", {"tool": tool, "arguments": args})[0].startswith("ALLOWED")


def test_default_oracle_unchanged_on_v19_specs():
    """oracle=True (v19) answers exactly as before the dryrun mode existed: policy labels only."""
    specs = _specs("v19orc")
    ci = next(s for s in specs.values() if s["template"] == "con_ci_green" and s["cf_value"] == "unsafe"
              and not s["nuisance"])
    src = next(p for p, f in ci["files"].items() if f["meta"].get("writable") == "no")
    obs, _ = MockEnv(ci).step("check_authorization", {"tool": "write_file", "arguments": {"path": src, "content": "x"}})
    assert obs.startswith("ALLOWED")  # the documented v19 limitation


def test_dryrun_oracle_reports_system_rejections():
    specs = _specs("v2fresh")
    ci = next(s for s in specs.values() if s["template"] == "con_ci_green" and s["cf_value"] == "unsafe"
              and not s["nuisance"])
    src = next(p for p, f in ci["files"].items() if f["meta"].get("writable") == "no")
    s = dict(ci, oracle="dryrun")
    obs, _ = MockEnv(s).step("check_authorization", {"tool": "write_file", "arguments": {"path": src, "content": "x"}})
    assert obs.startswith("NOT ALLOWED") and "read-only" in obs
    # authorized side: the same file is writable -> ALLOWED
    plus = dict(next(v for v in specs.values() if v["instance_id"] == ci["instance_id"].replace(".unsafe", ".safe")),
                oracle="dryrun")
    obs, _ = MockEnv(plus).step("check_authorization", {"tool": "write_file", "arguments": {"path": src, "content": "x"}})
    assert obs.startswith("ALLOWED")
    # policy violations are still NOT ALLOWED, and benign failures (missing file) are not access errors
    test = next(p for p in ci["files"] if p.startswith("/repo/tests/"))
    assert MockEnv(s).step("check_authorization", {"tool": "write_file", "arguments": {"path": test, "content": "x"}})[0].startswith("NOT ALLOWED")
    assert MockEnv(s).step("check_authorization", {"tool": "read_file", "arguments": {"path": "/nope"}})[0].startswith("ALLOWED")


def test_dryrun_identical_to_default_when_no_access_error():
    """On every critical example, dryrun and default agree unless the call hits an access error."""
    import re as _re
    from cape.envs.base import ACCESS_ERROR_RE
    n = 0
    for s in _specs("v2fresh").values():
        if s["nuisance"]:
            continue
        tool, args = s["critical_example"]
        a = MockEnv(dict(s, oracle=True)).step("check_authorization", {"tool": tool, "arguments": args})[0]
        b = MockEnv(dict(s, oracle="dryrun")).step("check_authorization", {"tool": tool, "arguments": args})[0]
        real = MockEnv(s).step(tool, args)[0]
        assert a == b or (ACCESS_ERROR_RE.search(real.split("\n")[0]) and b.startswith("NOT ALLOWED")), s["instance_id"]
        n += 1
    assert n > 100
