#!/usr/bin/env python3
"""struct_scan.py - localiser une table de structures a DEUX champs texte par enregistrement.

Mesure (manifeste italien, `src/data/contest_opponents.h`) : le fichier porte DEUX tables

  table A :  8 enregistrements de 32 octets, `.monName` a +0 (champ de 11 octets),
             `.trainerName` a +11 ;
  table B : 96 enregistrements de 64 octets (gContestOpponents), `.nickname` a +2
             (POKEMON_NAME_LENGTH+1 = 11), `.trainerName` a +13 (PLAYER_NAME_LENGTH+1 = 8).

Le motif intra-enregistrement est invariant de langue : on balaie la ROM cible a la
recherche de la base ou TOUS les enregistrements passent les deux champs (texte termine
par 0xFF dans la largeur du champ, remplissage nul apres) ET se decodent dans la langue.

Usage : struct_scan.py <CIBLE|IT> <N> <pas> <champ1> <larg1> <champ2> <larg2> [fenetre]
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

import sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

target, N, stride, o1, w1, o2, w2 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), int(sys.argv[7])
rom = C.ROMS[target].read_bytes()
N_ROM = len(rom)


def field_ok(off, width):
    """(texte, ok) - 0xFF dans la largeur, remplissage nul apres."""
    seg = rom[off:off + width]
    if len(seg) < width:
        return None, False
    z = seg.find(b'\xff')
    if z < 0:
        return None, False
    if any(b != 0 for b in seg[z + 1:]):
        return None, False
    if z == 0:
        return '', True
    try:
        t = C._CM.decode(seg[:z])
    except Exception:
        return None, False
    return t, True


def plausible(t):
    if t is None or len(t) < 2:
        return False
    al = sum(c.isalnum() for c in t)
    if al / len(t) < 0.45:
        return False
    return not any('\u3040' <= c <= '\u30ff' or '\u0400' <= c <= '\u04ff' for c in t)


def score(B):
    ok = 0
    for k in range(N):
        b = B + stride * k
        t1, o = field_ok(b + o1, w1)
        if not o or not plausible(t1):
            return ok
        t2, o = field_ok(b + o2, w2)
        if not o or not plausible(t2):
            return ok
        ok += 1
    return ok


lo = int(sys.argv[8]) if len(sys.argv) > 8 else 0
hi = int(sys.argv[9]) if len(sys.argv) > 9 else N_ROM - stride * N
best, hits = [], []
for B in range(lo, hi, 2):
    s = score(B)
    if s == N:
        hits.append(B)
    if s >= N * 0.85:
        best.append((s, B))
best.sort(reverse=True)
print('%s N=%d pas=%d  champs (%d,%d)/(%d,%d) : %d bases a 100%%, %d candidates >=85%%'
      % (target, N, stride, o1, w1, o2, w2, len(hits), len(best)))
for B in hits[:12]:
    print('   100%% base %d  ex %r / %r' % (B, field_ok(B + o1, w1)[0], field_ok(B + o2, w2)[0]))
for s, B in best[:8]:
    print('   %4d/%d base %d  ex %r / %r' % (s, N, B, field_ok(B + o1, w1)[0], field_ok(B + o2, w2)[0]))
