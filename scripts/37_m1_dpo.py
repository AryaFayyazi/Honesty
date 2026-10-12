#!/usr/bin/env python
"""LoRA DPO on the mechanism-1 preference data (docs/preregistration_v21.md; data: scripts/36_m1_pref_data.py).

python scripts/37_m1_dpo.py stage=train [smoke=true] [data=pairs]      # GPU (HF): adapter -> outputs/m1pref/lora_<arm>
python scripts/37_m1_dpo.py stage=merge                                 # GPU: merged checkpoint for the v18 evaluation

Loss per pair (sum log-probs over the sampled turn's tokens only; the context is never trained on):
  L = -log sigmoid(beta * [(pi_c - ref_c) - (pi_r - ref_r)]) + alpha * NLL_c / |c|
Anchor rows (verified authorized x+ turns with no over-refusal sample to pair with): anchor_w * NLL_a / |a|.
Memory: the DPO gradient factorises, d/dθ L = -beta*sigmoid(-z) * (∇pi_c - ∇pi_r), so z is computed with no-grad
forwards and chosen / rejected are back-propagated one sequence at a time with that coefficient (exact gradient,
activations of a single sequence in memory). The reference is the base model (adapter disabled), precomputed.
"""
import hashlib
import json
import time

import numpy as np
import pandas as pd
import torch
from omegaconf import OmegaConf

from cape.train_data import m1pref as M
from cape.utils.config import REPO_ROOT, load_config, resolve_model
from cape.utils.repro import write_json

D = OmegaConf.create({"stage": "train", "data": "pairs", "arm": "m1pref", "out": "outputs/m1pref",
                      "base": "Qwen/Qwen3.8-27B", "beta": 0.1, "alpha": 0.2, "anchor_w": 1.0, "lr": 2e-5,
                      "epochs": 2, "accum": 16, "r": 16, "max_len": 16384, "max_train": 2400, "max_val": 200,
                      "smoke": False, "seed": 0, "ckpt_root": "/data/models/cape_ws/ckpt"})
TM = (r".*language_model\.layers\.\d+\.(self_attn\.(q|k|v|o)_proj|linear_attn\.(in_proj_qkv|in_proj_z|out_proj)"
      r"|mlp\.(gate|up|down)_proj)")  # language model only, as scripts/17_ei_sft.py


def build_rows(cfg, fmt):
    od = REPO_ROOT / cfg.out
    P = pd.read_parquet(od / f"{cfg.data}.parquet")
    S = pd.read_parquet(od / "sites.parquet", columns=["site_id", "prefix"]).set_index("site_id")
    specs = {}
    rows = []
    for r in P.itertuples():
        if r.bench not in specs:
            specs[r.bench] = {json.loads(l)["instance_id"]: json.loads(l)
                              for l in open(REPO_ROOT / f"outputs/capebench/{r.bench}/scenarios.jsonl")}
        spec = specs[r.bench][r.instance_id]
        claim, orc = r.variant.split("|")
        vs = M.variant_spec(spec, claim, orc == "orc", M.paraphrase_for(r.site_id))
        M.check_clean(vs["system_prompt"])
        ctx = M.rerender(list(S.loc[r.site_id].prefix), fmt, spec, vs)
        c = [int(x) for x in r.chosen_ids]
        rj = [int(x) for x in r.rejected_ids] if r.kind == "pair" else None
        if len(ctx) + max(len(c), len(rj or [])) > cfg.max_len:
            continue
        rows.append({"kind": r.kind, "split": r.split, "ctx": ctx, "c": c, "r": rj, "site_type": r.site_type,
                     "variant": r.variant})
    return rows


def seq_logp(model, ctx, tgt, grad: bool, chunk: int = 1024):
    """Sum log p(tgt | ctx) under the model; lm_head applied in chunks on the target positions only."""
    hf = model.base_model.model if hasattr(model, "base_model") else model
    x = torch.tensor([ctx + tgt], device=model.device)
    with torch.set_grad_enabled(grad):
        h = hf.model(input_ids=x).last_hidden_state[0]
        pos = torch.arange(len(ctx) - 1, len(ctx) + len(tgt) - 1, device=x.device)
        y = x[0, len(ctx):]
        head = hf.get_output_embeddings()
        tot = 0.0
        for a in range(0, len(pos), chunk):
            lp = torch.log_softmax(head(h[pos[a:a + chunk]]).float(), -1)
            tot = tot + lp.gather(1, y[a:a + chunk, None]).sum()
    return tot


