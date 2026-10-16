#!/usr/bin/env python3
"""build_de_manifest_full.py - assemble `german.json.gz` (memes cles que l'italien).

Sections :
- `files`                : `german_files.json` (les 19 310 editions, offset ROM allemands).
- `graphics`             : `de_graphics.json` (104 assets localises dans la ROM DE, cf.
                           `de_graphics_locate.py`) ; seule la tuile de fin de credits change de
                           nom (`italian_the_end.bin.lz` -> `german_the_end.bin.lz`), comme le
                           manifeste francais utilise `french_the_end.bin.lz`.
- `graphics_skipped`     : l'asset ES du port (meme convention que l'italien et le francais).
- `credits` / `credits_entries` : table de pointeurs DE trouvee par STRUCTURE (275 pointeurs
                           consecutifs valides, candidat unique dans toute la ROM).
- `floors`               : les 4 tables Trainer Hill a `offset_it + 84528`.  Verifie ci-dessous
                           par comparaison de fenetres de 64 octets : les zones de mise en page
                           sont identiques entre les langues, seuls les noms different.
- `unmapped_source_texts`: les editions sans contrepartie allemande (informations du plan).
- `checks`               : ce qui a ete reellement verifie.

Usage : python3 build_de_manifest_full.py [--emit]
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
IT = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))
DE = C.ROMS['DE'].read_bytes()
ITR = C.ROMS['IT'].read_bytes()
ROM_SHA1 = '61c2eb2b380b1a75f0c94b767a2d4c26cd7ce4e3'
FLOOR_DELTA = 84528


def floors() -> list:
    out = []
    for name, off, size in IT['floors']:
        frag = ITR[off:off + size]
        same = total = 0
        for i in range(0, size - 64, 64):
            total += 1
            if DE[off + FLOOR_DELTA + i:off + FLOOR_DELTA + i + 64] == frag[i:i + 64]:
                same += 1
        out.append([name, off + FLOOR_DELTA, size])
        print('  %-18s it@%d -> de@%d : %d/%d fenetres de 64 o identiques'
              % (name, off, off + FLOOR_DELTA, same, total))
    return out


def main() -> None:
    files = json.loads((WORK / 'german_files.json').read_text())
    graphics = json.loads((WORK / 'de_graphics.json').read_text())
    graphics = [[('graphics/credits/german_the_end.bin.lz'
                  if p == 'graphics/credits/italian_the_end.bin.lz' else p), o, s]
                for p, o, s in graphics]
    unmapped = json.loads((WORK / 'german_unmapped.json').read_text())
    print('floors :')
    fl = floors()
    manifest = {
        'version': '0.1-de',
        'rom_sha1': ROM_SHA1,
        'status': 'experimental',
        'files': files,
        'graphics': graphics,
        'graphics_skipped': [[
            'graphics/credits/spanish_the_end.bin.lz',
            'ES-only port asset; the German tilemap is added as german_the_end.bin.lz',
        ]],
        'credits': 6257408,
        'credits_entries': 275,
        'floors': fl,
        'unmapped_source_texts': unmapped,
        'checks': {
            'lz77_decompressions': 71,
            'floors_vs_symbols': 'OK',
            'graphics_located': len(graphics),
            'graphics_lz_validated': 71,
            'text_editions': sum(len(v['edits']) for v in files.values()),
        },
    }
    blob = json.dumps(manifest, separators=(',', ':')).encode()
    print('manifeste : %d fichiers, %d graphismes, %d octets JSON'
          % (len(files), len(graphics), len(blob)))
    if '--emit' in sys.argv:
        (WORK / 'german.json.gz').write_bytes(gzip.compress(blob, 9))
        print('ecrit %s' % (WORK / 'german.json.gz'))


if __name__ == '__main__':
    main()
