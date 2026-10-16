#!/usr/bin/env python3
"""probe_u32.py <fichier> - les champs `u32` d'un fichier (index alphabetique des
mots easy_chat) sont-ils localisables par la CHAINE DE POINTEURS du tableau ?

Enregistrement mesure (12 octets) : .text (4) + .alphabeticalOrder (4) + .enabled (1)
+ 3 de remplissage. L'ordre des enregistrements est celui des EC_INDEX, identique dans
toutes les langues, et l'edition `u32` du manifeste pointe sur le champ a +4.

On reconstruit donc, cote ITALIEN, la suite des pointeurs `(idx -> adresse du mot)`,
on la traduit en adresses ALLEMANDES via les editions `c` deja resolues, et on cherche
cette suite dans la ROM allemande (pas de 12).

Usage : probe_u32.py src/data/easy_chat/easy_chat_group_status.h
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
LOCALES = Path(f"{REF_DIR}")
rel = sys.argv[1]
it_rom = C.ROMS['IT'].read_bytes()
de_rom = C.ROMS['DE'].read_bytes()
man = json.loads(gzip.decompress((LOCALES / 'italian.json.gz').read_bytes()))['files']
mapping = json.loads((WORK / 'mapping_de_verifie.json').read_text())
de_of = {i: off for i, off in mapping.get(rel, [])}

ed = sorted(man[rel]['edits'])
u32 = [(i, e) for i, e in enumerate(ed) if e[4] in ('u32', 'u16s')]
txt = [(i, e) for i, e in enumerate(ed) if e[4] in ('c', 'asm', 'u8array')]
print('%s : %d editions | %d u32 | %d texte' % (rel, len(ed), len(u32), len(txt)))

# base italienne du tableau : on prend le plus petit offset u32 et on verifie le pas
base_it = min(e[2] for _, e in u32) - 4
pas = 12
idx_of = {}
for i, e in sorted(u32, key=lambda t: t[1][2]):
    d = e[2] - 4 - base_it
    if d % pas:
        print('   PAS INCORRECT pour l edition %d (d=%d)' % (i, d))
    idx_of[i] = d // pas
print('base IT supposee %d | indices %d..%d' % (base_it, min(idx_of.values()), max(idx_of.values())))

# table adresse IT -> adresse DE, via les editions texte
addr = {}
for i, e in txt:
    if i in de_of:
        addr[0x08000000 + e[2]] = 0x08000000 + de_of[i]

# suite attendue cote DE, dans l'ordre des indices
attendu = {}
for i, e in u32:
    ptr_it = int.from_bytes(it_rom[e[2] - 4:e[2]], 'little')
    if ptr_it in addr:
        attendu[idx_of[i]] = addr[ptr_it]
print('enregistrements dont le pointeur est traduisible : %d/%d' % (len(attendu), len(u32)))
if len(attendu) < 8:
    sys.exit('trop peu pour chercher')

# recherche de la suite dans la ROM DE
cible = sorted(attendu)
n = len(cible)
best = None
lo = int.from_bytes(de_rom[0:4], 'little')
for b in range(0, len(de_rom) - 4, 4):
    if int.from_bytes(de_rom[b:b + 4], 'little') != attendu[cible[0]]:
        continue
    b0 = b - cible[0] * pas
    if b0 < 0:
        continue
    ok = sum(1 for k in cible
             if int.from_bytes(de_rom[b0 + k * pas:b0 + k * pas + 4], 'little') == attendu[k])
    if best is None or ok > best[1]:
        best = (b0, ok)
print('meilleure base DE : %s | %d/%d pointeurs concordants' % (best, best[1] if best else 0, n))
if best and best[1] >= n * 0.9:
    b0 = best[0]
    print('   -> controle des champs : les valeurs u32 lues a +4 pour 6 indices :')
    for k in cible[:6]:
        v = int.from_bytes(de_rom[b0 + k * pas + 4:b0 + k * pas + 8], 'little')
        print('      idx %3d : valeur DE = %d' % (k, v))
    print('   DE offsets u32 pour les 4 premieres editions :',
          [b0 + idx_of[i] * pas + 4 for i, _ in u32[:4]])
    print('   verite IT attendue (indicative) :', [e[2] for _, e in u32[:4]])
