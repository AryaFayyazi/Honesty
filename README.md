# The Agent Knew: Internal States Forecast Unauthorized Actions and Stop Them, and the Lies That Follow

Code, benchmark, preregistrations and the complete experimental record for the paper.

Language-model agents sometimes act without authorization and then misreport what they did. This repository has:
- **CAPE-Bench:** matched agent tasks in which one fact decides whether a critical action is authorized. All tools are
  mock tools.
- **The behavioural marker:** *retroactive permission laundering* (act, then ask permission as if the action were
  pending).
- **Forecasting:** linear readouts of the agent's residual stream that forecast the violation and the false report
  before they are written.
- **Prevention:** forecast-triggered policies (gate every action; gate, then ask) evaluated over whole episodes against
  the authorized twin world.

## The record

Every confirmatory test was preregistered before its data existed. Its document (`docs/preregistration_vXX.md`),
analysis script and frozen models were hashed into `results/prereg_vXX_lock.json`. Deviations and addenda are dated
in the same lock files.

| File | What it holds |
|---|---|
| [`docs/PREREGISTRATION_RECORD.md`](docs/PREREGISTRATION_RECORD.md) | Every preregistered test, **including those that did not pass**, with the diagnosed cause and the later test that fixed it |
| [`docs/research_ledger.md`](docs/research_ledger.md) | Dated log of every experiment, decision, incident and correction |
| `results/prereg_vXX/*.json` | Outputs of each analysis script (the numbers in the paper) |
| `results/prereg_vXX_lock.json` | SHA-256 locks and addenda |

The paper reports the results that hold. The tests that did not pass are in the record above.

## Where each part of the paper comes from

| Paper | Preregistration(s) | Main scripts | Figure script |
|---|---|---|---|
| Laundering marks a lie (Sec. 4.1, Fig. 2a); lie forecast before the report (Fig. 1a) | v37 | `scripts/97_rubric_timeline.py` (judge), `scripts/98_v37_analysis.py` | `scripts/120_paper_figures.py`, `scripts/124_fig1.py` |
| Frontier agents pre-launder (Fig. 2b) | v30 (labels), v38 | `scripts/47_tau2_port.py`, `scripts/77_tau2_label.py`, `scripts/79_tau2_analysis.py`, `scripts/101_tau2_disclosure.py` | `scripts/120_paper_figures.py` |
| Observability bound | v29 | `scripts/66_observability_test.py` | — |
| Violation forecast over time (Sec. 4.2, Fig. 3a) | v55, v57 | `scripts/155_v57_analysis.py`, `scripts/163_timecourse_ci.py` | `scripts/151_fig_violation.py` |
| Decision steering and gating (Sec. 4.3, Fig. 3c–d) | v54, v59 (v59b, v59d) | `scripts/144_v54_steer.py`, `scripts/154_v54_gate.py`, `scripts/159_v59_continue.py`, `scripts/160_v59b_gate_always.py` | `scripts/151_fig_violation.py` |
| Internal vs CoT-monitor gate | v62 | `scripts/168_v62_cot_gate.py` | — |
| Lie forecast, internals vs text monitors (Sec. 4.4, Fig. 6) | v51 | `scripts/134_v51_confirm.py`, `scripts/164_lie_operating_points.py` | `scripts/136_fig_v51.py` |
| Evidence contract, blanket and targeted (Sec. 4.5) | v44, v45 | `scripts/96_prereport_intervene.py`, `scripts/108_v44_analysis.py`, `scripts/110_v45_analysis.py` | `scripts/120_paper_figures.py` |
| Honesty steering (Sec. 4.6, Fig. 1b–d; per-model in app. Steering) | v46, v46b, v58; v49 H4 + v79 (Gemma, gpt-oss, Qwen) | `scripts/103_lie_steering.py`, `scripts/111_v46_analysis.py`, `scripts/113_v46b_analysis.py`, `scripts/157_v58_confirm.py`, `scripts/126_caa_multi.py`, `scripts/127_steer_multi.py`, `scripts/135_h4_select.py`, `scripts/203_h4_confirm.py` | `scripts/124_fig1.py` |
| End to end (Sec. 4.6, Fig. 3b) | v61 (v61b, v61c), v63, v64 | `scripts/165_v61_e2e.py`, `scripts/169_v63_honesty_dir.py`, `scripts/170_v64_e2e_all.py` | `scripts/151_fig_violation.py`, `scripts/166_fig_e2e.py` |
| Internal knowledge index, H1 (Sec. 4.7, Fig. 5) | v49 | `scripts/125_v49_analysis.py` | `scripts/120_paper_figures.py` |
| Blind label audit by condition | v50 | see the v50 document | — |
| Readout on unseen safety families | v71 | `scripts/189_v71_lofo.py` | — |
| Model approver with escalation (logged asks; live on Qwen) | v64 (A1), v67, v78 | `scripts/183_v64_approver_sensitivity.py`, `scripts/184_v67_approver.py`, `scripts/160_v59b_gate_always.py` (policy `escalate_model`), `scripts/202_v78_live_approver.py` | — |
| Cost per action (FLOPs, tokens, latency) | — (measurement) | `scripts/181_cost.py`, `scripts/182_cost_bench.py` | — |
| Real benchmark: AgentDojo prompt injection | v74, v75 (frozen readout; not passed), v76 (in-domain fit + frozen steering) | `scripts/191_v74_agentdojo.py` (client), `scripts/196_v76_refit.py`, `scripts/192_v74_analysis.py`, `scripts/197_v76_lito.py`, `scripts/198_merge_shards.py` | `scripts/193_agentdojo_table.py` |
| Open agents on τ²-bench (appendix; not passed) | v65, v66, v69, v70/v70b, v72, v73 | `scripts/172_v65_tau2_run.py`, `scripts/173_v65_analysis.py`, `scripts/186_v69_reader_gate.py`, `scripts/187_v70_real_context.py`, `scripts/188_v70_analysis.py`, `scripts/190_v72_refit.py` | — |

