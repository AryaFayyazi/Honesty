#!/usr/bin/env python
"""Phase-0 smoke test (GPU).

python scripts/00_smoke_model.py model=Qwen/Qwen3.8-27B dtype=bfloat16

1. load tokenizer  2. load model  3. print architecture  4. verify 64 language layers  5. generate a harmless tool
call  6. register temporary hooks  7. record selected hidden states  8. print shapes. Also records versions.
"""
import json
import time

import torch

from cape.activations.hooks import ResidualCapture
from cape.agents.actor import ChatFormatter
from cape.agents.tool_parser import parse_tool_call
from cape.models.load import discover_transformer_blocks, load_hf_model, load_tokenizer, model_path, text_config
from cape.utils.config import load_config
from cape.utils.repro import env_metadata, make_run_dir, snapshot, write_json


def main():
    cfg = load_config(None)
    mcfg = cfg.model
    run = make_run_dir("smoke")
    snapshot(run, cfg, model_revision=mcfg.get("revision"))
    print(json.dumps(env_metadata(mcfg.get("revision")), indent=2))
    t0 = time.time()
    tok = load_tokenizer(mcfg)
    print("[1] tokenizer:", type(tok).__name__, "vocab", len(tok))
    model = load_hf_model(mcfg, dtype=cfg.get("dtype", "bfloat16"))
    print(f"[2] model loaded in {time.time() - t0:.0f}s:", type(model).__name__,
          f"{sum(p.numel() for p in model.parameters()) / 1e9:.2f}B params")
    tc = text_config(model)
    print("[3] text config: hidden", tc.hidden_size, "layers", tc.num_hidden_layers)
    blocks, types = discover_transformer_blocks(model, expected=mcfg.get("num_layers"))
    full = [i for i, t in enumerate(types) if t == "full_attention"]
    print(f"[4] {len(blocks)} language layers discovered. block type: {type(blocks[0]).__name__}")
    print("    full-attention layers:", full)
    assert full == list(mcfg.full_attention_layers), "full-attention indices differ from config"

    fmt = ChatFormatter(tok, enable_thinking=True, reasoning_effort="low")
    ids = fmt.initial_ids("You are a helpful assistant with file tools.",
                          "Please read the file /docs/readme.txt and tell me what it says.")
    x = torch.tensor([ids], device=model.device)
    with torch.no_grad():
        out = model.generate(x, max_new_tokens=768, do_sample=False, eos_token_id=[fmt.ids.tool_call_end, fmt.ids.im_end])
    gen = out[0, len(ids):].tolist()
    text = tok.decode(gen, skip_special_tokens=False)
    name, args, err = parse_tool_call(text.split("</think>")[-1])
    print("[5] generated:", repr(text[-300:]))
    print("    parsed tool call:", name, args, err)

    layers = list(mcfg.pilot_layers) + list(mcfg.pilot_adjacent_deltanet)
    full_ids = out[0].tolist()
    sp = fmt.split_generation(gen)
    pos = torch.tensor([len(ids) - 1, len(ids) + (sp["action_start"] or len(gen)) - 1])
    cap = ResidualCapture(blocks, layers, {"pts": ("point", pos), "win": ("window", [(len(ids) - 8, len(ids) - 1)])})
    with cap, torch.no_grad():
        model(torch.tensor([full_ids], device=model.device), use_cache=False)
    print("[6-7] hooks registered on layers", layers)
    shapes = {f"{k}/L{l}": list(v.shape) for k, d in cap.out.items() for l, v in d.items()}
    print("[8] shapes:", shapes)
    assert all(s[-1] == tc.hidden_size for s in shapes.values())
    assert not any(b._forward_hooks for b in blocks), "hooks leaked"
    write_json(run / "metrics.json", {"n_layers": len(blocks), "full_attention_layers": full, "tool": name,
                                      "args": args, "parse_error": err, "shapes": shapes,
                                      "model_path": model_path(mcfg)})
    print("SMOKE OK ->", run)


if __name__ == "__main__":
    main()
