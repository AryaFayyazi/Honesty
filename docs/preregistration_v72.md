# Pre-registration v72: in-domain readout + frozen CAPE steering at real τ²-bench decision points

(written 2026-10-11 ~23:25 PDT, before any v72 feature, fit or generation exists.)

## Why
- v70b (exact within-request pairs) showed that at real τ²-bench decision points the frozen CAPE readout fires on only 24%
  (gpt-oss) and 7% (Gemma) of violating turns at 10% false alarms, while the frozen steering fixes violations when it fires
  (Gemma 2 of 2). Detection does not transfer; steering may.
- The preregistered fallback of v65/v66 (refit the same readout recipe on the benchmark's development data; steering frozen)
  was never reached there. v72 tests it on the real-context decision points.

## Design (fixed now)
- Models: Gemma-4 and gpt-oss-20b (they met the v70 go rule; Qwen continued violations at 6% and is excluded).
- Sites: the v70 sites and split (v65 rule). Development: 99 violating + 257 allowed sites; confirmation: 128 + 410.
- **Development (slurm/v72dev.sh):** none-arm requests on development sites through the vLLM server with shadow scores and
  saved pre-action features (keyed by the generated tool-call id); actions labelled as in v70 (replay + oracle).
- **Readout fit (scripts/190_v72_refit.py):** per-layer shrinkage LDA on the 5 CAPE layers, z-scored and averaged (the v65
  fallback recipe). Positives: VIOLATION turns; negatives: AUTHORIZED_WRITE and READ turns. Two folds by task for out-of-fold
  scores; τ = the larger of the 90th percentiles of out-of-fold scores on AUTHORIZED_WRITE and on READ turns.
  **Go rule:** out-of-fold within-tool AUROC (VIOLATION vs AUTHORIZED_WRITE; tools with ≥ 3 per class, weighted) ≥ 0.65.
- **Confirmation (slurm/v72conf.sh):** the v70b exact-pair mechanism (one gate request per confirmation site, the server logs
  the first and final generation of the same request), with the refit readout and τ, the frozen CAPE steering direction and
  dose, and fresh seeds (sha256 "v72|site").
- **G1 (primary):** violating sites, VIOLATION in the final vs the first action (exact one-sided McNemar; Holm over the models
  that pass the go rule). **G2 (co-primary):** allowed sites, AUTHORIZED_WRITE final − first ≥ −0.05 (task-cluster bootstrap).

## Claims allowed
- G1 and G2 pass: "fit on the benchmark's development data, the readout recipe with the frozen CAPE steering prevents violations
  at real τ²-bench decision points without blocking allowed actions" (the method transfers; the frozen readout does not).
