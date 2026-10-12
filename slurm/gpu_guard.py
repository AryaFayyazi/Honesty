#!/usr/bin/env python3
"""General GPU-sharing guard (user rule, 2026-10-04): arya may use 2 GPUs only while no other user needs one. The moment
another user's GPU job is PENDING and arya has 2 RUNNING jobs:
  1. hold all of arya's pending jobs (no dependency cascades),
  2. cancel arya's most recently started running job and resubmit it (same wrapper + command; rollouts/steering resume
     from checkpoints) to run after arya's other running job,
  3. switch PERMANENTLY to one-GPU mode: re-chain every pending arya job into a strict serial order (topological order of
     the existing dependencies, ties by job id), each job additionally depending on the previous one, then release.
In one-GPU mode it keeps enforcing the serial chain for newly submitted jobs (appends them to the tail).
Soft one-GPU mode (flag file content starts with "soft"; user rule 2026-10-05: back to one GPU once the v49 headline
results are in): nothing is cancelled; the pending chain's head waits for ALL running jobs, so usage drains to one GPU
as soon as either running job ends.
Usage: gpu_guard.py [--dry-run]   Log: /data/models/cape_ws/outputs/slurm_logs/gpu_guard.log
"""
import re
import subprocess
import sys
import time
from datetime import datetime

LOG = "/data/models/cape_ws/outputs/slurm_logs/gpu_guard.log"; FLAG = "/home/arya/new_safety/cape/slurm/ONE_GPU_MODE"; DRY = "--dry-run" in sys.argv; SIM = "--simulate-other" in sys.argv
CWD = "/home/arya/new_safety/cape"


def sh(args):
    return subprocess.run(args, capture_output=True, text=True, cwd=CWD).stdout.strip()


def log(m):
    line = f"{datetime.now():%F %T} {'[DRY] ' if DRY else ''}{m}"
    print(line, flush=True)
    if not DRY:
        open(LOG, "a").write(line + "\n")


def arya_jobs():
    out = {}
    for l in sh(["squeue", "-u", "arya", "-h", "-o", "%i|%j|%t|%E|%S|%y"]).splitlines():
        i, n, t, e, start, nice = l.split("|", 5)
        deps = [d for d in re.findall(r"(after\w*):(\d+)", e)]
        out[i] = {"name": n, "state": t, "deps": deps, "start": start, "nice": int(nice) if nice.strip().lstrip("-").isdigit() else 0}
    return out


def job_command(i):
    txt = sh(["scontrol", "show", "job", i]); cmdline = next(l.strip()[len("Command="):] for l in txt.splitlines() if l.strip().startswith("Command="))
    wrapper, _, rest = cmdline.partition(" ")
    if rest.startswith("bash -c "):
        return wrapper, ["bash", "-c", rest[len("bash -c "):]]
    return wrapper, rest.split()


def serial_order(J):
    pend = {i for i, v in J.items() if v["state"] == "PD"}
    indeg = {i: {d for _, d in J[i]["deps"] if d in pend} for i in pend}; order = []
    while indeg:
        key = lambda i: (J[i].get("nice", 0), int(i))      # 2026-10-05: respect priority tiers (nice), then job id
        ready = sorted([i for i, d in indeg.items() if not d], key=key) or [sorted(indeg, key=key)[0]]
        nxt = ready[0]; order.append(nxt); indeg.pop(nxt)
        for d in indeg.values():
            d.discard(nxt)
    return order


def set_dep(i, deps):
    spec = ",".join(f"{k}:{d}" for k, d in deps) if deps else ""
    if DRY:
        log(f"would set {i} dependency={spec or '(none)'}"); return
    sh(["scontrol", "update", f"JobId={i}", f"Dependency={spec}"])


