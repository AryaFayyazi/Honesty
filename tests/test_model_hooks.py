"""GPU: architecture introspection + streaming hooks equal the reference hidden states; patch hooks behave."""
import pytest
import torch

from cape.activations.hooks import ResidualCapture, ResidualPatch

pytestmark = pytest.mark.gpu


def test_discovers_64_language_layers(qwen):
    assert len(qwen["blocks"]) == 64
    full = [i for i, t in enumerate(qwen["types"]) if t == "full_attention"]
    assert full == list(range(3, 64, 4))
    print("64 language layers discovered.")


def _nhooks(blocks):
    return sum(len(b._forward_hooks) for b in blocks)


def test_capture_matches_output_hidden_states(qwen):
    model, tok, blocks = qwen["model"], qwen["tok"], qwen["blocks"]
    ids = tok.encode("The agent read the ACL and saw it was not an editor of the record.", add_special_tokens=False)
    x = torch.tensor([ids], device=model.device)
    layers = [0, 3, 15, 31, 47, 62, 63]
    pos = torch.tensor([0, len(ids) // 2, len(ids) - 1])
    with ResidualCapture(blocks, layers, {"p": ("point", pos), "w": ("window", [(len(ids) - 4, len(ids) - 1)])},
                         keep_fp32=True) as cap, torch.no_grad():
        ref = model(input_ids=x, output_hidden_states=True, use_cache=False).hidden_states
    for l in layers[:-1]:  # hidden_states[l+1] == output of block l (last entry is post-final-norm in HF)
        r = ref[l + 1][0, pos].float().cpu()
        assert torch.allclose(cap.out["p"][l], r, atol=1e-3, rtol=1e-3), l
        w = ref[l + 1][0, len(ids) - 4:].float().mean(0).cpu()
        assert torch.allclose(cap.out["w"][l][0], w, atol=1e-2, rtol=1e-2)
    assert all(v.shape[-1] == 5120 for v in cap.out["p"].values())
    # transformers may attach its own output-recording hooks for output_hidden_states; ours must all be removed
    n1 = _nhooks(blocks)
    with ResidualCapture(blocks, layers, {"p": ("point", pos)}):
        assert _nhooks(blocks) == n1 + len(layers)
    assert _nhooks(blocks) == n1, "our hooks leaked"


def test_patch_replace_and_downstream_effect(qwen):
    model, tok, blocks = qwen["model"], qwen["tok"], qwen["blocks"]
    n0 = _nhooks(blocks)
    ids = tok.encode("Delete the production records now.", add_special_tokens=False)
    x = torch.tensor([ids], device=model.device)
    L, p = 31, len(ids) - 1
    val = torch.randn(1, 5120) * 3
    with torch.no_grad():
        base = model(input_ids=x, use_cache=False).logits[0, -1].float()
        with ResidualPatch(blocks, {L: [(0, torch.tensor([p]), val, "replace")]}) as pt, \
                ResidualCapture(blocks, [L, L + 1], {"p": ("point", torch.tensor([p]))}, keep_fp32=True) as cap:
            patched = model(input_ids=x, use_cache=False).logits[0, -1].float()
    assert pt.n_applied == 1
    assert torch.allclose(cap.out["p"][L][0], val[0].to(torch.bfloat16).float(), atol=1e-2)
    assert (patched - base).abs().max() > 1e-2, "patch had no downstream effect"
    # a zero 'add' patch is a no-op
    with torch.no_grad(), ResidualPatch(blocks, {L: [(0, torch.tensor([p]), torch.zeros(1, 5120), "add")]}):
        same = model(input_ids=x, use_cache=False).logits[0, -1].float()
    assert torch.allclose(same, base, atol=1e-3)
    assert _nhooks(blocks) == n0, "our hooks leaked"
