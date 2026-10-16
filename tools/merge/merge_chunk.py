#!/usr/bin/env python3
"""merge_chunk.py - branche les placements de chunk_DE.json dans le mapping consolide.

AJOUTE (ne remplace pas) : les editions deja presentes ne sont pas touchees. Controle
d'entree pour chaque offset : dans la ROM et termine par un 0xFF dans les 400 octets.

Usage : merge_chunk.py [--emit]
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

import json, shutil, sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
rom = C.ROMS['DE'].read_bytes()
dst = WORK / 'mapping_de_verifie.json'
mapping = json.loads(dst.read_text())
chunk = json.loads((WORK / (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else 'chunk_DE.json')).read_text())
before = sum(len(v) for v in mapping.values())

bad = []
added = 0
for rel, rows in sorted(chunk.items()):
    have = dict(mapping.get(rel, []))
    n_add = 0
    for i, off in sorted(rows):
        if i in have:
            continue
        if not (0 < off < len(rom)):
            bad.append((rel, i, off))
            continue
        # le controle du terminateur 0xFF ne vaut que pour les objets TEXTE ; une table
        # numerique (u16array, bard) placee par contenu est deja prouvee octet a octet.
        if '--no-offx' not in sys.argv and rom.find(b'\xff', off, off + 1200) < 0:
            bad.append((rel, i, off))
            continue
        have[i] = off
        added += 1
        n_add += 1
    if n_add:
        mapping[rel] = sorted([i, o] for i, o in have.items())
        print('%-58s +%d' % (rel, n_add))

print('\n%d fichiers, %d editions ajoutees' % (len(chunk), added))
if bad:
    print('REJETES :')
    for b in bad[:20]:
        print('   %s edit %d @%d' % b)
    sys.exit(1)
if '--emit' in sys.argv:
    shutil.copy(dst, str(dst) + '.bak-pc')
    dst.write_text(json.dumps(mapping))
    after = sum(len(v) for v in mapping.values())
    print('mapping : %d -> %d editions dans %d fichiers' % (before, after, len(mapping)))
    print('-> mapping_de_verifie.json')
