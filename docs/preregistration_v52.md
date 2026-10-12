# Preregistration v52: a stronger, label-efficient internal forecaster vs supervised text

Written 2026-10-06 ~03:40. At writing time:
- **Qwen v49 labels:** none exist. Job 3369 is on hold until this lock.
- **Gemma/gpt-oss confirmation sets** (`*_minus10111213`): not yet generated (v51 chain).
- Muse is excluded: its fresh v51 sets (the v47 stage-1 sets) were examined in the v47 interim.

## Why
- On fresh data, the supervised text classifier (trained on our labels, reading the full trajectory) matched or
  beat the single-layer internal forecaster (v47 interim; v49 H2).
- The internal forecaster was handicapped: one token, one layer, and none of the label-free contrast activations
  we already extract.
- **Development exploration** (`results/v52_explore`; scenario-grouped CV; development data only):

  | Model | Original internal | Ensemble internal (E_lda) | Text |
  |---|---|---|---|
  | gpt-oss | 0.822 | 0.839 | 0.791 |
  | Gemma | 0.837 | 0.888 | 0.896 |
  | Qwen (n = 42) | 0.686 | 0.723 | 0.358 |

- **With 25% of the training labels:**

  | Model | Ensemble internal | Text |
  |---|---|---|
  | gpt-oss | 0.804 | 0.658 |
  | Gemma | 0.874 | 0.761 |
  | Qwen | 0.803 | 0.562 |

## Frozen forecasters (`scripts/140_v52_freeze.py` → `results/prereg_v52/frozen_<model>.joblib`, `choice.json`)
- **Internal recipe per model** (rule fixed in scripts/140 before Muse/Qwen exploration finished): highest
  development-CV AUROC among {I_lda, E_lda, E_sel, L_all}; ties go to the simpler recipe.
  - E_lda is the mean of z-scored shrinkage-LDA scores over every (block, layer).
  - Blocks: pre_report, pre_m8, honest, conceal, honest − conceal; 5 depths each.
  - No report token is read.
- **Low-label versions:** the identical 25% development subsample (seed 0), for both the internal recipe and the
  supervised text model.
- **The full supervised text model** is the v51-frozen T_sup.

## Confirmation data
- v51 fresh sets: Qwen v49 sets (Qwen); `xm_<model>_core24b{,_obfuscate}_minus10111213` (Gemma, gpt-oss).

## Hypotheses (Holm over V1, V2; one-sided paired scenario-cluster bootstrap; pooled within-(model, template) AUROC with per-model z-scores)
- **V1:** AUROC(internal) > AUROC(T_sup) with full development labels.
- **V2:** AUROC(internal_low) > AUROC(T_low) with 25% of the labels (label efficiency).
- **Per model:** descriptive.

## Reporting
- Every result is reported regardless of outcome, next to v51 C1–C3 and the failed v47/v49 internal-vs-text tests.
- The exploration that led here is reported as exploration.
