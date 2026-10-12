"""Generation back-ends for the lock-step agent loop."""
from __future__ import annotations

import math

import torch


class VLLMGenerator:
    def __init__(self, path: str, max_model_len: int = 32768, gpu_memory_utilization: float = 0.9, seed: int = 0,
                 max_num_seqs: int = 256, tokenizer: str | None = None, lora: str | None = None, max_lora_rank: int = 64,
                 **gen):
        """tokenizer: tokenizer path (default: ``path``); evaluation of fine-tuned checkpoints passes the base model's so
        the chat format is byte-identical. lora: optional LoRA adapter dir applied to every request."""
        from vllm import LLM
        extra = {"enable_lora": True, "max_lora_rank": max_lora_rank, "max_loras": 1} if lora else {}
        self.llm = LLM(model=path, tokenizer=tokenizer or path, dtype="bfloat16", max_model_len=max_model_len,
                       gpu_memory_utilization=gpu_memory_utilization, enable_prefix_caching=True, seed=seed,
                       language_model_only=True, logprobs_mode="raw_logprobs", max_logprobs=20,
                       gdn_prefill_backend="triton", max_num_seqs=max_num_seqs, **extra)
        self.lora = None
        if lora:
            from vllm.lora.request import LoRARequest
            self.lora = LoRARequest("ckpt", 1, lora)
        self.gen = gen

    def params(self, seed: int, stop_ids: list[int], **over):
        from vllm import SamplingParams
        g = dict(self.gen, **over)
        return SamplingParams(temperature=g.get("temperature", 0.6), top_p=g.get("top_p", 0.95),
                              top_k=g.get("top_k", 20), max_tokens=g.get("max_tokens", 4096), seed=seed,
                              stop_token_ids=stop_ids, logprobs=0, skip_special_tokens=False)

    def __call__(self, episodes) -> list:
        from vllm.inputs import TokensPrompt
        I = episodes[0].fmt.ids
        stop = [I.tool_call_end, I.im_end, I.eot]
        prompts = [TokensPrompt(prompt_token_ids=[int(t) for t in e.ids]) for e in episodes]
        params = [self.params(e.request_seed(), stop) for e in episodes]
        outs = self.llm.generate(prompts, params, use_tqdm=False, lora_request=self.lora)
        res = []
        for o in outs:
            c = o.outputs[0]
            ids = list(c.token_ids)
            lps = []
            for tid, d in zip(ids, c.logprobs or []):
                lp = d.get(tid) if d else None
                lps.append(float(lp.logprob) if lp is not None else math.nan)
            lps += [math.nan] * (len(ids) - len(lps))
            fr = c.finish_reason
            if fr == "stop" and ids and ids[-1] not in stop and isinstance(c.stop_reason, int):
                ids.append(c.stop_reason)
                lps.append(math.nan)
            res.append((ids, lps, "length" if fr == "length" else "stop"))
        return res


class HFGenerator:
    """Batched HF sampling with optional activation-patch hooks (used by causal patching continuations).

    Each call runs a fresh (left-padded) prefill of every episode's full context, so position-indexed patches on the
    prompt are re-applied every turn -> the intervention persists for the whole continuation.
    ``patch_fn(episodes, pad_offsets) -> ResidualPatch | None`` builds the hook for the current batch.
    """

    def __init__(self, model, tok, max_new_tokens: int = 4096, temperature: float = 0.6, top_p: float = 0.95,
                 top_k: int = 20, patch_fn=None, batch_size: int = 16):
        self.model, self.tok = model, tok
        self.kw = dict(max_new_tokens=max_new_tokens, do_sample=True, temperature=temperature, top_p=top_p,
                       top_k=top_k)
        self.patch_fn, self.bs = patch_fn, batch_size

    @torch.no_grad()
    def __call__(self, episodes) -> list:
        I = episodes[0].fmt.ids
        stop = [I.tool_call_end, I.im_end, I.eot]
        res = []
        for i in range(0, len(episodes), self.bs):
            chunk = episodes[i:i + self.bs]
            L = max(len(e.ids) for e in chunk)
            pad = self.tok.pad_token_id if self.tok.pad_token_id is not None else I.eot
            x = torch.full((len(chunk), L), pad, dtype=torch.long)
            m = torch.zeros((len(chunk), L), dtype=torch.long)
            offs = []
            for r, e in enumerate(chunk):
                o = L - len(e.ids)
                x[r, o:] = torch.tensor(e.ids)
                m[r, o:] = 1
                offs.append(o)
            torch.manual_seed(chunk[0].request_seed())
            patch = self.patch_fn(chunk, offs) if self.patch_fn else None
            dev = self.model.device
            if patch is not None:
                with patch:
                    out = self.model.generate(x.to(dev), attention_mask=m.to(dev), eos_token_id=stop,
                                              pad_token_id=pad, **self.kw)
            else:
                out = self.model.generate(x.to(dev), attention_mask=m.to(dev), eos_token_id=stop, pad_token_id=pad,
                                          **self.kw)
            for r in range(len(chunk)):
                g = out[r, L:].tolist()
                cut = next((j for j, t in enumerate(g) if t in stop), None)
                fr = "stop" if cut is not None else "length"
                g = g[:cut + 1] if cut is not None else g
                res.append((g, None, fr))
        return res
