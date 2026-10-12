#!/usr/bin/env python
"""v76 Addendum 2 interim: the preregistered scripts/192 `analyze` restricted to one model (no other model's confirmation data are
read), raw p for C1 (Holm completed when all models finish). python scripts/199_v76_gemma_interim.py <actor>"""
import importlib.util
import json
import os
import sys

os.environ.setdefault("V74_OUT", "outputs/v76"); os.environ.setdefault("V74_RES", "results/prereg_v76")
s = importlib.util.spec_from_file_location("a", "scripts/192_v74_analysis.py"); a = importlib.util.module_from_spec(s); s.loader.exec_module(a)
A = sys.argv[1]; a.ACTORS = (A,)
a.analyze()
r = json.load(open(a.RES / "summary.json")); os.replace(a.RES / "summary.json", a.RES / f"summary_interim_{A}.json")
print("interim saved", a.RES / f"summary_interim_{A}.json")
