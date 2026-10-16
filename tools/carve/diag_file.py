#!/usr/bin/env python3
"""diag_file.py <fichier> - ou et pourquoi le carver decroche sur UN fichier.

Rejoue l'etage 1 de carve4 et compare, objet par objet, la position predite a la
verite italienne. Affiche la premiere divergence et le voisinage (tailles EN/cible,
textes decodes des deux cotes) pour voir si c'est l'ancre ou la marche qui casse.

Usage : diag_file.py data/text/tv.inc [n_avant] [n_apres]
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

import bisect, gzip, json, sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
sys.path.insert(0, f"{VFWORK}")
import carve4 as C  # noqa: E402
from charmap import Charmap  # noqa: E402

LOCALES = Path(f"{REF_DIR}")
CM = Charmap(f"{REF_TREE}/charmap.txt")
rel0 = sys.argv[1]
avant = int(sys.argv[2]) if len(sys.argv) > 2 else 2
apres = int(sys.argv[3]) if len(sys.argv) > 3 else 8

man_ref = json.loads(gzip.decompress((LOCALES / 'spanish.json.gz').read_bytes()))
man_it = json.loads(gzip.decompress((LOCALES / 'italian.json.gz').read_bytes()))
truth = sorted(man_it['files'][rel0]['edits'])

en_rom = C.ROMS['EN'].read_bytes()
en_sk = C.Skeleton(en_rom)
it = C.Skeleton(C.ROMS['IT'].read_bytes())

loc = {r: C.locate_file(man_ref, r, en_rom, en_sk) for r in man_ref['files']}
print('%s : %d objets localises cote EN (sur %d editions)' % (rel0, len(loc[rel0]), len(truth)))
if not loc[rel0]:
    sys.exit(0)

# NB : dans carve4 les regions sont construites GLOBALEMENT (tous fichiers confondus),
# donc une region peut traverser une frontiere de fichier - d'ou l'ecart entre ce
# diagnostic local et l'oracle.
glob = []
for r, lst in loc.items():
    for idx, p, size, k in lst:
        glob.append((p, k, r, idx, size))
glob.sort()
regs, cur = [], [glob[0]]
for it2 in glob[1:]:
    if it2[1] - cur[-1][1] > 1:
        regs.append(cur)
        cur = []
    cur.append(it2)
regs.append(cur)
mine = [r for r in regs if any(x[2] == rel0 for x in r)]
print('regions touchant le fichier : %s' % [(len(r), r[0][2], r[0][1], r[-1][1]) for r in mine][:8])

pred = {}
for rg in regs:
    if len(rg) < 6:
        continue
    en_start, k_first, k_last = rg[0][0], rg[0][1], rg[-1][1]
    cnt_n = k_last - k_first + 1
    en_sizes = en_sk.sizes[k_first:k_last + 1]
    en_span = en_sk.starts[k_first + cnt_n] - en_sk.starts[k_first]
    cands = []
    lo_k = bisect.bisect_left(it.starts, max(1, en_start - 250000))
    hi_k = bisect.bisect_right(it.starts, min(len(it.data) - 400, en_start + 250000))
    for k in range(lo_k, min(hi_k, len(it.starts) - cnt_n - 1)):
        off = it.starts[k]
        if off <= 0:
            continue
        span = it.starts[k + cnt_n] - off
        if not 0.5 * en_span <= span <= 1.6 * en_span:
            continue
        c = C.corr(it.sizes[k:k + cnt_n], en_sizes)
        if c < 0.45:
            continue
        cands.append((c, off, k, span))
    if not cands:
        if any(x[2] == rel0 for x in rg):
            print('   region n=%d en=%d (fichier %s) : AUCUN candidat'
                  % (cnt_n, en_start, rg[0][2]))
        continue
    cands.sort(reverse=True)
    c, off, k, span = cands[0]
    if any(x[2] == rel0 for x in rg):
        print('   region n=%d en=%d (%s) -> corr %.3f @%d (span %.3f)'
              % (cnt_n, en_start, rg[0][2], c, off, span / en_span))
    for (p, kk, r, idx, size) in rg:
        pred[(r, idx)] = it.starts[k + (kk - k_first)] + (p - en_sk.starts[kk])

# comparaison avec la verite, dans l'ordre du manifeste
print('\n%-4s %-10s %-10s %-6s %s' % ('i', 'verite', 'predit', 'ecart', 'texte verite / texte predit'))
mauvais, total, vus = [], 0, 0
for i, e in enumerate(truth):
    off_t = e[2]
    off_p = pred.get((rel0, i))
    if off_p is None:
        continue
    total += 1
    if off_t == off_p:
        continue
    mauvais.append(i)
    vus += 1
    if vus <= apres:
        et = it.data.find(b'\xff', off_t, off_t + 400)
        ep = it.data.find(b'\xff', off_p, off_p + 400)
        print('%-4d %-10d %-10d %+-6d  V:%r' % (i, off_t, off_p, off_p - off_t,
                                               CM.decode(it.data[off_t:et])[:58]))
        print('%-4s %-10s %-10s %-6s  P:%r' % ('', '', '', '', CM.decode(it.data[off_p:ep])[:58]))
print('\n%d/%d objets a la bonne position | %d faux' % (total - len(mauvais), total, len(mauvais)))
if mauvais:
    import itertools
    runs = [(k, len(list(g))) for k, g in itertools.groupby(
        [i for i in range(len(truth)) if i in set(mauvais)], key=lambda x: x)]
    print('indices faux (debut/fin) : %s ... %s' % (mauvais[:12], mauvais[-6:]))


