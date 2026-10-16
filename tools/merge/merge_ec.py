#!/usr/bin/env python3
"""merge_ec.py - remplace les entrees easy_chat du mapping par celles de la chaine.

La chaine (`ec_chain.py`) est AUTORITAIRE sur ces fichiers : elle lit directement,
dans la ROM allemande, le pointeur de chaque enregistrement (donc l'offset de chaque
mot) et le champ rang (offset = base + 12k + 4). Elle couvre les 18 groupes et les
deux kinds de chaque fichier, donc on REMPLACE l'existant (des entrees u32 avaient ete
posees par la chaine de pointeurs avec un decalage de +12 sur certains groupes, cf.
conditions : le rang lu etait celui de l'enregistrement suivant).
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

import json, collections
from pathlib import Path

WORK = Path(f"{WORK}")
mapping = json.loads((WORK / 'mapping_de_verifie.json').read_text())
ec = json.loads((WORK / 'ec_edits_DE.json').read_text())

before = sum(len(v) for v in mapping.values())
old_ec = sum(len(mapping.get(r, [])) for r in ec)
for rel, rows in ec.items():
    mapping[rel] = sorted(rows)
after = sum(len(v) for v in mapping.values())

(WORK / 'mapping_de_verifie.json').write_text(json.dumps({k: sorted(v) for k, v in mapping.items()}))
print('easy_chat : %d fichiers, avant %d entrees, apres %d (chaine %d)'
      % (len(ec), old_ec, sum(len(ec[r]) for r in ec), sum(len(ec[r]) for r in ec)))
print('mapping : %d -> %d editions dans %d fichiers' % (before, after, sum(1 for v in mapping.values() if v)))
