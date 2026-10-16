#!/usr/bin/env python3
"""anchors_sec.py - ancres par SECTION : ou chaque section d'entree se trouve dans la cible.

Chaque section du .map fournit jusqu'a N sondes de 32 octets reparties dans la
section (on ecarte les fenetres peu informatives). On les cherche dans la ROM
cible : une sonde trouvee en un seul endroit donne l'ANCRE de la section
(en_position -> position cible), donc le DECALAGE local.

Les sections de LANGUE (texte) ne se retrouvent pas : leurs trous seront combles
par la marche locale entre les ancres voisines.

Usage : anchors_sec.py <CIBLE> [--verbose]
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

import collections, json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, f"{WORK}")
from zones import ROMS
from secalign import load_sections

WORK = Path(f"{WORK}")
PW = 32


def probes(A, a, size, n=6):
    """fenetres informatives reparties dans la section."""
    out = []
    if size < PW:
        return out
    step = max(PW, size // (n + 1))
    p = a + min(step, max(0, size - PW))
    while p + PW <= a + size and len(out) < n:
        w = A[p:p + PW]
        if len(set(w)) >= 8 and w.count(0) <= PW // 3:
            out.append((p, bytes(w)))
        p += step
    return out


def main():
    target = sys.argv[1]
    verbose = '--verbose' in sys.argv
    A = ROMS['EN'].read_bytes()
    B = ROMS[target].read_bytes()
    secs = load_sections()
    print("%s : %d sections" % (target, len(secs)))
    rows = []
    for (sec, f, a, sz) in secs:
        ps = probes(A, a, sz)
        found = None
        nhit = 0
        for (p, w) in ps:
            occ, q = [], B.find(w)
            while q >= 0 and len(occ) < 4:
                occ.append(q)
                q = B.find(w, q + 1)
            if len(occ) == 1:
                found = (p, occ[0])
                nhit = 1
                break
            if len(occ) > 1:
                # plusieurs occurrences : on note la plus proche de la meme position
                found = (p, min(occ, key=lambda o: abs(o - p)))
                nhit = len(occ)
                break
        rows.append([sec, f, a, sz, found[0] if found else None,
                     found[1] if found else None, nhit, len(ps)])
    anch = [r for r in rows if r[4] is not None]
    print("   sections ancrees : %d/%d (%.1f%%)" % (len(anch), len(rows), 100.0 * len(anch) / len(rows)))
    print("   sections NON ancrees : %d (%.2f Mo)"
          % (len(rows) - len(anch), sum(r[3] for r in rows if r[4] is None) / 1e6))
    if verbose:
        print("   non ancrees (les 25 plus grosses) :")
        for r in sorted([r for r in rows if r[4] is None], key=lambda r: -r[3])[:25]:
            print("      %-22s %-40s @%08X %9d o" % (r[0], r[1], r[2], r[3]))
    # coherence : decalage par section ancre, en ordre
    print("   decalage (cible - EN) le long de la ROM :")
    prev = None
    for r in anch:
        d = r[5] - r[4]
        new = (prev is None) or (d != prev)
        if new or verbose:
            print("      @%08X %-40s %+8d %s" % (r[4], r[1], d, "<-- saut" if new and prev is not None else ""))
        prev = d
    out = WORK / ('anchors_sec_%s.json' % target)
    out.write_text(json.dumps(rows))
    print("-> %s" % out)


if __name__ == '__main__':
    main()
