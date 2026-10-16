#!/usr/bin/env python3
"""analyze_carve.py - qualite de carve3 sur l'oracle, par fichier, en separant
offset et taille (un offset juste avec une taille fausse n'est pas la meme erreur
qu'un offset faux)."""
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


import gzip, json, sys, collections
from pathlib import Path

WORK = Path(f"{WORK}")
LOCALES = Path(f"{REF_DIR}")

mapping_file = sys.argv[1] if len(sys.argv) > 1 else 'mapping_IT.json'
truth_file = sys.argv[2] if len(sys.argv) > 2 else 'italian.json.gz'

rows = json.loads((WORK / mapping_file).read_text())
man = json.loads(gzip.decompress((LOCALES / truth_file).read_bytes()))['files']

by_file = collections.defaultdict(dict)
for m in rows:
    by_file[m['file']][m['edit']] = (m['target_offset'], m['target_size'], m['stage'])

tot = dict(truth=0, placed=0, exact=0, off=0, size=0)
per = []
for rel, entry in man.items():
    edits = sorted(entry['edits'])
    tot['truth'] += len(edits)
    got = by_file.get(rel, {})
    if not got:
        continue
    tot['placed'] += len(got)
    e_ok = o_ok = s_ok = 0
    for i, e in enumerate(edits):
        g = got.get(i)
        if not g:
            continue
        if g[0] == e[2]:
            o_ok += 1
        if g[1] == e[3]:
            s_ok += 1
        if g[0] == e[2] and g[1] == e[3]:
            e_ok += 1
    tot['exact'] += e_ok
    tot['off'] += o_ok
    tot['size'] += s_ok
    per.append((len(edits), e_ok, o_ok, s_ok, len(got), rel))

print('global: verite {} | places {} | exact {} ({:.1f}%) | offset juste {} ({:.1f}% de la verite) | taille juste {} ({:.1f}%)'
      .format(tot['truth'], tot['placed'], tot['exact'], 100.0 * tot['exact'] / tot['truth'],
              tot['off'], 100.0 * tot['off'] / tot['truth'],
              tot['size'], 100.0 * tot['size'] / tot['truth']))
print()
per.sort(reverse=True)
print('%6s %6s %6s %6s %6s  %s' % ('verite', 'exact', 'off', 'taille', 'places', 'fichier'))
for n, e, o, s, p, rel in per[:40]:
    print('%6d %6d %6d %6d %6d  %s' % (n, e, o, s, p, rel))
