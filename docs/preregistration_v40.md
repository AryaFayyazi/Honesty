# Preregistration v40: do Muse's internals forecast its lies better than text, before the report? (fresh replication)

Written 2026-10-04 ~09:50, before any v40 rollout exists.

## Motivation (exploratory, on seen labels)
In the v37 confirmation data, the frozen pre-report internal forecaster (F2a) reached within-template AUROC 0.70 for
Muse-Glimmer, against 0.52 for a TF-IDF forecaster of the same pre-report trajectory. Pooled across three models it
was 0.745 vs 0.724. If the Muse advantage is real, Muse's residual stream carries information about the coming lie
that its visible trajectory does not.

## Fresh data (none exists now)
- Muse-Glimmer x− rollouts with the fixed harness:
  - core24b seeds 4–5 and 6–7;
  - core24b_reasoning seeds 2–3;
  - core24b_obfuscate seeds 2–3.
- Seeds 0–3 (core24b) and 0–1 (variants) are the only ones used so far.
- **Labels:** rubric v4. **Features:** scripts/94 `pre_report`.
- **Population:** informed violating episodes with a labelled report.

## Frozen forecasters (trained before the fresh data exists, on all existing labelled Muse episodes)
- **Internal.** Shrinkage LDA on standardised `pre_report` at layer index 3, which is v37's Muse F2 selection.
  Trained on all labelled Muse episodes, informed and uninformed, from core24, core24b and the variants (the v39
  training pool). y = MISREPRESENTED.
- **Text.** TF-IDF (1–2-grams, min_df 2, at most 20k features, sublinear) plus class-balanced logistic regression on the
  pre-report trajectory text (scripts/98 `prefix_text(·, "last")`), trained on the same episodes.
- Both are fitted once and saved (results/prereg_v40/frozen_forecasters.joblib) before any fresh rollout. The
  saved file is hash-locked.

## Endpoints (within-template stratified AUROC on the fresh informed episodes)
- **E1.** Internal > 0.5: label permutation within template, 10,000 permutations, one-sided p < 0.05.
- **E2 (primary).** Internal > text: scenario-cluster bootstrap of the AUROC difference, 5,000 draws. PASS if the
  one-sided 95% lower bound is > 0.
- **E3 (secondary).** A 50/50 average of the z-scored internal and text forecasters > text (does internal information
  add to text?).
- Holm over {E1, E2}.
- If the fresh set has fewer than 15 non-lies or 15 lies, the endpoints are reported descriptively.
