#!/usr/bin/env python3
"""Second-GPU guard (user rule 2026-10-04): arya may use 2 GPUs only while no other user needs one.
Every 60 s: if another user's job is PENDING in partition gpu and arya has 2 RUNNING jobs, then the running job of the
GPU-2 chain (slurm/gpu2_chain.json) is cancelled and re-queued INTO the GPU-1 chain right after the GPU-1 job that is
running now (downstream holds first, so no dependency cascade). Rollouts resume (finished sets are skipped).
Exits when the GPU-2 chain has no live jobs left. Log: /data/models/cape_ws/outputs/slurm_logs/gpu2_preempt.log"""
import json
import subprocess
import time
from datetime import datetime

CHAIN = "/home/arya/new_safety/cape/slurm/gpu2_chain.json"; LOG = "/data/models/cape_ws/outputs/slurm_logs/gpu2_preempt.log"
sh = lambda c: subprocess.run(c, shell=True, capture_output=True, text=True).stdout.strip()


def log(m):
    open(LOG, "a").write(f"{datetime.now():%F %T} {m}\n")


def jobs():
    out = {}
    for l in sh("squeue -u arya -h -o '%i|%j|%t|%E'").splitlines():
        i, n, t, e = l.split("|", 3); out[i] = (n, t, e)
    return out


def main():
    log("guard started")
    while True:
        J = json.load(open(CHAIN))["B_chain"]; Q = jobs()
        live = [b for b in J if b["id"] in Q]
        if not live:
            log("GPU-2 chain finished; guard exits"); return
        others = [l for l in sh("squeue -h -p gpu -t PD -o '%u|%r'").splitlines() if l and not l.startswith("arya|")]
        running = {i: v for i, v in Q.items() if v[1] == "R"}
        if others and len(running) >= 2:
            b_run = next((b for b in J if b["id"] in running), None)
            a_run = next((i for i in running if i not in {b["id"] for b in J}), None)
            if b_run and a_run:
                idx = next(k for k, b in enumerate(J) if b["id"] == b_run["id"]); down = [b["id"] for b in J[idx + 1:] if b["id"] in Q]
                a_next = [i for i, v in Q.items() if v[1] == "PD" and f"afterany:{a_run}" in v[2] and i not in down]
                if down:
                    sh(f"scontrol hold {' '.join(down)}")
                if a_next:
                    sh(f"scontrol hold {' '.join(a_next)}")
                sh(f"scancel {b_run['id']}"); time.sleep(3)
                cmd = b_run["cmd"].replace("'", "'\\''")
                new = sh(f"cd /home/arya/new_safety/cape && sbatch --parsable -J {b_run['name']} --dependency=afterany:{a_run} {b_run['wrapper']} bash -c '{cmd}'")
                J[idx]["id"] = new
                if down:
                    sh(f"scontrol update JobId={down[0]} Dependency=afterany:{new}")
                tail = down[-1] if down else new
                for i in a_next:
                    sh(f"scontrol update JobId={i} Dependency=afterany:{tail}")
                if down:
                    sh(f"scontrol release {' '.join(down)}")
                if a_next:
                    sh(f"scontrol release {' '.join(a_next)}")
                json.dump({"B_chain": J}, open(CHAIN, "w"), indent=1)
                log(f"PREEMPTED for other user ({others[:2]}): cancelled {b_run['name']} {b_run['id']} -> requeued {new} after {a_run}; "
                    f"downstream {down}; GPU-1 next {a_next} now after {tail}")
        time.sleep(60)


if __name__ == "__main__":
    main()
