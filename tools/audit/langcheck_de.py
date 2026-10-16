#!/usr/bin/env python3
"""langcheck_de.py - piege des BLOCS ANGLAIS de la ROM allemande.

Un objet place sur un bloc anglais de la ROM Smaragd est byte-identique a son
homologue anglais. On mesure donc, par fichier, la part d'objets dont les octets
allemands sont EXACTEMENT ceux de l'anglais :

  * une poignee d'identiques est normal (noms propres, formules, « POKéMON ») ;
  * une majorite d'identiques veut dire que l'ancre est tombee sur un bloc anglais.

Usage : langcheck_de.py [mapping.json] [--only-rel fichier]
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

sys.path.insert(0, f"{WORK}")
sys.path.insert(0, f"{VFWORK}")
import carve7 as C  # noqa: E402
import gzip  # noqa: E402

WORK = Path(f"{WORK}")
LOCALES = Path(f"{REF_DIR}")
mapping = json.loads((WORK / (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--')
                               else 'mapping_de_verifie.json')).read_text())

man_ref = json.loads(gzip.decompress((LOCALES / 'spanish.json.gz').read_bytes()))
en_rom = C.ROMS['EN'].read_bytes()
en_sk = C.Skeleton(en_rom)
DE = C.ROMS['DE'].read_bytes()

loc = {r: C.locate_file(man_ref, r, en_rom, en_sk) for r in man_ref['files']}

rows = []
for rel, lst in mapping.items():
    src = {idx: p for idx, p, _, _ in loc.get(rel, [])}
    if not src:
        continue
    n = idem = forme = 0
    for i, off in lst:
        p = src.get(i)
        if p is None:
            continue
        n += 1
        e_en = en_rom.find(b'\xff', p, p + 400)
        e_de = DE.find(b'\xff', off, off + 400)
        if e_en < 0 or e_de < 0:
            continue
        forme += 1
        if en_rom[p:e_en] == DE[off:e_de]:
            idem += 1
    if n:
        rows.append((idem / n, idem, n, forme, rel))

rows.sort(reverse=True)
print('%-6s %6s %6s %6s  %s' % ('part', 'ident', 'total', 'forme', 'fichier'))
for part, idem, n, forme, rel in rows[:30]:
    flag = '  <-- BLOC ANGLAIS ?' if part >= 0.5 else ''
    print('%6.3f %6d %6d %6d  %s%s' % (part, idem, n, forme, rel, flag))
suspects = [r for r in rows if r[0] >= 0.5]
print('\nfichiers suspects (>= 50 %% d objets identiques a l anglais) : %d'
      % len(suspects))
print('   editions concernees : %d' % sum(r[2] for r in suspects))
