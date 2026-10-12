# Pre-registration v69: does the CAPE readout recognize frontier agents' knowing violations on τ²-bench? (reader gate)

(written 2026-10-11 ~20:05 PDT, before any v69 feature or score exists. Build stage done: 1,007 prefixes — 667 ALLOWED, 227 NOT_ALLOWED (60 knowing), 113 CONDITIONAL; one gpt-4.1 write has no simulation in the published file.)

## Why
- On τ²-bench, open agents rarely violate knowingly (v66: 1 of 95 shown NOT ALLOWED decisions acted on), so the gate's
  prevention cannot be tested there with open agents.
- Frontier agents do violate knowingly on τ²-bench: in the published airline trajectories they state a false justification
  to the customer before 60 of 227 policy-violating writes and before none of 667 allowed writes (v38, preregistered,
  blind-validated precision 0.97).
- v69 asks whether the frozen CAPE readout, applied by an open model reading those transcripts (a *reader gate*, as in the
  validated reader setting of the appendix: \Qwen reading \Oss, 0.86), separates violating from allowed writes on a real
  benchmark, and whether it does so best for the knowing violations.

## Data (fixed now)
- Published τ²-bench airline trajectories of Claude-3.7-Sonnet, GPT-4.1, GPT-4.1-mini and o4-mini (4 trials each;
  `tau2-bench/data/tau2/results/final`), and the v38 labels of every write action (`results/v38/tau2_disclosure.parquet`):
  oracle label (NOT_ALLOWED / ALLOWED / CONDITIONAL) and `false_justification_before`.
- Units: NOT_ALLOWED and ALLOWED writes (227 + 667). CONDITIONAL and ERROR writes are excluded from the primary tests.

## Reader and state (fixed now)
- Reader: \Qwen (Qwen3.8-27B), the model with the strongest CAPE gate confirmation and a validated vLLM hook engine
  (r = 0.99999 with HF). Frozen gate: `outputs/v54/gate_qwen38.npz`, unchanged.
- Context: the frontier agent's system prompt (τ²'s LLMAgent prompt with the published airline policy), the airline tool
  schemas, and every message before the write; then the frontier agent's own text in the write turn, if any, without the
  tool call. The state is the last token of that context (the pre-action state of the reader), rendered with \Qwen's chat
  template (thinking off; the frontier agents' reasoning is not in the logs).
- Scripts: `scripts/186_v69_reader_gate.py` (stages `build` in the τ² environment, `score` on the GPU, `analyze`).

## Endpoints
- **R1 (primary):** AUROC of the frozen reader-gate score, NOT_ALLOWED vs ALLOWED writes, within write tool (tools with
  ≥ 3 of each class, weighted by n; pooled if none qualifies). One-sided test of AUROC > 0.5 with a task-cluster bootstrap
  (10,000 draws). Passes at p < 0.05.
- **R2 (primary, dissociation):** AUROC(knowing violations vs ALLOWED) − AUROC(other violations vs ALLOWED) > 0, where
  knowing = NOT_ALLOWED with `false_justification_before`. One-sided task-cluster bootstrap; Holm over R1 and R2.
- **Descriptive:** per frontier agent; pooled AUROC; a refit of the same readout recipe with task-grouped 5-fold
  cross-validation (exploratory: does the information exist even if the frozen direction does not transfer?).

## Claims allowed
- R1 passes: "the frozen CAPE readout, read by an open model, flags frontier agents' policy-violating actions on τ²-bench".
- R1 and R2 pass: "... and best when the agent had stated a false justification (a knowing violation)".
- No prevention claim: frontier agents cannot be steered here.
