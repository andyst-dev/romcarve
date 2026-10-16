#!/usr/bin/env python3
"""place_chunk.py - placer une suite CONTIGUE d'editions manquantes dans une ROM cible.

Deux lecons de Route111 (session 6) :
 - la fenetre de recherche ne se fonde pas sur un delta monotone : on prend dlo=min et
   dhi=max des deltas des editions voisines resolues (l'ancien batch_pool construisait une
   fenetre VIDE des que d1 > d2 : sur Route111 d1=4989 et d2=70844) ;
 - le DEBUT D'UN POOL N'EST PAS TOUJOURS PRECEDE D'UN 0xFF : dans un fichier de scripts il
   suit des octets de structure (`0f 00 b0 35 1f 08 09 03 02`) que la marche a 0xFF ne voit
   pas. On balaie donc TOUTE position dont le premier octet decode une lettre.

L'appariement se fait par CORRELATION DES LONGUEURS avec la reference (objets dans le meme
ordre, c'est le pas qui change) ; la plausibilite du texte n'est verifiee que sur les
finalistes, ce qui rend le balayage rapide. La tete du pool est prise au plus petit offset
dont l'octet precedent n'est pas une lettre (un depart quelques octets DANS le premier objet
rend exactement la meme marche).

Reference par defaut : le manifeste ITALIEN contre la ROM ALLEMANDE.

Usage : place_chunk.py <fichier> [--dmin N] [--dmax N] [--emit] [--maxlen N] [--top N]
        place_chunk.py <fichier> --oracle      # reference ESPAGNOL, cible ITALIEN, verite
                                               # = manifeste italien (le chiffre qui compte)
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

import bisect, gzip, json, sys, time
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
LOC = f"{REF_DIR}/"
rel = sys.argv[1]
emit = '--emit' in sys.argv
ORACLE = '--oracle' in sys.argv
arg = lambda name, dflt: int(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else dflt
dmin_forced = arg('--dmin', None)
dmax_forced = arg('--dmax', None)
maxlen = arg('--maxlen', 3000)
topk = arg('--top', 25)

if ORACLE:
    # oracle : reference ESPAGNOL, cible ITALIEN, verite = manifeste italien lui-meme
    # (les ancres sont les offsets italiens des AUTRES fichiers : parfaites par
    # construction, ce qui teste le balayage, la correlation et la tete, pas les ancres).
    refpath, target, truthpath = LOC + 'spanish.json.gz', 'IT', LOC + 'italian.json.gz'
    _it = json.load(gzip.open(LOC + 'italian.json.gz'))['files']
    cur = {}
    for _f, _v in _it.items():
        if _f == rel:
            continue
        for _i, _e in enumerate(sorted(_v['edits'])):
            cur.setdefault(_f, []).append([_i, _e[2]])
else:
    refpath, target, anchorpath, truthpath = LOC + 'italian.json.gz', 'DE', 'mapping_de_verifie.json', None
    cur = json.loads((WORK / anchorpath).read_text())

man = json.load(gzip.open(refpath))['files']
rom = C.ROMS[target].read_bytes()
CM = C._CM
GOOD = sorted({b[0] for k, b in CM.enc.items() if len(b) == 1 and k.isascii() and k.isalpha()})
GOODSET = set(GOOD)

delts = []
for f, entry in man.items():
    ed = sorted(entry['edits'])
    got = dict(cur.get(f, []))
    for i, e in enumerate(ed):
        if i in got:
            delts.append((e[2], got[i] - e[2]))
delts.sort()
itoffs = [d[0] for d in delts]

ed = sorted(man[rel]['edits'])
have = {i for i, _ in cur.get(rel, [])}
miss = [i for i in range(len(ed)) if i not in have]
if not miss:
    print('rien a placer'); sys.exit(0)
chunks = []
s = miss[0]
for k in range(1, len(miss)):
    if miss[k] != miss[k - 1] + 1 or ed[miss[k]][2] != ed[miss[k - 1]][2] + ed[miss[k - 1]][3]:
        chunks.append((s, miss[k - 1])); s = miss[k]
chunks.append((s, miss[-1]))
chunks = [c for c in chunks if c[1] - c[0] + 1 >= 3]
print('%s [%s] : %d editions manquantes, %d suites' % (rel, target, len(miss), len(chunks)))


def clean(t, minratio=0.45):
    if not t:
        return False
    t = t.split('\\')[0].split('\n')[0]
    if not t:
        return False
    if any('\u3040' <= c <= '\u30ff' or '\u0400' <= c <= '\u04ff' for c in t):
        return False
    return sum(c.isalnum() for c in t) / len(t) >= minratio


def head_ok(p):
    try:
        t = CM.decode(rom[p:p + 64])
    except Exception:
        return None
    return t if clean(t) else None


out = {}
for i0, i1 in chunks:
    a = ed[i0][2]
    b = ed[i1][2] + ed[i1][3]
    itlens = [e[3] for e in ed[i0:i1 + 1]]
    n = len(itlens)
    if dmin_forced is not None:
        dlo, dhi = dmin_forced, dmax_forced
    else:
        k = bisect.bisect_left(itoffs, a) - 1
        j = bisect.bisect_left(itoffs, b)
        d1 = delts[k][1] if k >= 0 else (delts[j][1] if j < len(delts) else 0)
        d2 = delts[j][1] if j < len(delts) else d1
        dlo, dhi = min(d1, d2), max(d1, d2)
    marge = max(2000, (b - a) // 2)
    lo = max(0, a + dlo - marge)
    hi = min(len(rom), a + dhi + marge)
    print('  suite [%d..%d] span=%d  d=[%d,%d]  fenetre=%d o' % (i0, i1, b - a, dlo, dhi, hi - lo))
    t0 = time.time()
    res = []
    for p in range(lo, hi):
        if rom[p] not in GOODSET:
            continue
        if head_ok(p) is None:
            continue
        q = p
        lens = []
        good = True
        for _ in range(n):
            z = rom.find(b'\xff', q, q + maxlen)
            if z < 0:
                good = False
                break
            lens.append(z + 1 - q)
            q = z + 1
        if not good:
            continue
        mx = sum(itlens) / n
        my = sum(lens) / n
        num = sum((itlens[i] - mx) * (lens[i] - my) for i in range(n))
        dx = sum((x - mx) ** 2 for x in itlens) ** 0.5
        dy = sum((y - my) ** 2 for y in lens) ** 0.5
        res.append((num / (dx * dy) if dx and dy else 0.0, p, q))
    res.sort(reverse=True)
    final = None
    for c, s, e in res[:topk]:
        k = s
        ok = 0
        for i in range(n):
            z = rom.find(b'\xff', k, k + maxlen)
            if z < 0:
                break
            if clean(CM.decode(rom[k:z])):
                ok += 1
            k = z + 1
        print('       corr=%.4f start=%d end=%d delta=%d  lisibles=%d/%d' % (c, s, e, s - a, ok, n))
        if ok / n >= 0.90 and final is None:
            final = (c, s, e)
    # PIEGE DE LA TETE : demarrer quelques octets DANS le premier objet donne la meme marche
    if final:
        top = max(c[0] for c in res)
        elig = [c for c in res if c[0] >= top - 0.02]
        heads = [c for c in elig if rom[c[1] - 1] not in GOODSET]
        if heads:
            final = min(heads, key=lambda c: c[1])
            print('    tete retenue : start=%d (parmi %d candidats quasi a egalite)' % (final[1], len(elig)))
    if final:
        c, s, e = final
        p = s
        for i in range(i0, i1 + 1):
            q = rom.find(b'\xff', p, p + maxlen)
            if q < 0:
                break
            out[i] = p
            p = q + 1
    print('    %.1fs' % (time.time() - t0))

if out:
    print('-> %d editions' % len(out))
    for i, p in sorted(out.items())[:6]:
        t = CM.decode(rom[p:rom.find(b'\xff', p, p + maxlen)])
        print('   [%d] %d %r' % (i, p, t[:70]))
    if ORACLE and truthpath:
        truth = json.load(gzip.open(truthpath))['files'][rel]['edits']
        truth = sorted(truth)
        good = sum(1 for i, p in out.items() if truth[i][2] == p)
        print('ORACLE %s : %d/%d offsets exacts' % (rel, good, len(out)))
    if emit:
        f = WORK / 'chunk_DE.json'
        d = json.loads(f.read_text()) if f.exists() else {}
        d[rel] = sorted([i, o] for i, o in out.items())
        f.write_text(json.dumps(d))
        print('-> chunk_DE.json (%s)' % rel)
