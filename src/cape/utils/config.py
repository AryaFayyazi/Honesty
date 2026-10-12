"""Config handling: YAML defaults + hydra-style ``key=value`` CLI overrides (OmegaConf)."""
from __future__ import annotations

import sys
from pathlib import Path

from omegaconf import DictConfig, OmegaConf

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "configs"


def load_config(default_yaml: str | None = None, argv: list[str] | None = None) -> DictConfig:
    """Load ``configs/<default_yaml>`` and merge dotted ``key=value`` overrides from argv.

    ``model=Qwen/Qwen3.8-27B`` resolves to ``configs/models/<alias>.yaml`` when such an alias exists,
    otherwise it is kept as a raw string (HF repo id or path).
    """
    argv = sys.argv[1:] if argv is None else argv
    cfg = OmegaConf.create({})
    if default_yaml:
        cfg = OmegaConf.merge(cfg, OmegaConf.load(CONFIG_DIR / default_yaml))
    overrides = [a for a in argv if "=" in a and not a.startswith("--")]
    cli = OmegaConf.from_dotlist(overrides)
    cfg = OmegaConf.merge(cfg, cli)
    if "model" in cfg and isinstance(cfg.model, str):
        cfg.model = resolve_model(cfg.model)
    return cfg


MODEL_ALIASES = {
    "Qwen/Qwen3.8-27B": "qwen38_27b.yaml",
    "qwen38_27b": "qwen38_27b.yaml",
    "openai/gpt-oss-20b": "gpt_oss_20b.yaml",
    "gpt_oss_20b": "gpt_oss_20b.yaml",
    "openai/gpt-oss-120b": "gpt_oss_120b.yaml",
}


def resolve_model(name: str) -> DictConfig:
    if name in MODEL_ALIASES:
        return OmegaConf.load(CONFIG_DIR / "models" / MODEL_ALIASES[name])
    if (CONFIG_DIR / "models" / f"{name}.yaml").exists():  # e.g. fine-tuned checkpoints qwen38_27b_ei<k>
        return OmegaConf.load(CONFIG_DIR / "models" / f"{name}.yaml")
    return OmegaConf.create({"name": name, "hf_id": name})
