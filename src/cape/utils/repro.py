"""Reproducibility: run directories, config snapshots, environment metadata."""
from __future__ import annotations

import datetime as _dt
import json
import os
import platform
import subprocess
import uuid
from pathlib import Path

from omegaconf import DictConfig, OmegaConf

from cape.utils.config import REPO_ROOT


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return None


def code_hash() -> str:
    """sha256 over tracked source files (the repo is not under version control)."""
    import hashlib
    h = hashlib.sha256()
    for d in ("src", "scripts", "configs"):
        for f in sorted((REPO_ROOT / d).rglob("*")):
            if f.is_file() and f.suffix in (".py", ".yaml", ".sh"):
                h.update(str(f.relative_to(REPO_ROOT)).encode())
                h.update(f.read_bytes())
    return h.hexdigest()[:16]


def env_metadata(model_revision: str | None = None, seed: int | None = None) -> dict:
    meta = {
        "git_commit": _git_commit(),
        "code_hash": code_hash(),
        "model_revision": model_revision,
        "seed": seed,
        "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
        "hostname": platform.node(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "python": platform.python_version(),
    }
    try:
        import torch
        meta["torch"] = torch.__version__
        meta["cuda"] = torch.version.cuda
        meta["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:
        pass
    for mod in ("transformers", "vllm", "sklearn"):
        try:
            meta[mod] = __import__(mod).__version__
        except Exception:
            meta[mod] = None
    return meta


def make_run_dir(experiment: str, base: str | Path = REPO_ROOT / "outputs", run_id: str | None = None) -> Path:
    date = _dt.date.today().isoformat()
    run_id = run_id or (_dt.datetime.now().strftime("%H%M%S") + "-" + uuid.uuid4().hex[:6])
    d = Path(base) / experiment / date / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def snapshot(run_dir: Path, cfg: DictConfig | dict, **meta) -> None:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    if isinstance(cfg, DictConfig):
        OmegaConf.save(cfg, run_dir / "config.yaml")
    else:
        (run_dir / "config.yaml").write_text(json.dumps(cfg, indent=2, default=str))
    (run_dir / "env.json").write_text(json.dumps(env_metadata(**meta), indent=2))


def write_json(path: Path, obj) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, default=str))
