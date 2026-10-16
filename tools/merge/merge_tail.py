#!/usr/bin/env python3
"""merge_tail.py - editions asm de la traine, verifiees a la lecture.

Chaque entree a ete relue : le texte allemand dit la meme chose que le texte
italien de la meme edition (les missions du jeu, pas seulement une longueur
plausible).  Elles viennent de `gap_fill.py` (trou encadre : le texte se
termine juste avant le voisin de droite, ou commence juste apres celui de
gauche) ; la POSITION retenue est celle du debut de texte allemand, verifiee
contre la convention du manifeste italien (meme decalage depuis le debut de
l'objet).

Usage : python3 merge_tail.py [--emit]
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
import shutil
import sys
from pathlib import Path

WORK = Path(f"{WORK}")
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())

ACCEPT = [
    ('data/maps/PetalburgCity_House2/scripts.inc', 1, 2141399,
     'Ho sfidato NORMAN una volta <-> Ich bin erst einmal gegen NORMAN angetreten'),
    ('data/maps/LilycoveCity_House1/scripts.inc', 0, 2246271,
     'I POKéMON sono compagni dell uomo <-> POKéMON sind die Partner der Menschen'),
    ('data/maps/Route119_House/scripts.inc', 0, 2605150,
     'GROTTA dei TEMPI <-> URZEITHOEHLE'),
    ('data/maps/SlateportCity_Mart/scripts.inc', 0, 2169100,
     'Al MERCATO c e merce interessante <-> Der MARKT bietet einige interessante'),
    ('data/maps/ShoalCave_LowTideLowerRoom/scripts.inc', 0, 2355729,
     'Il freddo penetrante <-> Die eisige Kaelte'),
    ('data/maps/SootopolisCity_House7/scripts.inc', 1, 2283284,
     'La grotta che collega CENERIDE <-> Die Hoehle, die XENEROVILLE mit der Welt'),
    ('src/mystery_event_msg.c', 0, 6839188,
     'Trovata una BACCA <-> Eine BEERE! Vater in der ARENA von BLUETENBURG CITY'),
]

if __name__ == '__main__':
    new = []
    for rel, i, off, note in ACCEPT:
        have = dict(cur.get(rel, []))
        if i in have:
            if have[i] != off:
                sys.exit('CONFLIT %s[%d] : deja %d, propose %d' % (rel, i, have[i], off))
            print('deja place  %s[%d] = %d' % (rel, i, off))
            continue
        new.append((rel, i, off, note))
    print('%d nouveaux' % len(new))
    for rel, i, off, note in new:
        print('  %-58s [%2d] -> %d  // %s' % (rel, i, off, note))
    if '--emit' not in sys.argv:
        sys.exit(0)
    shutil.copy(WORK / 'mapping_de_verifie.json', WORK / 'mapping_de_verifie.json.bak-tail')
    for rel, i, off, _ in new:
        cur.setdefault(rel, []).append([i, off])
        cur[rel].sort()
    (WORK / 'mapping_de_verifie.json').write_text(json.dumps(cur, separators=(',', ':')))
    print('%d editions ecrites, sauvegarde .bak-tail' % len(new))
