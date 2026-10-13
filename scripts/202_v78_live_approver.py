#!/usr/bin/env python
"""v78 descriptive approver statistics (main env, CPU): decisions of the live model approver on the asks of the gate-then-ask arm
(APPROVE / DENY / ESCALATE), escalation share (= share of asks a person sees), asks per episode by world, and the channel-approver run
(tag _esc64) for reference. -> results/prereg_v78/approver_live.json"""
import json

import pandas as pd

from cape.utils.config import REPO_ROOT


def main():
    Q = pd.read_parquet(REPO_ROOT / "outputs/v59/asks_escmodel_qwen38.parquet"); Q = Q[Q.arm == "gate_always"]
    out = {"asks": int(len(Q)), "by_world": Q.groupby("world").size().to_dict(),
           "decisions": Q.approver_decision.value_counts().to_dict(),
           "escalation_share": float((Q.approver_decision == "ESCALATE").mean()) if len(Q) else None,
           "escalated_then_approved_by_channel": int(((Q.approver_decision == "ESCALATE") & Q.oracle_approved).sum())}
    R = json.load(open(REPO_ROOT / "results/prereg_v59/always_escmodel_qwen38.json")); ref = json.load(open(REPO_ROOT / "results/prereg_v59/always_esc64_qwen38.json"))
    out["live_model_approver"] = {k: R.get(k) for k in ("violation", "D1", "completion", "D2prime", "asks_per_episode", "holm")}
    out["channel_approver_reference"] = {k: ref.get(k) for k in ("violation", "D1", "completion", "D2prime", "asks_per_episode", "holm")}
    (REPO_ROOT / "results/prereg_v78").mkdir(parents=True, exist_ok=True); json.dump(out, open(REPO_ROOT / "results/prereg_v78/approver_live.json", "w"), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
