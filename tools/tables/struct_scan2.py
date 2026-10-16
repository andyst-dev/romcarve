#!/usr/bin/env python3
"""struct_scan2.py - variante de struct_scan pour un nombre quelconque de champs texte.

Usage : struct_scan2.py <CIBLE> <N> <pas> <spec> [lo] [hi]
  spec = "off:large,off:large,..." (champs de largeur fixe, texte 0xFF-termine dedans,
         remplissage nul apres le 0xFF dans la largeur du champ ; un champ vide est
         accepte). Les champs marques '*' (off:large*) sont de la donnee non textuelle
         et ne sont pas decodes (ex. slot japonais en kana).
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

target, N, stride = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
fields = []
for part in sys.argv[4].split(','):
    raw = part.strip()
    skip = raw.endswith('*')
    o, w = raw.rstrip('*').split(':')
    fields.append((int(o), int(w), skip))
rom = C.ROMS[target].read_bytes()
N_ROM = len(rom)
lo = int(sys.argv[5]) if len(sys.argv) > 5 else 0
hi = int(sys.argv[6]) if len(sys.argv) > 6 else N_ROM - stride * N


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
        for o, w, skip in fields:
            seg = rom[b + o:b + o + w]
            if len(seg) < w:
                return ok
            z = seg.find(b'\xff')
            if z < 0 or any(seg[z + 1:]):
                return ok
            if skip:
                continue
            try:
                t = C._CM.decode(seg[:z])
            except Exception:
                return ok
            if z > 0 and not plausible(t):
                return ok
        ok += 1
    return ok


hits, best = [], []
for B in range(lo, hi, 2):
    s = score(B)
    if s == N:
        hits.append(B)
    if s >= N * 0.9:
        best.append((s, B))
best.sort(reverse=True)
print('%s N=%d pas=%d %d champs : %d bases a 100%%, %d >=90%%' % (target, N, stride, len(fields), len(hits), len(best)))
for B in hits[:10]:
    ex = []
    for o, w, skip in fields[:3]:
        seg = rom[B + o:B + o + w]
        z = seg.find(b'\xff')
        ex.append(C._CM.decode(seg[:z]) if not skip and z >= 0 else '?')
    print('   100%% base %d  ex %s' % (B, ex))
for s, B in best[:6]:
    print('   %4d/%d base %d' % (s, N, B))
