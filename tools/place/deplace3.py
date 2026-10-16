#!/usr/bin/env python3
"""deplace3.py - placement des pools par PASSES, du plus fiable au moins fiable.

1. GROS POOLS (>= @BIG objets) : recherche dans une fenetre large, acceptes si la
   correlation des longueurs depasse le second candidat d'une marge nette ;
2. le decalage est alors interpole le long de l'axe EN (pools places + ancres de
   section) ;
3. POOLS MOYENS puis PETITS : fenetre etroite autour du decalage interpole, marge
   plus faible exigee ;
4. CONTROLE : en ordre EN, les offsets cibles doivent croitre. Toute violation
   fait tomber le pool fautif.

Les ancres de CONTENU (texte allemand retrouve dans la ROM, cf. dechain.py) sont
injectees comme pools deja resolus et servent d'ancres.

Usage : deplace3.py <CIBLE> <manifeste> [--big N]
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

import bisect, collections, gzip, json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, f"{WORK}")
from zones import ROMS
from place3 import file_names
from deplace import walk_pool, corr, TB
from deplace2 import runs_of

WORK = Path(f"{WORK}")


def pool_at(B, run, pos, ln, c):
    """valide un candidat : N objets valides depuis c ; rend (corr, full)."""
    if len(run) < 3 or any(ln[i] is None for i in run[:-1]):
        return None
    Len = [ln[i] for i in run[:-1]]
    full = walk_pool(B, c, len(run))
    if full is None or len(full) != len(run):
        return None
    return corr(Len, full[:len(Len)]), full


def main():
    target = sys.argv[1]
    man = json.loads(gzip.decompress(Path(sys.argv[2]).read_bytes()))
    BIG = int(sys.argv[sys.argv.index('--big') + 1]) if '--big' in sys.argv else 25
    B = ROMS[target].read_bytes()
    syms = json.loads((WORK / 'en_symbols.json').read_text())
    wins = [w for w in json.loads((WORK / ('anchors_sec_%s.json' % target)).read_text())
            if w[4] is not None]
    wpos = np.array([w[4] for w in wins], dtype=float)
    wsh = np.array([w[5] - w[4] for w in wins], dtype=float)

    allruns = []
    for rel, entry in man['files'].items():
        names = file_names(rel)
        pos, ln, runs = runs_of(rel, sorted(entry['edits']), syms, names)
        for run in runs:
            if len(run) >= 3:
                allruns.append({'rel': rel, 'run': run, 'pos': pos, 'ln': ln,
                                'en0': pos[run[0]], 'n': len(run), 'done': None})
    allruns.sort(key=lambda r: r['en0'])
    print("%s : %d runs ; gros pools (>= %d objets) : %d"
          % (target, len(allruns), BIG, sum(1 for r in allruns if r['n'] >= BIG)))

    def shift_expect(en):
        pl = [(r['en0'], r['tgt'] - r['en0']) for r in allruns if r['done']]
        if len(pl) >= 2:
            pl.sort()
            xs = np.array([p[0] for p in pl], float)
            ys = np.array([p[1] for p in pl], float)
            i = int(np.searchsorted(xs, en))
            lo = max(0, min(i - 1, len(xs) - 2))
            x0, x1, y0, y1 = xs[lo], xs[lo + 1], ys[lo], ys[lo + 1]
            return (y0 + (y1 - y0) * (en - x0) / (x1 - x0)) if x1 > x0 else y0
        j = int(np.searchsorted(wpos, en))
        lo, hi = max(0, j - 4), min(len(wpos), j + 4)
        return float(np.median(wsh[lo:hi])) if hi > lo else float(np.median(wsh))

    def attempt(r, tol, mincorr, minmargin):
        en0 = r['en0']
        ex = shift_expect(en0)
        best = None
        runner = 0.0
        for d in range(int(ex - tol), int(ex + tol) + 1):
            c = en0 + d
            if c <= 0 or c >= len(B) or B[c - 1] != 0xFF:
                continue
            got = pool_at(B, r['run'], r['pos'], r['ln'], c)
            if got is None:
                continue
            sc, _full = got
            if best is None or sc > best[0]:
                runner = best[0] if best else 0.0
                best = (sc, c)
            elif sc > runner:
                runner = sc
        if best and best[0] >= mincorr and best[0] - runner >= minmargin:
            r['tgt'] = best[1]
            r['corr'] = best[0]
            r['margin'] = best[0] - runner
            r['done'] = True
            return True
        return False

    # ---- passe 1 : gros pools
    n1 = 0
    for r in sorted(allruns, key=lambda r: -r['n']):
        if r['n'] >= BIG and attempt(r, 60000, 0.80, 0.25):
            n1 += 1
    print("   passe 1 (gros) : %d places" % n1)
    # ---- passes suivantes : de plus en plus petits, fenetre de plus en plus etroite
    for nmin, tol, mincorr in ((12, 8000, 0.62), (6, 3000, 0.55), (3, 800, 0.45)):
        n = 0
        for r in sorted([r for r in allruns if not r['done']], key=lambda r: -r['n']):
            if r['n'] < nmin:
                continue
            if attempt(r, tol, mincorr, 0.05):
                n += 1
        print("   passe n>=%d (tol %d) : %d places" % (nmin, tol, n))
    # ---- controle de monotonie en ordre EN
    placed = [r for r in allruns if r['done']]
    placed.sort(key=lambda r: r['en0'])
    drop = 0
    last = -1
    for r in placed:
        if r['tgt'] < last or r['tgt'] - r['en0'] < -3000000 or r['tgt'] - r['en0'] > 3000000:
            r['done'] = False
            drop += 1
        else:
            last = r['tgt']
    if drop:
        print("   controle de monotonie : %d pools ecartes" % drop)

    mapping = {}
    for r in allruns:
        if not r['done']:
            continue
        d = mapping.setdefault(r['rel'], {})
        c = r['tgt']
        full = walk_pool(B, c, len(r['run']))
        if full is None:
            continue
        p = c
        for j, idx in enumerate(r['run']):
            d[idx] = p
            p += full[j]
    tot = sum(len(v) for v in mapping.values())
    print("   editions placees : %d" % tot)
    ok = bad = nop = 0
    per = collections.Counter()
    per_ok = collections.Counter()
    for rel, entry in man['files'].items():
        for idx, e in enumerate(sorted(entry['edits'])):
            per[rel] += 1
            p = mapping.get(rel, {}).get(idx)
            if p is None:
                nop += 1
                continue
            if p == e[2]:
                ok += 1
                per_ok[rel] += 1
            else:
                bad += 1
    n = ok + bad + nop
    print("\nORACLE PASSES %s : %d/%d exacts (%.2f%%) | faux %d | non places %d"
          % (target, ok, n, 100.0 * ok / n, bad, nop))
    rows = sorted(((per_ok[r], per[r], r) for r in per), key=lambda x: x[0] - x[1])
    print("   fichiers parfaits : %d/%d"
          % (sum(1 for g2, n2, _ in rows if g2 == n2 and n2), len(rows)))
    print("   pires :")
    for g2, n2, rel in rows[:8]:
        print("      %-56s %d/%d" % (rel, g2, n2))
    print("   meilleurs :")
    for g2, n2, rel in rows[-12:][::-1]:
        print("      %-56s %d/%d" % (rel, g2, n2))
    (WORK / ('gmap3_%s.json' % target)).write_text(json.dumps(
        {k: [[i, p] for i, p in v.items()] for k, v in mapping.items()}))
    print("-> gmap3_%s.json" % target)


if __name__ == '__main__':
    main()
