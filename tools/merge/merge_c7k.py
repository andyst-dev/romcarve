#!/usr/bin/env python3
"""merge_c7k.py - branchement du carver, qualite mesuree PAR KIND.

`merge_c7.py` mesurait la qualite d'un fichier sur TOUTES ses editions. Or un fichier
d'easy_chat a deux kinds : la chaine ('c') et l'index alphabetique ('u32'), et le
carver ne sait resoudre que le premier. Le fichier scorait donc 108/218 = 0,495 et
n'entrait jamais, alors que sa moitie texte etait exacte a 108/109.

Ici la qualite est mesuree sur les seules editions des kinds que le carver place
(`asm`, `c`, `u8array`), et seules celles-la sont ajoutees.

Usage : merge_c7k.py [seuil] [n_min]   (defaut 0.98 et 8)
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

WORK = Path(f"{WORK}")
LOCALES = Path(f"{REF_DIR}")
TEXT_KINDS = ('asm', 'c', 'u8array')
seuil = float(sys.argv[1]) if len(sys.argv) > 1 else 0.98
n_min = int(sys.argv[2]) if len(sys.argv) > 2 else 8

truth = json.loads(gzip.decompress((LOCALES / 'italian.json.gz').read_bytes()))['files']
it_rows = json.loads((WORK / 'map_it_c7.json').read_text())
de_rows = json.loads((WORK / 'mapping_DE.json').read_text())

it_by = collections.defaultdict(dict)
for m in it_rows:
    it_by[m['file']][m['edit']] = (m['target_offset'], m['target_size'])
de_by = collections.defaultdict(dict)
for m in de_rows:
    de_by[m['file']][m['edit']] = (m['target_offset'], m['target_size'])

mapping = json.loads((WORK / 'mapping_de_verifie.json').read_text())
have = {k: {i for i, _ in v} for k, v in mapping.items()}
tot_before = sum(len(v) for v in mapping.values())

sel, added = [], 0
for rel, entry in truth.items():
    edits = sorted(entry['edits'])
    idx_txt = [i for i, e in enumerate(edits) if e[4] in TEXT_KINDS]
    if len(idx_txt) < n_min:
        continue
    got = it_by.get(rel)
    if not got:
        continue
    good = sum(1 for i in idx_txt
               if got.get(i) and got[i][0] == edits[i][2] and got[i][1] == edits[i][3])
    if good / len(idx_txt) < seuil:
        continue
    derows = de_by.get(rel, {})
    miss = {i: derows[i] for i in idx_txt if i in derows and i not in have.get(rel, set())}
    if not miss:
        continue
    sel.append((len(miss), good, len(idx_txt), rel))
    mapping.setdefault(rel, [])
    for i, (off, size) in sorted(miss.items()):
        mapping[rel].append([i, off])
    added += len(miss)

sel.sort(reverse=True)
print('fichiers acceptes (kinds texte, oracle >= %.2f) : %d' % (seuil, len(sel)))
for k, g, n, rel in sel[:30]:
    print('   +%-5d %-52s oracle %d/%d' % (k, rel, g, n))
print('... total ajoute : %d' % added)

out = {k: sorted(v) for k, v in mapping.items()}
(WORK / 'mapping_de_verifie.json').write_text(json.dumps(out))
tot_after = sum(len(v) for v in out.values())
alled = sum(len(v['edits']) for v in truth.values())
print('\nmapping allemand : %d -> %d / %d editions (%.1f%% -> %.1f%%) dans %d fichiers'
      % (tot_before, tot_after, alled, 100.0 * tot_before / alled,
         100.0 * tot_after / alled, sum(1 for v in out.values() if v)))
