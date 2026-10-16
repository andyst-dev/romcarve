#!/usr/bin/env python3
"""show_file.py - montrer un fichier edition par edition, IT contre DE, avec les objets DE.

Sert a LIRE un fichier pour trancher un decalage : la colonne DE doit etre la traduction de la
colonne IT, et le ratio (taille DE jusqu'au 0xFF / taille IT) doit rester dans [0.45, 2.6].

Usage : python3 show_file.py <fichier> [nb_editions] [--objs]
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

import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
IT = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
CUR = json.loads((WORK / 'mapping_de_verifie.json').read_text())
DE = C.ROMS['DE'].read_bytes()
ITROM = C.ROMS['IT'].read_bytes()
CM = C._CM


def main():
    rel = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 10 ** 9
    eds = sorted(IT[rel]['edits'])
    have = dict(CUR.get(rel, []))
    offs = [have[i] for i in sorted(have)]
    print('#### %s : %d editions, %d placees' % (rel, len(eds), len(have)))
    if '--objs' in sys.argv and offs:
        lo, hi = min(offs) - 600, max(offs) + 900
        p = lo
        print('  -- objets DE %d..%d --' % (lo, hi))
        while p < hi:
            z = DE.find(b'\xff', p)
            if z < 0:
                break
            print('     %d..%d (%d) %r' % (p, z, z - p + 1, CM.decode(DE[p:z])[:70]))
            p = z + 1
    print('  -- editions --')
    for i, e in enumerate(eds):
        o = have.get(i)
        itt = CM.decode(ITROM[e[2]:e[2] + 52])
        if o is None:
            print('   [%2d] IT@%-8d sz=%-4d %-54r MISSING' % (i, e[2], e[3], itt))
            continue
        z = DE.find(b'\xff', o, o + 20000)
        det = CM.decode(DE[o:z])[:52]
        r = (z - o + 1) / e[3] if e[3] else 0
        flag = '  <<<' if (r < 0.45 or r > 2.6) else ''
        print('   [%2d] IT@%-8d sz=%-4d %-54r DE@%-9d r=%.2f %r%s'
              % (i, e[2], e[3], itt, o, r, det, flag))
        if i >= n:
            break


if __name__ == '__main__':
    main()
