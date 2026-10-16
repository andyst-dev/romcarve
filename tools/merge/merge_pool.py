#!/usr/bin/env python3
"""merge_pool.py - branche les pools places par marche (pool_DE.json).

Les fichiers concernes etaient VIDES dans le mapping (move_descriptions.h avait ete
retire par revert_bad.py, match_call_messages.h n'avait jamais ete place) : on
REMPLACE, apres avoir verifie que chaque offset tombe sur un objet 0xFF.
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
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
rom = C.ROMS['DE'].read_bytes()
mapping = json.loads((WORK / 'mapping_de_verifie.json').read_text())
pool = json.loads((WORK / 'pool_DE.json').read_text())
before = sum(len(v) for v in mapping.values())
for rel, rows in pool.items():
    for i, off in rows:
        if not (0 < off < len(rom)) or rom.find(b'\xff', off, off + 400) < 0:
            print('REJETE %s edit %d @%d' % (rel, i, off))
            sys.exit(1)
    mapping[rel] = sorted(rows)
    print('%-50s %d editions' % (rel, len(rows)))
(WORK / 'mapping_de_verifie.json').write_text(json.dumps({k: sorted(v) for k, v in mapping.items()}))
after = sum(len(v) for v in mapping.values())
print('mapping : %d -> %d editions dans %d fichiers' % (before, after, sum(1 for v in mapping.values() if v)))
