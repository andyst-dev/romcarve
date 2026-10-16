#!/usr/bin/env python3
"""fix_prefix.py - editions posees sur le DEBUT D'OBJET au lieu du DEBUT DU TEXTE.

L'objet allemand commence souvent par un long prefixe de codes de controle (pointeurs + codes)
suivi du texte ; l'offset doit pointer le TEXTE.

Deux candidats essayes, dans cet ordre :
  1. la mise en page du prefixe est la meme dans les deux langues, donc
     `offset_de = debut_objet + (offset_it - debut_objet_it)` (exact quand les prefixes ont la
     meme structure : mesure sur PetalburgCity[0], MtPyre_2F[0], delta 0) ;
  2. sinon, on cherche le PLUS PETIT `p` de l'objet tel que `de[p:fin_objet]` se DECODE (aucun
     kana, longueur suffisante) et commence par une lettre - c'est le premier mot allemand.

Un candidat n'est retenu que si le texte est lisible ET si le ratio de taille tombe dans
[0.5, 2.4].  Les cas restants sont listes a part (a lire a la main).

Usage : python3 fix_prefix.py [--emit]
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
import re
import sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
IT = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
CUR = json.loads((WORK / 'mapping_de_verifie.json').read_text())
DE = C.ROMS['DE'].read_bytes()
ITROM = C.ROMS['IT'].read_bytes()
CM = C._CM
KANA = re.compile(r'[\u3040-\u30ff\u31f0-\u31ff]')
LETTER = re.compile(r'[A-ZÄÖÜÉÀÈ0-9]')


def readable(s: str) -> bool:
    if len(s) < 8:
        return False
    bad = len(KANA.findall(s)) + sum(1 for c in s if ord(c) < 32)
    return bad / max(len(s), 1) < 0.04


def find_start(obj_start: int, it_off: int, size: int, z: int):
    it_obj = ITROM.rfind(b'\xff', 0, it_off) + 1
    cands = [obj_start + (it_off - it_obj)]
    for p in range(obj_start, z):
        if LETTER.match(CM.decode(DE[p:p + 1])) and readable(CM.decode(DE[p:z])):
            cands.append(p)
            break
    for cand in cands:
        if not (obj_start <= cand < z):
            continue
        txt = CM.decode(DE[cand:z])
        r = (z - cand + 1) / size
        if readable(txt) and 0.5 <= r <= 2.4:
            return cand, txt, r
    return None


def main():
    proposals = {}
    leftovers = []
    for rel, v in IT.items():
        placed = dict(CUR.get(rel, []))
        for i, (start, end, it_off, it_size, kind) in enumerate(sorted(v['edits'])):
            if kind not in ('c', 'asm', 'u8array') or it_size < 4 or i not in placed:
                continue
            off = placed[i]
            if DE[off - 1] != 0xFF:
                continue                      # pas un debut d'objet : autre classe
            z = DE.find(b'\xff', off, off + 40000)
            if z < 0 or 0.5 <= (z - off + 1) / it_size <= 2.4:
                continue
            got = find_start(off, it_off, it_size, z)
            if got:
                cand, txt, r = got
                proposals.setdefault(rel, {})[i] = cand
                print('OK   %-58s [%3d] %d -> %d  r=%.2f  %r' % (rel[-58:], i, off, cand, r, txt[:56]))
            else:
                leftovers.append((rel, i, off))
    print()
    print('%d propositions, %d a lire a la main' % (sum(len(t) for t in proposals.values()), len(leftovers)))
    for rel, i, off in leftovers:
        print('   reste %-58s [%3d] @%d  %r' % (rel[-58:], i, off, CM.decode(DE[off:off + 46])))
    if '--emit' in sys.argv:
        (WORK / 'fix_prefix.json').write_text(json.dumps(proposals, indent=1))
        print('ecrit fix_prefix.json')


if __name__ == '__main__':
    main()
