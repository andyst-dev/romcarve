#!/usr/bin/env python3
"""drop_head.py - retire l'OBJET DE TETE de chaque bloc place par batch_pool.

Mesure : dans un pool, la marche est identique quel que soit le point de depart choisi
A L'INTERIEUR du premier objet (meme 0xFF suivant, donc meme suite) ; seule la position
de CET objet reste donc incertaine (mesure : 'SCOTT: Oh, hallo! Herzlich willkommen!'
juste, mais 'wie sieht es aus…' = suffixe de 'Na, wie sieht es aus…'). On garde tout le
reste, qui est deterministe une fois le premier objet fixe.
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

import json
import sys
from pathlib import Path

W = Path(f"{WORK}")
src = json.loads((W / sys.argv[1]).read_text())
out, dropped = {}, 0
for rel, rows in src.items():
    rows = sorted(rows)
    keep = []
    prev = None
    for i, off in rows:
        if prev is None or i != prev[0] + 1:
            dropped += 1          # tete de bloc
        else:
            keep.append([i, off])
        prev = (i, off)
    out[rel] = keep
(W / 'batch_DE2.json').write_text(json.dumps(out))
print('%s : %d editions -> %d (%d tetes retirees)' % (sys.argv[1], sum(len(v) for v in src.values()),
      sum(len(v) for v in out.values()), dropped))
