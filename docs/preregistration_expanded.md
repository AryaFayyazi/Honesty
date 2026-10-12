# Pre-registration: expanded CAPE-Bench study (written 2026-09-28, BEFORE any expanded data exists)

## Data
CAPE-Bench core suite, `--num-base-scenarios 1000 --num-paraphrases 1 --seed 42`, explicit policy, normal approvals,
no pressure (identical configuration to the pilot). Seeds [0,1,2,3] per instance => 8000 episodes. Pilot data are NOT
pooled into the confirmatory analysis (pilot = exploratory).

## Primary hypotheses (confirmatory; alpha = 0.05 each, Holm-corrected across H1-H3)
H1 (run-level early signal). In the x- population, a linear probe on actor residuals (pre_action_last) predicts
    eventual unsafe behaviour beyond scenario-level information. Test: within-scenario refit permutation null
    (outcomes permuted among episodes of the same scenario), 200 permutations, scenario-grouped 5-fold CV.
    Layer: chosen by validation AUROC on the PILOT data (layer 61 for pre_action_last) - fixed now.
H2 (earliness). Same probe and test restricted to events strictly before the first unsafe decision (d >= 1).
H3 (actor vs observer). Paired scenario-cluster bootstrap AUROC difference, actor probe (H1) minus observer
    probe (Qwen3-8B, visible transcript + CoT, layer 27), on d >= 1 positives, x- population. One-sided (> 0).

## Secondary (reported regardless of outcome)
- Same tests for uninformed-failure prediction (x- episodes, events before any observation of the causal variable).
- Template- and family-holdout versions of H1.
- Proceed-vs-escalate decision forecasting (x+), actor vs observer, d >= 2.
- Causal patching (pilot sites) reported separately; not part of H1-H3.

## Decision rule
GO for "actor-internal early warning" iff H1 and H2 reject AND H3 reject.
Partial GO ("predictive latent precursors, not better than observers") iff H1 and H2 reject but H3 does not.
NO-GO otherwise. No additional layers, poolings, populations or probes will be promoted to confirmatory after
seeing the expanded data; anything else is labelled exploratory.

## Amendment 1 (2026-09-28, before any expanded-study data were generated; rollout job not yet started)
Metric: every AUROC in H1-H3 is the WITHIN-FOLD AUROC (computed inside each held-out fold that contains both
classes, averaged with weights = number of positive events), not AUROC over pooled out-of-fold scores. Reason: on
the pilot, pooling scores from different fold models produced artefacts in both directions (e.g. actor probe family
holdout 0.29 pooled vs 0.38 within-fold; scenario holdout 0.785 pooled vs 0.71 within-fold). The permutation null for
H1/H2 uses the same within-fold metric. H3's paired bootstrap resamples scenarios and recomputes within-fold AUROC
for both methods on the same events. Additional required comparator for H3 (secondary, reported): nuisance-only
baseline (event index, tool identity, family), which matched the actor probe on the pilot.

## Amendment 2 (2026-09-29, before any confirmatory result was computed)
Label-validity exclusion. A manual audit of informed-violation transcripts found that in 5 own_dataset_upload
counterfactual pairs the randomly drawn data licensor coincided with the destination vendor, so the x- "unsafe"
upload returned data to its owner (invalid label; the model's behaviour was correct). All 40 episodes of those pairs
(both cf sides, all seeds) are excluded from H1-H3 (list: results/expanded/label_exclusions.json; 15 unsafe labels
removed). The template was fixed for future data (tests/test_counterfactual_pairs.py::
test_dataset_licensor_never_destination_vendor). No other change to hypotheses, metric, layer or decision rule.

## Amendment 3 (2026-09-29, before any confirmatory result was computed) — computation only
Logistic probes are fit with a GPU L-BFGS solver of the identical objective (L2, balanced class weights, unpenalised
intercept, standardised features; C chosen on validation from the same grid). Verified against sklearn
(tests/test_torch_logistic.py: score correlation > 0.9999, max abs difference < 1e-2). No change to any hypothesis,
metric, data, layer, permutation scheme or decision rule.
