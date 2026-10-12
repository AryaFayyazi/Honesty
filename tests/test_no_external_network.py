"""Fail if any agent-facing environment can reach the network, a real filesystem or a subprocess."""
import ast
import socket
import urllib.request
from pathlib import Path

import pytest

from cape.envs.base import TOOLS, MockEnv
from cape.envs.capebench.generator import generate

ENV_DIR = Path(__file__).resolve().parents[1] / "src" / "cape" / "envs"
FORBIDDEN_MODULES = {"socket", "requests", "urllib", "http", "httpx", "aiohttp", "subprocess", "ftplib", "smtplib",
                     "paramiko", "shutil", "pathlib", "os"}
FORBIDDEN_CALLS = {"open", "exec", "eval", "__import__", "compile"}


@pytest.mark.parametrize("path", sorted(ENV_DIR.rglob("*.py")), ids=lambda p: p.name)
def test_env_sources_have_no_network_or_io(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert a.name.split(".")[0] not in FORBIDDEN_MODULES, f"{path.name} imports {a.name}"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in FORBIDDEN_MODULES, f"{path.name} imports {node.module}"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in FORBIDDEN_CALLS, f"{path.name} calls {node.func.id}()"


def test_no_generic_network_tool():
    names = {t["function"]["name"] for t in TOOLS}
    assert not names & {"http_request", "fetch", "curl", "browse", "shell", "bash", "python"}


PROBES = [("open_mock_url", {"url": "https://example.com"}), ("open_mock_url", {"url": "http://169.254.169.254/"}),
          ("execute_mock_command", {"command": "curl https://example.com"}),
          ("execute_mock_command", {"command": "ssh prod-db 'rm -rf /'"}),
          ("execute_mock_command", {"command": "python -c 'import socket'"}),
          ("send_message", {"recipient": "someone@real-company.com", "subject": "s", "body": "b"}),
          ("upload_artifact", {"path": "/etc/passwd", "destination": "s3://real-bucket"}),
          ("read_file", {"path": "/etc/passwd"}), ("write_file", {"path": "/tmp/x", "content": "y"})]


def test_all_scenarios_fully_sandboxed(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise AssertionError("network access attempted from the agent sandbox")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.chdir(tmp_path)
    for spec in generate(num_base=24, num_paraphrases=1, seed=3):
        env = MockEnv(spec)
        for name, args in PROBES:
            obs, _ = env.step(name, args)
            assert isinstance(obs, str)
        # mock "real" resources resolve only to in-memory state
        assert env.step("read_file", {"path": "/etc/passwd"})[0].startswith("Error: file not found")
        assert env.step("open_mock_url", {"url": "https://example.com"})[0].startswith("404")
    assert list(tmp_path.iterdir()) == [], "environment wrote to the real filesystem"
