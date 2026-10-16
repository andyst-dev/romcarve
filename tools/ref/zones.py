#!/usr/bin/env python3
"""zones.py - mesure les plages IDENTIQUES au meme offset entre la ROM anglaise
et une ROM cible, et caracterise les zones de difference.

Idee (plan J1, point 8) : BPEE et BPED partagent 4,59 Mo au meme offset en ~1028
plages ; les grandes plages sont des ancres ABSOLUES. Entre deux ancres, la
"zone de difference" ne contient que des donnees de langue (textes, graphismes,
credits) : c'est la que l'alignement doit se faire.

Usage : zones.py <CIBLE> [min_run]
"""
from __future__ import annotations
# --- where things live -------------------------------------------------------
# These tools read and write a workspace you point at with environment variables:
#   LOC_WORK          scratch workspace (JSON artefacts, caches, outputs)
#   LOC_ROMS          directory holding the cartridge images you work from
#   LOC_REF_MANIFEST  the reference-language manifest (e.g. italian.json.gz)
#   LOC_REF_TREE      the patched decomp tree of the reference language
#   LOC_VFWORK        workspace of an earlier language pass, if a tool reuses it
#   LOC_SCRATCH       throwaway directory for dumps
import os as _os
from pathlib import Path as _Path

WORK = _Path(_os.environ.get("LOC_WORK", "."))
ROMS = _Path(_os.environ.get("LOC_ROMS", str(WORK / "roms")))
REF_MANIFEST = _Path(_os.environ.get("LOC_REF_MANIFEST", str(WORK / "italian.json.gz")))
REF_DIR = REF_MANIFEST.parent
REF_TREE = _Path(_os.environ.get("LOC_REF_TREE", str(WORK / "pret_patched")))
VFWORK = _Path(_os.environ.get("LOC_VFWORK", str(WORK / "vf_work")))
SCRATCH = _Path(_os.environ.get("LOC_SCRATCH", str(WORK / "scratch")))
# -----------------------------------------------------------------------------

import sys
from pathlib import Path
import numpy as np

ROMS = {
    'EN': Path(f"{ROMS}/emeraude_en.gba"),
    'FR': Path(f"{ROMS}/emeraude_fr.gba"),
    'IT': Path(f"{WORK}/roms/it_bpei.gba"),
    'DE': Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba"),
}


def load(target):
    return ROMS['EN'].read_bytes(), ROMS[target].read_bytes()


def eq_runs(a: bytes, b: bytes, min_run=64):
    """[(start, length)] des plages ou a[i] == b[i], longueur >= min_run."""
    n = min(len(a), len(b))
    A = np.frombuffer(a[:n], dtype=np.uint8)
    B = np.frombuffer(b[:n], dtype=np.uint8)
    eq = (A == B)
    # frontieres
    idx = np.flatnonzero(np.diff(eq.view(np.int8)))
    starts = np.concatenate(([0], idx + 1))
    ends = np.concatenate((idx + 1, [n]))
    vals = eq[starts]
    out = [(int(s), int(e - s)) for s, e, v in zip(starts, ends, vals)
           if v and (e - s) >= min_run]
    return out


def main():
    target = sys.argv[1]
    min_run = int(sys.argv[2]) if len(sys.argv) > 2 else 64
    a, b = load(target)
    runs = eq_runs(a, b, min_run)
    cov = sum(l for _, l in runs)
    print("%s vs %s : %d plages identiques >= %d o, couverture %.2f Mo (%.1f%%)"
          % ('EN', target, len(runs), min_run, cov / 1e6, 100.0 * cov / len(a)))
    runs.sort(key=lambda x: -x[1])
    print("  20 plus grandes :")
    for s, l in runs[:20]:
        print("     %9d  %9d o" % (s, l))
    # zones de difference entre les plages >= 4096 (ancres)
    anchors = sorted([r for r in runs if r[1] >= 4096])
    print("  ancres (>= 4096 o) : %d, couverture %.2f Mo"
          % (len(anchors), sum(l for _, l in anchors) / 1e6))
    gaps = []
    prev_end = 0
    for s, l in anchors:
        if s > prev_end:
            gaps.append((prev_end, s - prev_end))
        prev_end = max(prev_end, s + l)
    if prev_end < len(a):
        gaps.append((prev_end, len(a) - prev_end))
    gaps.sort(key=lambda x: -x[1])
    print("  %d zones de difference, total %.2f Mo" % (len(gaps), sum(l for _, l in gaps) / 1e6))
    print("  20 plus grandes zones :  [debut, taille]  |  nb 0xFF EN / cible")
    for s, l in gaps[:20]:
        ff_en = a.count(b'\xff', s, s + l)
        ff_t = b.count(b'\xff', s, s + l)
        print("     %9d %8d | %8d / %8d" % (s, l, ff_en, ff_t))
    # histogramme des tailles de zone
    import collections
    h = collections.Counter()
    for _, l in gaps:
        h[min(9, len(str(l)) - 1)] += 1
    print("  tailles de zone par ordre de grandeur :", dict(sorted(h.items())))


if __name__ == '__main__':
    main()
