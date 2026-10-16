#!/usr/bin/env python3
"""enlocate.py - met en cache le placement COTE ANGLAIS des editions du manifeste
de reference (recherche de contenu en anglais : legitime). Sortie : en_locate.json

  { "<fichier>": [[edit_idx, en_offset, en_size], ...], ... }
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

import gzip, json, sys, time
from pathlib import Path
sys.path.insert(0, f"{WORK}")
import carve3

WORK = Path(f"{WORK}")
man = json.loads(gzip.decompress(Path(sys.argv[1]).read_bytes()))
en_rom = carve3.ROMS['EN'].read_bytes()
en_sk = carve3.Skeleton(en_rom)
out, lost = {}, {}
tot = 0
t0 = time.time()
for rel in man['files']:
    got = carve3.locate_file(man, rel, en_rom, en_sk)
    out[rel] = [[i, p, s] for (i, p, s, _k) in got]
    n = len(man['files'][rel]['edits'])
    tot += len(out[rel])
    if len(out[rel]) < n:
        lost[rel] = (len(out[rel]), n)
print("%d/%d editions placees cote EN (%.1f%%) en %.1f s"
      % (tot, sum(len(v['edits']) for v in man['files'].values()), 100.0 * tot /
         sum(len(v['edits']) for v in man['files'].values()), time.time() - t0))
(WORK / 'en_locate.json').write_text(json.dumps(out))
print("-> en_locate.json")
if lost:
    print("fichiers incomplets : %d (total %d editions perdues)"
          % (len(lost), sum(n - g for g, n in lost.values())))
    for rel, (g, n) in sorted(lost.items(), key=lambda kv: -(kv[1][1] - kv[1][0]))[:15]:
        print("   %-58s %d/%d" % (rel, g, n))
