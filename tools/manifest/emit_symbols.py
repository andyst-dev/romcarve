#!/usr/bin/env python3
"""emit_symbols.py - produit tools/locales/german-symbols.s.gz depuis un ELF GBA.

Le manifeste d'une variante localisee ne peut pas s'appuyer sur l'ELF du jeu
d'origine (c'est la ROM de l'utilisateur) : chaque variante livre donc son propre
releve de symboles, que `tools/build_release.py` assemble et que `gen_recipe.py`
lit pour retrouver les plages de sections.

Format identique aux autres variantes (tools/locales/italian-symbols.s.gz) :
pour chaque symbole DEFINI, quatre lignes, en ordre alphabetique (celui de nm) :

    .global NAME
    .type NAME, %function     (T/t/w/W)  ou  %object  (D/d/B/b/R/r/A/S/V/G)
    .equ NAME, <adresse en decimal>
    .size NAME, <taille en decimal>

Usage : python3 emit_symbols.py <elf> <sortie.s.gz> --nm <arm-none-eabi-nm>
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

import argparse
import gzip
import subprocess
from pathlib import Path

FUNCTION = set("TtWw")
OBJECT = set("DdBbRrASVvGg")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("elf", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--nm", default="arm-none-eabi-nm")
    args = ap.parse_args()

    listing = subprocess.check_output(
        [args.nm, "-S", "--defined-only", str(args.elf)], text=True, errors="ignore")
    lines = [".syntax unified"]
    kept = 0
    for line in listing.splitlines():
        parts = line.split()
        if len(parts) == 3:
            addr, kind, name = parts        # pas de taille connue
            size = "0"
        elif len(parts) == 4:
            addr, size, kind, name = parts
        else:
            continue
        if kind in FUNCTION:
            t = "%function"
        elif kind in OBJECT:
            t = "%object"
        else:
            continue                      # U, N et compagnie : rien a declarer
        lines.append(".global " + name)
        lines.append(".type " + name + ", " + t)
        lines.append(".equ " + name + ", " + str(int(addr, 16)))
        lines.append(".size " + name + ", " + str(int(size, 16)))
        kept += 1
    data = ("\n".join(lines) + "\n").encode()
    args.out.write_bytes(gzip.compress(data, mtime=0))
    print("symboles ecrits : %d | sortie : %s (%d octets compresses)"
          % (kept, args.out, args.out.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
