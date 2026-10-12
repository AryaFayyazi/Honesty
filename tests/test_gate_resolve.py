"""The gate's resolved-effect view must never read label matchers / counterfactual fields (non-circularity)."""
import json

from cape.envs.base import MockEnv
from cape.guard.resolve import FORBIDDEN_SPEC_KEYS, resolve_effect
from cape.utils.config import REPO_ROOT


class Guarded(dict):
    def __getitem__(self, k):
        assert k not in FORBIDDEN_SPEC_KEYS, f"resolver read forbidden key {k}"
        return super().__getitem__(k)

    def get(self, k, d=None):
        assert k not in FORBIDDEN_SPEC_KEYS, f"resolver read forbidden key {k}"
        return super().get(k, d)


def test_resolver_reads_no_label_fields():
    specs = [json.loads(l) for l in open(REPO_ROOT / "outputs/capebench/v2fresh/scenarios.jsonl")][:120]
    calls = [("write_file", {"path": "/repo/tests/conftest.py", "content": "x"}),
             ("send_message", {"recipient": "a@ext.example", "subject": "s", "body": "/data/exports/x.csv"}),
             ("query_database", {"query": "delete from tickets where id = 3"}),
             ("execute_mock_command", {"command": "restart-service notify --host h"}),
             ("upload_artifact", {"path": "/p", "destination": "vendor"}), ("delete_record", {"table": "t", "record_id": "1"})]
    for s in specs:
        env = MockEnv(s)
        env.spec = Guarded(s)
        for n, a in calls:
            assert resolve_effect(env, n, a, [])
            assert resolve_effect(env, n, a, [], identity=True)
            assert resolve_effect(env, n, a, [], authz=True)
