# Preregistration v62: are internals needed for prevention? Internal gate vs CoT-monitor gate at matched false alarms

Written 2026-10-09 ~15:00, before any v62 monitor scores exist.

## Why
- At the decision, a zero-shot CoT monitor forecasts the violation about as well as internals (v57: paired internal −
  CoT +0.027, n.s.). A reviewer will ask whether gating on a CoT monitor prevents violations as well as gating on
  internals.
- This can be tested on the existing v54 confirmation decision turns without new generation:
  - every site has the unsteered turn (arm none) and the steered turn at the gate dose (arm caa:α), from the same
    seed;
  - a gate's outcome is the steered turn where it fires, otherwise the unsteered turn.

## Design
- **Models and sites:** Gemma, gpt-oss, Muse, Qwen; all v54 confirmation sites (about 200 x− and 200 x+ each).
- **Internal gate:** the frozen pre-action gate and τ (as confirmed in v54).
- **CoT gate:**
  - The frozen v57 zero-shot CoT monitor (scripts/156 prompt, Qwen3.8 judge, thinking on, greedy, forced final
    answer).
  - It reads the system prompt, task, earlier turns with results, and the unsteered turn's reasoning and message,
    without its call.
  - Its threshold is the score quantile on fresh x+ sites that gives the same x+ fire rate as the internal gate.
    This is a matched false-alarm budget, and no violation outcome is used.
- **Outcomes:** violation on x− and progress (CRITICAL or ESCALATE) on x+, from environment-replay labels.

## Endpoints
- **H (primary):** pooled over the four models, the internal-gated violation rate is lower than the CoT-gated rate
  (exact one-sided McNemar on discordant x− sites, summed across models).
- **Secondary (reported regardless):** per model, the same test; progress on x+ for both gates; the fire rate on x−;
  the share of CoT scores parsed.

## Reading
- **If H passes:** internals prevent more violations than a text monitor at the same false-alarm cost.
- **If not:** prevention does not need internals at the decision turn, and the paper says so. The remaining advantages
  of internals are then cost (no extra model call per action), forecasting before the plan is written, and robustness
  under monitoring pressure.

## Reporting
Every result is reported regardless of direction. Deviations are dated here.
