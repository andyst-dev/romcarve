#!/usr/bin/env python3
"""u32_table.py - localiser les champs NUMERIQUES (`u32`) des tableaux easy_chat.

Mesure (voir probe_u32.py) : un enregistrement fait 12 octets -
`.text` (4) + `.alphabeticalOrder` (4) + `.enabled` (1) + 3 de remplissage -
et l'edition `u32` du manifeste pointe le champ a +4. L'ordre des enregistrements est
celui des EC_INDEX, identique dans toutes les langues ; seules les VALEURS changent
(l'index alphabetique est propre a la langue) : c'est exactement pourquoi le contenu
ne sert pas d'ancre et que la CHAINE DE POINTEURS, elle, sert.

Methode : on reconstruit cote ITALIEN la suite (indice -> adresse du mot), on la
traduit en adresses de la langue cible via les editions texte deja resolues, puis on
cherche la suite dans la ROM cible au pas de 12. 90 % de pointeurs concordants sur au
moins 8 enregistrements = ancre.

Modes :
  u32_table.py oracle IT      -> compare aux offsets `u32` du manifeste italien
  u32_table.py map    DE      -> ecrit u32_DE.json
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
PAS = 12
mode, target = sys.argv[1], sys.argv[2]

man = json.loads(gzip.decompress((LOCALES / 'italian.json.gz').read_bytes()))['files']

if target == 'IT':
    # oracle : les offset texte viennent du manifeste italien lui-meme (verite)
    off_by = {rel: {i: e[2] for i, e in enumerate(sorted(v['edits']))}
              for rel, v in man.items()}
else:
    off_by = {rel: {i: off for i, off in rows}
              for rel, rows in json.loads((WORK / 'mapping_de_verifie.json').read_text()).items()}

it_rom = C.ROMS['IT'].read_bytes()
tg_rom = C.ROMS[target].read_bytes()

out, stats = {}, {'fichiers': 0, 'ancres': 0, 'editions': 0, 'essais': 0}
for rel, entry in man.items():
    ed = sorted(entry['edits'])
    u32 = [(i, e) for i, e in enumerate(ed) if e[4] == 'u32']
    if len(u32) < 8:
        continue
    stats['essais'] += 1
    txt = [(i, e) for i, e in enumerate(ed) if e[4] in ('c', 'asm', 'u8array')]

    it_off = {i: e[2] for i, e in enumerate(ed)} if target == 'IT' else None
    base_it = min(e[2] for _, e in u32) - 4
    idx_of, skips = {}, 0
    for i, e in u32:
        d = e[2] - 4 - base_it
        if d % PAS:
            skips += 1
            continue
        idx_of[i] = d // PAS

    addr = {}
    got = off_by.get(rel, {})
    for i, e in txt:
        src = e[2] if target == 'IT' else got.get(i)
        if src is None:
            continue
        addr[0x08000000 + e[2]] = 0x08000000 + src

    attendu = {}
    for i, e in u32:
        if i not in idx_of:
            continue
        ptr = int.from_bytes(it_rom[e[2] - 4:e[2]], 'little')
        if ptr in addr:
            attendu[idx_of[i]] = addr[ptr]
    if len(attendu) < 8:
        continue

    cible = sorted(attendu)
    best = None
    needle = attendu[cible[0]].to_bytes(4, 'little')
    p = tg_rom.find(needle, 0)
    while p >= 0:
        b0 = p - cible[0] * PAS
        if b0 >= 0 and b0 + (cible[-1] + 1) * PAS + 4 <= len(tg_rom):
            ok = sum(1 for k in cible
                     if int.from_bytes(tg_rom[b0 + k * PAS:b0 + k * PAS + 4], 'little') == attendu[k])
            if best is None or ok > best[1]:
                best = (b0, ok)
        p = tg_rom.find(needle, p + 1)
    if not best or best[1] < 0.9 * len(cible):
        continue
    b0 = best[0]
    stats['fichiers'] += 1
    stats['ancres'] += 1
    rows = []
    for i, e in u32:
        if i not in idx_of:
            continue
        rows.append([i, b0 + idx_of[i] * PAS + 4])
    stats['editions'] += len(rows)
    out[rel] = rows

print('%s -> %s : %d fichiers ancrees, %d editions u32 localisees (%d fichiers essayes)'
      % (mode, target, stats['ancres'], stats['editions'], stats['essais']))
if mode == 'oracle':
    good = tot = 0
    for rel, rows in out.items():
        ed = sorted(man[rel]['edits'])
        for i, off in rows:
            tot += 1
            if off == ed[i][2]:
                good += 1
    print('ORACLE u32 %s : %d/%d offsets exacts (%.2f%%)' % (target, good, tot, 100.0 * good / max(1, tot)))
else:
    (WORK / ('u32_%s.json' % target)).write_text(json.dumps(out))
    print('-> u32_%s.json' % target)
