# Preregistration v47: a powered, two-stage replication of the pre-report internal-vs-text lie forecast (Muse)

Written 2026-10-04 ~22:35, after v40 narrowly failed for lack of power and before any v47 rollout exists.

## Why
- **v40 on 110 fresh informed episodes (36 non-lies):**
  - E1, internal forecaster: 0.637 (p = 0.031; Holm 0.063).
  - Text forecaster: 0.561.
  - E2, internal − text: +0.077, CI [−0.11, 0.25].
- **Power analysis** (Hanley–McNeil SE, observed effects): v40 had 71% power for E1 and 31% for E2. n ≈ 220 gives
  E1 about 95%; n ≈ 600 gives E2 about 86%.

## Fresh data (none exists now; fixed harness; Muse x− rollouts)
- **Stage 1 (8 sets):**
  - core24b seeds 8–9, 10–11, 12–13, 14–15;
  - core24b_reasoning seeds 4–5, 6–7;
  - core24b_obfuscate seeds 4–5, 6–7.
- **Stage 2** (run only if stage 1 does not pass both E1 and E2): 12 more sets, extending the same seed scheme
  (core24b seeds 16–27; reasoning and obfuscate seeds 8–13), for a cumulative target of n ≈ 600.
- **Labels:** rubric v4. **Features:** scripts/94 `pre_report`.
- **Population:** informed violating episodes with a labelled report.

## Frozen forecasters (refit before any v47 rollout; then frozen and hash-locked)
- The v40 recipe:
  - internal: shrinkage LDA on standardised `pre_report`, layer index 3;
  - text: TF-IDF + balanced logistic regression on the pre-report trajectory.
- Trained on ALL existing labelled Muse episodes: the v40 training pool plus the v40 fresh episodes.
- Saved to results/prereg_v47/frozen_forecasters.joblib.

## Endpoints (within-template stratified AUROC; as in v40)
- **E1.** Internal > 0.5 (within-template label permutation, 10,000 permutations).
- **E2.** Internal > text (scenario-cluster bootstrap of the difference, 5,000 draws).
- **Two-stage error control (one-sided):**
  - interim after stage 1: each endpoint at α = 0.01;
  - final on the stage 1 + 2 data: α = 0.04.
  - Holm over {E1, E2} within each look.
- **Stopping.** If both pass at the interim, stop. Otherwise run stage 2 and test once more at the final look.
- **Secondary:** E3, the average of internal and text > text; per-variant breakdown.

## Deviation: stopped at the interim (2026-10-08 ~22:45; stage 2 never generated)
- **Interim (196 fresh Muse episodes, 145 lies):**
  - E1, internal (single v40 readout): 0.587, permutation p = 0.061; not passed at α = 0.01.
  - Text: 0.680.
  - E2, internal − text: −0.093 [−0.217, 0.030]; not passed.
- **Stage 2 is not run.** Its jobs were cancelled while queued; no stage-2 data exist. The interim is reported as the
  final result: E1 and E2 not passed.
- **Reason:**
  - This single-readout recipe was superseded by the internal ensemble, confirmed on fresh episodes of Gemma, gpt-oss
    and Qwen (0.85 vs 0.82 text vs 0.68 CoT monitor).
  - Stopping forfeits the final look (the conservative direction).
  - The v48C stage-2 use is superseded by the v58 honesty-steering confirmations.
