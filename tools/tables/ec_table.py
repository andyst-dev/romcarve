#!/usr/bin/env python3
"""ec_table.py - trouver une table easy_chat en ROM cible par sa STRUCTURE.

Enregistrement = 12 octets : .text (4, pointeur) + .alphabeticalOrder (4)
+ .enabled (1) + 3 de remplissage. N (nombre d'enregistrements) vient du
manifeste de reference (nombre d'editions `u32` du fichier) ; l'ORDRE des
enregistrements est celui des EC_INDEX, identique dans toutes les langues, et
les mots d'un groupe sont EMPILES dans l'ordre des enregistrements.

Criteres (tous mesures sur l'oracle italien) :
  1. les N enregistrements B+12k sont valides : pointeur dans la plage ROM et
     dans la zone des mots, octet `enabled` a +8 dans {0,1} ;
  2. le rang a +4 tombe dans [0,N) et les N rangs sont DISTINCTS (permutation) ;
  3. les mots pointes se decodent comme de la langue cible ;
  4. les mots sont CONTIGUS dans l'ordre des enregistrements :
     ptr[k+1] == ptr[k] + longueur(mot) + 1, chaque mot finissant par 0xFF.
     C'est le critere decisif : il n'y a pas deux tables candidates qui le
     respectent.

Usage : ec_table.py <CIBLE> [fichier ...]
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

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
LOCALES = Path(f"{REF_DIR}")

target = sys.argv[1]
only = sys.argv[2:]

with gzip.open(LOCALES / 'italian.json.gz') as fh:
    man = json.load(fh)['files']

rom = C.ROMS[target].read_bytes()
N_ROM = len(rom)


def word_end(off, cap=200):
    """Debut de l'objet suivant si l'objet a off est un texte 0xFF-termine."""
    if not (0 <= off < N_ROM):
        return None
    z = rom.find(b'\xff', off, off + cap)
    if z < 0:
        return None
    return z + 1


def plausible(off, minlen=2):
    e = word_end(off)
    if e is None or e - off - 1 < minlen:
        return False
    try:
        t = C._CM.decode(rom[off:e - 1])
    except Exception:
        return False
    t = t.split('\\')[0].split('\n')[0]
    if len(t) < minlen:
        return False
    al = sum(ch.isalnum() for ch in t)
    if al / max(1, len(t)) < 0.45:
        return False
    return not any('\u3040' <= ch <= '\u30ff' or '\u0400' <= ch <= '\u04ff' for ch in t)


def score(B, N, word_lo, word_hi):
    ptrs, ranks = [], []
    for k in range(N):
        o = B + 12 * k
        if o + 12 > N_ROM:
            return None
        p = int.from_bytes(rom[o:o + 4], 'little')
        r = int.from_bytes(rom[o + 4:o + 8], 'little')
        e = rom[o + 8]
        if not (0x08000000 <= p < 0x0A000000):
            return None
        if not (word_lo <= p - 0x08000000 <= word_hi):
            return None
        if e not in (0, 1):
            return None
        ptrs.append(p - 0x08000000)
        ranks.append(r)
    if len(set(ranks)) != N or any(not (0 <= r < N) for r in ranks):
        return None
    ends = [word_end(p) for p in ptrs]
    if any(x is None for x in ends):
        return None
    contig = all(ptrs[k + 1] == ends[k] for k in range(N - 1))
    npl = sum(1 for p in ptrs if plausible(p))
    return (contig, npl, ptrs, ranks)


def find_table(N, lo, hi, word_lo, word_hi):
    out = []
    for B in range(lo, hi, 4):
        s = score(B, N, word_lo, word_hi)
        if not s:
            continue
        contig, npl, ptrs, ranks = s
        out.append((1 if contig else 0, npl / N, B))
    out.sort(key=lambda x: (-x[0], -x[1]))
    return out[:8]


WORD_LO, WORD_HI = 5_850_000, 6_000_000
SEARCH_LO, SEARCH_HI = 5_850_000, 6_000_000

res, details = {}, {}
for rel, entry in sorted(man.items()):
    if 'easy_chat' not in rel or rel.endswith('words_by_letter.h'):
        continue
    if only and rel not in only:
        continue
    ed = sorted(entry['edits'])
    N = sum(1 for e in ed if e[4] == 'u32')
    if N < 8:
        continue
    cands = find_table(N, SEARCH_LO, SEARCH_HI, WORD_LO, WORD_HI)
    print('%-56s N=%3d  -> %s' % (rel.split('/')[-1], N,
          ['B=%d cont=%d pl=%.2f' % c for c in cands[:3]]))
    if cands:
        res[rel] = cands[0][2]
        details[rel] = cands[:5]

(WORK / ('ec_tables_%s.json' % target)).write_text(json.dumps(res))
(WORK / ('ec_tables_%s_detail.json' % target)).write_text(json.dumps(details))
print('\n%d tables localisees -> ec_tables_%s.json' % (len(res), target))
