import os

import pytest

os.environ.setdefault("HF_HUB_CACHE", "/data/models")
os.environ.setdefault("HF_HUB_OFFLINE", "1")


def _cuda():
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


@pytest.fixture(scope="session")
def qwen():
    if not _cuda():
        pytest.skip("GPU test: run via `sbatch -J tests slurm/run.sh pytest -m gpu ...`")
    from cape.models.load import discover_transformer_blocks, load_hf_model, load_tokenizer
    from cape.utils.config import resolve_model
    cfg = resolve_model("Qwen/Qwen3.8-27B")
    model = load_hf_model(cfg)
    blocks, types = discover_transformer_blocks(model, expected=cfg.num_layers)
    return {"cfg": cfg, "model": model, "tok": load_tokenizer(cfg), "blocks": blocks, "types": types}
