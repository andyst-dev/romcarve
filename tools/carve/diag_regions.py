#!/usr/bin/env python3
"""diag_regions.py - pourquoi l'etage 1 de carve3 rate-t-il une region ?

Pour chaque REGION (suite d'objets contigus cote EN, spans pris dans le manifeste
ESPAGNOL - jamais la cible), on connait la verite italienne (italian.json.gz).

On regarde alors la liste des candidats que carve3 construit et on repond a :
  - la verite etait-elle dans la fenetre de recherche (+-250 ko) ?
  - etait-elle dans les candidats retenus (0xFF avant, run suffisant, span plausible) ?
  - si oui, a quel RANG de correlation se classait-elle, et quel score a gagne ?

Usage : diag_regions.py [manifeste_ref] [fichier_de_sortie]
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

import bisect, gzip, json, sys, collections
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve3 as C  # noqa: E402

LOCALES = Path(f"{REF_DIR}")
WORK = Path(f"{WORK}")

man_ref = json.loads(gzip.decompress(
    Path(sys.argv[1] if len(sys.argv) > 1 else LOCALES / 'spanish.json.gz').read_bytes()))
man_it = json.loads(gzip.decompress((LOCALES / 'italian.json.gz').read_bytes()))

en_rom = C.ROMS['EN'].read_bytes()
en_sk = C.Skeleton(en_rom)
sk = C.Skeleton(C.ROMS['IT'].read_bytes())

# verite : offset italien de chaque (fichier, indice d'edition)
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
big = [r for r in regs if len(r) >= 6]

stats = collections.Counter()
detail = []
for rg in big:
    en_start = rg[0][0]
    k_first, k_last = rg[0][1], rg[-1][1]
    cnt_n = k_last - k_first + 1
    en_sizes = en_sk.sizes[k_first:k_last + 1]
    en_span = en_sk.starts[k_first + cnt_n] - en_sk.starts[k_first]
    rel0, idx0 = rg[0][2], rg[0][3]
    truth = verite.get((rel0, idx0))

    d_in_window = d_is_cand = d_rank = d_win = None
    off_win = None
    best_t = None
    cands = []
    if truth is not None:
        lo = max(1, en_start - 250000)
        hi = min(len(sk.data) - 400, en_start + 250000)
        d_in_window = lo <= truth < hi
    for off in range(max(1, en_start - 250000), min(len(sk.data) - 400, en_start + 250000)):
        if sk.data[off - 1] != 0xFF:
            continue
        k = bisect.bisect_left(sk.starts, off)
        if k >= len(sk.starts) or sk.starts[k] != off or sk.run[k] < cnt_n:
            continue
        span = sk.starts[k + cnt_n] - off
        if not 0.5 * en_span <= span <= 1.6 * en_span:
            continue
        c = C.corr(sk.sizes[k:k + cnt_n], en_sizes)
        if c < 0.45:
            continue
        cands.append((c, off, k, span))
        if truth is not None and off == truth:
            d_is_cand = True
            best_t = c
    if cands:
        cands.sort(reverse=True)
        off_win = cands[0][1]
        if d_is_cand:
            rank = [i for i, c in enumerate(cands) if c[1] == truth][0]
            d_rank = rank
    ok = (off_win == truth) if (truth is not None and off_win is not None) else False

    if truth is None:
        stats['pas de verite'] += 1
    elif not d_in_window:
        stats['verite HORS fenetre'] += 1
    elif not d_is_cand:
        stats['verite dans fenetre mais PAS candidate'] += 1
    elif not cands:
        stats['aucun candidat'] += 1
    elif ok:
        stats['RESOLU (1er candidat = verite)'] += 1
    else:
        stats['verite candidate mais battue (rang %s)' % ('1+' if d_rank else '?')] += 1
        stats['   _rang>0'] += 1

    detail.append(dict(rel=rel0, n=cnt_n, en=en_start, truth=truth, win=off_win,
                       cand=bool(d_is_cand), rank=d_rank, ok=ok,
                       c_truth=round(best_t, 3) if best_t else None,
                       c_win=round(cands[0][0], 3) if cands else None))

print('regions >= 6 objets : %d' % len(big))
for k, v in stats.most_common():
    print('   %-46s %d' % (k, v))
print()
worse = [d for d in detail if d['truth'] is not None and not d['ok']]
worse.sort(key=lambda d: -d['n'])
print('regions non resolues, par volume d objets :')
for d in worse[:25]:
    print('   %-52s n=%-4d en=%-9d verite=%-9s choix=%-9s cand=%s rang=%s cT=%s cW=%s'
          % (d['rel'], d['n'], d['en'], d['truth'], d['win'], d['cand'], d['rank'],
             d['c_truth'], d['c_win']))
Path(WORK / 'diag_regions.json').write_text(json.dumps(detail))
print('\n-> diag_regions.json')
