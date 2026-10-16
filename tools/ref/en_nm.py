#!/usr/bin/env python3
"""en_nm.py - table de symboles COMPLETE du ROM anglais depuis en.elf.

Le .map de ld ne liste que les symboles GLOBAUX : les labels des .inc (locaux au
fichier objet) en sont absents. `nm` sur l'ELF linke les voit tous (313 152
symboles), avec adresse et taille quand elle existe.

Sortie : en_symbols.json  { "nom": [[offset_rom, taille, type], ...] }
         (liste : un nom peut exister dans plusieurs fichiers objets)
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

import json, subprocess, sys
from pathlib import Path

WORK = Path(f"{WORK}")
ELF = WORK / 'en.elf'
ROM_LO, ROM_HI = 0x08000000, 0x09000000
WANT = set('RrDdTtBbVvWwAa')


def main():
    out = subprocess.run(['nm', '-S', str(ELF)], capture_output=True, text=True)
    if out.returncode != 0:
        print("nm a echoue:", out.stderr[:400])
        sys.exit(1)
    syms = {}
    n_line = n_keep = 0
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3:
            addr, typ, name = parts
            size = 0
        elif len(parts) == 4:
            addr, size, typ, name = parts
            try:
                size = int(size, 16)
            except ValueError:
                continue
        else:
            continue
        n_line += 1
        if typ not in WANT:
            continue
        try:
            a = int(addr, 16)
        except ValueError:
            continue
        if not (ROM_LO <= a < ROM_HI):
            continue
        if name.startswith('.') or name.startswith('$'):
            continue
        syms.setdefault(name, []).append([a - ROM_LO, size, typ])
        n_keep += 1
    multi = sum(1 for k, v in syms.items() if len(v) > 1)
    print("symboles ROM : %d (dont %d noms presents plusieurs fois) sur %d lignes nm"
          % (n_keep, multi, n_line))
    (WORK / 'en_symbols.json').write_text(json.dumps(syms))
    print("-> en_symbols.json")
    if multi:
        print("   exemples de collisions :")
        for k, v in list((k, v) for k, v in syms.items() if len(v) > 1)[:8]:
            print("      %-40s %s" % (k, [(hex(a), s, t) for a, s, t in v]))


if __name__ == '__main__':
    main()