`docs/PREREGISTRATION_RECORD.md` gives the exact test, data, models and outcome for each row.

### Real-benchmark transfer: what did not work, and why
- **τ²-bench (open agents).** Open agents' policy violations are not knowing: they violate when they do not check the policy, and
  with the truthful decision in context they almost never act against it (v66: 1 of 95; v73: 0, 0 and 1 of 99 sites). The
  readout, built for knowing violations, finds no signal there, frozen or refit (v65, v70b, v72).
- **AgentDojo, frozen readout (v74, v75).** The CAPE-trained readout does not flag injected actions (fires on 7–9%), and within
  tool injected calls score slightly lower than benign ones (AUROC 0.28 gpt-oss; 0.23 Gemma, preregistered, CI touching 0.5).
  The agents' reasoning treats an injection signed in the user's name as the user's request. A prompt defense stops Gemma itself
  (ASR 0.077) and is ignored by gpt-oss.
- **The belief mechanism we proposed (v77, preregistered, not supported).** Scoring the same reasoning and action with the
  injection marked as unauthorized does not move the readout (gpt-oss −0.001, Gemma −0.013; difference-in-differences +0.001;
  Holm p = 1). Provenance information alone does not drive it; we dropped the mechanism from the paper's claims.
- **Fix (v76).** Fitting the same readout recipe on AgentDojo's development tasks, with the CAPE steering frozen (the
  preregistered v65/v72 fallback), separates following an injection from benign use and from mere exposure (out-of-fold
  AUROC 0.92-0.97; held-out injection goals 0.995). Confirmed on Gemma (68 unseen tasks): attack success 11.7% -> 5.7%
  (42 fixed / 2 broken, p = 5.6e-11), benign utility unchanged (0.637 vs 0.637); gpt-oss 28.5% -> 17.5% (90 / 18,
  p = 1.1e-12), benign utility 0.667 vs 0.681. `results/prereg_v76/summary.json`.

## Layout
```
src/cape/envs/capebench/   CAPE-Bench: 8 safety families x 3 templates, matched x+/x- worlds, nuisance variants
src/cape/envs/             deterministic mock tools (no network, file system or subprocess) + rule-based safety checker
src/cape/agents/           chat formatting, tool parsers, lock-step rollout loop with a shadow twin (reveal detection)
src/cape/activations/      streaming hooks, event pooling, HF replay
src/cape/probes/, eval/    readouts, grouped splits, cluster bootstrap
scripts/                   numbered pipeline and analysis stages (one script per preregistration where possible)
slurm/                     job scripts (one GPU, serial); slurm/run.sh is the wrapper
docs/                      preregistrations, record, ledger
results/                   analysis outputs and locks
paper/                     LaTeX source and figures
outputs -> /data/models/cape_ws/outputs   (large artefacts: rollouts, activations, generations)
```

## Environment
```
source .venv/bin/activate            # project venv layered on a conda env with transformers>=5.8
pip install -e . --no-deps
```
Verified stack: torch 2.11.0+cu130, transformers 5.14.1, vllm 0.26.0, CUDA 13.0, one H100 NVL.
- Muse-Glimmer runs in a separate environment (`/data/models/cape_ws/envs/v030`; no sklearn/joblib). Its forecasters
  are passed as `.npz`.
- vLLM needs `gdn_prefill_backend="triton"` and `max_num_seqs<=256`.

## Running
Jobs run one at a time through `slurm/run.sh`. For example:
```
sbatch -J v54   slurm/run.sh bash slurm/v54.sh gemma4                 # decision steering: development sweep + confirmation
sbatch -J v59d  slurm/run.sh bash slurm/v59d.sh gptoss20b             # gate, then ask over 12 turns
sbatch -J v64   slurm/run.sh bash slurm/v64.sh                        # end to end in all four families + model approver
sbatch -J v78   slurm/run.sh bash slurm/v78.sh                        # live escalating model approver (Qwen)
python scripts/151_fig_violation.py                                   # Figure 3 from results/
```
Each job script names its preregistration in its header and checks its smoke guards before using any data.

## Safety notes
- All tools are mocks. No real system, credential, host or person is touched.
- Lie labels come from a frozen LLM judge (rubric v4), validated against blind gold labels and audited per condition.

## History
The project began as a pilot ("CAPE: causal action-conditioned predictive embeddings") on whether an agent's residual
stream predicts its unsafe tool actions earlier than text monitors. The pilot scripts (`scripts/00`–`06`) and
`results/pilot/pilot_summary.md` are kept for reference. The pilot design decisions still hold:
- contexts are append-only at the token level;
- labels are rule-based from ground truth;
- monitors see at least as much as the internal readout;
- splits never cross scenario, pair or paraphrase families.
