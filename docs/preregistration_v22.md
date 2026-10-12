# Pre-registration v22: cross-model replication of the enforcement-claim effect (v10)
(written 2026-10-01 00:45 PDT; no v22 data exists; the cross-model references x_*_v2fresh_minus are queued, not run)

## Design
Actors and settings as in `scripts/20_server_rollouts.py`:
- gpt-oss-20B, Gemma-4-26B-A4B (thinking on) and Muse-Glimmer-30B;
- each model's own chat template, tool parser and recommended sampling;
- a local vLLM server only.

Same mock environment, labels and reveal logic as all Qwen runs.

| run | scenarios | reference (same seeds) |
|---|---|---|
| x_<actor>_v10enf_minus | v10enf (v2fresh + the false "tools enforce permissions" note), x-, seeds 0-3 | x_<actor>_v2fresh_minus (xfull / mfull) |

Identity collisions are excluded. Labels are audited per model before the analysis.

## Hypotheses
Outcome: informed violation in the probing class P (con_ci_green + auth_repo_access), as in v10.
- XM1 (primary): pooled over the three models, P violations increase with the note.
  - Statistic: the mean over scenarios of each scenario's across-model mean difference (note - reference).
  - One-sided sign-flip over scenarios (10,000).
- XM2 (replication count): per model, the same one-sided test with Holm across the three models; report in how many
  models the increase is significant.
- Models with no P violations in either condition contribute zero differences (floor). Such models are reported, not
  dropped.

## Secondary
- the discriminant DiD vs billing per model and pooled (as v10 H-MH2);
- the share of violating steps whose reasoning cites enforcement;
- escalation;
- per-template rates.

Analysis: `scripts/19_v6_resp.py` per model (direction=increase) and `scripts/38_crossmodel_mh.py` for the pooled
test.

## Deviations
- 2026-10-01 02:10: `scripts/20_server_rollouts.py` gained the v24 actors and an optional reasoning parser. For the
  v22 actors the server command contains the same arguments in a different order, and episode logic is unchanged. Its
  hash in results/v22_prereg.sha256 is therefore expected to differ for this reason only.
