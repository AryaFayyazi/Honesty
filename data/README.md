# Data

Each directory of the experiment outputs is packed as a gzipped tar archive, split into parts below 95 MB
(GitHub's file limit). Reassemble and extract one archive with:

```bash
cat data/<name>.tar.gz.part* | tar xzf -
```

This creates `<name>/` with the original layout (as under `outputs/` in the scripts' paths).

| Archive | Contents |
|---|---|
| `capebench` | CAPE-Bench scenario specifications (matched unauthorized / authorized worlds; mock tools only) |
| `rollouts*`, `disclosure*`, `prereport`, `monitor`, ... | Episodes, judge labels and monitor outputs of the CAPE-Bench experiments |
| `v54` ... `v76` | Episodes, server logs, labels and frozen readouts (small `.npz`) of the preregistered tests (see `docs/PREREGISTRATION_RECORD.md`; directory names = preregistration numbers) |
| `v65`-`v73` | Open agents on τ²-bench airline (our episodes and labels) |
| `v74`-`v76` | AgentDojo prompt-injection experiments (our episodes, server logs, calibrated readouts) |

Not included:
- Regenerable caches: residual-stream activations and pre-action feature files larger than 5 MB (recompute with
  the scripts from the episodes and the public model weights) and one token-id parquet.
- Third-party benchmarks: τ²-bench (https://github.com/sierra-research/tau2-bench) and AgentDojo
  (`pip install agentdojo==0.1.35`, benchmark v1.2.2) are used unchanged and are not redistributed.
- Model weights (public on Hugging Face; ids in `configs/` and the paper's appendix).
