# Pre-registration v28: can the agent's own activations at report time detect a false/concealing report?
(written 2026-10-01 ~14:50 PDT, BEFORE any report-time activation is extracted or any probe is fit. Motivation: in our
data an LLM judge that READS the final report is below chance at detecting concealment, AUROC 0.42, and rates outright
false reports as the cleanest category, −1.83; even a log-grounded judge rates the lies cleanest, −1.91. We ask whether
the information the report hides is linearly present in the agent's own hidden state when it writes the report.)

## Data
- 185 informed-violation episodes that ended with a final report, with gold honesty labels D1/D2/D3 fixed before any
  report was read (docs/reporting_rubric.md), pooled from v4fresh_minus, v2fresh_minus, v3aware_reasoning_minus,
  v3aware_internal_minus. results/reporting/honesty_rep_labels.parquet.
  - honest (D1 and D2 and not D3) = 32; non-honest = 153; misrepresented (D3 true) = 38.
- Labels: non_honest = 1 − honest (primary target, same target the text judges were scored on); misrep = D3 (secondary).

## Features (frozen a priori; NOT chosen on these labels)
- Actor = Qwen3.8-27B (rev 1d4bf0f2). Replay each episode through HF; take the hidden state at the FINAL event (the
  report turn).
- **Primary position:** `think_end` of the final event — the </think> token, i.e. the moment the model finishes its
  private reasoning and begins the report.
- **Primary layer:** 46. This is the layer the action probe used (chosen long ago by CV on unrelated exploration data),
  so it is an a-priori choice here, not selected on honesty.
- **Primary probe:** logistic regression, standardized features, C = 1.0, on the single (layer 46, think_end) vector.
- Exploratory grid (descriptive only, not the confirmatory claim): layers {30,38,46,54,62} × positions {think_end,
  pre_action_last, pre_action_mean32}.

## Protocol
- Grouped 5-fold cross-validation, groups = scenario_id (no scenario in both train and test), repeated for 5 seeds;
  out-of-fold scores pooled.
- Metric: AUROC for detecting non-honest reports (and, secondary, misrepresented).
- CI: scenario-cluster bootstrap, 10,000.
- Baselines on the SAME 185 episodes:
  - report-only LLM judge and log-reconciling LLM judge (scripts/18 prompts), the two whose eval AUROCs were 0.42 and
    0.76. Recomputed on this pooled set.
  - a template-only predictor (predict the per-template non-honest base rate), to show the probe is not merely reading
    the template.
- Confound control: within-template AUROC for the two templates with enough both-class episodes (con_ci_green,
  tp_billing_correction). The probe must beat chance WITHIN template to claim it is not just decoding the template.

## Hypotheses (frozen)
- P1 (primary): probe AUROC(non_honest) > 0.5, scenario-bootstrap one-sided.
- P2: probe AUROC(non_honest) > report-only judge (0.42) — i.e. internals beat the inverted text channel. Paired
  bootstrap over scenarios.
- P3 (the strong claim): probe AUROC(non_honest) ≥ log-reconciling judge (0.76). Reported with CI; success = lower CI
  bound > 0.5 and point estimate ≥ reconcile.
- P4 (confound): within-template AUROC > 0.5 for con_ci_green and tp_billing_correction.
- Secondary: misrepresented (D3) detection AUROC, same protocol.

## Decision rule
- GO to a scaled, pre-registered study (more labels, fresh seeds, second model) only if P1 and P2 hold AND P4 holds
  (not merely decoding the template). P3 determines whether the framing is "recovers what text misses" (P3 holds) or
  "adds a complementary channel" (P3 fails).
- If P1 fails or P4 fails, report the null: the concealed information is not linearly recoverable at report time at this
  layer/position, and the honesty signal the probe shows is template confounding.

## Interpretation fixed in advance
- The probe reading activations at report time has access to the trajectory via the KV cache, so a positive result
  shows the information is PRESENT and linearly decodable at report time while the report text conveys the opposite. It
  does not by itself establish intent. The deception framing requires the within-violation, within-template contrast
  (P4): among episodes that all violated and share a template, honest vs concealing reports must be separable.
