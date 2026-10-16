#!/usr/bin/env python3
"""walk_anchor.py - remplir TOUTES les suites manquantes qui ont une ancre des deux cotes.

Pour chaque groupe manquant [a..b] encadre par une edition resolue a gauche et une a droite :
on descend les objets depuis l'ancre gauche (les deux regles de pas sont essayees : contigue, ou
en sautant les 0x00 de remplissage) et on ne garde la suite que si la marche retombe EXACTEMENT
sur l'ancre de droite. C'est le controle le plus sur dont on dispose : il ne suppose ni la regle
de pas, ni la correlation des longueurs, et il a deja fait tomber `union_room.h`.

Sortie : walk_DE.json . Usage : walk_anchor.py [--emit] [--files f1,f2] [--verbose]
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
EMIT = '--emit' in sys.argv
VERBOSE = '--verbose' in sys.argv
only = set(sys.argv[sys.argv.index('--files') + 1].split(',')) if '--files' in sys.argv else None

man = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
de = C.ROMS['DE'].read_bytes()
it = C.ROMS['IT'].read_bytes()
CM = C._CM


def clean(t, r=0.45):
    t = t.split('\\')[0].split('\n')[0]
    if not t:
        return False
    if any('\u3040' <= c <= '\u30ff' or '\u0400' <= c <= '\u04ff' for c in t):
        return False
    return sum(c.isalnum() for c in t) / len(t) >= r


def tstart(p, z):
    for q in range(p, min(p + 140, z)):
        t = CM.decode(de[q:z])
        if t and t[0].isascii() and (t[0].isalnum() or t[0] in '{[') and clean(t):
            return q
    return p


def walk(p, n, skipz):
    """n debuts d'objets a partir de p (p inclus), puis la position suivante"""
    st = []
    for _ in range(n):
        z = de.find(b'\xff', p, p + 1200)
        if z < 0:
            return None
        st.append(p)
        p = z + 1
        if skipz:
            while de[p] == 0:
                p += 1
    return st, p


out = {}
stats = []
for rel in sorted(man):
    if only and rel not in only:
        continue
    ed = sorted(man[rel]['edits'])
    have = dict(cur.get(rel, []))
    miss = [i for i in range(len(ed)) if i not in have]
    if not miss:
        continue
    gs = []
    s = miss[0]
    for k in range(1, len(miss)):
        if miss[k] != miss[k - 1] + 1:
            gs.append((s, miss[k - 1]))
            s = miss[k]
    gs.append((s, miss[-1]))
    for a, b in gs:
        n = b - a + 1
        left, right = have.get(a - 1), have.get(b + 1)
        if left is None or right is None:
            continue
        sols = set()
        for skipz in (True, False):
            z = de.find(b'\xff', left, left + 1200)
            if z < 0:
                continue
            p = z + 1
            if skipz:
                while de[p] == 0:
                    p += 1
            w = walk(p, n, skipz)
            if w is None:
                continue
            st, nxt = w
            if nxt != right:
                continue
            sols.add(tuple(tstart(o, de.find(b'\xff', o, o + 1200)) for o in st))
        if len(sols) == 1:
            key = list(sols)[0]
            for t, o in enumerate(key):
                out.setdefault(rel, {})[a + t] = o
            if VERBOSE:
                print('   %-56s [%d..%d] %d editions (ancre %d..%d OK)'
                      % (rel, a, b, n, a - 1, b + 1), flush=True)
        elif len(sols) > 1:
            stats.append((rel, a, b, 'ambigue'))

tot = sum(len(v) for v in out.values())
print('%d editions dans %d fichiers' % (tot, len(out)))
for f in sorted(out):
    print('   %-56s %3d' % (f, len(out[f])))
for s in stats:
    print('   AMBIGU %s [%d..%d]' % (s[0], s[1], s[2]))
if EMIT and out:
    (WORK / 'walk_DE.json').write_text(json.dumps(
        {k: sorted([i, o] for i, o in v.items()) for k, v in out.items()}))
    print('-> walk_DE.json')
