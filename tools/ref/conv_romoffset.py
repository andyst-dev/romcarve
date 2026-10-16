#!/usr/bin/env python3
"""conv_romoffset.py - QUELLE est la convention de rom_offset du manifeste ?

On prend les premieres editions d'un fichier et on affiche, cote a cote :
  - l'extrait de SOURCE que couvre l'edition (arbre epingle) ;
  - le rom_offset et la taille declares ;
  - les OCTETS de la ROM a cet offset, decodes, plus le debut de l'objet qui contient
    cet offset (le 0xFF precedent marque le debut d'objet) ;
  - le texte attendu (encodage du litteral de la declaration).

But : savoir si rom_offset est le debut de l'objet, la position du texte DANS l'objet,
ou autre chose.

Usage : conv_romoffset.py <fichier> [n]
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
sys.path.insert(0, f"{VFWORK}")
from charmap import Charmap

WORK = Path(f"{WORK}")
TREE = Path(f"{REF_TREE}")
CM = Charmap(str(TREE / 'charmap.txt'))
IT = (WORK / 'roms/it_bpei.gba').read_bytes()


def main():
    rel = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    man = json.loads(gzip.decompress(Path(f"{REF_DIR}/italian.json.gz").read_bytes()))
    src = (TREE / rel).read_text(encoding='utf-8', errors='replace')
    edits = sorted(man['files'][rel]['edits'])
    print("%s : %d editions (fichier source de %d caracteres)" % (rel, len(edits), len(src)))
    for i, e in enumerate(edits[:n]):
        cs, ce, off, size, kind = e
        frag = src[cs:ce].replace('\n', ' ')[:44]
        body = IT[off:IT.find(b'\xff', off, off + 400)]
        prev_ff = IT.rfind(b'\xff', max(0, off - 200), off)
        obj_start = prev_ff + 1 if prev_ff >= 0 else None
        print("\n  ed.%d char[%d:%d] rom=%d size=%d kind=%s" % (i, cs, ce, off, size, kind))
        print("      source  : %r" % frag)
        print("      ROM a l'offset : %r" % CM.decode(body)[:52])
        if obj_start is not None:
            ob = IT[obj_start:IT.find(b'\xff', obj_start, obj_start + 400)]
            print("      objet qui contient l'offset : debut %d (%+d), texte %r"
                  % (obj_start, off - obj_start, CM.decode(ob)[:44]))
        # texte attendu de la declaration
        p = src.rfind('_(', 0, cs)
        if p >= 0:
            q = src.index(')', p)
            lits = []
            import re
            for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', src[p:q]):
                lits.append(m.group(1))
            try:
                enc = CM.encode(''.join(lits))
                print("      attendu : %r (%d o + 0xFF)  | char du litteral : %d" % (CM.decode(enc)[:44], len(enc), p))
            except Exception as ex:
                print("      attendu : encodage impossible (%s)" % ex)


if __name__ == '__main__':
    main()
