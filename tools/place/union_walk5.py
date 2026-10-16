#!/usr/bin/env python3
"""union_walk5.py - union_room.h : marche AVANT/ARRIERE depuis les positions resolues,
en gardant le PREFIXE PROPRE et SANS ECRASER une position deja tenue.

union_walk4 exigeait que la marche retombe pile sur la position resolue suivante. Mesure :
depuis l'entree 30 elle donne 22 objets allemands justes (verifies un a un contre l'italien)
puis decroche a l'entree 53 (objet fusionne avec des octets de structure). On garde donc le
prefixe tant que chaque objet se DECODE proprement.

Deux passes, dans cet ordre, et jamais d'ecrasement :
 1. marches AVANT depuis chaque position resolue (indices croissants) ;
 2. marches ARRIERE depuis chaque position resolue (indices decroissants), seulement pour
    les indices encore libres.
Une marche s'arrete au premier objet qui ne se decode pas proprement, et net sur tout indice
deja tenu.

Usage : union_walk5.py [--emit]
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

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
rel = 'src/data/union_room.h'
with gzip.open(f"{REF_DIR}/italian.json.gz") as fh:
    man = json.load(fh)['files']
ed = sorted(man[rel]['edits'])
de = C.ROMS['DE'].read_bytes()
it = C.ROMS['IT'].read_bytes()
CM = C._CM
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
known = dict(cur.get(rel, {}))


def clean(t, minratio=0.55):
    if not t:
        return False
    t = t.split('\\')[0].split('\n')[0]
    if not t:
        return False
    if any('\u3040' <= c <= '\u30ff' or '\u0400' <= c <= '\u04ff' for c in t):
        return False
    if t.count('?') / len(t) > 0.15:
        return False
    return sum(c.isalnum() for c in t) / len(t) >= minratio


def next_start(z):
    q = z + 1
    while q < len(de) and de[q] == 0:
        q += 1
    return q


def prev_start(p):
    z = de.rfind(b'\xff', max(0, p - 900), p)
    if z < 0:
        return None
    z2 = de.rfind(b'\xff', max(0, z - 900), z)
    if z2 < 0:
        return None
    return next_start(z2)


def text_at(p, maxlen=900):
    z = de.find(b'\xff', p, p + maxlen)
    if z < 0:
        return None
    try:
        return CM.decode(de[p:z])
    except Exception:
        return None


pos = dict(known)
bornes = sorted(known)
n_fwd = 0
for i0 in bornes:
    q = next_start(de.find(b'\xff', pos[i0], pos[i0] + 900))
    for i in range(i0 + 1, len(ed)):
        if i in pos:
            break
        t = text_at(q)
        if t is None or not clean(t):
            break
        pos[i] = q
        n_fwd += 1
        q = next_start(de.find(b'\xff', q, q + 900))
n_bwd = 0
for i1 in reversed(bornes):
    p = prev_start(pos[i1])
    for i in range(i1 - 1, -1, -1):
        if i in pos or p is None:
            break
        t = text_at(p)
        if t is None or not clean(t):
            break
        pos[i] = p
        n_bwd += 1
        p = prev_start(p)

print('nouvelles : avant %d, arriere %d' % (n_fwd, n_bwd))
print('total : %d / %d' % (len(pos), len(ed)))
print('\ncontrole IT<->DE des nouvelles entrees :')
for i in sorted(pos):
    if i not in known:
        tit = CM.decode(it[ed[i][2]:ed[i][2] + ed[i][3] - 1])
        print('   [%3d] IT %r' % (i, tit[:44]))
        print('         DE %r' % (text_at(pos[i])[:44],))
out = {rel: sorted([i, o] for i, o in pos.items())}
(WORK / 'union5_DE.json').write_text(json.dumps(out))
if '--emit' in sys.argv:
    (WORK / 'chunk_DE.json').write_text(json.dumps(out))
    print('-> chunk_DE.json')
