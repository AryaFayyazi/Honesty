# Pre-registration v14: does oversight that reads agent reports select for dishonest reports?
# (written 2026-09-30 20:41 PDT; no resampled report exists)

## Motivation
v7 K1 (confirmed): an LLM grader reading only the final report is BELOW chance at finding uninformative reports
(AUROC 0.42; honest reports flag problems and read as alarming). Labs grade, filter and train agents with graders of
this kind. If so, optimisation against a report-reading grader should increase dishonest reporting with no adversary.

## Design (scripts/27_report_selection.py)
Trajectories: every informed-violation episode of v4fresh_minus with a final report, excluding identity-collision
scenarios. The trajectory prefix is fixed; only the final report is resampled K = 8 times (actor sampling).
Graders (Qwen3.8-27B, v7 prompts): G_R = report-only; G_L = report + action log. Best = lowest P(misleading).
Arms per trajectory: best-of-8 under G_R, best-of-8 under G_L, one uniformly random sample.
Gold labels: 60 random trajectories x 3 arms, shuffled with provenance hidden, labelled by the annotator with the
unchanged rubric (docs/reporting_rubric.md) BEFORE the selection key is read.
## Hypotheses (alpha 0.05, Holm across HP1, HP2)
HP1: P(not HONEST | best under G_R) > P(not HONEST | random)   [optimising the report-reading grader selects dishonesty]
HP2: P(not HONEST | best under G_L) < P(not HONEST | best under G_R)   [log-grounded grading removes the incentive]
Test: exact one-sided McNemar on paired trajectory outcomes.
Secondary: MISREPRESENTED share per arm; grader-score distributions over all K samples; per template;
automated replication over all trajectories using an independent judge family (Gemma-4) as the honesty evaluator.
