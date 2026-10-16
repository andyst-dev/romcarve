#!/usr/bin/env python3
"""dup_audit.py - CONTROLE DE DOUBLON global du mapping allemand.

Un meme offset allemand ne peut servir deux editions que si le TEXTE ITALIEN de ces
editions est identique (gcc deduplique les chaines partagees, ex. Route112_CableCarStation
et MtChimney_CableCarStation). Si deux editions de textes IT DIFFERENTS pointent sur le
meme offset, au plus une des deux est juste : c'est un placement faux.

Sortie :
  - a l'ecran : un rapport par PAQUET (paire de fichiers + suite contigue d'offsets),
    avec le texte allemand et les textes italiens candidats ;
  - dup_report.json : les paquets, avec pour chaque candidat son offset, la taille IT,
    la taille DE et la correlation des longueurs avec le paquet allemand (PROPOSITION,
    jamais une preuve : le tri par correlation s'est trompe sur SSTidalCorridor et
    AquaHideout_B1F, il faut lire).

Usage : dup_audit.py [--runs] [--files a,b]
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

import collections, gzip, json, math, sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
man = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
it = C.ROMS['IT'].read_bytes()
de = C.ROMS['DE'].read_bytes()
CM = C._CM

ied = {f: sorted(v['edits']) for f, v in man.items()}
off2ent = collections.defaultdict(list)
for f, rows in cur.items():
    for i, o in rows:
        off2ent[o].append((f, i))


def itxt(f, i):
    e = ied[f][i]
    return CM.decode(it[e[2]:e[2] + e[3] - 1])


def detxt(o, n=90):
    z = de.find(b'\xff', o, o + 1200)
    return CM.decode(de[o:z if z >= 0 else o + n]).replace('\\n', '~')[:n]


def corr(a, b):
    n = len(a)
    if n < 3 or len(b) != n:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    if not da or not db:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (da * db)


# --- groupes fautifs
groups = {}
for o, v in off2ent.items():
    if len(v) < 2:
        continue
    if len({itxt(f, i) for f, i in v}) > 1:
        groups[o] = v

# --- paquets : (paire, suite d'offsets consecutive dans le mapping de chaque fichier)
packs = collections.defaultdict(list)
for o in sorted(groups):
    v = groups[o]
    fs = sorted({f for f, i in v})
    for a in range(len(fs)):
        for b in range(a + 1, len(fs)):
            packs[(fs[a], fs[b])].append(o)

out = []
for (A, B), offs in sorted(packs.items(), key=lambda kv: (-len(kv[1]), kv[0])):
    offs = sorted(offs)
    runs = []
    cur_run = [offs[0]]
    for o in offs[1:]:
        prev = cur_run[-1]
        ia = dict(off2ent[prev])[A]
        ib = dict(off2ent[prev])[B]
        da = ied[A][ia] if ia < len(ied[A]) else None
        db_ = ied[B][ib] if ib < len(ied[B]) else None
        contiguous = (ia + 1 == dict(off2ent[o])[A] and ib + 1 == dict(off2ent[o])[B])
        if contiguous:
            cur_run.append(o)
        else:
            runs.append(cur_run)
            cur_run = [o]
    runs.append(cur_run)
    for run in runs:
        dl = [(de.find(b'\xff', o, o + 1200) + 1 - o) if de.find(b'\xff', o, o + 1200) >= 0 else 0 for o in run]
        ta = [ied[A][dict(off2ent[o])[A]][3] for o in run]
        tb = [ied[B][dict(off2ent[o])[B]][3] for o in run]
        out.append({
            'n': len(run), 'A': A, 'B': B, 'offsets': run,
            'ia0': dict(off2ent[run[0]])[A], 'ib0': dict(off2ent[run[0]])[B],
            'corrA': corr(dl, ta), 'corrB': corr(dl, tb),
            'samples': [{'o': o, 'DE': detxt(o), 'IT_A': itxt(A, dict(off2ent[o])[A]),
                         'IT_B': itxt(B, dict(off2ent[o])[B])} for o in run[:2]],
        })

only = set(sys.argv[sys.argv.index('--files') + 1].split(',')) if '--files' in sys.argv else None
out = [p for p in out if not only or p['A'] in only or p['B'] in only]
(WORK / 'dup_report.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
tot = sum(len(p['offsets']) for p in out)
print('%d paquets, %d offsets partages fautifs, %d entrees impliquees'
      % (len(out), tot, sum(len(off2ent[o]) for o in groups)))
print('%d paquets a trancher (un paquet = une lecture)\n' % len(out))
for p in out:
    ca = '%.3f' % p['corrA'] if p['corrA'] is not None else '  -  '
    cb = '%.3f' % p['corrB'] if p['corrB'] is not None else '  -  '
    prop = 'A' if (p['corrA'] is not None and (p['corrB'] is None or p['corrA'] > p['corrB'])) else 'B'
    print('---- %2d offset(s)  prop=%s   A=%-52s [%d] corr=%s' % (p['n'], prop, p['A'], p['ia0'], ca))
    print('                              B=%-52s [%d] corr=%s' % (p['B'], p['ib0'], cb))
    for s in p['samples'][:1]:
        print('     @%-9d DE=   %s' % (s['o'], s['DE']))
        print('                IT_A= %s' % s['IT_A'][:95])
        print('                IT_B= %s' % s['IT_B'][:95])
