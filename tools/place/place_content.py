#!/usr/bin/env python3
"""place_content.py - placer les editions manquantes dont les OCTETS sont identiques
dans les deux ROMs (recherche de contenu UNIQUE).

C'est la preuve la plus forte possible : les octets de l'objet (terminateur 0xFF compris)
existent tels quels dans la ROM allemande, une seule fois. Cela couvre les chaines restees
en anglais dans toutes les langues, les chaines japonaises et les litteraux a octets de
controle (clavier du nom, table de lettres d'easy_chat, etc.).

Garde-fou : les objets COURTS (< 8 octets) sont listes pour relecture, et le match doit
etre a une frontiere d'objet (0xFF ou remplissage nul avant).

Usage : place_content.py [--emit]
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

import gzip, json, sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
it = C.ROMS['IT'].read_bytes()
de = C.ROMS['DE'].read_bytes()
man = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
CM = C._CM
GOOD = {b[0] for k, b in CM.enc.items() if len(b) == 1 and k.isascii() and k.isalpha()}

out, shorts, ambiguous, nomatch = {}, [], 0, 0
for f, v in sorted(man.items()):
    ed = sorted(v['edits'])
    have = {i for i, _ in cur.get(f, [])}
    for i, e in enumerate(ed):
        if i in have:
            continue
        if e[3] < 4:
            continue
        pat = it[e[2]:e[2] + e[3]]
        k = de.find(pat)
        if k < 0:
            nomatch += 1
            continue
        if de.find(pat, k + 1) >= 0:
            ambiguous += 1
            continue
        # objet COURT : un motif de 4 a 7 octets peut coincider par hasard (':À:À').
        # On exige alors qu'il soit a une frontiere d'objet certaine (0xFF juste avant).
        if e[3] < 8 and de[k - 1] != 0xFF:
            ambiguous += 1
            continue
        out.setdefault(f, []).append([i, k])
        if e[3] < 8:
            shorts.append((f, i, k, e[3], de[max(0, k - 1)]))

tot = sum(len(v) for v in out.values())
print('%d editions placees par contenu unique dans %d fichiers' % (tot, len(out)))
print('%d sans correspondance, %d ambigues (ignorees)' % (nomatch, ambiguous))

# FILTRE DE COHERENCE : une chaine courte peut avoir une correspondance unique AILLEURS
# dans la ROM (blob graphique, autre table). Le delta d'une edition doit rester proche du
# delta median de SON fichier (mesure : naming_screen 'mnopqrs' a 8,7 Mo du groupe, alors
# que les 5 autres editions du fichier sont a 83 660).
dropped = []
for f in list(out):
    ds = sorted(off - sorted(man[f]['edits'])[i][2] for i, off in out[f])
    med = ds[len(ds) // 2]
    keep = []
    for i, off in out[f]:
        if abs((off - sorted(man[f]['edits'])[i][2]) - med) > 1024:
            dropped.append((f, i, off, off - sorted(man[f]['edits'])[i][2], med))
        else:
            keep.append([i, off])
    if keep:
        out[f] = keep
    else:
        del out[f]
for f, i, off, d, med in dropped:
    print('   ECARTE %-50s [%2d] @%d delta=%d (median %d)' % (f, i, off, d, med))
print('-> %d editions retenues' % sum(len(v) for v in out.values()))

print('\nobjets courts (<8 o) a relire :')
for f, i, k, sz, prev in shorts:
    print('   %-50s [%2d] @%d sz=%d prev=%s' % (f, i, k, sz, hex(prev)))

if '--emit' in sys.argv:
    (WORK / 'content_DE.json').write_text(json.dumps(out))
    print('-> content_DE.json')
