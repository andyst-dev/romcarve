#!/usr/bin/env python3
"""probe_why.py - pour une poignee de regions, dire EXACTEMENT quel filtre de
l'etage 1 rejette la verite italienne."""
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


import bisect, gzip, json, sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve3 as C

LOCALES = Path(f"{REF_DIR}")
man_ref = json.loads(gzip.decompress((LOCALES / 'spanish.json.gz').read_bytes()))
man_it = json.loads(gzip.decompress((LOCALES / 'italian.json.gz').read_bytes()))

en_rom = C.ROMS['EN'].read_bytes()
en_sk = C.Skeleton(en_rom)
sk = C.Skeleton(C.ROMS['IT'].read_bytes())

verite = {}
for rel, entry in man_it['files'].items():
    for i, e in enumerate(sorted(entry['edits'])):
        verite[(rel, i)] = e[2]

loc = {rel: C.locate_file(man_ref, rel, en_rom, en_sk) for rel in man_ref['files']}
glob = []
for rel, lst in loc.items():
    for idx, p, size, k in lst:
        glob.append((p, k, rel, idx, size))
glob.sort()
regs, cur = [], [glob[0]]
for it in glob[1:]:
    if it[1] - cur[-1][1] > 1:
        regs.append(cur)
        cur = []
    cur.append(it)
regs.append(cur)

CAS = ['data/text/tv.inc', 'data/scripts/contest_hall.inc',
       'src/data/text/move_descriptions.h', 'data/scripts/lilycove_lady.inc',
       'src/data/text/abilities.h', 'data/text/blend_master.inc',
       'data/maps/MossdeepCity_Gym/scripts.inc']

for rel0 in CAS:
    rg = next((r for r in regs if r[0][2] == rel0 and len(r) >= 6), None)
    if rg is None:
        print(rel0, ': region introuvable'); continue
    en_start, k_first = rg[0][0], rg[0][1]
    k_last = rg[-1][1]
    cnt_n = k_last - k_first + 1
    en_sizes = en_sk.sizes[k_first:k_last + 1]
    en_span = en_sk.starts[k_first + cnt_n] - en_sk.starts[k_first]
    truth = verite.get((rg[0][2], rg[0][3]))
    print('\n== %s  n=%d  en=%d  span_en=%d  verite_it=%s' % (rel0, cnt_n, en_start, en_span, truth))
    if truth is None:
        print('   pas de verite'); continue
    print('   dans fenetre +-250k :', max(1, en_start - 250000) <= truth < min(len(sk.data) - 400, en_start + 250000))
    print('   octet avant = 0xFF :', sk.data[truth - 1] == 0xFF, '(%02X)' % sk.data[truth - 1])
    k = bisect.bisect_left(sk.starts, truth)
    memb = k < len(sk.starts) and sk.starts[k] == truth
    print('   est un debut d objet du squelette :', memb,
          '| plus proche debut: %d (ecart %d)' % (sk.starts[k], sk.starts[k] - truth) if k < len(sk.starts) else '')
    if memb:
        span = sk.starts[k + cnt_n] - truth if k + cnt_n < len(sk.starts) else None
        print('   run[k] = %d (il faut >= %d)' % (sk.run[k], cnt_n))
        print('   span cible = %s | ratio = %s (attendu 0.5..1.6)'
              % (span, round(span / en_span, 3) if span else None))
        if span:
            c = C.corr(sk.sizes[k:k + cnt_n], en_sizes)
            print('   correlation du profil de tailles = %.3f (seuil 0.45)' % c)
    else:
        # verite non alignee sur un debut d'objet : chercher le debut qui precede
        kk = bisect.bisect_right(sk.starts, truth) - 1
        print('   debut d objet precedent: %d (+%d), run=%d, tailles %s'
              % (sk.starts[kk], truth - sk.starts[kk], sk.run[kk], sk.sizes[kk:kk + 4]))
