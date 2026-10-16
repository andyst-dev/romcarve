#!/usr/bin/env python3
"""poolfit.py - trouver le DEBUT DU POOL cible d'un fichier, par ajustement local.

Pour un fichier du manifeste :
  - cote EN, les positions des objets viennent des symboles du ROM anglais (nm) :
    labels locaux des .inc inclus. Les objets texte sont CONTIGUS et empiles, donc
    la longueur de l'objet i = adresse(i+1) - adresse(i) ;
  - cote cible, on cherche le debut du pool dans une FENETRE de decalage restreinte
    par les ancres de section voisines ; pour chaque candidat on enjambe N objets
    (termines par 0xFF) et on score :
        * validite : tous les octets dans la table de texte, bon nombre d'objets ;
        * correlation des LONGUEURS avec celles de l'EN (une traduction garde les
          longueurs relatives) ;
        * rapport de taille total plausible.

Usage : poolfit.py <CIBLE> <manifeste> <fichier> [--top N]
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

import bisect, gzip, json, re, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, f"{WORK}")
from zones import ROMS
from place3 import file_names
from place4 import TB

WORK = Path(f"{WORK}")
TREE = Path(f"{REF_TREE}")


def corr(a, b):
    n = min(len(a), len(b))
    if n < 8:
        return 0.0
    a, b = np.array(a[:n], float), np.array(b[:n], float)
    va, vb = a.std(), b.std()
    if va == 0 or vb == 0:
        return 0.0
    return float(((a - a.mean()) * (b - b.mean())).mean() / (va * vb))


def en_objects(rel, names, syms, edits):
    """positions et longueurs EN des objets texte, dans l'ordre du fichier."""
    pos, sz = [], []
    for e in sorted(edits):
        j = bisect.bisect_right([p for p, _n in names], e[0]) - 1
        nm = names[j][1] if j >= 0 else None
        c = syms.get(nm) if nm else None
        if not c:
            pos.append(None)
            sz.append(None)
            continue
        pos.append(c[0][0])
        sz.append(c[0][1] or None)
    # longueurs manquantes : par l'ecart au prochain objet connu (empiles)
    known = [(i, p) for i, p in enumerate(pos) if p is not None]
    for k in range(len(known) - 1):
        i, p = known[k]
        i2, p2 = known[k + 1]
        if sz[i] is None and i2 == i + 1:
            sz[i] = p2 - p
    return pos, sz


def walk_pool(B, c, n, tbset=TB, maxlen=400):
    """enjambe n objets empiles depuis c ; rend les positions et longueurs."""
    pos, ln = [], []
    p = c
    for _ in range(n):
        e = B.find(b'\xff', p, p + maxlen)
        if e < 0:
            return None, None
        body = B[p:e]
        if not body or any(x not in tbset for x in body):
            return None, None
        pos.append(p)
        ln.append(e + 1 - p)
        p = e + 1
    return pos, ln


def main():
    target = sys.argv[1]
    man = json.loads(gzip.decompress(Path(sys.argv[2]).read_bytes()))
    rel = sys.argv[3]
    topn = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 5
    B = ROMS[target].read_bytes()
    syms = json.loads((WORK / 'en_symbols.json').read_text())
    names = file_names(rel)
    edits = sorted(man['files'][rel]['edits'])
    pos, sz = en_objects(rel, names, syms, edits)
    n = len(edits)
    have = [(i, p) for i, p in enumerate(pos) if p is not None]
    print("%s : %d editions | %d positions EN connues" % (rel, n, len(have)))
    if len(have) != n or any(s is None for s in sz):
        print("   attribution incomplète (positions %d/%d, longueurs %d/%d)"
              % (len(have), n, sum(1 for s in sz if s), n))
    L_en = [s for s in sz if s]
    print("   longueurs EN : %d valeurs, moyenne %.1f" % (len(L_en), np.mean(L_en) if L_en else 0))

    # fenetre de recherche : decalage estime par le decalage local des ancres
    # (on prend le decalage min/max observes sur les fenetres dans +-4 Mo)
    wins = json.loads((WORK / ('anchors_sec_%s.json' % target)).read_text())
    sh = sorted(set(w[5] - w[4] for w in wins if w[4] is not None))
    en0 = pos[have[0][0]]
    ref = [w for w in wins if w[4] is not None and abs(w[4] - en0) < 1200000]
    shifts = sorted(set(w[5] - w[4] for w in ref))
    lo, hi = min(shifts), max(shifts)
    print("   fenetre de decalage locale : [%+d, %+d] (largeur %d)" % (lo, hi, hi - lo))

    cands = []
    for d in range(lo - 64, hi + 65):
        c = en0 + d
        if c < 0 or c >= len(B):
            continue
        if c == 0 or B[c - 1] != 0xFF:
            continue
        pos2, ln2 = walk_pool(B, c, n)
        if pos2 is None:
            continue
        r = corr(L_en, ln2) if L_en else 0.0
        ratio = sum(ln2) / max(1, sum(L_en))
        cands.append((r, ratio, c, ln2))
    cands.sort(key=lambda x: -x[0])
    print("   %d candidats valides" % len(cands))
    for r, ratio, c, ln2 in cands[:topn]:
        print("      @%9d (0x%08X) corr %.3f ratio longueurs %.3f | 1er objet %r"
              % (c, c + 0x08000000, r, ratio, bytes(B[c:c + 24])))
    return cands


if __name__ == '__main__':
    main()
