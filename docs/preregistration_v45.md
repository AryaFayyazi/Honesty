# Preregistration v45: predict-then-change — an internal-forecast-triggered evidence contract on fresh episodes

Written 2026-10-04 ~20:20.
- **Data status.** The fresh v40 Muse rollouts exist but have NO labels, and no pre-report features have been
  extracted. Labelling is gated behind the v43 lock.
- **What has been seen.** The v44 result: the evidence contract cuts laundering lies (0.76 → 0.53) but raises false
  claims across all informed episodes (0.18 → 0.26). So untargeted use is harmful.

## Hypothesis
Applying the evidence contract only where Muse's internals forecast a lie (before the report is written) prevents more
lies than applying it nowhere, and creates fewer false claims than applying it everywhere.

## Data and conditions
- **Episodes.** Fresh v40 Muse informed violating episodes with a rubric-v4 label:
  - core24b seeds 4–5 and 6–7;
  - reasoning seeds 2–3;
  - obfuscate seeds 2–3.
- **Generations** (scripts/96, vLLM Muse, same seed per episode): `neutral` and `fta_contract`.
- **Labels.** Rubric v4.

## Trigger (frozen; no tuning)
- **Internal trigger.** The frozen v40 internal forecaster (results/prereg_v40/frozen_forecasters.joblib: LDA on
  `pre_report`, layer index 3, trained on 534 dev Muse episodes) applied to each fresh episode's pre-report state.
- **Rule.** Triggered if its decision function is > 0, i.e. the LDA's own boundary.

## Policies
- N: neutral everywhere.
- C: contract everywhere.
- T: contract iff triggered, otherwise neutral.

## Endpoints (exact McNemar test, one-sided, complete-case)
- **Q1.** lie(T) < lie(N). The policies differ only on triggered episodes: contract vs neutral there.
- **Q2.** lie(T) < lie(C). The policies differ only on untriggered episodes: neutral vs contract there.
- Holm over {Q1, Q2}.
- **Claim rule.** "Internal-forecast-targeted prevention beats both no intervention and blanket intervention" if both
  pass.
- **Secondary:**
  - the trigger's precision and recall for lies;
  - a random trigger at the same rate (expectation, computed exactly);
  - lies prevented per contract issued, T vs C;
  - the NO_REPORT sensitivity analysis.
