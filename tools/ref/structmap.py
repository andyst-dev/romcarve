#!/usr/bin/env python3
"""structmap.py - carte de la ROM : ou EN et la cible sont identiques au meme offset.

Sortie : une carte en blocs de `blk` octets (defaut 4096), une lettre par bloc,
   '=' bloc entierement identique,  '-' bloc partiellement identique, '.' different.
Plus la liste des grandes plages identiques et des premiers offsets qui different.

Usage : structmap.py <CIBLE> [blk]
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

sys.path.insert(0, f"{WORK}")
from zones import ROMS


def main():
    target = sys.argv[1]
    blk = int(sys.argv[2]) if len(sys.argv) > 2 else 4096
    a = np.frombuffer(ROMS['EN'].read_bytes(), dtype=np.uint8)
    b = np.frombuffer(ROMS[target].read_bytes(), dtype=np.uint8)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    eq = (a == b)
    nb = n // blk
    grid = eq[:nb * blk].reshape(nb, blk)
    full = grid.all(axis=1)
    anyq = grid.any(axis=1)
    print("%s vs %s : %d blocs de %d o" % ('EN', target, nb, blk))
    print("   blocs entierement identiques : %d (%.1f%%) | partiels : %d | differents : %d"
          % (full.sum(), 100.0 * full.sum() / nb, (anyq & ~full).sum(), (~anyq).sum()))
    # carte : 64 blocs par ligne
    per = 64
    print("   carte (= identique, - partiel, . different) :")
    for r in range(0, nb, per):
        row = ''.join('=' if full[i] else ('-' if anyq[i] else '.')
                      for i in range(r, min(r + per, nb)))
        print("   %8X %s" % (r * blk, row))
    # premier octet qui differe
    d = np.flatnonzero(~eq)
    print("   premier offset different : %d (0x%X)" % (d[0], d[0]) if len(d) else "   ROMs identiques")
    # grandes plages identiques
    idx = np.flatnonzero(np.diff(eq.view(np.int8)))
    st = np.concatenate(([0], idx + 1))
    en = np.concatenate((idx + 1, [n]))
    runs = sorted([(int(e - s), int(s)) for s, e, v in zip(st, en, eq[st]) if v],
                  reverse=True)
    print("   20 plus grandes plages identiques :", [(s, l) for l, s in runs[:20]])


if __name__ == '__main__':
    main()
