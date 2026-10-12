#!/usr/bin/env python
"""Label every WRITE tool call in the published tau2-bench airline trajectories of frontier agents (Claude-3.7-Sonnet,
GPT-4.1, GPT-4.1-mini, o4-mini; data/tau2/results/final) with the truthful policy oracle (src/cape/tau2port.decide),
computed from the live DB state at the moment of the call (the trajectory's tool calls are replayed in order on a fresh
environment). Also records epistemic flags: had the agent READ the targeted reservation / user before writing?

Runs in the tau2 env:  /data/models/cape_ws/envs/tau2/bin/python scripts/77_tau2_label.py
Output: results/v30/tau2_write_labels.csv (one row per write call) + results/v30/tau2_episodes.csv
"""
import glob
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cape import tau2port as TP  # noqa: E402

FINAL = Path("/data/models/cape_ws/datasets/tau2-bench/data/tau2/results/final")
OUT = ROOT / "results/v30"


def env_for(task):
    from tau2.registry import registry
    env = registry.get_env_constructor("airline")()
    st = task.initial_state
    env.set_state(initialization_data=st.initialization_data if st else None,
                  initialization_actions=st.initialization_actions if st else None, message_history=[])
    return env


def main():
    from tau2.data_model.tasks import Task
    OUT.mkdir(parents=True, exist_ok=True)
    rows, eps = [], []
    for f in sorted(glob.glob(str(FINAL / "*_airline_*.json"))):
        model = Path(f).name.split("_airline_")[0]
        d = json.load(open(f))
        tasks = {str(t["id"]): Task.model_validate(t) for t in d["tasks"]}
        for sim in d["simulations"]:
            task = tasks[str(sim["task_id"])]
            env = env_for(task)
            read_res, read_users, n_write = set(), set(), 0
            msgs = sim["messages"]
            for mi, m in enumerate(msgs):
                for tc in (m.get("tool_calls") or []):
                    name = tc["name"]; args = tc.get("arguments") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    if name in TP.WRITE_TOOLS:
                        n_write += 1
                        try:
                            dec = TP.decide(env.tools, name, dict(args))
                        except Exception as e:
                            dec = f"ERROR: {e}"
                        rid = args.get("reservation_id"); uid = args.get("user_id")
                        rows.append({"model": model, "sim_id": sim["id"], "task_id": str(sim["task_id"]), "trial": sim.get("trial"),
                                     "msg_idx": mi, "tool_call_id": tc.get("id"), "tool": name, "args": json.dumps(args),
                                     "decision": dec, "label": ("NOT_ALLOWED" if dec.startswith("NOT ALLOWED") else
                                                                "CONDITIONAL" if dec.startswith("ALLOWED ONLY IF") else
                                                                "ALLOWED" if dec.startswith("ALLOWED") else
                                                                "ERROR" if dec.startswith("ERROR") else "CONDITIONAL"),
                                     "read_reservation_before": bool(rid is not None and rid in read_res),
                                     "read_user_before": bool(uid is not None and uid in read_users),
                                     "n_prior_writes": n_write - 1})
                    if name == "get_reservation_details":
                        read_res.add(args.get("reservation_id"))
                    if name == "get_user_details":
                        read_users.add(args.get("user_id"))
                    try:   # keep the DB state in sync with the trajectory (errors are part of the trajectory)
                        env.make_tool_call(tool_name=name, requestor=tc.get("requestor", "assistant"), **args)
                    except Exception:
                        pass
            eps.append({"model": model, "sim_id": sim["id"], "task_id": str(sim["task_id"]), "trial": sim.get("trial"),
                        "reward": (sim.get("reward_info") or {}).get("reward"), "n_writes": n_write, "n_messages": len(msgs)})
        print(model, "done", flush=True)
    # tool schemas + agent system prompt for the reader-mode extractor (scripts/78, transformers env)
    from tau2.registry import registry
    env0 = registry.get_env_constructor("airline")()
    tools = [t.openai_schema for t in env0.get_tools()]
    try:
        from tau2.agent.llm_agent import AGENT_INSTRUCTION, SYSTEM_PROMPT
        sysp = SYSTEM_PROMPT.format(domain_policy=env0.get_policy(), agent_instruction=AGENT_INSTRUCTION)
    except Exception as e:
        sysp = env0.get_policy(); print("system prompt fallback:", e)
    json.dump({"tools": tools, "system_prompt": sysp}, open(OUT / "tau2_airline_agent_context.json", "w"), indent=1)
    W = pd.DataFrame(rows); E = pd.DataFrame(eps)
    W.to_csv(OUT / "tau2_write_labels.csv", index=False); E.to_csv(OUT / "tau2_episodes.csv", index=False)   # tau2 env has no pyarrow
    print(W.groupby(["model", "label"]).size().unstack(fill_value=0))
    print("NOT_ALLOWED with vs without prior reservation read:\n",
          W[W.label == "NOT_ALLOWED"].groupby(["model", "read_reservation_before"]).size().unstack(fill_value=0))


if __name__ == "__main__":
    main()
