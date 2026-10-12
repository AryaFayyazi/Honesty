"""vLLM rollout -> saved token ids -> HF teacher-forced replay must be equivalent.

CPU checks: chat-template equivalence of the initial prompt; appended tool-response segments tokenise identically
standalone and in context; decode/encode round-trip of every non-generated segment.
GPU checks: HF replay log-probs of the sampled tokens match vLLM's raw log-probs within bf16 tolerance; left-padded
batched forward (used by patching continuations) matches the unpadded forward.
Set CAPE_ROLLOUTS to the rollout parquet (default: outputs/rollouts/calib_medium.parquet).
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from cape.agents.actor import ChatFormatter
from cape.utils.config import REPO_ROOT

ROLL = Path(os.environ.get("CAPE_ROLLOUTS", REPO_ROOT / "outputs/rollouts/calib_medium.parquet"))
N_CHECK = int(os.environ.get("CAPE_N_CHECK", 6))


@pytest.fixture(scope="module")
def data():
    if not ROLL.exists():
        pytest.skip(f"no rollouts at {ROLL}")
    eps = pd.read_parquet(ROLL)
    toks = pd.read_parquet(str(ROLL).replace(".parquet", "_tokens.parquet")).set_index("episode_id")
    # prefer multi-turn episodes
    eps = eps.sort_values("n_events", ascending=False).head(N_CHECK)
    return eps, toks


@pytest.fixture(scope="module")
def tok():
    from cape.models.load import load_tokenizer
    from cape.utils.config import resolve_model
    return load_tokenizer(resolve_model("Qwen/Qwen3.8-27B"))


def _segments(mask):
    segs, start = [], 0
    for i in range(1, len(mask) + 1):
        if i == len(mask) or mask[i] != mask[start]:
            segs.append((start, i, int(mask[start])))
            start = i
    return segs


def test_chat_template_equivalence(data, tok):
    eps, toks = data
    specs = {json.loads(l)["instance_id"]: json.loads(l)
             for l in open(REPO_ROOT / "outputs/capebench/pilot/scenarios.jsonl")}
    fmt = ChatFormatter(tok, reasoning_effort="medium")
    for ep in eps.itertuples():
        ids = list(toks.loc[ep.episode_id].input_ids)
        s = specs[ep.instance_id]
        init = fmt.initial_ids(s["system_prompt"], s["task_prompt"])
        assert ids[:len(init)] == init, "initial prompt must equal the chat-template rendering"


def test_segments_tokenise_identically(data, tok):
    eps, toks = data
    for ep in eps.itertuples():
        tk = toks.loc[ep.episode_id]
        ids, mask = list(tk.input_ids), list(tk.gen_mask)
        for a, b, g in _segments(mask):
            if g:
                continue
            seg = ids[a:b]
            assert tok.encode(tok.decode(seg), add_special_tokens=False) == seg, (ep.episode_id, a, b)
        # tool-response segments built standalone equal in-context tokenisation (special-token boundaries)
        full = tok.encode(tok.decode(ids[:mask.index(1)]), add_special_tokens=False)
        assert full == ids[:mask.index(1)]


@pytest.mark.gpu
def test_replay_logprobs_match_vllm(data, qwen):
    from cape.activations.replay import compare_logprobs, replay_episode
    eps, toks = data
    stats = []
    for ep in eps.itertuples():
        tk = toks.loc[ep.episode_id]
        ids = list(tk.input_ids)
        gm = np.asarray(tk.gen_mask)
        pos = [int(p) for p in np.nonzero(gm)[0]]
        _, lp = replay_episode(qwen["model"], qwen["blocks"], ids, list(ep.events), [31], ["pre_action_last"],
                               check_positions=pos)
        c = compare_logprobs(np.asarray(tk.logprobs, dtype=np.float64)[pos], lp)
        print(ep.episode_id, len(ids), json.dumps(c))
        stats.append(c)
    df = pd.DataFrame(stats)
    # bf16 kernels differ between vLLM (FlashAttn3 / FlashInfer GDN) and HF (SDPA / fla): token-level noise is
    # expected, systematic divergence is not.
    assert df.mean_prob_abs.max() < 0.02, df
    assert df.mean_abs.max() < 0.1, df
    assert df["corr"].min() > 0.98, df


@pytest.mark.gpu
def test_left_padding_equivalence(qwen):
    model, tok = qwen["model"], qwen["tok"]
    a = tok.encode("The file owner is dana.kim; proceed to share it?", add_special_tokens=False)
    b = tok.encode("Short prompt.", add_special_tokens=False)
    L = len(a)
    x = torch.full((2, L), tok.pad_token_id, dtype=torch.long)
    m = torch.zeros((2, L), dtype=torch.long)
    x[0], m[0] = torch.tensor(a), 1
    x[1, L - len(b):], m[1, L - len(b):] = torch.tensor(b), 1
    with torch.no_grad():
        ref = model(input_ids=torch.tensor([b], device=model.device), use_cache=False).logits[0, -1].float()
        out = model(input_ids=x.to(model.device), attention_mask=m.to(model.device), use_cache=False).logits[1, -1].float()
    p, q = torch.softmax(ref, -1), torch.softmax(out, -1)
    tv = 0.5 * (p - q).abs().sum().item()
    print("left-pad total variation", tv)
    assert tv < 0.05
