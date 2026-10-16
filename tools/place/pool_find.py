#!/usr/bin/env python3
"""pool_find.py - placer un pool empaquete a partir du DELTA des voisins resolus.

Un pool de chaines se deplace entre langues par un delta qui DERIVE le long du pool
(le texte allemand est plus long) : le delta ne sert donc qu'a trouver le DEBUT du pool
dans la ROM cible, puis on MARCHE les objets (le nombre d'objets est invariant).

On prend donc les editions resolues les plus proches AVANT et APRES le pool dans l'ordre
des offsets italiens, on interpole leur delta, on cherche dans une fenetre le debut ou
l'objet se decode comme de la langue cible, et on descend N objets.

Usage : pool_find.py <fichier> <idx_debut> <idx_fin> [marge]
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

import bisect, gzip, json, sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
rel, i0, i1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
marge = int(sys.argv[4]) if len(sys.argv) > 4 else 400

with gzip.open(f"{REF_DIR}/italian.json.gz") as fh:
    man = json.load(fh)['files']
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
de = C.ROMS['DE'].read_bytes()

# deltas des editions resolues, dans l'ordre des offsets italiens
delts = []
for f, entry in man.items():
    ed = sorted(entry['edits'])
    got = dict(cur.get(f, []))
    for i, e in enumerate(ed):
        if i in got:
            delts.append((e[2], got[i] - e[2], f))
delts.sort()
itoffs = [d[0] for d in delts]
ed = sorted(man[rel]['edits'])
a = ed[i0][2]
b = ed[i1][2] + ed[i1][3]
lo_i = bisect.bisect_left(itoffs, a) - 1
hi_i = bisect.bisect_left(itoffs, b)
before = delts[lo_i] if lo_i >= 0 else None
after = delts[hi_i] if hi_i < len(delts) else None
print('pool IT %d..%d ; %d objets' % (a, b, i1 - i0 + 1))
print('  voisin avant : %s delta %+d (%s)' % (before[0], before[1], before[2]) if before else '  aucun avant')
print('  voisin apres : %s delta %+d (%s)' % (after[0], after[1], after[2]) if after else '  aucun apres')
d1 = before[1] if before else (after[1] if after else 0)
d2 = after[1] if after else d1


def plausible(off):
    e = de.find(b'\xff', off, off + 2000)
    if e < 0:
        return None
    try:
        t = C._CM.decode(de[off:e])
    except Exception:
        return None
    t = t.split('\\')[0].split('\n')[0]
    if len(t) < 2:
        return None
    al = sum(c.isalnum() for c in t)
    if al / len(t) < 0.40:
        return None
    if any('\u3040' <= c <= '\u30ff' or '\u0400' <= c <= '\u04ff' for c in t):
        return None
    return t


def ascii_alnum(ch):
    return ch.isascii() and ch.isalnum()


def ascii_letter(ch):
    return ch.isascii() and ch.isalpha()


it_lens = [e[3] for e in ed[i0:i1 + 1]]
cands = []
for start in range(a + d1 - marge, a + d2 + marge):
    t0 = plausible(start)
    if t0 is None or not t0[0].isalnum() or not ascii_alnum(t0[0]):
        continue
    prev = de[start - 1:start]
    if prev and ascii_letter(chr(prev[0])):
        continue
    p = start
    lens = []
    ok = 0
    n = i1 - i0 + 1
    for _ in range(n):
        q = de.find(b'\xff', p, p + 2000)
        if q < 0:
            break
        if plausible(p):
            ok += 1
        lens.append(q + 1 - p)
        p = q + 1
    if ok / n < 0.80:
        continue
    # correlation des longueurs avec l'italien (l'allemand est plus long mais proportionnel)
    m = min(len(lens), len(it_lens))
    if m < 4:
        continue
    xs, ys = it_lens[:m], lens[:m]
    mx, my = sum(xs) / m, sum(ys) / m
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(m))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    corr = num / (dx * dy) if dx and dy else 0.0
    cands.append((corr, start, p, ok / n))
cands.sort(reverse=True)
print('  %d candidats >=80%%' % len(cands))
attendu = (b + d2) if after else None
tol = max(64, (b - a) // 20)
if attendu is not None:
    print('  fin attendue ~ %d (fin IT %d + delta %+d), tolerance %d' % (attendu, b, d2, tol))
    proches = [c for c in cands if abs(c[2] - attendu) <= tol]
    print('  %d candidats dont la fin est a <=%d octets de l attendue' % (len(proches), tol))
    if proches:
        # le vrai debut commence par une LETTRE ASCII (les octets de structure qui precedent
        # decodent souvent en chiffre ou en kana) : on prend le plus petit tel debut.
        # Attention : la lettre se lit sur le texte DECODE, pas sur l'octet brut (0xC8 -> 'N').
        def first_ok(c):
            t = plausible(c[1])
            return bool(t) and t[0].isascii() and t[0].isalpha()
        lettres = [c for c in proches if first_ok(c)]
        if lettres:
            best = min(lettres, key=lambda c: c[1])
            print('  RETENU : debut %d fin %d corr %+.3f  %r' % (best[1], best[2], best[0], plausible(best[1])))
            sys.exit(0)
        best = min(proches, key=lambda c: c[1])
        print('  RETENU (sans lettre) : debut %d fin %d corr %+.3f  %r' % (best[1], best[2], best[0], plausible(best[1])))
        sys.exit(0)
print('  pas de fin concluante : classement par correlation')
if cands:
    best = max(cands, key=lambda c: c[0])
    print('  RETENU (corr) : debut %d fin %d corr %+.3f  %r' % (best[1], best[2], best[0], plausible(best[1])))
    sys.exit(0)
