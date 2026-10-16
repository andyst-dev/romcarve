#!/usr/bin/env python3
"""bracket.py - ou doit se trouver le pool allemand d'un fichier.

Pour un fichier, affiche ses editions IT manquantes et, surtout, l'INTERVALLE ALLEMAND exact
donne par les deux editions RESOLUES qui l'encadrent dans l'ordre IT global. Puis balaie cet
intervalle a la recherche des enchainements d'objets allemands lisibles (le pool cherche est
le plus long d'entre eux), en verifiant que la marche du bon nombre d'objets retombe avant la
borne haute.

Usage : bracket.py <fichier> [largeur d'affichage]
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
man = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
de = C.ROMS['DE'].read_bytes()
it = C.ROMS['IT'].read_bytes()
CM = C._CM

seq = []
for f, v in man.items():
    ed = sorted(v['edits'])
    got = dict(cur.get(f, []))
    for i, e in enumerate(ed):
        seq.append((e[2], f, i, got.get(i, -1)))
seq.sort()
itofs = [s[0] for s in seq]
RES = [g for g, s in enumerate(seq) if s[3] >= 0]

rel = sys.argv[1]
W = int(sys.argv[2]) if len(sys.argv) > 2 else 60
ed = sorted(man[rel]['edits'])
have = dict(cur.get(rel, []))
miss = [i for i in range(len(ed)) if i not in have]
print('%s : %d editions, %d placees, manquants %s' % (rel, len(ed), len(have), miss))
print('plage IT %d .. %d' % (ed[0][2], ed[-1][2] + ed[-1][3]))

a, b = ed[miss[0]][2], ed[miss[-1]][2] + ed[miss[-1]][3]
k = bisect.bisect_left(RES, bisect.bisect_left(itofs, a)) - 1
while k >= 0 and seq[RES[k]][0] >= a:
    k -= 1
j = bisect.bisect_left(RES, bisect.bisect_left(itofs, b))
while j < len(RES) and seq[RES[j]][0] <= b:
    j += 1
if k < 0 or j >= len(RES):
    print("pas d'encadrement")
    sys.exit()
L, R = seq[RES[k]], seq[RES[j]]
print('ancre GAUCHE %s [%d] IT@%d -> DE@%d' % (L[1], L[2], L[0], L[3]))
print('ancre DROITE %s [%d] IT@%d -> DE@%d' % (R[1], R[2], R[0], R[3]))
lo, hi = L[3], R[3]
print('INTERVALLE ALLEMAND [%d, %d] = %d o pour %d editions' % (lo, hi, hi - lo, len(miss)))
if hi <= lo:
    print('!! intervalle INVERSE : une des deux ancres est fausse')
    sys.exit()


def clean(t):
    if not t:
        return False
    t = t.split('\\')[0].split('\n')[0]
    if not t:
        return False
    if any('\u3040' <= c <= '\u30ff' for c in t):
        return False
    return sum(c.isalnum() for c in t) / len(t) >= 0.45


print('--- runs allemands lisibles dans l\'intervalle (>= 4 objets) ---')
best = []
p = lo
run = []
while p < hi:
    z = de.find(b'\xff', p, min(hi + 1, p + 1200))
    if z < 0:
        p += 1
        run = []
        continue
    if clean(CM.decode(de[p:z])):
        run.append(p)
    else:
        if len(run) >= 4:
            best.append((len(run), run[0], run[-1]))
        run = []
    p = z + 1
if len(run) >= 4:
    best.append((len(run), run[0], run[-1]))
for n, s, e in sorted(best, reverse=True)[:6]:
    print('  %d objets  @%d .. @%d' % (n, s, e))
    q = s
    for i in range(min(n, 6)):
        z = de.find(b'\xff', q, q + 1200)
        print('      @%-9d %r' % (q, CM.decode(de[q:z]).replace('\\n', '~')[:W]))
        q = z + 1
print('--- editions IT manquantes ---')
for i in miss[:12]:
    print('   [%2d] %r' % (i, CM.decode(it[ed[i][2]:ed[i][2] + ed[i][3] - 1]).replace('\\n', '~')[:W]))
