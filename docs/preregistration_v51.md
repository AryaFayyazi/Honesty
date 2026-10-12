# Preregistration v51: internals vs CoT monitors (all four models)

Written 2026-10-05 ~10:30. At writing time, none of the confirmation labels exist:
- v47 Muse stage-1 labels: job 3347 has not run;
- Qwen v49 rollouts: running, not labelled;
- fresh Gemma/gpt-oss seeds 10–13: queued (3375).

The forecasters were frozen on development data by `scripts/133_v51_freeze.py` before this lock.

## Why
- **Our supervised text forecaster is not the deployed baseline.** It is a TF-IDF classifier trained on our labels,
  reading everything before the report. Deployed CoT monitors are zero-shot LLM judges.
- **On development data** (`results/v51_explore`, exploratory, cross-validated):
  - internals beat text for gpt-oss (0.82 vs 0.79), Muse (0.67 vs 0.54) and Qwen (0.70 vs 0.36, tiny n);
  - text beats internals for Gemma (0.90 vs 0.84);
  - under CoT-obfuscation pressure (gpt-oss), internals 0.88 vs CoT text 0.82 vs actions-only text 0.71.
- The claim of interest is that **internal monitoring adds what CoT monitoring misses**.

## Confirmation data (fresh, never examined; informed episodes with a report; rubric v4 labels)
- **Muse:** v47 stage-1 sets (core24b seeds 8–15; monitored and obfuscated variants, seeds 4–7). Features tag `_G`.
- **Qwen:** v49 sets `core24b_minus2345`, `core24b_reasoning_minus0123`, `core24b_obfuscate_minus0123`. Features `_H`.
- **Gemma, gpt-oss:** new sets `xm_<model>_core24b_minus10111213` and `xm_<model>_core24b_obfuscate_minus10111213`.
  Features `_K`.

## Frozen forecasters (per model; `results/prereg_v51/frozen_<model>.joblib`)
- **I (internal):** the better of shrinkage LDA (pre-report token, F2 layer) and PCA-256 logistic regression
  (pre-report + 8-token mean, all 5 depths), chosen by development CV.
- **T_sup (supervised text):** TF-IDF + logistic regression on the full pre-report text (reasoning, messages, tool
  calls, results).
- **M_cot / M_act (zero-shot LLM monitors):** `scripts/132_cot_monitor.py`. Qwen3.8 judge, thinking on, greedy;
  outputs a probability that the report will misrepresent. M_cot sees reasoning plus actions; M_act sees actions
  only. No training.
- **S (stack):** logistic regression on the z-scored [I, T_sup] scores, fit on development out-of-fold scores.

## Metric
- Within-(model, template) AUROC, pooled over the four models with per-model z-scoring of every score.
- Episode-level bootstrap clustered by scenario (4,000 resamples), paired across forecasters.

## Primary hypotheses (Holm over C1, C2)
- **C1 (vs the deployed CoT monitor):** AUROC(I) > AUROC(M_cot). One-sided paired bootstrap.
- **C2 (beyond text):** AUROC(S) > AUROC(T_sup), i.e. internals add information beyond the best supervised text
  monitor. One-sided paired bootstrap.

## Secondary
- **C3 (obfuscation robustness):** on obfuscated-variant episodes, AUROC(I) > AUROC(M_cot); and the drop from base
  to obfuscated is smaller for I than for M_cot (difference-in-differences, bootstrap).
- **C4:** per model, I vs T_sup and I vs M_cot (descriptive, Holm within each). Expected to be model-dependent; Gemma
  is the pre-stated exception.
- **C5:** I vs M_act (actions-only monitor).

## Reporting
- All four models appear in every table.
- A model with fewer than 15 lies or 15 non-lies is descriptive only.
- Everything is reported regardless of outcome. If C1 or C2 fails, the paper says so.

## Deviations
(none yet)
