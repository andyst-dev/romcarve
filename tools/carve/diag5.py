#!/usr/bin/env python3
"""diag5.py - la verite italienne du Nième objet de chaque region est-elle un debut
d'objet du squelette ? Teste si « ancrer sur le 2e objet » rattrape les regions dont
le 1er objet echoue (hypothese : l'objet de tete est fusionne avec le precedent par
le squelette quand aucun 0xFF ne le precede).

Ne fait aucun calcul de correlation : lecture seule, rapide.
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

import bisect, gzip, json, sys, collections
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve4 as C  # noqa: E402

LOCALES = Path(f"{REF_DIR}")
man_ref = json.loads(gzip.decompress((LOCALES / 'spanish.json.gz').read_bytes()))
man_it = json.loads(gzip.decompress((LOCALES / 'italian.json.gz').read_bytes()))

en_rom = C.ROMS['EN'].read_bytes()
en_sk = C.Skeleton(en_rom)
sk = C.Skeleton(C.ROMS['IT'].read_bytes())

verite = {}
for rel, entry in man_it['files'].items():
    for i, e in enumerate(sorted(entry['edits'])):
        verite[(rel, i)] = e[2]

loc = {rel: C.locate_file(man_ref, rel, en_rom, en_sk) for rel in man_ref['files']}
glob = []
for rel, lst in loc.items():
    for idx, p, size, k in lst:
        glob.append((p, k, rel, idx, size))
glob.sort()
regs, cur = [], [glob[0]]
for it in glob[1:]:
    if it[1] - cur[-1][1] > 1:
        regs.append(cur)
        cur = []
    cur.append(it)
regs.append(cur)
big = [r for r in regs if len(r) >= 6]


def is_start(off):
    k = bisect.bisect_left(sk.starts, off)
    return k < len(sk.starts) and sk.starts[k] == off


stats = collections.Counter()
prof = collections.Counter()   # rang du premier objet de la region qui EST un debut
for rg in big:
    ok_any = False
    first_ok = None
    for j, (p, kk, rel, idx, size) in enumerate(rg[:6]):
        t = verite.get((rel, idx))
        if t is None:
            continue
        if is_start(t):
            ok_any = True
            if first_ok is None:
                first_ok = j
    prof[first_ok] += 1
    stats['region avec au moins un debut dans ses 6 premiers objets'] += 1 if ok_any else 0
    if not ok_any:
        stats['region SANS aucun debut dans ses 6 premiers objets'] += 1

print('regions >= 6 objets : %d' % len(big))
print('rang du 1er objet de la region dont la verite est un debut de squelette :')
for j in sorted(prof, key=lambda x: (x is None, x)):
    print('   objet #%s : %d regions' % (j if j is not None else 'AUCUN', prof[j]))
print('   -> au moins un debut dans les 6 premiers : %d | aucun : %d'
      % (stats['region avec au moins un debut dans ses 6 premiers objets'],
         stats['region SANS aucun debut dans ses 6 premiers objets']))
