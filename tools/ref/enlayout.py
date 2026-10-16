#!/usr/bin/env python3
"""enlayout.py - carte du ROM ANGLAIS depuis pokeemerald.map.

Le .map de ld liste, section par section, chaque FICHIER OBJET d'entree avec
l'adresse et la taille de sa contribution, puis ses symboles :

     .rodata         0x082e9530   0x612b0c
     src/main.o(.rodata)
     .rodata        0x082e9530       0x50 src/main.o
                    0x082e9530                gGameVersion

=> la ROM est une CONCATENATION de sections d'entree, dans un ordre fixe.
C'est la structure qui rend l'alignement d'une autre langue calculable : chaque
section garde sa place, seuls les fichiers portant du texte changent de taille.

Sortie : en_layout.json  { "sections": [[section, fichier, adresse, taille], ...],
                          "symbols": {"nom": adresse, ...} }
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

import json, re, sys
from pathlib import Path

MAP = Path(f"{WORK}/en.map")
OUT = Path(f"{WORK}/en_layout.json")

SEC = re.compile(r'^(\S+)\s+0x([0-9a-f]{8})\s+(0x[0-9a-f]+)\s+(\S+\.o)$')
SEC0 = re.compile(r'^(\S+)\s+0x([0-9a-f]{8})\s+(0x[0-9a-f]+)$')
SYM = re.compile(r'^\s+0x([0-9a-f]{8})(?:\s+0x([0-9a-f]+))?\s+(\S+)$')
INPT = re.compile(r'^\s+(\S+\.o)\(([^)]*)\)$')


def main():
    sections = []      # [section, input_file, addr, size]
    symbols = {}       # name -> (addr, size)
    cur_sec = None
    cur_file = None
    for line in MAP.read_text(errors='replace').splitlines():
        m = SEC.match(line.strip())
        if m:
            cur_sec, addr, size, f = m.group(1), int(m.group(2), 16), int(m.group(3), 16), m.group(4)
            sections.append([cur_sec, f, addr, size])
            cur_file = f
            continue
        m = SEC0.match(line.strip())
        if m:
            cur_sec = m.group(1)
            continue
        m = SYM.match(line)
        if m:
            name = m.group(3)
            if name.startswith('0x') or name.endswith('.o'):
                continue
            symbols[name] = (int(m.group(1), 16),
                             int(m.group(2), 16) if m.group(2) else 0)
    print("sections d'entree : %d | symboles : %d" % (len(sections), len(symbols)))
    bysec = {}
    for s, f, a, z in sections:
        bysec.setdefault(s, [0, 0])
        bysec[s][0] += 1
        bysec[s][1] += z
    for s, (n, tot) in sorted(bysec.items(), key=lambda kv: -kv[1][1])[:12]:
        print("   %-22s %5d sections %10d o" % (s, n, tot))
    ro = [x for x in sections if x[0] == '.rodata']
    ro.sort(key=lambda x: x[2])
    print("\n.rodata : %d fichiers d'entree, de 0x%X a 0x%X" % (len(ro), ro[0][2], ro[-1][2]))
    print("   30 plus gros :")
    for s, f, a, z in sorted(ro, key=lambda x: -x[3])[:30]:
        print("      %9d o  @0x%08X  %s" % (z, a, f))
    OUT.write_text(json.dumps({'sections': sections,
                               'symbols': {k: list(v) for k, v in symbols.items()}}))
    print("->", OUT)


if __name__ == '__main__':
    main()
