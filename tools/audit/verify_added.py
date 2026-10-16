#!/usr/bin/env python3
"""verify_added.py - controle COTE ALLEMAND des editions ajoutees par carve4.

Ne reecrit rien (verify_de.py, lui, reconstruit le mapping depuis gmap3 : ne pas le
lancer ici). On compare le mapping courant a une sauvegarde et on mesure, sur les
seules lignes nouvelles :

  1. objet bien forme : 0xFF juste avant (sauf en tete de region) + terminateur 0xFF ;
  2. tous les octets appartiennent a la table de texte du charmap ;
  3. le texte se decode sans '?' (premiers 200 caracteres).

Usage : verify_added.py <sauvegarde.json> [mapping.json]
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

import gzip, json, sys, collections
from pathlib import Path

sys.path.insert(0, f"{VFWORK}")
sys.path.insert(0, f"{WORK}")
from charmap import Charmap          # noqa: E402
from place4 import TB                # noqa: E402

WORK = Path(f"{WORK}")
TREE = Path(f"{REF_TREE}")
CM = Charmap(str(TREE / 'charmap.txt'))
DE = Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba").read_bytes()

old = json.loads((WORK / sys.argv[1]).read_text())
cur = json.loads((WORK / (sys.argv[2] if len(sys.argv) > 2 else 'mapping_de_verifie.json')).read_text())
old_i = {k: {i for i, _ in v} for k, v in old.items()}

new = collections.defaultdict(list)
for rel, lst in cur.items():
    for i, off in lst:
        if i not in old_i.get(rel, set()):
            new[rel].append((i, off))

tot = sum(len(v) for v in new.values())
print('editions nouvelles : %d dans %d fichiers' % (tot, len(new)))

shape = text = dec = 0
perfile = []
for rel, rows in new.items():
    a = b = c = 0
    for i, off in rows:
        if off <= 0 or off >= len(DE):
            continue
        if DE[off - 1] != 0xFF:
            # legal en tete de region : le premier objet du fichier n'est pas precede d'un 0xFF
            pass
        e = DE.find(b'\xff', off, off + 400)
        if e < 0:
            continue
        a += 1
        body = DE[off:e]
        if body and all(x in TB for x in body):
            b += 1
        t = CM.decode(body)
        if '?' not in t[:200]:
            c += 1
    shape += a
    text += b
    dec += c
    perfile.append((len(rows), a, b, c, rel))

print('   objet bien forme (terminateur 0xFF < 400 o) : %d/%d' % (shape, tot))
print('   tous les octets dans la table de texte      : %d/%d' % (text, tot))
print('   texte decodable sans "?"                    : %d/%d' % (dec, tot))
perfile.sort(reverse=True)
print()
print('%6s %6s %6s %6s  %s' % ('lignes', 'forme', 'texte', 'decod', 'fichier'))
for n, a, b, c, rel in perfile:
    print('%6d %6d %6d %6d  %s' % (n, a, b, c, rel))
