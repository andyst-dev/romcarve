#!/usr/bin/env python3
"""revert_bad.py <sauvegarde_avant> [seuil] - retire les apports de la session 4 sur
les fichiers dont le texte ALLEMAND ne tient pas la porte de qualite.

L'oracle italien prouve la methode, pas le placement allemand : un fichier peut etre
exact sur l'italien et tomber sur du remplissage en allemand (`move_descriptions.h`).
On ne retire QUE les lignes ajoutees depuis <sauvegarde_avant>, jamais celles qui
precedaient.

Usage : revert_bad.py mapping_de_verifie.json.bak-c4 0.70
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

import json, re, sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
sys.path.insert(0, f"{VFWORK}")
from charmap import Charmap  # noqa: E402

WORK = Path(f"{WORK}")
LOCALES = Path(f"{REF_DIR}")
CM = Charmap(f"{REF_TREE}/charmap.txt")
DE = Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba").read_bytes()
seuil = float(sys.argv[2]) if len(sys.argv) > 2 else 0.70

old = json.loads((WORK / sys.argv[1]).read_text())
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
old_i = {k: {i for i, _ in v} for k, v in old.items()}
# seules les editions de TEXTE se jugent au texte : un champ `u32` (index alphabetique
# d'easy_chat) echouerait forcement la porte et ferait jeter un fichier sain.
import gzip  # noqa: E402
KIND = {}
for _rel, _v in json.loads(gzip.decompress(
        (LOCALES / 'italian.json.gz').read_bytes()))['files'].items():
    for _i, _e in enumerate(sorted(_v['edits'])):
        KIND[(_rel, _i)] = _e[4]


def plausible(t):
    if not t:
        return False
    if t.count('?') / len(t) > 0.12:
        return False
    if re.search(r'[\u3000-\u9fff\u3040-\u30ff\u0400-\u04ff]', t):
        return False
    return sum(1 for c in t if c.isalnum()) / len(t) >= 0.45


out, dropped, kept = {}, [], 0
for rel, lst in cur.items():
    neuf = [(i, off) for i, off in lst
            if i not in old_i.get(rel, set()) and KIND.get((rel, i)) in ('c', 'asm', 'u8array')]
    # tout le reste est conserve tel quel : les editions deja en place ET les apports
    # d'un autre KIND (u32...), qui ne se jugent pas au texte.
    garde = [(i, off) for i, off in lst
             if not (i not in old_i.get(rel, set()) and KIND.get((rel, i)) in ('c', 'asm', 'u8array'))]
    if not neuf:
        out[rel] = garde
        continue
    ok = 0
    for i, off in neuf:
        if off <= 0 or off >= len(DE):
            continue
        e = DE.find(b'\xff', off, off + 400)
        if e > 0 and plausible(CM.decode(DE[off:e])):
            ok += 1
    part = ok / len(neuf)
    if part < seuil:
        dropped.append((part, len(neuf), rel))
        out[rel] = garde
    else:
        out[rel] = garde + neuf
        kept += len(neuf)

dropped.sort()
print('fichiers dont les apports sont RETIRES (part plausible < %.2f) : %d'
      % (seuil, len(dropped)))
for part, n, rel in dropped:
    print('   %.3f  %4d lignes  %s' % (part, n, rel))
print('\nlignes retirees : %d | conservees : %d'
      % (sum(n for _, n, _ in dropped), kept))

(WORK / 'mapping_de_verifie.json').write_text(json.dumps({k: sorted(v) for k, v in out.items()}))
tot = sum(len(v) for v in out.values())
print('mapping allemand : %d editions dans %d fichiers' % (tot, sum(1 for v in out.values() if v)))
