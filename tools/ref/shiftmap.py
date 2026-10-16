#!/usr/bin/env python3
"""shiftmap.py - structure de la ROM par tranche : donnees de langue et decalage.

Sur l'ORACLE (manifeste cible connu) : pour chaque edition dont l'offset EN et
l'offset cible sont connus, on calcule le DECALAGE d'octets (cible - EN) et on le
resume par tranche de 256 Ko, avec le nombre d'editions de la tranche.
On voit ainsi ou sont les donnees de langue et comment le decalage evolue.

Usage : shiftmap.py <CIBLE> <manifeste_cible.json.gz> [tranche]
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

import collections, gzip, json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, f"{WORK}")
from zones import ROMS

WORK = Path(f"{WORK}")


def main():
    target = sys.argv[1]
    man = json.loads(gzip.decompress(Path(sys.argv[2]).read_bytes()))
    blk = int(sys.argv[3]) if len(sys.argv) > 3 else 262144
    loc = json.loads((WORK / 'en_locate.json').read_text())
    per = collections.defaultdict(collections.Counter)
    cnt = collections.Counter()
    for rel, entry in man['files'].items():
        got = {i: p for i, p, _s in loc.get(rel, [])}
        for idx, e in enumerate(sorted(entry['edits'])):
            p = got.get(idx)
            if p is None:
                continue
            per[p // blk][e[2] - p] += 1
            cnt[p // blk] += 1
    print("%s : %d tranches de %d o | editions placees cote EN par tranche"
          % (target, len(range(0, 16777216, blk)), blk))
    print("   %8s %7s %-28s %s" % ("offset", "edits", "decalage dominant", "3 plus gros"))
    for k in sorted(per):
        top = per[k].most_common(3)
        print("   %8X %7d %-28s %s" % (k * blk, cnt[k], "%+d (%d ed.)" % (top[0][0], top[0][1]),
              ["%+d:%d" % t for t in top[1:]]))
    tot = sum(cnt.values())
    print("   total editions avec offset EN : %d" % tot)
    multi = sum(1 for k in per if len(per[k]) > 3)
    print("   tranches a plus de 3 decalages distincts : %d" % multi)


if __name__ == '__main__':
    main()
