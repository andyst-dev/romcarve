#!/usr/bin/env python3
"""delta_audit.py - chercher les entrees FAUSSES par le delta LOCAL.

La ROM est une concatenation de sections dans un ordre fixe : l'ordre des editions est le meme
dans toutes les langues. Donc, le long de l'ordre IT global, l'ecart (offset allemand - offset
italien) varie par PALIERS mais reste LOCALEMENT lisse (mesure du plan : erreur mediane 205 o,
p90 4 866 sur 4 000 editions resolues). Une entree dont le delta s'eloigne du delta MEDIAN de
ses voisines IT est presque toujours un placement dans le pool d'un AUTRE fichier - la classe
de faux que le controle de doublon ne voit pas (aucun autre fichier ne revendique l'offset).

Sortie : les entrees suspectes (fichier, index, offset, texte allemand, delta, delta local,
ecart), triees par ecart decroissant.

Usage : delta_audit.py [seuil] [--files a,b]
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

import collections, gzip, json, statistics as st, sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
THRESH = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 50000
man = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
de = C.ROMS['DE'].read_bytes()
CM = C._CM

seq = []
for f, v in man.items():
    ed = sorted(v['edits'])
    got = dict(cur.get(f, []))
    for i, e in enumerate(ed):
        seq.append([e[2], f, i, got.get(i, -1)])
seq.sort()
res = [k for k, s in enumerate(seq) if s[3] >= 0]
deltas = {k: seq[k][3] - seq[k][0] for k in res}
K = 12
out = []
for pos, k in enumerate(res):
    near = [deltas[res[q]] for q in range(max(0, pos - K), min(len(res), pos + K + 1)) if res[q] != k]
    if len(near) < 4:
        continue
    med = st.median(near)
    d = deltas[k]
    if abs(d - med) > THRESH:
        f, i, o = seq[k][1], seq[k][2], seq[k][3]
        z = de.find(b'\xff', o, o + 1200)
        out.append((abs(d - med), f, i, o, d, med, CM.decode(de[o:z]).replace('\n', '~')[:70]))

byfile = collections.Counter(f for _, f, _, _, _, _, _ in out)
print('%d entrees suspectes (ecart > %d) dans %d fichiers' % (len(out), THRESH, len(byfile)))
print()
for gap, f, i, o, d, med, txt in sorted(out, reverse=True):
    print('%-56s [%2d] @%-9d delta %+d (local %+.0f, ecart %d)' % (f, i, o, d, med, gap))
    print('      DE=%r' % txt)
(WORK / 'delta_suspects.json').write_text(json.dumps([[f, i] for _, f, i, _, _, _, _ in out], indent=1))
print('\ntop fichiers :', byfile.most_common(15))