def enforce_serial(J, head, known=None, head_wait=()):
    """known: job ids whose dependencies are kept (default: J); head_wait: jobs the chain's first job must also wait for
    (set before release, so no job is ever released without its full dependency list)."""
    order = serial_order(J); prev = head; known = set(known or J)
    if not DRY and order:
        sh(["scontrol", "hold"] + order)
    for n, i in enumerate(order):
        deps = [(k, d) for k, d in J[i]["deps"] if d in known]
        waits = ([prev] if prev else []) + (list(head_wait) if n == 0 else [])
        for w in waits:
            if not any(d == w for _, d in deps):
                deps.append(("afterany", w))
        set_dep(i, deps); prev = i
    if not DRY and order:
        sh(["scontrol", "release"] + order)
    return order


def main():
    import os
    log("guard started" + (" (one-GPU mode already on)" if os.path.exists(FLAG) else ""))
    while True:
        J = arya_jobs(); running = {i: v for i, v in J.items() if v["state"] == "R"}
        others = [l for l in sh(["squeue", "-h", "-p", "gpu", "-t", "PD", "-o", "%u|%i|%b"]).splitlines() if l and not l.startswith("arya|") and "gpu" in l]
        if SIM:
            others = ["simulated|0|gres:gpu:1"]
        one_gpu = os.path.exists(FLAG); soft = one_gpu and open(FLAG).read().startswith("soft")
        if soft and not others and len(running) >= 2:   # drain without preempting
            P = {i: v for i, v in J.items() if v["state"] == "PD"}; order = serial_order(J)
            broken = bool(order) and not all(any(d == r for _, d in P[order[0]]["deps"]) for r in running)
            for a, b in zip(order, order[1:]):
                broken = broken or not any(d == a for _, d in P[b]["deps"])
            if broken:
                chain = enforce_serial(P, None, known=J, head_wait=list(running))
                log(f"SOFT ONE-GPU MODE: chain {chain} waits for running {list(running)}")
        elif (others or (one_gpu and not soft)) and len(running) >= 2:
            victim = max(running, key=lambda i: running[i]["start"]); keep = [i for i in running if i != victim][0]
            log(f"{'other user waiting: ' + str(others[:3]) if others else 'one-GPU mode'}; preempting {victim} {running[victim]['name']} (keep {keep})")
            if not DRY:
                pend = [i for i, v in J.items() if v["state"] == "PD"]
                if pend:
                    sh(["scontrol", "hold"] + pend)
                wrapper, cmd = job_command(victim); sh(["scancel", victim]); time.sleep(3)
                new = sh(["sbatch", "--parsable", "-J", running[victim]["name"], f"--dependency=afterany:{keep}", wrapper] + cmd)
                for i in pend:   # dependents of the victim now depend on its resubmission
                    J[i]["deps"] = [(k, new if d == victim else d) for k, d in J[i]["deps"]]
                J[new] = {"name": running[victim]["name"], "state": "PD", "deps": [("afterany", keep)], "start": ""}; J.pop(victim)
                log(f"resubmitted {victim} as {new} after {keep}")
                open(FLAG, "w").write(datetime.now().isoformat())
                order = enforce_serial({i: v for i, v in J.items() if v["state"] == "PD"}, keep)
                log(f"ONE-GPU MODE: serial chain after {keep}: {order}")
            else:
                order = serial_order(J); log(f"would resubmit {victim} after {keep}; would chain pending serially: {order}")
        elif one_gpu:   # keep the serial invariant: every pending job (in chain order) must wait for its predecessor
            P = {i: v for i, v in J.items() if v["state"] == "PD"}; order = serial_order(J)
            head = next(iter(running), None); prev = head; broken = False
            for i in order:
                if prev and not any(d == prev for _, d in P[i]["deps"]):
                    broken = True; break
                prev = i
            if broken:
                order = enforce_serial(P, head); log(f"ONE-GPU MODE: re-chained new/unchained jobs after {head}: {order}")
        if DRY:
            return
        time.sleep(60)


if __name__ == "__main__":
    main()
