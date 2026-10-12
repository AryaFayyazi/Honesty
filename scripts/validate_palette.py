#!/usr/bin/env python3
"""Python port of the dataviz skill's palette validator (lightness band, chroma floor, CVD separation, normal-vision floor,
contrast). Usage: python scripts/validate_palette.py "#hex,#hex,..." [all]"""
import math, sys, itertools
BAND = (0.43, 0.77); CHROMA_FLOOR = 0.10; CVD_TARGET, CVD_FLOOR = 8.0, 6.0; NORMAL_FLOOR = 15.0; CONTRAST_MIN = 3.0; SURF = "#ffffff"
M = {"protan": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
     "deutan": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
     "tritan": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]]}
s2l = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
lin = lambda h: [s2l(int(h.lstrip("#")[i:i + 2], 16) / 255) for i in (0, 2, 4)]
def ok(rgb):
    r, g, b = rgb; c = lambda x: math.copysign(abs(x) ** (1 / 3), x)
    l, m, s = c(.4122214708*r+.5363325363*g+.0514459929*b), c(.2119034982*r+.6806995451*g+.1073969566*b), c(.0883024619*r+.2817188376*g+.6299787005*b)
    return [.2104542553*l+.7936177850*m-.0040720468*s, 1.9779984951*l-2.4285922050*m+.4505937099*s, .0259040371*l+.7827717662*m-.8086757660*s]
sim = lambda h, k: [max(0, min(1, sum(M[k][i][j] * lin(h)[j] for j in range(3)))) for i in range(3)]
dE = lambda a, b, k=None: 100 * math.dist(ok(sim(a, k) if k else lin(a)), ok(sim(b, k) if k else lin(b)))
lum = lambda h: sum(w * v for w, v in zip((.2126, .7152, .0722), lin(h)))
con = lambda a, b: (max(lum(a), lum(b)) + .05) / (min(lum(a), lum(b)) + .05)
P = [c.strip() for c in sys.argv[1].split(",")]; allp = len(sys.argv) > 2
pairs = list(itertools.combinations(range(len(P)), 2)) if allp else [(i, i + 1) for i in range(len(P) - 1)]
fail = False
for c in P:
    L, a, b = ok(lin(c)); C = math.hypot(a, b)
    print(f"{c}: L={L:.3f} {'OK' if BAND[0] <= L <= BAND[1] else 'OUT-OF-BAND'}  C={C:.3f} {'OK' if C >= CHROMA_FLOOR else 'LOW'}  contrast={con(c, SURF):.2f}")
    fail |= not (BAND[0] <= L <= BAND[1]) or C < CHROMA_FLOOR
w = min((dE(P[i], P[j], k), k, P[i], P[j]) for k in ("protan", "deutan") for i, j in pairs); n = min((dE(P[i], P[j]), P[i], P[j]) for i, j in pairs)
print(f"CVD worst {w[2]}-{w[3]} dE {w[0]:.1f} ({w[1]}) -> {'PASS' if w[0] >= CVD_TARGET else 'FLOOR(needs labels)' if w[0] >= CVD_FLOOR else 'FAIL'}")
print(f"normal worst {n[1]}-{n[2]} dE {n[0]:.1f} -> {'PASS' if n[0] >= NORMAL_FLOOR else 'FAIL'}")
fail |= w[0] < CVD_FLOOR or n[0] < NORMAL_FLOOR; print("RESULT:", "FAIL" if fail else "PASS"); sys.exit(1 if fail else 0)
