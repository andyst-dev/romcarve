#!/usr/bin/env python3
"""verify_all.py <sauvegarde_avant> - memes controles cote allemand, mais separes
entre les editions deja presentes (avant) et les nouvelles (apres). C'est la seule
facon de savoir si un apport degrade ou non le mapping.

Usage : verify_all.py mapping_de_verifie.json.bak-c4
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

import json, sys
from pathlib import Path

sys.path.insert(0, f"{VFWORK}")
sys.path.insert(0, f"{WORK}")
from charmap import Charmap  # noqa: E402
from place4 import TB        # noqa: E402

WORK = Path(f"{WORK}")
CM = Charmap(f"{REF_TREE}/charmap.txt")
DE = Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba").read_bytes()

old = json.loads((WORK / sys.argv[1]).read_text())
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
old_i = {k: {i for i, _ in v} for k, v in old.items()}


def stats(rows):
    n = forme = texte = dec = 0
    for rel, off in rows:
        n += 1
        if off <= 0 or off >= len(DE):
            continue
        e = DE.find(b'\xff', off, off + 400)
        if e < 0:
            continue
        forme += 1
        body = DE[off:e]
        if body and all(x in TB for x in body):
            texte += 1
        if '?' not in CM.decode(body):
            dec += 1
    return n, forme, texte, dec


vieux, neufs = [], []
for rel, lst in cur.items():
    for i, off in lst:
        (neufs if i not in old_i.get(rel, set()) else vieux).append((rel, off))

for nom, rows in (('DEJA EN PLACE', vieux), ('NOUVELLES', neufs)):
    n, f, t, d = stats(rows)
    print('%-14s %5d editions | bien forme %5d (%5.1f%%) | octets en table %5d (%5.1f%%) | sans "?" %5d (%5.1f%%)'
          % (nom, n, f, 100.0 * f / max(1, n), t, 100.0 * t / max(1, n), d, 100.0 * d / max(1, n)))

print()
for rel in ('data/text/tv.inc', 'src/data/pokemon/pokedex_text.h',
            'src/data/text/move_descriptions.h', 'data/text/contest_strings.inc'):
    rows = [(rel, off) for i, off in cur[rel] if i not in old_i.get(rel, set())]
    print('== %s (%d nouvelles)' % (rel, len(rows)))
    for _, off in rows[:4]:
        e = DE.find(b'\xff', off, off + 400)
        print('   @%d (%d o) : %r' % (off, e - off + 1, CM.decode(DE[off:e])[:120]))
