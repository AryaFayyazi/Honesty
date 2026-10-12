# Pre-registration v76: the CAPE readout recipe fit on AgentDojo development tasks, with frozen CAPE steering

(written 2026-10-12 ~02:00 PDT, before any v76 generation, feature or fit exists. Seen before writing: v74 and v75 gpt-oss
development results; no Gemma attacked-episode score.)

## Why
- The frozen CAPE readout does not transfer to AgentDojo for gpt-oss (v74: fires on 7% of injected calls; v75 under spotlighting: 12%).
  Its scores are not uninformative but *reversed* within tool (injected vs benign calls of the same tool: AUROC 0.28), consistent with
  the readout tracking believed authorization, which an injection that impersonates the user raises (v75 Addendum 2).
- A reversed signal is a domain-shifted signal: the representation separates injected from benign actions, but the CAPE-trained
  direction does not point the right way on this benchmark. The preregistered fallback of v65/v72 is exactly this case: fit the
  same readout recipe on the benchmark's development data and keep the CAPE steering frozen. It never applied on τ² (no signal to
  fit: v72 out-of-fold 0.15/0.29). v76 applies it on AgentDojo.
- The test separates following an injection from merely seeing one: exposed but non-injected calls in attacked episodes are
  negatives (as CAPE's hard negatives: other actions after the reveal), so a readout that only detects injected text in context
  fails the go rule.

## Design (fixed now)
- Benchmark, suites, attack (important_instructions, undefended), split (29 development / 68 confirmation user tasks), sampling,
  seeds: as v74 (scripts/191). Model: Gemma-4 (the strongest CAPE steering: violations 0.58 → 0.04 on fired sites in the vLLM
  validation). Other models may be added by addendum before their data.
- **Development (slurm/v76dev_part.sh):** arm none; benign episodes (3 trials) and attacked episodes (1 trial; may be sharded over
  GPUs, merged by key); pre-action features at the 5 CAPE layers saved per tool call (server save_feats, keyed by call id).
- **Readout fit (scripts/196_v76_refit.py):** the CAPE recipe (per-layer shrinkage LDA at the 5 CAPE layers, z-scored, averaged; as
  scripts/150/190). Positives: tagged injected calls (v74 rule). Negatives: all other tool calls (benign episodes and non-injected
  calls of attacked episodes). Two folds by sha256("v76|suite|user task") for out-of-fold scores; the deployed readout is the fit on
  all development calls. τ = the 90th percentile of out-of-fold scores on benign-episode tool calls (10% false alarms per benign
  action).
- **Go rule:** development ASR ≥ 0.10; ≥ 10 injected calls; out-of-fold within-tool AUROC (injected vs other calls of the same
  tool; tools with ≥ 3 of each; weighted by injected calls) ≥ 0.70; out-of-fold fire rate on injected calls ≥ 0.25.
- **Confirmation (slurm/v76conf_arm.sh):** confirmation user tasks; arms none and gate (refit readout, development τ, frozen CAPE
  steering direction and dose), one GPU each; attacked episodes (1 trial per pair) then benign episodes (3 trials per task); seeds
  identical across arms. Outputs outputs/v76, results/prereg_v76.

## Endpoints (scripts/192 `analyze` with V74_OUT=outputs/v76, V74_RES=results/prereg_v76)
- **C1 (primary):** attack success, gate vs none, paired by (user task, injection task): exact one-sided McNemar (Holm over models).
- **C2 (co-primary):** benign utility, gate − none, task-cluster bootstrap one-sided 95% lower bound ≥ −0.10.
- **Descriptive:** utility under attack; per-suite ASR; fired requests, steering changes; development AUROC vs exposed non-injected
  calls; comparison with v74's descriptive prompt-defense arms where available.

## Claims allowed
- C1 and C2 pass: "fit on 29 development tasks of AgentDojo, the CAPE readout recipe with the frozen CAPE steering reduces
  prompt-injection attack success on the confirmation tasks without loss of benign utility" (the method transfers; the frozen
  readout's direction does not).
- Go rule fails: "the pre-action state carries no linearly readable signal of following an injection (beyond seeing one)".

## Addendum 1 (2026-10-12 ~03:00 PDT; before any gpt-oss or Muse v76 data; Gemma development partly complete, its fit not run)
- gpt-oss-20b and Muse join v76 with the identical design (scripts/191, 196; slurm/v76dev_part.sh, v76conf_arm.sh; Muse in the
  vLLM-0.30 env). Holm in C1 is over all models that pass the go rule. Reason: Gemma's undefended attack success may fall below the
  10% go threshold (first development shard 0.097), and the GPU budget allows these runs now.

## Addendum 2 (2026-10-12 ~05:00 PDT; operational, before any confirmation outcome was inspected)
- GPU deadline. The Gemma gate arm (job 3601) runs slower than the none arm (steering regenerates fired turns). When the none arm's
  job ends, the gate-arm job is stopped and resumed as two shards on two GPUs (slurm/v76conf_shard.sh, env V74_SHARD; completed
  episodes are kept, in-flight ones restart with the same seeds). Shard files are merged by scripts/198_merge_shards.py (first
  completed record per episode key; last server record per request id) before scripts/192 `analyze`. gpt-oss's arms run after.
- C1 Holm is over all models passing the go rule (Gemma, gpt-oss); an interim Gemma-only analysis reports the raw p and is marked
  interim until gpt-oss's confirmation completes.

## Addendum 3 (2026-10-12 ~07:45 PDT; before any confirmation endpoint was computed)
- The gpt-oss server raised a batch exception on a malformed tool-call argument (11 times in the none arm so far); the client retries
  three times and otherwise records "[server error]" as the agent's turn. Rule fixed now: an episode with a "[server error]" turn is
  treated as an error and excluded together with its paired episode (scripts/192 `rows`); counts are reported. So far 0 such episodes
  in every v76 file.
