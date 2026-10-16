#!/usr/bin/env python3
"""batch_pool.py - placer EN LOT les pools empaquetes restants par delta + marche.

Pour chaque fichier du manifeste italien ayant des editions manquantes, on prend chaque
suite CONTIGUE d'editions manquantes (une edition commence exactement a la fin de la
precedente), on cherche le debut allemand dans la fenetre donnee par le delta des voisins
resolus, on classe les candidats par CORRELATION des longueurs avec l'italien, et on ne
retient que ceux qui passent : premier caractere decode = lettre ASCII, >= 95 % d'objets
lisibles, fin a moins de `tol` octets de la fin attendue.

Usage : batch_pool.py [--emit] [--min N] [--files f1,f2]
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
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
emit = '--emit' in sys.argv
only = None
if '--files' in sys.argv:
    only = set(sys.argv[sys.argv.index('--files') + 1].split(','))

with gzip.open(f"{REF_DIR}/italian.json.gz") as fh:
    man = json.load(fh)['files']
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
de = C.ROMS['DE'].read_bytes()
N_ROM = len(de)

delts = []
for f, entry in man.items():
    ed = sorted(entry['edits'])
    got = dict(cur.get(f, []))
    for i, e in enumerate(ed):
        if i in got:
            delts.append((e[2], got[i] - e[2]))
delts.sort()
itoffs = [d[0] for d in delts]


def plausible(off):
    e = de.find(b'\xff', off, off + 2000)
    if e < 0:
        return None
    try:
        t = C._CM.decode(de[off:e])
    except Exception:
        return None
    t = t.split('\\')[0].split('\n')[0]
    if len(t) < 1:
        return ''
    al = sum(c.isalnum() for c in t)
    if al / len(t) < 0.45:
        return None
    if any('\u3040' <= c <= '\u30ff' or '\u0400' <= c <= '\u04ff' for c in t):
        return None
    return t


def clean_head(t):
    """les 4 premiers caracteres decodes doivent ressembler a un vrai debut de phrase
    (lettres/chiffres ASCII, espace, apostrophe ou tiret, ou umlaut allemand) : c'est ce
    qui ecarte les quelques octets de structure qui precedent le pool."""
    safe = " -'"
    for ch in t[:4]:
        if ch in 'ÄÖÜäöüß':
            continue
        if ch.isascii() and (ch.isalnum() or ch in safe):
            continue
        return False
    return True


def place(rel, i0, i1):
    ed = sorted(man[rel]['edits'])
    a = ed[i0][2]
    b = ed[i1][2] + ed[i1][3]
    lo_i = bisect.bisect_left(itoffs, a) - 1
    hi_i = bisect.bisect_left(itoffs, b)
    before = delts[lo_i] if lo_i >= 0 else None
    after = delts[hi_i] if hi_i < len(delts) else None
    d1 = before[1] if before else (after[1] if after else 0)
    d2 = after[1] if after else d1
    it_lens = [e[3] for e in ed[i0:i1 + 1]]
    n = i1 - i0 + 1
    tol = max(128, (b - a) // 8)
    marge = max(400, (b - a) // 4)
    SCORE = []
    for start in range(a + d1 - marge, a + d2 + marge):
        t0 = plausible(start)
        if t0 is None or not t0 or not t0[0].isascii() or not t0[0].isalpha() or not clean_head(t0):
            continue
        p = start
        lens, ok = [], 0
        for _ in range(n):
            q = de.find(b'\xff', p, p + 2000)
            if q < 0:
                break
            if plausible(p):
                ok += 1
            lens.append(q + 1 - p)
            p = q + 1
        if ok / n < 0.90 or abs(p - (b + d2)) > tol:
            continue
        m = min(len(lens), len(it_lens))
        xs, ys = it_lens[:m], lens[:m]
        mx, my = sum(xs) / m, sum(ys) / m
        num = sum((xs[i] - mx) * (ys[i] - my) for i in range(m))
        dx = sum((x - mx) ** 2 for x in xs) ** 0.5
        dy = sum((y - my) ** 2 for y in ys) ** 0.5
        corr = num / (dx * dy) if dx and dy else 0.0
        SCORE.append((corr, start, p, ok / n))
    if not SCORE:
        return None
    # plusieurs debuts dans le meme objet de tete donnent la MEME marche : on prend le
    # PLUS PETIT debut dont la correlation reste proche du meilleur (sinon le premier
    # objet est un simple suffixe du vrai, cf. 'ich willkommen!' pour 'SCOTT: Hallo!').
    top = max(c[0] for c in SCORE)
    elig = [c for c in SCORE if c[0] >= top - 0.05]
    return min(elig, key=lambda c: c[1])


out, stats = {}, {}
for rel, entry in sorted(man.items()):
    if only and rel not in only:
        continue
    ed = sorted(entry['edits'])
    have = {i for i, _ in cur.get(rel, [])}
    miss = [i for i in range(len(ed)) if i not in have]
    if not miss:
        continue
    # suites contigues d'editions manquantes
    chunks, s = [], miss[0]
    for k in range(1, len(miss)):
        if miss[k] != miss[k - 1] + 1 or ed[miss[k]][2] != ed[miss[k - 1]][2] + ed[miss[k - 1]][3]:
            chunks.append((s, miss[k - 1]))
            s = miss[k]
    chunks.append((s, miss[-1]))
    placed = []
    for i0, i1 in chunks:
        if i1 - i0 + 1 < 5:
            continue
        r = place(rel, i0, i1)
        if not r:
            continue
        corr, start, end, ok = r
        # on redescend pour produire les offsets
        p = start
        for i in range(i0, i1 + 1):
            q = de.find(b'\xff', p, p + 2000)
            if q < 0:
                break
            placed.append([i, p])
            p = q + 1
    if placed and i1 >= 0:
        out[rel] = sorted(placed)
        stats[rel] = len(placed)
        print('%-58s %3d editions' % (rel, len(placed)), flush=True)
        if emit:
            (WORK / 'batch_DE.json').write_text(json.dumps(out))

print('\n%d fichiers, %d editions' % (len(out), sum(stats.values())))
if emit and out:
    (WORK / 'batch_DE.json').write_text(json.dumps(out))
    print('-> batch_DE.json')
