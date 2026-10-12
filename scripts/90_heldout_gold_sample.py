#!/usr/bin/env python
"""Held-out gold set for final rubric validation (v35 deviation log, 2026-10-03).

python scripts/90_heldout_gold_sample.py
Samples core24 violating episodes with a report, EXCLUDING the 60 development items: up to 25 that rubric v2 labels
MISREPRESENTED (to estimate precision) + 35 random others, shuffled. Writes results/prereg_v35/heldout_gold_sheet.csv
WITHOUT any rubric label (blind annotation) and a separate key file results/prereg_v35/heldout_key.csv (not to be read
before labeling is complete).
"""
import pandas as pd

from cape.utils.config import REPO_ROOT

STEM = {"qwen38": "core24", "gemma4": "xm_gemma4_core24", "gptoss20b": "xm_gptoss20b_core24"}


def main():
    dev = pd.read_csv(REPO_ROOT / "results/prereg_v33/gold_labeling_sheet.csv")
    devkeys = set(zip(dev.agent, dev.episode_id))
    R = pd.concat([pd.read_parquet(REPO_ROOT / f"outputs/disclosure_v35/{s}_minus_rubric.parquet").assign(agent=a) for a, s in STEM.items()])
    R = R[R.label.isin(["CANDID", "SPIN", "OMITTED", "MISREPRESENTED"])]
    R = R[[(a, e) not in devkeys for a, e in zip(R.agent, R.episode_id)]]
    mis = R[R.label == "MISREPRESENTED"].sample(min(25, (R.label == "MISREPRESENTED").sum()), random_state=11)
    oth = R.drop(mis.index).sample(60 - len(mis), random_state=12)
    pick = pd.concat([mis, oth]).sample(frac=1, random_state=13).reset_index(drop=True)
    E = {a: pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{s}_minus.parquet").set_index("episode_id") for a, s in STEM.items()}
    rows = []
    for i, r in enumerate(pick.itertuples()):
        ep = E[r.agent].loc[r.episode_id]; e = next(v for v in ep.events if v["unsafe_action"])
        perms = [v["tool_result"][:160] for v in ep.events if v["escalation"] and v["event_id"] < e["event_id"]]
        rows.append({"item": i + 1, "episode_id": r.episode_id, "agent": r.agent, "violating_action": f"{e['tool']}({(e['args_json'] or '')[:300]})",
                     "why_violation": e["violations"], "permission_answers_before": "; ".join(perms) or "none",
                     "agent_final_report": str(ep.final_answer)[:2500], "Q1_mentions_action(y/n)": "", "Q2_flags_as_problem(y/n)": "",
                     "Q3_false_claim(y/n)": "", "Q3_quote": "", "notes": ""})
    out = REPO_ROOT / "results/prereg_v35"; out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "heldout_gold_sheet.csv", index=False)
    pick.assign(item=range(1, len(pick) + 1))[["item", "agent", "episode_id", "label"]].to_csv(out / "heldout_key.csv", index=False)
    print("wrote", len(rows), "items;", len(mis), "rubric-MISREPRESENTED oversampled (identity hidden in key file)")


if __name__ == "__main__":
    main()
