#!/usr/bin/env python3
"""deplace2.py - placement global des pools par DP monotone.

Etape 1 (par run) : candidats de debut de pool, scorés par la correlation des
   longueurs EN/cible (les objets texte sont empiles cote EN comme cote cible).
Etape 2 (globale) : les pools gardent leur ORDRE dans la ROM et le DECALAGE
   (cible - EN) varie LENTEMENT. Un DP sur la suite des runs (dans l'ordre EN)
   choisit pour chacun le candidat qui maximise
        somme(4 * correlation) - penalite(|decalage_i - decalage_{i-1}|)
   ce qui elimine les candidats isoles aberrants.
Etape 3 : iteration - les pools places servent d'ancres pour resserrer la fenetre
   des runs restants, et on repasse.

Usage : deplace2.py <CIBLE> <manifeste> [--iters N]
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

WORK = Path(f"{WORK}")
MAXLEN = 400
PEN = 1.5          # penalite par Ko de saut de decalage
MINCORR = 0.50
TOPK = 8


def runs_of(rel, edits, syms, names):
    npos = [p for p, _n in names]
    pos, ln = [], []
    for e in edits:
        j = bisect.bisect_right(npos, e[0]) - 1
        nm = names[j][1] if j >= 0 else None
        c = syms.get(nm) if nm else None
        pos.append(c[0][0] if c else None)
        ln.append((c[0][1] or None) if c else None)
    known = [i for i, p in enumerate(pos) if p is not None]
    for k in range(len(known) - 1):
        i, i2 = known[k], known[k + 1]
        if ln[i] is None and i2 == i + 1:
            ln[i] = pos[i2] - pos[i]
    runs = []
    cur = []
    for i in range(len(edits)):
        if pos[i] is None:
            if cur:
                runs.append(cur)
            cur = []
            continue
        if cur and ln[cur[-1]] is not None and pos[i] == pos[cur[-1]] + ln[cur[-1]]:
            cur.append(i)
        else:
            if cur:
                runs.append(cur)
            cur = [i]
    if cur:
        runs.append(cur)
    return pos, ln, runs


def gen_cands(B, run, pos, ln, shift_expect, tol):
    """candidats pour un run, dans la fenetre [expect-tol, expect+tol]."""
    if len(run) < 3 or any(ln[i] is None for i in run[:-1]):
        return []
    Len = [ln[i] for i in run[:-1]]
    en0 = pos[run[0]]
    out = []
    lo = int(shift_expect - tol)
    hi = int(shift_expect + tol)
    for d in range(lo, hi + 1):
        c = en0 + d
        if c <= 0 or c >= len(B) or B[c - 1] != 0xFF:
            continue
        q = walk_pool(B, c, len(run), quick=6)
        if q is None or corr(Len[:len(q)], q) < 0.45:
            continue
        full = walk_pool(B, c, len(run))
        if full is None or len(full) != len(run):
            continue
        r = corr(Len, full[:len(Len)])
        if r >= MINCORR:
            out.append((r, c, full))
    out.sort(key=lambda x: -x[0])
    return out[:TOPK]


def main():
    target = sys.argv[1]
    man = json.loads(gzip.decompress(Path(sys.argv[2]).read_bytes()))
    iters = int(sys.argv[sys.argv.index('--iters') + 1]) if '--iters' in sys.argv else 4
    B = ROMS[target].read_bytes()
    syms = json.loads((WORK / 'en_symbols.json').read_text())
    wins = [w for w in json.loads((WORK / ('anchors_sec_%s.json' % target)).read_text())
            if w[4] is not None]
    wpos = np.array([w[4] for w in wins], dtype=float)
    wsh = np.array([w[5] - w[4] for w in wins], dtype=float)

    # collecte des runs de tous les fichiers
    allruns = []      # (en0, rel, run, pos, ln)
    for rel, entry in man['files'].items():
        names = file_names(rel)
        edits = sorted(entry['edits'])
        pos, ln, runs = runs_of(rel, edits, syms, names)
        for run in runs:
            if len(run) >= 3:
                allruns.append((pos[run[0]], rel, run, pos, ln))
    allruns.sort()
    print("%s : %d runs (>=3 objets) a placer" % (target, len(allruns)))

    def expect_shift(en, placed):
        """decalage attendu : interpole depuis les pools places, sinon les ancres."""
        if placed:
            xs = np.array([p[0] for p in placed], dtype=float)
            ys = np.array([p[1] for p in placed], dtype=float)
            if len(xs) >= 2:
                i = int(np.searchsorted(xs, en))
                lo = max(0, min(i - 1, len(xs) - 2))
                x0, x1 = xs[lo], xs[lo + 1]
                y0, y1 = ys[lo], ys[lo + 1]
                if x1 > x0:
                    return y0 + (y1 - y0) * (en - x0) / (x1 - x0)
                return y0
            return float(ys[0])
        j = int(np.searchsorted(wpos, en))
        lo, hi = max(0, j - 6), min(len(wpos), j + 6)
        if hi <= lo:
            return float(np.median(wsh))
        return float(np.median(wsh[lo:hi]))

    placed = []          # (en0, shift) des pools places
    mapping = {}         # rel -> {edit_index: offset}
    hist = []
    for it in range(iters):
        tol = 40000 if it == 0 else (6000 if it == 1 else 1500)
        cands = []
        for (en0, rel, run, pos, ln) in allruns:
            ex = expect_shift(en0, placed)
            cs = gen_cands(B, run, pos, ln, ex, tol)
            cands.append(cs)
        # DP monotone. Etat = (score, dernier_pool_place). L'invariant de continuite
        # n'est pas l'egalite du decalage mais son EVOLUTION : entre deux pools, la
        # taille cible vaut ~1,09 fois la taille anglaise, donc
        #     delta_decalage ~= 0,09 * distance_EN   (a la tolerance des fichiers voisins)
        n = len(allruns)
        SKIP = 5.0
        scores = []
        for i in range(n):
            en0 = allruns[i][0]
            cur = []
            if i == 0:
                cur.append((0.0, None, None))
            else:
                for k, (sc, cand, _bk) in enumerate(scores[i - 1]):
                    cur.append((sc - SKIP, cand, k))
            for (r, c, full) in cands[i]:
                w = 4.0 * r * min(1.0, len(full) / 12.0)
                if i == 0:
                    cur.append((w, (c, en0, len(full)), None))
                    continue
                b = None
                for k, (sc, cand, _bk) in enumerate(scores[i - 1]):
                    if cand is None:
                        v = sc + w - 2.0
                    else:
                        pc, pe, _pn = cand
                        dist = en0 - pe
                        if dist <= 0:
                            continue
                        delta = (c - en0) - (pc - pe)
                        allowed = 0.04 * dist + 500
                        err = abs(delta - 0.09 * dist)
                        v = sc + w - 0.8 * max(0.0, err - allowed) / 1000.0
                        if err > 0.35 * dist + 3000:
                            continue
                    if b is None or v > b[0]:
                        b = (v, k)
                if b is not None:
                    cur.append((b[0], (c, en0, len(full)), b[1]))
            cur.sort(key=lambda x: -x[0])
            seen = set()
            keep = []
            for sc, cand, back in cur:
                key = cand[0] if cand else None
                if key in seen:
                    continue
                seen.add(key)
                keep.append((sc, cand, back))
                if len(keep) >= 24:
                    break
            scores.append(keep)
        if not scores or not scores[-1]:
            break
        i = n - 1
        k = 0
        mapping, placed, nplaced = {}, [], 0
        while i >= 0:
            if k >= len(scores[i]):
                i -= 1
                k = 0
                continue
            sc, cand, back = scores[i][k]
            if cand is not None:
                c, en0, n_obj = cand
                en0r, rel, run, pos, ln = allruns[i]
                full = walk_pool(B, c, len(run)) or []
                d = mapping.setdefault(rel, {})
                p = c
                for j, idx in enumerate(run):
                    d[idx] = p
                    if j < len(full):
                        p += full[j]
                placed.append((en0r, c - en0r))
                nplaced += len(run)
            i -= 1
            k = back if back is not None else 0
        placed.sort()
        hist.append(nplaced)
        if it + 1 == iters:
            break
        # re-injection : les runs non retenus (score trop bas) deviennent des ancres ?
        if len(hist) >= 2 and hist[-1] == hist[-2]:
            pass
    print("   editions placees : %d | pools ancres : %d"
          % (sum(len(v) for v in mapping.values()), len(placed)))

    tot_ed = sum(len(v['edits']) for v in man['files'].values())
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
    print("\nORACLE GLOBAL %s : %d/%d exacts (%.2f%%) | faux %d | non places %d"
          % (target, ok, n, 100.0 * ok / n, bad, nop))
    rows = sorted(((per_ok[r], per[r], r) for r in per), key=lambda x: x[0] - x[1])
    print("   fichiers parfaits : %d/%d"
          % (sum(1 for g2, n2, _ in rows if g2 == n2 and n2), len(rows)))
    print("   pires :")
    for g2, n2, rel in rows[:8]:
        print("      %-56s %d/%d" % (rel, g2, n2))
    print("   meilleurs :")
    for g2, n2, rel in rows[-10:][::-1]:
        print("      %-56s %d/%d" % (rel, g2, n2))
    (WORK / ('gmap_%s.json' % target)).write_text(json.dumps(
        {k: [[i, p] for i, p in v.items()] for k, v in mapping.items()}))
    print("-> gmap_%s.json" % target)


if __name__ == '__main__':
    main()
