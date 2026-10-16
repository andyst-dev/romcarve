#!/usr/bin/env python3
"""anchors_de.py - ancres allemandes par resolution MONOTONE des candidats.

Le texte allemand source (bras `#elif GERMAN` de la branche amont) s'encode et se
retrouve dans la ROM Smaragd. Pour chaque declaration, plusieurs occurrences sont
possibles ; l'ordre des declarations dans le fichier est celui du ROM, donc la suite
des positions cible doit etre STRICTEMENT CROISSANTE. On resout par plus longue
sous-suite croissante, puis on verifie la contiguite (objet i+1 = objet i + len + 1).

Sortie : anchors_de_<fichier>.json -> [[nom, offset_cible, longueur], ...]
Usage : anchors_de.py <fichier>
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

import bisect, json, sys
from pathlib import Path
sys.path.insert(0, f"{VFWORK}")
from charmap import Charmap

WORK = Path(f"{WORK}")
TREE = Path(f"{REF_TREE}")
CM = Charmap(str(TREE / 'charmap.txt'))
DE = Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba").read_bytes()
GERMAN = json.loads((WORK / 'de_german_source.json').read_text())


def main():
    rel = sys.argv[1]
    items = []
    for name, lit, off, why in GERMAN[rel]:
        try:
            enc = CM.encode(lit)
        except Exception:
            enc = None
        items.append((name, enc))
    n = len(items)
    # candidats = occurrences qui sont des debuts d'objet (precede d'un 0xFF)
    cand = []
    for name, enc in items:
        offs = []
        if enc and len(enc) >= 4:
            p = DE.find(enc)
            while p >= 0 and len(offs) < 200:
                if p > 0 and DE[p - 1] == 0xFF:
                    offs.append(p)
                p = DE.find(enc, p + 1)
        cand.append(offs)
    print("%s : %d declarations | %d avec candidats | %d candidats au total"
          % (rel, n, sum(1 for c in cand if c), sum(len(c) for c in cand)))

    # plus longue sous-suite croissante : DP classique sur les indices de candidats
    NEG = -10 ** 9
    best = [1] * len(cand[0]) if cand[0] else []
    par = [None] * len(cand[0]) if cand[0] else []
    states = [(0, i, v) for i, v in enumerate(best)]
    allstates = {0: (best, par)}
    for i in range(1, n):
        cur = [1] * len(cand[i])
        pc = [None] * len(cand[i])
        prevb, prevp = allstates[i - 1]
        if cand[i] and cand[i - 1]:
            # candidats tries : pour chaque cible, le meilleur precedent d'offset <
            import bisect as bs
            arr = cand[i - 1]
            # prefixe max de longueur
            pref = [NEG] * len(arr)
            prefarg = [-1] * len(arr)
            m, arg = NEG, -1
            for k in range(len(arr)):
                if prevb[k] > m:
                    m, arg = prevb[k], k
                pref[k] = m
                prefarg[k] = arg
            for j, o in enumerate(cand[i]):
                k = bs.bisect_left(arr, o) - 1
                if k >= 0 and pref[k] > NEG:
                    cur[j] = pref[k] + 1
                    pc[j] = prefarg[k]
        allstates[i] = (cur, pc)
        if cur and max(cur) > max([v for v in best] or [NEG]):
            best = cur
    # reconstruction depuis l'etat de meilleure longueur
    endn = max(range(n), key=lambda i: max(allstates[i][0]) if allstates[i][0] else NEG)
    arr, pc = allstates[endn]
    k = max(range(len(arr)), key=lambda j: arr[j]) if arr else -1
    chain = []
    i = endn
    while i >= 0 and k is not None and k >= 0:
        chain.append((i, items[i][0], cand[i][k], len(items[i][1]) if items[i][1] else 0))
        if i == 0:
            break
        k = allstates[i][1][k]
        i -= 1
    chain.reverse()
    print("   chaine croissante : %d objets (de %d a %d)"
          % (len(chain), chain[0][0], chain[-1][0]))
    # verification : terminateur 0xFF juste et objets contigus
    good = sum(1 for (_i, _nm, o, ln) in chain if DE[o + ln] == 0xFF)
    contig = sum(1 for a, b in zip(chain, chain[1:]) if b[2] == a[2] + a[3] + 1)
    print("   terminateur 0xFF juste : %d/%d | objets contigus : %d/%d"
          % (good, len(chain), contig, max(1, len(chain) - 1)))
    out = WORK / ('anchors_de_%s.json' % Path(rel).name)
    out.write_text(json.dumps([[nm, o, ln] for (_i, nm, o, ln) in chain]))
    print("-> %s" % out)


if __name__ == '__main__':
    main()
