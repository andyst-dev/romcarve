#!/usr/bin/env python3
"""dechain.py - deroule la CHAINE des objets texte a partir du texte allemand source.

Pour un fichier dont on a les declarations allemandes en source (src/strings.c,
src/battle_message.c), dans l'ordre du fichier :
  - chaque litteral s'encode (longueur connue) et se cherche dans la ROM DE ;
  - l'objet i+1 commence a l'objet i + len(litteral_i) + 1 (terminateur 0xFF),
    car les objets texte sont CONTIGUS (mesure : align 1, pas de remplissage) ;
  - programmation dynamique en table de hachage : on maximise la longueur de chaine
    exacte, avec une tolerance (les rares litteraux ou la branche s'ecarte de la
    cartouche cassent la contrainte de longueur).

Sortie : anchors_<fichier>.json  [[nom, offset_DE, longueur], ...]

Usage : dechain.py <fichier> [tol]
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
sys.path.insert(0, f"{VFWORK}")
from charmap import Charmap

WORK = Path(f"{WORK}")
TREE = Path(f"{REF_TREE}")
CM = Charmap(str(TREE / 'charmap.txt'))
DE = Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba").read_bytes()
GERMAN = json.loads((WORK / 'de_german_source.json').read_text())


def occ_of(enc, cap=60):
    """occurrences du litteral, mais on ne garde que celles qui sont un OBJET :
    dans un pool contigu, un objet commence juste apres le 0xFF du precedent.
    (Seule exception : le premier objet d'un pool, accepte meme sans 0xFF avant.)"""
    out, p = [], DE.find(enc)
    while p >= 0 and len(out) < cap:
        if p > 0 and DE[p - 1] == 0xFF:
            out.append(p)
        p = DE.find(enc, p + 1)
    return out


def main():
    rel = sys.argv[1]
    tol = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    items = []
    for name, lit, off, why in GERMAN[rel]:
        try:
            enc = CM.encode(lit)
        except Exception:
            enc = None
        items.append((name, enc))
    cand = [(name, enc, occ_of(enc) if enc and len(enc) >= 5 else [])
            for name, enc in items]
    n = len(cand)
    print("%s : %d declarations, %d avec candidats" %
          (rel, n, sum(1 for c in cand if c[2])))

    # DP : best[(i, off)] = longueur de chaine terminant a l'objet i en `off`
    best = {}
    par = {}
    for off in cand[0][2]:
        best[(0, off)] = 1
    best_end = (1 if cand[0][2] else 0, 0, cand[0][2][0] if cand[0][2] else -1)
    for i in range(1, n):
        step = len(cand[i - 1][1]) + 1 if cand[i - 1][1] else None
        prevb = {off: v for (j, off), v in best.items() if j == i - 1}
        cur = {}
        for off in cand[i][2]:
            v = 1
            p = -1
            if step:
                for d in range(-tol, tol + 1):
                    pv = prevb.get(off - step + d)
                    if pv is not None and pv + 1 > v:
                        v, p = pv + 1, off - step + d
            if p >= 0:
                par[(i, off)] = p
            cur[off] = v
            if v > best_end[0]:
                best_end = (v, i, off)
        # purge : on ne garde que la chaine max par objet
        best = {k: v for k, v in best.items() if k[0] == i - 1}
        best.update({(i, off): v for off, v in cur.items()})
    print("   plus longue chaine = %d objets (sur %d declarations, %.1f%%)"
          % (best_end[0], n, 100.0 * best_end[0] / max(1, n)))
    # longueur de chaine par declaration (pour voir ou ca casse)
    lvl = {}
    for (j, off), v in best.items():
        lvl[j] = max(lvl.get(j, 0), v)

    # reconstruction depuis la fin
    chain = []
    v, i, off = best_end
    while i >= 0 and v > 0:
        chain.append((i, cand[i][0], off, len(cand[i][1]) if cand[i][1] else 0))
        p = par.get((i, off))
        v -= 1
        if p is None:
            i -= 1
            if i < 0:
                break
            off = cand[i][2][0] if cand[i][2] else -1
            if off < 0:
                break
            continue
        i -= 1
        off = p
    chain.reverse()
    print("   chaine reconstruite : %d objets, %08X -> %08X"
          % (len(chain), chain[0][2] + 0x08000000, chain[-1][2] + 0x08000000))
    holes = [(chain[k - 1][0], chain[k][0]) for k in range(1, len(chain))
             if chain[k][0] != chain[k - 1][0] + 1]
    print("   ruptures de sequence : %d %s" % (len(holes), holes[:8]))
    bad = sum(1 for (_i, _nm, o, ln) in chain if DE[o + ln] != 0xFF)
    print("   terminateur 0xFF juste : %d/%d (%.1f%%)"
          % (len(chain) - bad, len(chain), 100.0 * (len(chain) - bad) / max(1, len(chain))))
    out = WORK / ('anchors_%s.json' % Path(rel).name)
    out.write_text(json.dumps([[nm, o, ln] for (_i, nm, o, ln) in chain]))
    print("-> %s" % out)
    for (_i, nm, o, _ln) in chain[:4] + chain[-4:]:
        print("   %08X %-40s %r" % (o + 0x08000000, nm[:40], CM.decode(DE[o:o + 40])))


if __name__ == '__main__':
    main()
