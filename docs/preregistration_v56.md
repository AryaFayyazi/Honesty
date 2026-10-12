# Preregistration v56: report-anchored honesty steering (fixes the v48 token-window flaw)

Written 2026-10-06 ~15:05, before any v56 generation exists.

## Diagnosis of the v48 null (fresh interim: window arm 0.785 → 0.791, p = 0.63)
- The v48 "token window 17–120" and the "delay 16" count generated tokens from the **start of generation**.
- Muse writes its reasoning (analysis channel) **before** the user-facing report (`<|start|>assistant to=user<|message|>`).
  In the v48C generations the report starts at a median of generated token ~67. In 36% of episodes it starts after
  token 120, so the window arm never steered the report in those episodes. Elsewhere it steered only the first ~50
  report tokens of ~400. The window arm also delayed the report start (median 113).
- The paper's description ("report tokens 17–120") did not match the implementation.
- Development data agrees: all-layer steering at α ≥ 10 from token 16 collapses the reports (report share 0.88 → 0.54;
  length ×3). Steering the reasoning derails the agent. The honesty effect should come from steering the report.
- The confirmed effect (+8 × gap from token 17: 0.71 → 0.44; random null) steered reasoning and report together.

## Intervention
- **Report-anchored CAA (mode `r0`):** + α · g_ℓ · u_ℓ at the five layers, on every report position from the report's
  `<|message|>` token onward. The report start is tracked per sequence during generation (embedding pre-hook). The
  reasoning is not steered.
- **Directions:** the same as v48 (outputs/reconcile/caa_directions.npz; cross-fitted folds on development, all-dev `a`
  on fresh episodes); random control = r_ℓ at the same scale and mode.
- **Built-in check (both runs):** with the same seed and batch, the steered and unsteered generations must be identical up
  to and including the report marker in ≥ 80% of episodes. Otherwise the run is invalid and is reported as such.

## Development (the 115 v48 development episodes; cross-fitted; neutral report turn)
- **Arms:** none; r0 at α ∈ {4, 8, 12, 16}.
- **Selection rule (the v48 rule, scripts/106 tag=v56dev):**
  - pass the guards (report share ≥ none − 0.10; mention ≥ none − 0.15);
  - pass the degradation guard (NO_REPORT + UNPARSED + OMITTED ≤ none + 0.05; mean tokens ≤ 1.5 × none);
  - most negative complete-case paired change in MISREPRESENTED vs none; ties go to the smaller α.
- If none qualifies: null; no confirmation.

## Confirmation (the 196 fresh v48 confirmation episodes, outputs/reconcile/v48_fresh_episodes.parquet)
- **Status of these episodes:** they have been used only for the none / window / +4 arms of v48. The report-anchored
  arm has never been run on them, and its α is chosen on development only.
- **Arms:** none (regenerated in the same run for exact pairing), chosen r0, random r0 at the same α.
- **Secondary arm:** replication of the confirmed configuration (+8 × gap from generated token 17, `d16`).
- **Endpoints:**
  - **S1:** lie(r0) < none;
  - **S2:** lie(r0) < random.
  - Exact one-sided McNemar, complete case, Holm over {S1, S2}, α = 0.05.
  - Guards and degradation guard re-checked.
- **Secondary:**
  - d16 replication vs none;
  - r0 vs d16 (does report-only steering keep the effect with less degradation?);
  - sensitivity with NO_REPORT counted as not MISREPRESENTED;
  - CANDID rate.
- **Replication:** on the v47 stage-2 fresh episodes, when they exist.

## Reporting
- Every result is reported regardless of direction. Deviations are dated here.
- The paper will describe the v48 window as it was implemented (from the start of generation).
