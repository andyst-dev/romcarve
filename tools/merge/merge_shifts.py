#!/usr/bin/env python3
"""merge_shifts.py - fichiers entiers DECALES (le placeur a demarre sur le mauvais
objet : mapping[i] pointait sur le texte de l'edition i+1 ou i+2).

Rien ne detecte ce defaut automatiquement (offsets distincts, textes allemands
lisibles) : il a fallu LIRE.  Chaque entree ci-dessous est justifiee par le texte
allemand qui dit la meme chose que le texte italien de la MEME edition ; la ou
l'italien est une adaptation libre, l'anglais de reference tranche
(EN[28] « This ROULETTE thing… It's rather demanding. » = l'allemand, alors que
l'italien a reformule).

Consequence : les listes ci-dessous REMPLACENT entierement le mapping du fichier
(les offsets devenus faux - ex. 2182462, un blob de codes de controle - doivent
disparaitre).

Usage : python3 merge_shifts.py [--emit]
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

# --- data/text/pc.inc : decale de 1 -----------------------------------------
# IT[0] {FD}A accende il PC. <-> DE 2612572 {FD}A schaltet den PC ein.
# IT[5] Accesso al PC di LANETTE. <-> DE 2612719 Verbindung zu LANETTEs PC hergestellt.
PC = {0: 2612572, 1: 2612596, 2: 2612619, 3: 2612658, 4: 2612693, 5: 2612719}

# --- data/text/pc_transfer.inc : decale de 1 --------------------------------
PC_TRANSFER = {0: 2615834, 1: 2615902, 2: 2615970, 3: 2616037, 4: 2616104, 5: 2616225}

# --- data/event_scripts.s : decale de 2 a partir de [16] --------------------
# IT[14] una porta in lontananza <-> 2615299 eine Tuer geoeffnet
# IT[15] un grosso buco nella parete <-> 2615356 In der Wand ist ein grosses Loch
# IT[16] CLUB WIRELESS chiuso per lavori <-> 2615389 KOLOSSEUM wird renoviert
# IT[18]/[19] restes en anglais dans les DEUX ROMs -> preuve du decalage
EVENT_SCRIPTS = {14: 2615299, 15: 2615356, 16: 2615389, 17: 2615452, 18: 2615513,
                 19: 2615577, 20: 2615637, 21: 2615653, 22: 2615711, 23: 2615738}

# --- data/maps/MauvilleCity_GameCorner/scripts.inc : decale de 2 ------------
# IT[0] Ti trovi nel CASINO di CICLAMIPOLI <-> 2180002 Willkommen in unserer SPIELHALLE
# IT[1] Vuoi dei GETTONI...SALVADANAIO <-> 2180036 Okay, du moechtest MUENZEn...
# IT[32] Non puoi giocare senza un SALVADANAIO <-> 2182423 Du kannst ohne MUENZKORB nicht spielen
# l'ancien [31]=2182462 (blob de codes de controle) est RETIRE.
GAMECORNER = {0: 2180002, 1: 2180036, 2: 2180128, 3: 2180208, 4: 2180245, 5: 2180297,
              6: 2180325, 7: 2180393, 8: 2180459, 9: 2180491, 10: 2180515, 11: 2180552,
              12: 2180583, 13: 2180630, 14: 2180698, 15: 2180719, 16: 2180732, 17: 2180772,
              18: 2180863, 19: 2180876, 20: 2180920, 21: 2180993, 22: 2181077, 23: 2181212,
              24: 2181299, 25: 2181409, 26: 2181525, 27: 2181605, 28: 2181675, 29: 2181806,
              30: 2181954, 31: 2182077, 32: 2182423}

REPLACE = {
    'data/text/pc.inc': PC,
    'data/text/pc_transfer.inc': PC_TRANSFER,
    'data/event_scripts.s': EVENT_SCRIPTS,
    'data/maps/MauvilleCity_GameCorner/scripts.inc': GAMECORNER,
}

# --- tetes de pool recuperees (methode show_align / tete de pool) -----------
ADD = {
    'src/map_name_popup.c': {0: 5833420},     # PIRAMIDE 1o P. <-> PYRAMIDE EBENE 1
    'data/scripts/secret_base.inc': {5: 2630519},  # BASE SEGRETA -> PC <-> GEHEIMBASIS ... PC
}

if __name__ == '__main__':
    cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
    problems = []
    for rel, table in REPLACE.items():
        have = dict(cur.get(rel, []))
        if not have:
            problems.append('fichier absent du mapping : %s' % rel)
        extra = sorted(set(have) - set(table))
        missing = sorted(set(table) - set(have))
        print('%-52s remplace : %d -> %d (%d nouveaux, %d retires)'
              % (rel[-50:], len(have), len(table), len(missing), len(extra)))
        if extra:
            print('      retires : %s' % extra)
    for rel, table in ADD.items():
        have = dict(cur.get(rel, []))
        for i, o in table.items():
            if i in have:
                problems.append('%s[%d] deja place' % (rel, i))
        print('%-52s +%d edition' % (rel[-50:], len(table)))
    if problems:
        sys.exit('CONFLIT : ' + ' | '.join(problems))
    if '--emit' not in sys.argv:
        sys.exit(0)
    shutil.copy(WORK / 'mapping_de_verifie.json', WORK / 'mapping_de_verifie.json.bak-shift')
    for rel, table in REPLACE.items():
        merged = dict(cur.get(rel, []))
        merged.update(table)          # corriger/ajouter ; les index hors table sont gardes
        cur[rel] = [[i, merged[i]] for i in sorted(merged)]
    for rel, table in ADD.items():
        merged = dict(cur.get(rel, []))
        merged.update(table)
        cur[rel] = [[i, merged[i]] for i in sorted(merged)]
    (WORK / 'mapping_de_verifie.json').write_text(json.dumps(cur, separators=(',', ':')))
    n = sum(len(v) for v in cur.values())
    print('ecrit : %d editions au total, sauvegarde .bak-shift' % n)
