#!/usr/bin/env python3
"""merge_u32.py - branche les champs u32 localises, apres controle STRUCTUREL.

Un champ u32 d'easy_chat se controle sans connaitre la langue :
  - la valeur doit etre un rang alphabetique valide : 0 <= v < nombre d'enregistrements ;
  - l'octet `enabled` juste apres (offset+4) doit valoir 0 ou 1 ;
  - le pointeur 4 octets juste avant (offset-4) doit tomber dans la plage ROM.

C'est le meme genre de preuve que le pointeur de fin d'enregistrement de la forme 3.

Usage : merge_u32.py
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

import collections, gzip, json, sys
from pathlib import Path

WORK = Path(f"{WORK}")
LOCALES = Path(f"{REF_DIR}")
DE = Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba").read_bytes()

man = json.loads(gzip.decompress((LOCALES / 'italian.json.gz').read_bytes()))['files']
u32 = json.loads((WORK / 'u32_DE.json').read_text())
mapping = json.loads((WORK / 'mapping_de_verifie.json').read_text())
have = {k: {i for i, _ in v} for k, v in mapping.items()}

ok_n = bad_n = 0
for rel, rows in u32.items():
    ed = sorted(man[rel]['edits'])
    n = max((i for i, e in enumerate(ed) if e[4] == 'u32'), default=-1) + 1
    garde = []
    for i, off in rows:
        if i in have.get(rel, set()):
            continue
        if off <= 4 or off + 8 > len(DE):
            bad_n += 1
            continue
        v = int.from_bytes(DE[off:off + 4], 'little')
        en = DE[off + 4]
        ptr = int.from_bytes(DE[off - 4:off], 'little')
        if 0 <= v < n and en in (0, 1) and 0x08000000 <= ptr < 0x0A000000:
            garde.append([i, off])
            ok_n += 1
        else:
            bad_n += 1
            print('   REJETE %-52s edit %3d @%d : rang=%d (n=%d) enabled=%d ptr=0x%08X'
                  % (rel, i, off, v, n, en, ptr))
    if garde:
        mapping.setdefault(rel, []).extend(garde)

print('champs u32 acceptes : %d | rejetes : %d' % (ok_n, bad_n))
out = {k: sorted(v) for k, v in mapping.items()}
(WORK / 'mapping_de_verifie.json').write_text(json.dumps(out))
tot = sum(len(v) for v in out.values())
alled = sum(len(v['edits']) for v in man.values())
print('mapping allemand : %d / %d editions (%.1f%%) dans %d fichiers'
      % (tot, alled, 100.0 * tot / alled, sum(1 for v in out.values() if v)))
