#!/usr/bin/env python3
"""chain.py - la ROM cible est-elle une CHAINE reconstructible ?

Pour les fichiers dont on a le texte allemand en source (src/strings.c,
src/battle_message.c), on connait la longueur encodee de chaque objet. Si les
objets se suivent dans la ROM avec un alignement fixe, alors
    offset(i+1) = offset(i) + align(len_i + 1 [terminateur])
et une seule ancre correcte suffit a derouler tout le fichier.

On mesure ici : (a) la relation entre offsets successifs trouves par recherche de
contenu, (b) le taux de respect de la regle pour align = 1, 2 et 4.
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
sys.path.insert(0, f"{VFWORK}")
from charmap import Charmap

WORK = Path(f"{WORK}")
TREE = Path(f"{REF_TREE}")
CM = Charmap(str(TREE / 'charmap.txt'))
DE = Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba").read_bytes()
GERMAN = json.loads((WORK / 'de_german_source.json').read_text())


def main():
    rel = sys.argv[1] if len(sys.argv) > 1 else 'src/battle_message.c'
    # on prend les litteraux du fichier, encodes, et on leur cherche TOUTES les
    # occurrences ; on garde ceux dont la sequence d'offsets est coherente avec la
    # regle d'enchainement (align 4) - c'est la chaine du fichier.
    items = []
    for name, lit, off, why in GERMAN[rel]:
        try:
            enc = CM.encode(lit)
        except Exception:
            continue
        if len(enc) < 8:
            continue
        items.append((name, enc))
    print("%s : %d litteraux utilisables" % (rel, len(items)))

    # occurrences de chaque litteral
    occ = []
    for name, enc in items:
        offs, p = [], DE.find(enc)
        while p >= 0 and len(offs) < 200:
            offs.append(p)
            p = DE.find(enc, p + 1)
        occ.append((name, enc, offs))
    multi = sum(1 for _n, _e, o in occ if len(o) > 1)
    print("   occurrences uniques : %d/%d" % (len(occ) - multi, len(occ)))

    # chaine : on part de chaque occurrence d'un litteral unique et on avance tant que
    # l'objet suivant respecte offset = precedent + align(len+1,4)
    for align in (1, 2, 4):
        for name, enc, offs in occ:
            pass
        # evaluation : pour chaque paire de litteraux successifs dans le FICHIER SOURCE
        # on ne connait pas l'ordre source ici -> on trie par offset trouve unique
        best = 0
        uniq = [(o[0], enc, o[0]) for _n, enc, o in occ if len(o) == 1]
        uniq.sort(key=lambda t: t[2])
        for i in range(len(uniq) - 1):
            n1, e1, o1 = uniq[i]
            n2, e2, o2 = uniq[i + 1]
            size = len(e1) + 1
            size = (size + align - 1) // align * align
            if o1 + size == o2:
                best += 1
        print("   align %d : paires consecutives coherentes %d/%d (%.1f%%)"
              % (align, best, max(1, len(uniq) - 1), 100.0 * best / max(1, len(uniq) - 1)))

    # detail : liste triee des offsets uniques avec l'ecart attendu vs reel
    uniq = sorted([(o[0], lib, o[0]) for lib, enc, o in occ if len(o) == 1], key=lambda t: t[2])
    for i in range(min(25, len(uniq) - 1)):
        n1, e1, o1 = uniq[i]
        n2, e2, o2 = uniq[i + 1]
        s = len(e1) + 1
        s4 = (s + 3) // 4 * 4
        print("      %08X %-40s len %3d | suivant a +%6d (attendu %d/%d)" %
              (o1 + 0x08000000, n1[:40], s, o2 - o1, s, s4))


if __name__ == '__main__':
    main()
