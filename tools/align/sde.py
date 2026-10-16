#!/usr/bin/env python3
"""sde.py - chercher une PHRASE ALLEMANDE dans la ROM Smaragd (encodee charmap).

Sert a retrouver les editions de la traine : le texte italien est connu, on
compose la phrase allemande attendue (mot distinctif), on l'encode et on
cherche ses occurrences.  Chaque touche est affichee avec l'objet qui la
contient et le texte decode (pour lire le contexte).

Usage : python3 sde.py "mot ou phrase" ["autre", ...]
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

import sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

CM = C._CM
de = C.ROMS['DE'].read_bytes()


def show(needle):
    try:
        data = CM.encode(needle)
    except Exception as exc:
        print('### %r : encodage impossible (%s)' % (needle, exc))
        return
    hits = []
    i = de.find(data)
    while i >= 0 and len(hits) < 25:
        hits.append(i)
        i = de.find(data, i + 1)
    print('### %r -> %d occurrences' % (needle, len(hits)))
    for h in hits[:12]:
        s = de.rfind(b'\xff', max(0, h - 600), h)
        z = de.find(b'\xff', h, h + 700)
        o = s + 1 if s >= 0 else 0
        print('   @%d (objet %d..%d)' % (h, o, z))
        print('      %r' % CM.decode(de[o:z])[:200])


if __name__ == '__main__':
    for a in sys.argv[1:]:
        show(a)
