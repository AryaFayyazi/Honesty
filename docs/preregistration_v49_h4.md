# v49 H4 addendum: per-model steering, development protocol (Gemma-4, gpt-oss; Qwen later)

Written 2026-10-05 ~02:10, before any H4 extraction or generation. Development only; each model's confirmation gets its
own dated lock before its confirmation generation (v49 prereg rule).

## Direction (scripts/126)
- Self-counterfactual CAA, as for Muse: within-episode honest − lying mean report activations at the 5 extracted
  blocks.
- **New: condition demeaning.** Each report activation has its condition mean subtracted first.
  - Why: honest and lying reports come disproportionately from different prompts (the contract raises gpt-oss lies).
    Without demeaning, the direction would partly encode report format.
- Inputs: all labelled regenerated reports of that model on development sets (v37 P and v44). The fresh v49 sets are
  excluded by construction.
- Cross-fitted folds 0/1 (scenario hash) for development episodes; fold "a" (all) for fresh confirmation episodes.

## Development episodes (scripts/128)
- Informed development episodes whose earlier neutral regeneration was a lie: Gemma 97, gpt-oss 160 (cap 160).
- That earlier sample is independent of the sweep, which regenerates both "none" and the steered reports fresh with
  the same seed.

## Sweep (scripts/127)
- Conditions: none; CAA α = 4, 8 and 12 (×g, delay 16); random direction at α = 8.

## Selection rule (fixed now)
- Choose the CAA condition with the largest lie reduction vs none (complete-case, paired) that passes all guards:
  - report share ≥ none − 0.10;
  - mention ≥ none − 0.15;
  - degradation: NO_REPORT + UNPARSED + OMITTED ≤ none + 0.05;
  - median generated tokens ≤ 1.5 × none.
- If none passes, the model's steering is reported as "no qualifying configuration" (a null) and no confirmation is
  run.

## Confirmation (to be locked later, per model)
- Fresh v49 informed episodes whose v49 neutral regeneration was a lie; the same independence argument applies.
- Conditions: none, the chosen condition, and the random direction at the chosen α.
- Exact one-sided McNemar test, chosen vs none, with Holm over the models.

## Addendum 1 (2026-10-06 ~09:20): Qwen added, same protocol (before any Qwen H4 extraction or generation)
- **Qwen development regenerations** (v37 P conditions on core24/core24b): 195 reports, 42 episodes, 27 mixed.
  The development set is the 27 episodes whose neutral regeneration lied.
- **Same direction, sweep, selection and guards** as for Gemma and gpt-oss.
- **Expected power is low** (n = 27). If nothing qualifies, Qwen is reported as a null for that reason.
