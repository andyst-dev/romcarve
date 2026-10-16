#!/usr/bin/env python3
"""head_show.py - montrer la fenetre avant l'ancre droite d'une edition de tete.

Usage : head_show.py <fichier> <index> [largeur]
Affiche, octet par octet, le decode de la region [ancre_droite - largeur, ancre_droite]
pour retrouver ou COMMENCE le texte allemand de l'edition <index> (prefixe de codes
de controle de longueur variable). Affiche aussi la cible italienne.
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

import gzip, json, sys
from pathlib import Path

WORK = Path(f"{WORK}")
sys.path.insert(0, str(WORK))
import carve7 as C  # noqa: E402

man = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
de = C.ROMS['DE'].read_bytes()
it = C.ROMS['IT'].read_bytes()
CM = C._CM

rel = sys.argv[1]
idx = int(sys.argv[2])
wid = int(sys.argv[3]) if len(sys.argv) > 3 else 400

ed = sorted(man[rel]['edits'])
have = dict(cur.get(rel, []))
print('fichier %s : %d editions, %d placees' % (rel, len(ed), len(have)))
print('cible IT [%d] %r' % (idx, CM.decode(it[ed[idx][2]:ed[idx][2] + ed[idx][3] - 1]).replace('\\n', '~')[:200]))
print('edition IT span @%d taille %d' % (ed[idx][2], ed[idx][3]))

# ancre droite : premiere edition resolue d'indice > idx
right = None
for i in range(idx + 1, len(ed)):
    if i in have:
        right = (i, have[i])
        break
left = None
for i in range(idx - 1, -1, -1):
    if i in have:
        left = (i, have[i])
        break
print('ancre gauche', left, 'ancre droite', right)
if right is None:
    sys.exit('pas d ancre droite')

hi = right[1]
lo = max(0, hi - wid)
print('--- decode [%d..%d] ---' % (lo, hi))
for p in range(lo, hi):
    if p + 1 < hi and de[p + 1] == 0xFF:
        pass
p = lo
while p < hi:
    z = de.find(b'\xff', p, hi + 1)
    if z < 0:
        break
    s = CM.decode(de[p:z])
    print('@%-9d %r' % (p, s.replace('\\n', '~')[:150]))
    p = z + 1

# recherche du premier mot allemand candidat : derniers octets avant l ancre
print('--- queue brute (60 o) ---')
print(repr(de[hi - 60:hi]))
