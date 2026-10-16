#!/usr/bin/env python3
"""ratio_audit.py - AUDIT DU RATIO DE TAILLE DE/IT, par edition.

Pour chaque edition TEXTE placee (`c`, `asm`, `u8array`), la taille allemande se lit sur la
ROM (jusqu'au `0xFF` inclus) et le rapport a la taille italienne du manifeste doit rester
dans [0.45, 2.6].  Hors de la, l'offset pointe presque toujours le texte d'une AUTRE edition.

Deux classes connues, que les autres audits ne voient pas :
  - le fichier entier est DECALE d'un ou deux crans (les offsets sont ceux du pool, mais
    attribues aux mauvaises editions) : le `dup_audit` ne dit rien (aucun offset partage) et
    le `delta_audit` non plus (le decalage reste localement lisse) ;
  - l'offset pointe un objet d'un tableau VOISIN (cas de `battle_message.c [467..471]`).

Usage :
    python3 ratio_audit.py [seuil]              # seuil = borne haute du ratio (defaut 2.6)
    python3 ratio_audit.py --shift <fichier>    # teste les decalages -2..+3 sur ce fichier
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

import collections
import gzip
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
IT = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
CUR = json.loads((WORK / 'mapping_de_verifie.json').read_text())
DE = C.ROMS['DE'].read_bytes()
CM = C._CM
TEXT = ('c', 'asm', 'u8array')


def de_size(off):
    z = DE.find(b'\xff', off, off + 20000)
    return None if z < 0 else z - off + 1


def main():
    if len(sys.argv) > 2 and sys.argv[1] == '--shift':
        rel = sys.argv[2]
        eds = sorted(IT[rel]['edits'])
        have = dict(CUR.get(rel, []))
        mn = min(have.values())
        objs, p = [], mn - 700
        while p < max(have.values()) + 800:
            z = DE.find(b'\xff', p)
            if z < 0:
                break
            objs.append((p, z - p + 1))
            p = z + 1
        print('%s : %d editions, %d objets DE autour du pool' % (rel, len(eds), len(objs)))
        first = min(range(len(objs)), key=lambda j: abs(objs[j][0] - mn))
        for k in range(-2, 4):
            tot = n = 0
            for i, e in enumerate(eds):
                j = first + i + k
                if 0 <= j < len(objs) and e[3] > 1:
                    tot += abs(math.log(e[3] / objs[j][1]))
                    n += 1
            if n:
                print('  decalage %+d : erreur moyenne %.3f sur %d editions'
                      % (k, tot / n, n))
        print('  reference = l\'objet dont le debut est le plus proche du plus petit offset mappe.')
        print('  ATTENTION : si l\'edition [0] commence a l\'INTERIEUR d\'un objet (prefixe de codes de')
        print('  controle), la reference est decalee d\'un cran - lire les deux sequences pour trancher.')
        sys.exit(0)

    hi = float(sys.argv[1]) if len(sys.argv) > 1 else 2.6
    lo = 0.45
    rows = []
    for rel, v in IT.items():
        placed = dict(CUR.get(rel, []))
        for i, (start, end, it_off, it_size, kind) in enumerate(sorted(v['edits'])):
            if kind not in TEXT or it_size < 4 or i not in placed:
                continue
            off = placed[i]
            ds = de_size(off)
            if ds is None:
                rows.append((99.0, rel, i, off, 'pas de 0xFF'))
                continue
            r = ds / it_size
            if r < lo or r > hi:
                rows.append((r, rel, i, off, CM.decode(DE[off:off + 70])))
    byfile = collections.Counter(r[1] for r in rows)
    print('%d editions texte hors de [%.2f, %.2f] dans %d fichiers'
          % (len(rows), lo, hi, len(byfile)))
    print()
    for r in sorted(rows)[:40]:
        print('  r=%.2f %-52s [%2d] @%-9d %r' % (r[0], r[1][-52:], r[2], r[3], r[4]))
    print()
    print('top fichiers :', byfile.most_common(20))


if __name__ == '__main__':
    main()
