#!/usr/bin/env python3
"""pool_walk.py - placer un POOL de chaines en marchant les objets 0xFF.

Deux fichiers n'avaient aucune ancre et sont des pools empaquetes : on part d'un
depart trouve par le balayage des RUNS (le plus long enchainement d'objets texte
lisibles dans la langue cible) et on descend les objets un a un ; l'edition k du
manifeste prend l'objet k.

Oracle obligatoire : la meme marche appliquee a la ROM italienne doit reproduire
les offsets du manifeste italien a l'identique.

Usage : pool_walk.py oracle <fichier> <debut> <premier_index>
        pool_walk.py map    <fichier> <debut> <premier_index>   -> pool_DE.json
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

import gzip, json, sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
mode, rel, start, first = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])

with gzip.open(f"{REF_DIR}/italian.json.gz") as fh:
    man = json.load(fh)['files']

ed = sorted(man[rel]['edits'])
idxs = list(range(first, len(ed)))

rom = C.ROMS['DE' if mode == 'map' else 'IT'].read_bytes()
rows = []
p = start
for i in idxs:
    z = rom.find(b'\xff', p, p + 400)
    if z < 0:
        print('!! pas de 0xFF apres %d (edit %d)' % (p, i))
        break
    rows.append([i, p])
    p = z + 1

if mode == 'oracle':
    good = sum(1 for i, off in rows if ed[i][2] == off)
    print('%s : %d/%d offsets exacts (%.2f%%)' % (rel, good, len(rows), 100.0 * good / max(1, len(rows))))
    for i, off in rows:
        if ed[i][2] != off:
            print('   edit %d : manifeste %d chaine %d' % (i, ed[i][2], off))
else:
    out = json.loads((WORK / 'pool_DE.json').read_text()) if (WORK / 'pool_DE.json').exists() else {}
    out[rel] = sorted(rows)
    (WORK / 'pool_DE.json').write_text(json.dumps(out))
    print('%s : %d editions -> pool_DE.json' % (rel, len(rows)))
