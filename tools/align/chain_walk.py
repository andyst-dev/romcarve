#!/usr/bin/env python3
"""chain_walk.py - placer une suite manquante par CHAINAGE GLOBAL depuis les editions resolues.

L'ORDRE des editions est le meme dans toutes les langues (fait mesure en J1 : 359/362 fichiers
a ordre 100 % identique). Donc si l'edition E est precedee, dans l'ORDRE IT, par des editions
dont la position allemande est connue, on DESCEND la chaine objet par objet : le nombre
d'objets a consommer est exactement le nombre d'editions du manifeste qui separent E de la
derniere edition resolue. Chaque edition resolue rencontree en route est un CONTROLE (si la
marche ne tombe pas dessus, on abandonne). Aucune correlation, aucune fenetre de delta.

Usage : chain_walk.py [--emit] [--files f1,f2]
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
emit = '--emit' in sys.argv
only = set(sys.argv[sys.argv.index('--files') + 1].split(',')) if '--files' in sys.argv else None

man = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
de = C.ROMS['DE'].read_bytes()
CM = C._CM

# sequence globale des editions dans l'ordre IT
seq = []
for f, v in man.items():
    ed = sorted(v['edits'])
    for i, e in enumerate(ed):
        seq.append((e[2], f, i, e[3]))
seq.sort()
itofs = [s[0] for s in seq]

# positions resolues, indexees dans la sequence globale
known_global = {}
for g, (o, f, i, s) in enumerate(seq):
    got = dict(cur.get(f, []))
    if i in got:
        known_global[g] = got[i]


def clean(t, minratio=0.45):
    if not t:
        return False
    t = t.split('\\')[0].split('\n')[0]
    if not t:
        return False
    if any('\u3040' <= c <= '\u30ff' or '\u0400' <= c <= '\u04ff' for c in t):
        return False
    return sum(c.isalnum() for c in t) / len(t) >= minratio


def next_start(z):
    # objets CONTIGUS (regle mesuree en J1 : align 1 -> 91,5 % de coherence). Ne PAS sauter
    # les 0x00 : dans ce charmap 0x00 est l'ESPACE, un objet peut legitimement commencer par
    # une espace (mesure : marche a 2008104 au lieu de 2008102, deux octets trop loin).
    return z + 1


def text_at(p, maxlen=1200):
    z = de.find(b'\xff', p, p + maxlen)
    if z < 0:
        return None
    try:
        return CM.decode(de[p:z])
    except Exception:
        return None


# chaine AVANT : une suite n'est GARDEE que si la marche, partie d'une edition resolue,
# retombe EXACTEMENT sur l'edition resolue suivante (controle deterministe).
pos = dict(known_global)
n_new = 0
validated = []
for g in sorted(known_global):
    p = known_global[g]
    run = {}
    k = g + 1
    while k < len(seq) and seq[k][1] == seq[g][1] and len(run) < 200:
        z = de.find(b'\xff', p, p + 1200)
        if z < 0:
            break
        p = next_start(z)
        if k in known_global:
            if known_global[k] == p:
                validated.append(run)
                n_new += len(run)
            else:
                print('   chaine %d->%d : atterrit a %d au lieu de %d - ecartee'
                      % (g, k, p, known_global[k]))
            break
        t = text_at(p)
        if t is None or not clean(t):
            break
        run[k] = p
        k += 1
for run in validated:
    pos.update(run)
print('chainage avant : %d nouvelles editions (chaines validees)' % n_new)

# chaine ARRIERE : depuis chaque edition resolue, remonter
def prev_start(p):
    z = de.rfind(b'\xff', max(0, p - 1200), p)
    if z < 0:
        return None
    z2 = de.rfind(b'\xff', max(0, z - 1200), z)
    if z2 < 0:
        return None
    return next_start(z2)


n_bwd = 0
validated_b = []
for g in sorted(known_global):
    p = known_global[g]
    run = {}
    k = g - 1
    while k >= 0 and seq[k][1] == seq[g][1] and len(run) < 200:
        q = prev_start(p)
        if q is None:
            break
        if k in known_global:
            if known_global[k] == q:
                validated_b.append(run)
                n_bwd += len(run)
            break
        t = text_at(q)
        if t is None or not clean(t):
            break
        run[k] = q
        p = q
        k -= 1
for run in validated_b:
    for kk, oo in run.items():
        if kk not in pos:
            pos[kk] = oo
print('chainage arriere : %d nouvelles editions (chaines validees)' % n_bwd)

out = {}
for g in sorted(pos):
    o, f, i, s = seq[g]
    if g in known_global:
        continue
    if only and f not in only:
        continue
    out.setdefault(f, []).append([i, pos[g]])
tot = sum(len(v) for v in out.values())
print('%d editions dans %d fichiers' % (tot, len(out)))
for f in sorted(out):
    print('   %-56s %2d' % (f, len(out[f])))
if emit:
    (WORK / 'chunk_DE.json').write_text(json.dumps(out))
    print('-> chunk_DE.json')
