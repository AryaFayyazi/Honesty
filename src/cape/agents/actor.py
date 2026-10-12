"""Token-level chat formatting for the actor.

The context is built append-only at the token level: every token the model generated is kept verbatim, and tool
responses are appended exactly as the Qwen chat template renders a ``tool`` message. The resulting token sequence is
the single source of truth for rollout (vLLM), replay (HF) and activation extraction, so all three see identical ids.
"""
from __future__ import annotations

from dataclasses import dataclass

from cape.envs.base import TOOLS

# Qwen3.5 / 3.8 special tokens (verified against the tokenizer in scripts/00_smoke_model.py)
SPECIAL = {"think": "<think>", "think_end": "</think>", "tool_call": "<tool_call>", "tool_call_end": "</tool_call>",
           "im_start": "<|im_start|>", "im_end": "<|im_end|>", "eot": "<|endoftext|>"}


@dataclass
class TokenIds:
    think: int
    think_end: int
    tool_call: int
    tool_call_end: int
    im_start: int
    im_end: int
    eot: int


def special_ids(tok) -> TokenIds:
    out = {}
    for k, s in SPECIAL.items():
        ids = tok.encode(s, add_special_tokens=False)
        assert len(ids) == 1, f"{s} is not a single token: {ids}"
        out[k] = ids[0]
    return TokenIds(**out)


class ChatFormatter:
    def __init__(self, tok, enable_thinking: bool = True, reasoning_effort: str = "medium"):
        self.tok = tok
        self.enable_thinking = enable_thinking
        self.reasoning_effort = reasoning_effort
        self.ids = special_ids(tok)

    def initial_text(self, system: str, user: str, tools: list | None = None, prior: list | None = None) -> str:
        """prior: earlier messages of the same session inserted between the system prompt and the task (prereg v20)."""
        return self.tok.apply_chat_template(
            [{"role": "system", "content": system}] + list(prior or []) + [{"role": "user", "content": user}],
            tools=tools or TOOLS,
            add_generation_prompt=True, tokenize=False, enable_thinking=self.enable_thinking,
            reasoning_effort=self.reasoning_effort)

    def initial_ids(self, system: str, user: str, tools: list | None = None, prior: list | None = None) -> list[int]:
        return self.tok.encode(self.initial_text(system, user, tools, prior), add_special_tokens=False)

    def tool_response_text(self, obs: str, close_assistant: bool) -> str:
        head = "<|im_end|>\n" if close_assistant else "\n"
        gen = "<|im_start|>assistant\n" + ("<think>\n" if self.enable_thinking else "<think>\n\n</think>\n\n")
        return f"{head}<|im_start|>user\n<tool_response>\n{obs.strip()}\n</tool_response><|im_end|>\n{gen}"

    def tool_response_ids(self, obs: str, close_assistant: bool = True) -> list[int]:
        return self.tok.encode(self.tool_response_text(obs, close_assistant), add_special_tokens=False)

    def split_generation(self, gen_ids: list[int]) -> dict:
        """Locate reasoning / content / action spans in one assistant turn (indices relative to gen start)."""
        I = self.ids
        think_end = gen_ids.index(I.think_end) if I.think_end in gen_ids else None
        tool_call = gen_ids.index(I.tool_call) if I.tool_call in gen_ids else None
        if tool_call is not None and think_end is not None and tool_call < think_end:
            tool_call = None  # a <tool_call> token inside the reasoning is not an action
            if I.tool_call in gen_ids[think_end + 1:]:
                tool_call = think_end + 1 + gen_ids[think_end + 1:].index(I.tool_call)
        end = len(gen_ids) - 1
        if tool_call is not None:
            action_start = tool_call
        else:  # final answer: first non-whitespace content token after </think>
            action_start = None
            if think_end is not None:
                for j in range(think_end + 1, len(gen_ids)):
                    if self.tok.decode([gen_ids[j]]).strip():
                        action_start = j
                        break
        return {"think_end": think_end, "action_start": action_start, "is_tool_call": tool_call is not None,
                "gen_end": end}
