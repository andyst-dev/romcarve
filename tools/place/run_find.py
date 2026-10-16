#!/usr/bin/env python3
"""run_find.py - trouver, dans la ROM cible, le run correspondant a un pool du manifeste.

Methode : on calcule pour chaque objet 0xFF d'une ROM sa validite (objet texte lisible,
4..140 octets), puis run[i] = nombre d'objets valides consecutifs a partir de i. Le pool
d'un fichier du manifeste italien est le run qui COMMENCE a son premier offset ; on lit sa
longueur, puis on cherche dans la ROM cible les debuts de run de meme longueur (ou >=) et
on liste les candidats avec leur premier et dernier texte.

Usage : run_find.py <fichier> [debut] [fin]
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

rel = sys.argv[1]
lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
hi = int(sys.argv[3]) if len(sys.argv) > 3 else 0

with gzip.open(f"{REF_DIR}/italian.json.gz") as fh:
    man = json.load(fh)['files']
ed = sorted(man[rel]['edits'])


def plausible(rom, a, b):
    if not (4 <= b - a <= 140):
        return False
    try:
        t = C._CM.decode(rom[a:b])
    except Exception:
        return False
    if len(t) < 3:
        return False
    al = sum(c.isalnum() for c in t)
    if al / len(t) < 0.40:
        return False
    return not any('\u3040' <= c <= '\u30ff' or '\u0400' <= c <= '\u04ff' for c in t)


def runs(lang):
    rom = C.ROMS[lang].read_bytes()
    ff = [i for i, b in enumerate(rom) if b == 0xff]
    starts = [0] + [i + 1 for i in ff]
    ok = [False] * len(starts)
    for i in range(len(starts) - 1):
        ok[i] = plausible(rom, starts[i], starts[i + 1] - 1)
    run = [0] * len(starts)
    for i in range(len(starts) - 2, -1, -1):
        run[i] = 1 + run[i + 1] if ok[i] else 0
    return rom, starts, run


# run du pool italien
rom_it, st_it, run_it = runs('IT')
pos = bisect.bisect_left(st_it, ed[0][2])
print('IT : premier offset %d -> objet %d (start %d) ; run = %d' % (ed[0][2], pos, st_it[pos], run_it[pos]))
n_run = run_it[pos]

rom, starts, run = runs('DE')
hi = hi or len(rom)
cands = []
for i in range(len(starts) - 1):
    if starts[i] < lo:
        continue
    if starts[i] > hi:
        break
    if run[i] == n_run:
        cands.append(i)
print('DE : %d debuts de run de longueur %d' % (len(cands), n_run))
for i in cands[:30]:
    a = starts[i]
    b = starts[min(i + n_run, len(starts) - 1)]
    first = C._CM.decode(rom[a:rom.find(b'\xff', a, a + 60)]).split('\\')[0]
    print('   @%d..%d  %r' % (a, b, first))
