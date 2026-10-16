#!/usr/bin/env python3
"""show_align.py - afficher de quoi aligner a la main un groupe manquant.

Pour chaque fichier demande : les editions IT manquantes, puis TOUS les objets allemands de
l'intervalle EXACT encadre par les editions resolues voisines. On lit les deux listes et on
aligne par le sens (voir DE_PLAN.md, section « alignement par le sens »).

Usage : show_align.py f1 f2 ...
"""
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


def interval(a, b):
    k = bisect.bisect_left(RES, bisect.bisect_left(itofs, a)) - 1
    while k >= 0 and seq[RES[k]][0] >= a:
        k -= 1
    j = bisect.bisect_left(RES, bisect.bisect_left(itofs, b))
    while j < len(RES) and seq[RES[j]][0] <= b:
        j += 1
    if k < 0 or j >= len(RES):
        return None
    return seq[RES[k]][3], seq[RES[j]][3]


for rel in sys.argv[1:]:
    ed = sorted(man[rel]['edits'])
    have = dict(cur.get(rel, []))
    miss = [i for i in range(len(ed)) if i not in have]
    if not miss:
        print('== %s : complet' % rel)
        continue
    a, b = miss[0], miss[-1]
    iv = interval(ed[a][2], ed[b][2] + ed[b][3])
    print('== %s  manquants %s  intervalle %s' % (rel, miss, iv))
    if iv is None:
        continue
    lo, hi = iv
    print('--- IT ---')
    for i in miss:
        print('   [%3d] %r' % (i, CM.decode(it[ed[i][2]:ed[i][2] + ed[i][3] - 1]).replace('\\n', '~')[:70]))
    print('--- DE [%d..%d] ---' % (lo, hi))
    p = lo
    while p < hi:
        z = de.find(b'\xff', p, p + 1200)
        if z < 0:
            break
        q = p
        while q < min(z, p + 140) and not (CM.decode(de[q:z])[:1].isascii() and CM.decode(de[q:z])[:1].isalnum()):
            q += 1
        print('   @%-9d %r' % (p, CM.decode(de[p:z]).replace('\\n', '~')[:70]))
        p = z + 1
