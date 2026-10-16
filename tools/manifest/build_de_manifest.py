#!/usr/bin/env python3
"""build_de_manifest.py - produit tools/locales/german.json.gz a partir de
~/de_work/mapping_de_verifie.json.

Mecanique (identique aux variantes FR/IT/ES) : le manifeste est un tableau de
CORRESPONDANCES entre des spans du SOURCE ANGLAIS epingle (start, end, sha256
du fichier) et des spans de la ROM DE LANGUE (rom_offset, size, kind).  Le
localiseur reecrit le span source par un initialiseur d'octets lu dans la ROM.

Donc :
  - `start`, `end`, `kind` et `sha256` sont ceux du manifeste ITALIEN (les spans
    du source anglais sont les memes pour toutes les langues, et l'arbre epingle
    est le meme) ;
  - `rom_offset` vient de `mapping_de_verifie.json`, `size` se derive de la ROM
    allemande :
      * kinds texte (`c`, `asm`, `u8array`) : jusqu'au terminateur `0xFF` inclus ;
      * kinds structurels (`u16s`, `u32`, `u8rows9`, `u8rows22`, `u16rows10`,
        `u16rows2`, `bard`, `u16array`) : la taille italienne, SAUF quand deux
        editions consecutives sont contigues cote italien - la disposition est
        alors invariante et la taille allemande est l'ecart entre les deux
        offsets allemands (c'est le cas des tableaux par lettre de
        `easy_chat_words_by_letter.h`, dont les longueurs changent avec la
        langue, et du tableau des types de `battle_message.c`).

Usage : python3 build_de_manifest.py [--emit]
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

WORK = Path(f"{WORK}")
REPO = Path(f"{REF_DIR}")
IT = json.load(gzip.open(REPO / 'tools/locales/italian.json.gz'))['files']
CUR = json.load(open(WORK / 'mapping_de_verifie.json'))
sys.path.insert(0, str(WORK))
import carve7 as C  # noqa: E402

de = C.ROMS['DE'].read_bytes()
TEXT_KINDS = {'c', 'asm', 'u8array'}


def text_size(offset: int, cap: int = 20000) -> int | None:
    z = de.find(b'\xff', offset, offset + cap)
    return None if z < 0 else z - offset + 1


def build_files() -> tuple[dict, list]:
    files, unmapped = {}, []
    for rel, entry in IT.items():
        edits = sorted(entry['edits'])
        placed = dict(CUR.get(rel, []))
        out = []
        for i, (start, end, it_off, it_size, kind) in enumerate(edits):
            off = placed.get(i)
            if off is None:
                if not CUR.get(rel):
                    pass
                continue
            if kind in TEXT_KINDS:
                size = text_size(off)
                if size is None:
                    raise SystemExit('%s[%d] : pas de 0xFF apres %d' % (rel, i, off))
            else:
                size = it_size
                # Longueurs LIBRES seulement : `u16array` (les listes de mots easy_chat) et
                # `bard` (les phonemes).  Pour `u32` et `u16s` la forme de l'initialiseur C est
                # FIXE (4 octets, 6 x u16) : prendre l'ecart entre offsets allemands fait ecrire
                # 12 octets la ou le localiseur en attend 4 (`struct.unpack("<I", data)` leve).
                if kind in ('u16array', 'bard') and i + 1 < len(edits) and edits[i + 1][2] == it_off + it_size:
                    nxt = placed.get(i + 1)
                    if nxt is not None and nxt > off:
                        size = nxt - off
            out.append([start, end, off, size, kind])
        files[rel] = {'sha256': entry['sha256'], 'edits': out}
        if len(out) != len(edits):
            missing = [i for i in range(len(edits)) if i not in placed]
            unmapped.append({'file': rel, 'missing_editions': missing,
                             'kinds': sorted({edits[i][4] for i in missing})})
    return files, unmapped


if __name__ == '__main__':
    files, unmapped = build_files()
    n_ed = sum(len(v['edits']) for v in files.values())
    print('fichiers : %d (dont %d sans aucune edition)'
          % (len(files), sum(1 for v in files.values() if not v['edits'])))
    print('editions : %d / %d' % (n_ed, sum(len(v['edits']) for v in IT.values())))
    print('fichiers incomplets : %d' % len(unmapped))
    ratios = []
    for rel, v in files.items():
        ite = {tuple(e[:2]): e for e in IT[rel]['edits']}
        for start, end, off, size, kind in v['edits']:
            it_size = ite[(start, end)][3]
            if kind in TEXT_KINDS and it_size:
                ratios.append((size / it_size, rel, start))
    ratios.sort()
    print('ratio taille DE/IT : min %.2f  median %.2f  max %.2f'
          % (ratios[0][0], ratios[len(ratios) // 2][0], ratios[-1][0]))
    print('  plus petits :', [(round(r, 2), f, s) for r, f, s in ratios[:5]])
    print('  plus grands :', [(round(r, 2), f, s) for r, f, s in ratios[-5:]])
    if '--emit' not in sys.argv:
        sys.exit(0)
    (WORK / 'german_files.json').write_text(json.dumps(files, separators=(',', ':')))
    (WORK / 'german_unmapped.json').write_text(json.dumps(unmapped, indent=1))
    print('ecrit german_files.json + german_unmapped.json')
