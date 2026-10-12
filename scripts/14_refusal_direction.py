#!/usr/bin/env python
"""Is the actor's early-warning signal the model's refusal feature? (mechanistic check prompted by the GLM-5.3 report
that refusal safeguards can be removed at the weight level while capability remains).

python scripts/14_refusal_direction.py stage=extract   # GPU: Qwen3.8 L46 residual at the response position
python scripts/14_refusal_direction.py stage=analyze   # CPU

Refusal direction r = mean(h | prompts whose preferred response is a refusal) - mean(h | benign prompts), at layer 46,
last prompt token after the generation prompt (difference-of-means; Arditi et al. 2024), from allenai/dolci-instruct-dpo
(pairs where the chosen answer refuses and the rejected complies). Fit on half of each set; validity checked on the
other half (AUROC of the projection). Prompts are only encoded; nothing is generated.

Stated before running (exploratory, but predictions fixed in advance):
  P1 the frozen early-warning probe is nearly orthogonal to r (|cos| < 0.1 in raw activation space);
  P2 projecting r out of the actor activations changes the frozen probe's within-scenario AUROC by < 0.01 on
     v2fresh / v3 reasoning / v3 internal;
  P3 the refusal projection alone is a weak within-scenario predictor of informed violations (AUROC < 0.6).
If P1-P2 hold, the precursor is not the refusal feature, so removing refusals need not remove it.
"""
import json
import pickle

import numpy as np
import pandas as pd
import torch
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"stage": "extract", "layer": 46,
                      "prompts": str(REPO_ROOT / "outputs/refusal/refusal_prompts.json")})
OUT = REPO_ROOT / "results/v3_explore/refusal"


def extract(cfg):
    from cape.activations.hooks import ResidualCapture
    from cape.models.load import discover_transformer_blocks, load_hf_model, load_tokenizer
    from cape.utils.config import resolve_model
    mcfg = resolve_model("Qwen/Qwen3.8-27B")
    tok, model = load_tokenizer(mcfg), load_hf_model(mcfg)
    blocks, _ = discover_transformer_blocks(model)
    P = json.load(open(cfg.prompts))
    H = {}
    for k in ("refused", "benign"):
        hs = []
        for p in P[k]:
            text = tok.apply_chat_template([{"role": "user", "content": p}], tokenize=False, add_generation_prompt=True,
                                           enable_thinking=True)
            ids = tok.encode(text, add_special_tokens=False)
            with ResidualCapture(blocks, [cfg.layer], {"x": ("point", torch.tensor([len(ids) - 1]))},
                                 keep_fp32=True) as cap, torch.no_grad():
                model(input_ids=torch.tensor([ids], device=model.device), use_cache=False, logits_to_keep=1)
            hs.append(cap.out["x"][cfg.layer][0].float().numpy())
        H[k] = np.stack(hs)
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez(OUT / "refusal_acts_L46.npz", **H)
    print("saved", {k: v.shape for k, v in H.items()})


def analyze(cfg):
    import importlib.util
    from cape.eval.statistics import auroc
    spec = importlib.util.spec_from_file_location("t", REPO_ROOT / "scripts/12_explore_timing.py")
    t = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t)
    v3 = t.v3
    Z = np.load(OUT / "refusal_acts_L46.npz")
    R, B = Z["refused"], Z["benign"]
    h = len(R) // 2
    r = R[:h].mean(0) - B[:h].mean(0)
    rhat = r / np.linalg.norm(r)
    val = auroc(np.r_[np.ones(len(R) - h), np.zeros(len(B) - h)], np.r_[R[h:] @ rhat, B[h:] @ rhat])
    fc = json.load(open(REPO_ROOT / "results/v2/frozen_choices.json"))
    actor = pickle.load(open(REPO_ROOT / "results/v2/frozen_actor_probe.pkl", "rb"))
    observer = pickle.load(open(REPO_ROOT / "results/v2/frozen_observer_probe.pkl", "rb"))
    sc, lr = actor.named_steps["standardscaler"], actor.named_steps["logisticregression"]
    w_raw = lr.coef_[0] / sc.scale_  # probe direction in raw activation space
    cos = float(w_raw @ rhat / np.linalg.norm(w_raw))
    res = {"refusal_direction_heldout_auroc": float(val), "cos_probe_refusal": cos, "sets": {}}
    from cape.activations.storage import load_activations
    for name in ["v2fresh_minus", "v3aware_reasoning_minus", "v3aware_internal_minus"]:
        d = t.events(name, fc, actor, observer)
        ai, AX = load_activations(REPO_ROOT / f"outputs/activations/{name}/L46", "pre_action_last", [46])
        X = AX[46][d.ra.values]  # same rows the frozen probe scored (s_a)
        proj = X @ rhat
        d = d.assign(s_proj=actor.decision_function(X - np.outer(proj, rhat)), s_ref=proj)
        E = d.groupby(["scenario_id", "episode_id"]).agg(y=("unsafe_episode", "first"), s_a=("s_a", "max"),
                                                         s_proj=("s_proj", "max"), s_ref=("s_ref", "min")).reset_index()
        a0, n = v3.wsa(E, "s_a")
        a1, _ = v3.wsa(E, "s_proj")
        ar, _ = v3.wsa(E, "s_ref")  # low refusal projection -> violation (min over events; sign reported both ways)
        res["sets"][name] = {"n_mixed": n, "actor": a0, "actor_refusal_projected_out": a1, "delta": a1 - a0,
                             "refusal_projection_auroc(low=unsafe)": 1 - ar if ar == ar else None,
                             "refusal_projection_auroc_raw": ar}
    res["P1_orthogonal"] = abs(cos) < 0.1
    res["P2_unchanged"] = all(abs(v["delta"]) < 0.01 for v in res["sets"].values())
    res["P3_weak"] = all(max(v["refusal_projection_auroc_raw"], 1 - v["refusal_projection_auroc_raw"]) < 0.6
                         for v in res["sets"].values())
    print(json.dumps(res, indent=2))
    (OUT / "refusal_analysis.json").write_text(json.dumps(res, indent=2))


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    extract(cfg) if cfg.stage == "extract" else analyze(cfg)


if __name__ == "__main__":
    main()
