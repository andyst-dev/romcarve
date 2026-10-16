#!/usr/bin/env python3
"""align_file.py - reapparier un fichier a son pool allemand, par l'ORDRE ITALIEN GLOBAL.

Pour un fichier dont les offsets sont suspects, la bonne fenetre n'est pas autour des offsets
actuels (ils peuvent etre faux) mais entre les deux editions VOISINES dans l'ordre italien
global, dont les offsets allemands sont resolus : c'est l'intervalle exact ou le pool doit
tenir (methode `place_interval.py` du plan).

On enumere les objets DE de cette fenetre, puis on les apparie aux editions du fichier par
programmation dynamique sur le logarithme du ratio de taille (appariement 1 objet = 1 edition,
ordre conserve, saut d'objet penalise).  La sortie se LIT : chaque ligne donne le texte italien
et le texte allemand propose.

Usage : python3 align_file.py <fichier> [--emit-json]
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

import gzip
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
IT = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
CUR = json.loads((WORK / 'mapping_de_verifie.json').read_text())
DE = C.ROMS['DE'].read_bytes()
ITROM = C.ROMS['IT'].read_bytes()
CM = C._CM

ORDER = []
for f, v in IT.items():
    got = dict(CUR.get(f, []))
    for i, e in enumerate(sorted(v['edits'])):
        ORDER.append((e[2], f, i, got.get(i)))
ORDER.sort()


def window(rel):
    key = [(k, o) for k, (o, f, i, d) in enumerate(ORDER) if f == rel and d is not None]
    if not key:
        return None
    k0, _ = key[0]
    k1, _ = key[-1]
    lo = hi = None
    for k in range(k0 - 1, -1, -1):
        if ORDER[k][3] is not None and ORDER[k][3] < min(ORDER[q][3] for q in range(k0, k1 + 1) if ORDER[q][3]):
            lo = ORDER[k][3]
            break
    for k in range(k1 + 1, len(ORDER)):
        if ORDER[k][3] is not None and ORDER[k][3] > max(ORDER[q][3] for q in range(k0, k1 + 1) if ORDER[q][3]):
            hi = ORDER[k][3]
            break
    return lo, hi


def main():
    rel = sys.argv[1]
    eds = sorted(IT[rel]['edits'])
    have = dict(CUR.get(rel, []))
    w = window(rel)
    print('#### %s : %d editions, %d placees' % (rel, len(eds), len(have)))
    print('     fenetre (voisins de l\'ordre IT) :', w)
    lo, hi = w if w else (min(have.values()) - 3000 if have else 0,
                          max(have.values()) + 5000 if have else len(DE))
    objs = []
    p = lo
    while p < hi:
        z = DE.find(b'\xff', p, hi + 400)
        if z < 0:
            break
        objs.append((p, z - p + 1))
        p = z + 1
    print('     %d objets DE dans la fenetre' % len(objs))
    n, m = len(eds), len(objs)
    SKIP = 0.45
    INF = 1e18
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    bk = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if dp[i][j] >= INF:
                continue
            if i < n and j < m:
                c = abs(math.log(max(eds[i][3], 2) / max(objs[j][1], 2)))
                if dp[i][j] + c < dp[i + 1][j + 1]:
                    dp[i + 1][j + 1] = dp[i][j] + c
                    bk[i + 1][j + 1] = 'pair'
            if j < m and dp[i][j] + SKIP < dp[i][j + 1]:
                dp[i][j + 1] = dp[i][j] + SKIP
                bk[i][j + 1] = 'skipobj'
            if i < n and dp[i][j] + 2.0 < dp[i + 1][j]:
                dp[i + 1][j] = dp[i][j] + 2.0
                bk[i + 1][j] = 'skiped'
    if dp[n][m] >= INF:
        print('     pas d\'appariement')
        return
    pairs = {}
    i, j = n, m
    while i > 0 or j > 0:
        t = bk[i][j]
        if t == 'pair':
            pairs[i - 1] = j - 1
            i, j = i - 1, j - 1
        elif t == 'skipobj':
            j -= 1
        elif t == 'skiped':
            i -= 1
        else:
            break
    bad = 0
    for i, e in enumerate(eds):
        j = pairs.get(i)
        itt = CM.decode(ITROM[e[2]:e[2] + 46])
        cur = have.get(i)
        if j is None:
            print('   [%2d] IT@%-8d sz=%-4d %-48r  NON APPARIE' % (i, e[2], e[3], itt))
            continue
        a, ln = objs[j]
        z = a + ln - 1
        r = ln / e[3]
        ok = 0.45 <= r <= 2.6
        if not ok:
            bad += 1
        moved = '' if cur == a else ('  actuel %d' % cur if cur is not None else '  (absent)')
        print('   [%2d] IT@%-8d sz=%-4d r=%.2f %-46r %r%s%s'
              % (i, e[2], e[3], r, itt, CM.decode(DE[a:z])[:46], '' if ok else ' <<<', moved))
    print('   -> %d appariements hors bande' % bad)
    if '--emit-json' in sys.argv:
        out = {str(i): objs[j][0] for i, j in pairs.items()}
        pth = WORK / ('align_' + rel.replace('/', '_') + '.json')
        pth.write_text(json.dumps(out, indent=1))
        print('   -> ecrit', pth)


if __name__ == '__main__':
    main()
