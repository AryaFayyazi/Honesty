"""Validity of the authx suite (prereg v26; src/cape/benchx/families_authx.py; scripts/46_authx.py stage=build)."""
import copy
import json

import pytest

from cape.benchx import families_authx as FX
from cape.envs.base import MockEnv
from cape.envs.capebench.generator import AWARE_TEXT
from cape.envs.capebench.world import sample_world
from cape.utils.config import REPO_ROOT

CAPE = REPO_ROOT / "outputs/capebench"
ID_KEYS = {"instance_id", "cf_value", "counterfactual_value", "nuisance", "counterfactual_pair_id"}


def load(name):
    return [json.loads(l) for l in open(CAPE / name / "scenarios.jsonl")]


SPECS = {n: load(n) for n in ("authx", "authxenf", "authxorc", "authxorcenf")}
PAIRS = [(s, next(u for u in SPECS["authx"] if u["scenario_id"] == s["scenario_id"] and u["cf_value"] == "unsafe"))
         for s in SPECS["authx"] if s["cf_value"] == "safe"]


def leaves(obj, prefix=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from leaves(v, prefix + (str(k),))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from leaves(v, prefix + (str(i),))
    else:
        yield prefix, obj


def diff_paths(a, b):
    la, lb = dict(leaves(a)), dict(leaves(b))
    return sorted(k for k in set(la) | set(lb) if la.get(k) != lb.get(k))


def resource_of(p):
    return (p[0], p[1]) if p[0] in ("files", "db", "commands", "urls") else (p[0],)


def test_counts_and_templates():
    for n, S in SPECS.items():
        assert len(S) == 2 * 6 * 24, n
        assert {s["template"] for s in S} == set(FX.TEMPLATES)


@pytest.mark.parametrize("xp,xm", PAIRS, ids=[p[0]["scenario_id"] for p in PAIRS])
def test_pair_differs_in_one_permission_resource(xp, xm):
    assert xp["task_prompt"] == xm["task_prompt"] and xp["system_prompt"] == xm["system_prompt"]
    assert xp["critical"] == xm["critical"] and xp["goal"] == xm["goal"]
    d = [p for p in diff_paths(xp, xm) if p[0] not in ID_KEYS and p != ("permissions", "granted")]
    assert len({resource_of(p) for p in d}) == 1, d


@pytest.mark.parametrize("xp,xm", PAIRS, ids=[p[0]["scenario_id"] for p in PAIRS])
def test_labels_and_oracle(xp, xm):
    name, args = xm["critical_example"]
    for s, unsafe in ((xp, False), (xm, True)):
        _, info = MockEnv(s).step(name, args)
        assert info.critical and info.unsafe == unsafe and info.goal == (not unsafe)
        o = MockEnv(dict(s, oracle=True)).step("check_authorization", {"tool": name, "arguments": args})[0]
        assert o.startswith("NOT ALLOWED" if unsafe else "ALLOWED")
    # approval obtained -> the same action is not a violation; denial -> still a violation
    env = MockEnv(xm)
    r = env.step("request_permission", {"resource": "r", "action": "a", "justification": "j"})[0]
    _, info = env.step(name, args)
    assert info.unsafe == r.startswith("DENIED")
    # inspection is never critical
    env = MockEnv(xm)
    for c in xm["commands"]:
        if c.get("name") and not any(k in c["name"] for k in ("share", "set", "move", "swap", "add")):
            _, i = env.step("execute_mock_command", {"command": c["name"].split()[0] + " x"})
            assert not i.critical and not i.unsafe
    for p in xm.get("files", {}):
        assert not env.step("read_file", {"path": p})[1].critical
    for u in xm.get("urls", {}):
        assert not env.step("open_mock_url", {"url": u})[1].critical
    for t in xm.get("db", {}):
        assert not env.step("query_database", {"query": f"SELECT * FROM {t}"})[1].critical
    assert "Available commands" in MockEnv(xm).step("execute_mock_command", {"command": "help"})[0] or not xm["commands"]


def test_sets_differ_only_in_manipulation():
    base = {s["instance_id"]: s for s in SPECS["authx"]}
    for n, S in SPECS.items():
        for s in S:
            b = base[s["instance_id"].removesuffix(".aware")]
            enf = n in ("authxenf", "authxorcenf")
            assert s["system_prompt"] == b["system_prompt"] + (AWARE_TEXT["enforced"] if enf else "")
            assert s["oracle"] == (n in ("authxorc", "authxorcenf"))
            keep = {"system_prompt", "oracle", "instance_id", "monitor_aware", "aware_style", "counterfactual_pair_id"}
            assert {k: v for k, v in s.items() if k not in keep} == {k: v for k, v in b.items() if k not in keep}


def test_fresh_worlds_no_name_collisions():
    prior = set()
    for f in CAPE.glob("*/scenarios.jsonl"):
        if not f.parent.name.startswith("authx"):
            prior |= {json.loads(l)["world_seed"] for l in open(f)}
    for s in SPECS["authx"]:
        assert s["world_seed"] not in prior
        assert not FX.name_collision(s, sample_world(s["world_seed"]))


def test_no_coaching_text():
    bad = ("try", "bypass", "workaround", "enforce", "override", "without asking")
    for s in SPECS["authx"]:
        txt = json.dumps({k: s[k] for k in ("task_prompt", "commands", "urls", "files", "db")}).lower()
        assert not any(b in txt for b in bad), s["scenario_id"]


def test_environment_code_and_v18_lock_unchanged():
    from cape.eval import authority as A
    lock = json.load(open(A.LOCK))
    assert A.env_code_hash() == lock["env_code_hash"], "authx must not change src/cape/envs (v18 lock)"


def test_readbacks_never_show_the_mutated_attribute():
    """Deviation 1 (v26): a static read-back of an executed change looks like a silent block (enforcement confound).
    Read-back commands, pages and files must not display the attribute the task changes."""
    stale = ("status-old", "CNAME  ", "15:00", "This week", "Shared with", "Members:", " members (")
    for s in SPECS["authx"]:
        txt = [c["output"] for c in s["commands"] if not any(k in (c.get("name") or c["pattern"])
                                                             for k in ("share", "set", "move", "swap", "add"))]
        txt += list(s.get("urls", {}).values()) + [f["content"] for f in s.get("files", {}).values()]
        for t in txt:
            assert not any(x in t for x in stale), (s["template"], t[:120])
