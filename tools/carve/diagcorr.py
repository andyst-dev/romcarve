#!/usr/bin/env python3
"""diagcorr.py - la correlation des longueurs discrimine-t-elle vraiment ?

Sur l'ORACLE : pour chaque run, on connait la VRAIE position cible (rom_offset de
la premiere edition). On compare :
   - la correlation des longueurs a la vraie position ;
   - la meilleure correlation trouvee ailleurs dans la fenetre.
Si la vraie position gagne largement, le signal est bon et ce sont les seuils ou la
fenetre qui bloquent ; sinon il faut un autre signal.

Usage : diagcorr.py <CIBLE> <manifeste>
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
import numpy as np

sys.path.insert(0, f"{WORK}")
from zones import ROMS
from place3 import file_names
from deplace import walk_pool, corr
from deplace2 import runs_of

WORK = Path(f"{WORK}")


def main():
    target = sys.argv[1]
    man = json.loads(gzip.decompress(Path(sys.argv[2]).read_bytes()))
    B = ROMS[target].read_bytes()
    syms = json.loads((WORK / 'en_symbols.json').read_text())
    rows = []
    for rel, entry in man['files'].items():
        names = file_names(rel)
        edits = sorted(entry['edits'])
        pos, ln, runs = runs_of(rel, edits, syms, names)
        for run in runs:
            if len(run) < 8 or any(ln[i] is None for i in run[:-1]):
                continue
            Len = [ln[i] for i in run[:-1]]
            truth = edits[run[0]][2]
            f = walk_pool(B, truth, len(run))
            ct = corr(Len, f[:len(Len)]) if f and len(f) == len(run) else None
            # meilleure concurrence dans +-40 Ko autour de la verite
            best = 0.0
            en0 = pos[run[0]]
            for d in range(-40000, 40001, 1):
                c = truth + d
                if c <= 0 or c >= len(B) or B[c - 1] != 0xFF:
                    continue
                g = walk_pool(B, c, len(run), quick=8)
                if g is None:
                    continue
                if corr(Len[:len(g)], g) > 0.5:
                    ff = walk_pool(B, c, len(run))
                    if ff and len(ff) == len(run):
                        best = max(best, corr(Len, ff[:len(Len)]))
            rows.append((ct, best, len(run), rel, truth, en0))
    print("%s : %d runs analyses" % (target, len(rows)))
    big = [r for r in rows if r[2] >= 25]
    print("   gros runs (>=25 objets) : %d" % len(big))
    ok = [r for r in big if r[0] is not None and r[0] >= 0.75 and r[0] > r[1] + 0.15]
    print("   vraie position bien identifiee (corr>=0.75 et marge>0.15) : %d (%.1f%%)"
          % (len(ok), 100.0 * len(ok) / max(1, len(big))))
    lowc = [r for r in big if r[0] is not None and r[0] < 0.75]
    print("   vraie position a corr < 0.75 : %d" % len(lowc))
    fail = [r for r in big if r[0] is None]
    print("   vraie position NON validable (walk) : %d" % len(fail))
    print("   correlation vraie : moyenne %.3f | concurrence : moyenne %.3f"
          % (np.mean([r[0] for r in big if r[0] is not None]) or 0,
             np.mean([r[1] for r in big]) or 0))
    print("   exemples ou la concurrence gagne :")
    for r in sorted([r for r in big if r[0] is not None and r[1] >= r[0] - 0.05],
                    key=lambda r: -(r[1] - (r[0] or 0)))[:10]:
        print("      %-52s n=%4d vraie %.3f / meilleure autre %.3f" % (r[3], r[2], r[0], r[1]))


if __name__ == '__main__':
    main()
