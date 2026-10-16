#!/usr/bin/env python3
"""secalign.py - alignement de la ROM cible par MARCHE DE SECTIONS.

Modele (verifie par le .map de ld) : la ROM est une CONCATENATION des sections
d'entree (fichiers .o), dans un ordre fixe. Entre deux langues, chaque section
tient la meme place ; seuls les fichiers portant du TEXTE changent de taille.

Marche :
  shift = 0
  pour chaque section (ordre des adresses EN) :
     de_start = en_start + shift
     si le contenu EN == contenu cible a de_start  -> section invariante, taille
        inchangee, shift inchange
     sinon -> section de langue : la taille cible est obtenue en enjambant le MEME
        nombre d'objets (0xFF) qu'en EN ; le prochain demarrage est aligne comme en EN
     shift += de_taille - en_taille

Toute erreur de marche casse les sections invariantes suivantes et se voit : la
verification est donc structurelle, pas declarative.

Usage : secalign.py <CIBLE> [--verbose]
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

import collections, json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, f"{WORK}")
from zones import ROMS

WORK = Path(f"{WORK}")


def load_sections():
    L = json.loads((WORK / 'en_layout.json').read_text())
    secs = [s for s in L['sections'] if s[2] >= 0x08000000 and s[3] > 0 and
            not s[0].startswith('.debug') and not s[0].startswith('.comment')]
    secs = [[s[0], s[1], s[2] - 0x08000000, s[3]] for s in secs]
    secs.sort(key=lambda s: (s[2], -s[3]))
    keep = []
    last = -1
    for s in secs:
        if s[2] < last:
            continue
        keep.append(s)
        last = s[2] + s[3]
    return keep


def align_fwd(secs, A, B, verbose=False, maxreport=25):
    """marche des sections ; rend [(section, fichier, en_start, en_size, de_start, de_size,
    identical)] et les statistiques."""
    out = []
    shift = 0
    stat = collections.Counter()
    reports = []
    for (sec, f, en_a, en_sz) in secs:
        de_a = en_a + shift
        if de_a < 0 or de_a + en_sz > len(B):
            stat['hors_rom'] += 1
            out.append((sec, f, en_a, en_sz, de_a, en_sz, None))
            continue
        same = A[en_a:en_a + en_sz] == B[de_a:de_a + en_sz]
        if same:
            de_sz = en_sz
            stat['identiques'] += 1
            stat['o_identiques'] += en_sz
            out.append((sec, f, en_a, en_sz, de_a, en_sz, True))
        else:
            # nombre d'objets 0xFF cote EN, on enjambe le meme nombre cote cible
            i0 = A.find(b'\xff', en_a, en_a + en_sz)
            n_ff = A.count(b'\xff', en_a, en_a + en_sz)
            pos = de_a
            for _ in range(n_ff):
                p = B.find(b'\xff', pos)
                if p < 0:
                    break
                pos = p + 1
            de_sz = pos - de_a
            stat['de_langue'] += 1
            stat['o_langue'] += en_sz
            out.append((sec, f, en_a, en_sz, de_a, de_sz, False))
            if verbose and len(reports) < maxreport:
                reports.append((sec, f, en_a, en_sz, de_a, de_sz, n_ff))
        shift += de_sz - en_sz
    return out, stat, reports, shift


def main():
    target = sys.argv[1]
    verbose = '--verbose' in sys.argv
    A = ROMS['EN'].read_bytes()
    B = ROMS[target].read_bytes()
    secs = load_sections()
    print("%s : %d sections d'entree (ROM >= 0x08000000)" % (target, len(secs)))
    out, stat, reports, shift = align_fwd(secs, A, B, verbose)
    print("   sections identiques : %d (%.2f Mo) | sections de langue : %d (%.2f Mo)"
          % (stat['identiques'], stat['o_identiques'] / 1e6, stat['de_langue'],
             stat['o_langue'] / 1e6))
    print("   shift final : %+d" % shift)
    if verbose:
        print("   sections de langue (20 premieres) :")
        for (sec, f, en_a, en_sz, de_a, de_sz, n_ff) in reports:
            print("      %-24s %-34s @%08X %8d o -> %8d o (%+d)  %d FF"
                  % (sec, f, en_a, en_sz, de_sz, de_sz - en_sz, n_ff))
    out_path = WORK / ('secalign_%s.json' % target)
    out_path.write_text(json.dumps(out))
    print("-> %s" % out_path)


if __name__ == '__main__':
    main()