def stage_train(cfg):
    from peft import LoraConfig, get_peft_model
    from cape.agents.actor import ChatFormatter
    from cape.models.load import load_hf_model, load_tokenizer
    mcfg = resolve_model(cfg.base)
    tok = load_tokenizer(mcfg)
    fmt = ChatFormatter(tok, enable_thinking=mcfg.chat.enable_thinking, reasoning_effort=mcfg.chat.reasoning_effort)
    rows = build_rows(cfg, fmt)
    rng = np.random.default_rng(cfg.seed)
    tr = [r for r in rows if r["split"] == "train"]
    va = [r for r in rows if r["split"] == "val" and r["kind"] == "pair"]
    tr = [tr[i] for i in rng.permutation(len(tr))][:cfg.max_train]
    va = va[:cfg.max_val]
    if cfg.smoke:
        tr = [r for r in tr if r["kind"] == "pair"][:3] + [r for r in tr if r["kind"] == "anchor"][:1]
        va = va[:2]
    print(f"train rows {len(tr)} (pairs {sum(r['kind'] == 'pair' for r in tr)}), val pairs {len(va)}", flush=True)
    model = load_hf_model(mcfg)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(r=cfg.r, lora_alpha=2 * cfg.r, lora_dropout=0.0, target_modules=TM))
    model.print_trainable_parameters()
    t0 = time.time()
    model.eval()
    with model.disable_adapter():  # reference = base weights
        for r in tr + va:
            r["ref_c"] = float(seq_logp(model, r["ctx"], r["c"], False))
            r["ref_r"] = float(seq_logp(model, r["ctx"], r["r"], False)) if r["r"] else None
    print(f"reference log-probs done {time.time() - t0:.0f}s mem {torch.cuda.max_memory_allocated() / 1e9:.1f}GB",
          flush=True)

    def val_stats():
        model.eval()
        m = []
        for r in va:
            pc, pr = float(seq_logp(model, r["ctx"], r["c"], False)), float(seq_logp(model, r["ctx"], r["r"], False))
            m.append(cfg.beta * ((pc - r["ref_c"]) - (pr - r["ref_r"])))
        m = np.array(m) if m else np.zeros(1)
        return {"val_reward_acc": float((m > 0).mean()), "val_margin": float(m.mean()), "n": len(va)}

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=cfg.lr, weight_decay=0.0)
    n_steps = max(1, (cfg.epochs * len(tr)) // cfg.accum) if not cfg.smoke else 1
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 10) * max(0.0, 1 - s / n_steps))
    log, step = [], 0
    for ep in range(cfg.epochs if not cfg.smoke else 1):
        order = rng.permutation(len(tr))
        model.train()
        for i, j in enumerate(order):
            r = tr[j]
            if r["kind"] == "pair":
                with torch.no_grad():
                    pc, pr = float(seq_logp(model, r["ctx"], r["c"], False)), float(seq_logp(model, r["ctx"], r["r"], False))
                z = cfg.beta * ((pc - r["ref_c"]) - (pr - r["ref_r"]))
                coef = cfg.beta * float(torch.sigmoid(torch.tensor(-z)))  # -dL/dz * beta
                lc = -(coef + cfg.alpha / len(r["c"])) * seq_logp(model, r["ctx"], r["c"], True) / cfg.accum
                lc.backward()
                lr_ = coef * seq_logp(model, r["ctx"], r["r"], True) / cfg.accum
                lr_.backward()
                log.append({"kind": "pair", "z": z, "loss": float(-torch.nn.functional.logsigmoid(torch.tensor(z))),
                            "site_type": r["site_type"], "variant": r["variant"]})
            else:
                la = -cfg.anchor_w * seq_logp(model, r["ctx"], r["c"], True) / len(r["c"]) / cfg.accum
                la.backward()
                log.append({"kind": "anchor", "nll_tok": float(la) * cfg.accum / cfg.anchor_w})
            if (i + 1) % cfg.accum == 0 or cfg.smoke and i == len(order) - 1:
                torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
                opt.step(); sched.step(); opt.zero_grad(); step += 1
                if step % 5 == 0 or cfg.smoke:
                    zz = [x["z"] for x in log[-cfg.accum * 5:] if x["kind"] == "pair"]
                    print(f"ep {ep} step {step}/{n_steps} pair_acc {np.mean(np.array(zz) > 0) if zz else float('nan'):.3f} "
                          f"margin {np.mean(zz) if zz else float('nan'):.3f} {time.time() - t0:.0f}s "
                          f"mem {torch.cuda.max_memory_allocated() / 1e9:.1f}GB", flush=True)
    vs = val_stats()
    print("validation:", vs, flush=True)
    out = REPO_ROOT / cfg.out / f"lora_{cfg.arm}{'_smoke' if cfg.smoke else ''}"
    model.save_pretrained(out)
    data_p = REPO_ROOT / cfg.out / f"{cfg.data}.parquet"
    write_json(out / "train_log.json", {"config": OmegaConf.to_container(cfg), "log": log, "steps": step,
                                         "n_train_rows": len(tr), "validation": vs, "seconds": time.time() - t0,
                                         "data_sha256": hashlib.sha256(data_p.read_bytes()).hexdigest()})
    print("saved", out)


def stage_merge(cfg):
    import shutil
    from pathlib import Path

    from peft import PeftModel
    from cape.models.load import load_hf_model, load_tokenizer
    base = resolve_model(cfg.base)
    model = load_hf_model(base)
    model = PeftModel.from_pretrained(model, REPO_ROOT / cfg.out / f"lora_{cfg.arm}").merge_and_unload()
    out = f"{cfg.ckpt_root}/{cfg.arm}"
    model.save_pretrained(out, safe_serialization=True, max_shard_size="5GB")
    load_tokenizer(base).save_pretrained(out)
    for f in ("chat_template.jinja", "generation_config.json", "preprocessor_config.json"):
        src = Path(base.local_path) / f
        if src.exists():
            shutil.copy(src, Path(out) / f)
    print("merged ->", out)


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    {"train": stage_train, "merge": stage_merge}[cfg.stage](cfg)


if __name__ == "__main__":
    main()
