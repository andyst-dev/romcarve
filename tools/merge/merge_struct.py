#!/usr/bin/env python3
"""merge_struct.py - branche les tables de structures resolues par delta constant.

`contest_DE.json` (208 editions, 2 tables de `contest_opponents.h`) et
`apprentice_DE.json` (112 editions, gApprentices). Les deux viennent d'une base trouvee
par balayage de structure (`struct_scan.py` / `struct_scan2.py`), oracle italien a 100 %
et delta constant identique pour les deux tables du meme fichier.
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
from pathlib import Path

WORK = Path(f"{WORK}")
mapping = json.loads((WORK / 'mapping_de_verifie.json').read_text())
before = sum(len(v) for v in mapping.values())
for name in ('contest_DE.json', 'apprentice_DE.json'):
    part = json.loads((WORK / name).read_text())
    for rel, rows in part.items():
        mapping[rel] = sorted(rows)
        print('%-50s %d editions' % (rel, len(rows)))
(WORK / 'mapping_de_verifie.json').write_text(json.dumps({k: sorted(v) for k, v in mapping.items()}))
after = sum(len(v) for v in mapping.values())
print('mapping : %d -> %d editions dans %d fichiers' % (before, after, sum(1 for v in mapping.values() if v)))
