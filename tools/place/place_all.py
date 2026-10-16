#!/usr/bin/env python3
"""place_all.py - place_chunk.py en LOT sur tous les fichiers a suite contigue manquante.

Reference : manifeste ITALIEN. Cible : ROM ALLEMANDE (ou --oracle pour l'oracle italien,
reference espagnole). Met les resultats dans chunk_DE.json (cle = fichier, val = [[i,off]...]).

La methode est celle validee par l'oracle : fenetre de delta [min,max], balayage de TOUTES
les tetes de texte possibles (le pool ne suit pas forcement un 0xFF), appariement par
correlation des longueurs, verification textuelle des finalistes, tete = plus petit offset
quasi a egalite dont l'octet precedent n'est pas une lettre.

Usage : place_all.py [--min N] [--oracle] [--files f1,f2] [--emit] [--verbose]
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

import bisect, gzip, json, statistics, sys, time
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
LOC = f"{REF_DIR}/"
MINCH = int(sys.argv[sys.argv.index('--min') + 1]) if '--min' in sys.argv else 5
ORACLE = '--oracle' in sys.argv
EMIT = '--emit' in sys.argv
VERBOSE = '--verbose' in sys.argv
WIDE = '--wide' in sys.argv
only = set(sys.argv[sys.argv.index('--files') + 1].split(',')) if '--files' in sys.argv else None
MAXLEN = 3000

if ORACLE:
    refpath, target, truthpath = LOC + 'spanish.json.gz', 'IT', LOC + 'italian.json.gz'
    truth = json.load(gzip.open(truthpath))['files']
    cur = {}
    for _f, _v in truth.items():
        for _i, _e in enumerate(sorted(_v['edits'])):
            cur.setdefault(_f, []).append([_i, _e[2]])
    namemap = dict(sorted(truth.items()))
else:
    refpath, target, truthpath = LOC + 'italian.json.gz', 'DE', None
    cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())

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
print('ancres : %d' % len(delts))


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


def do(rel):
    ed = sorted(man[rel]['edits'])
    have = set() if ORACLE else {i for i, _ in cur.get(rel, [])}
    miss = [i for i in range(len(ed)) if i not in have]
    if not miss:
        return {}
    chunks = []
    s = miss[0]
    for k in range(1, len(miss)):
        if miss[k] != miss[k - 1] + 1 or ed[miss[k]][2] != ed[miss[k - 1]][2] + ed[miss[k - 1]][3]:
            chunks.append((s, miss[k - 1])); s = miss[k]
    chunks.append((s, miss[-1]))
    chunks = [c for c in chunks if c[1] - c[0] + 1 >= MINCH]
    out = {}
    for i0, i1 in chunks:
        kinds = {ed[i][4] for i in range(i0, i1 + 1)}
        if not kinds <= {'asm', 'c', 'text'}:
            if VERBOSE:
                print('   %s [%d..%d] kinds=%s : IGNORE (non textuel)' % (rel, i0, i1, sorted(kinds)), flush=True)
            continue
        a = ed[i0][2]
        b = ed[i1][2] + ed[i1][3]
        itlens = [e[3] for e in ed[i0:i1 + 1]]
        n = len(itlens)
        k = bisect.bisect_left(itoffs, a) - 1
        j = bisect.bisect_left(itoffs, b)
        d1 = delts[k][1] if k >= 0 else (delts[j][1] if j < len(delts) else 0)
        d2 = delts[j][1] if j < len(delts) else d1
        # DELTA LOCAL MEDIAN (+/-200 ko) plutot que celui des deux voisins immediats :
        # mesure sur 4000 editions resolues, l'erreur mediane tombe a 205 octets (p90 4 866)
        # contre plusieurs milliers pour le voisin immediat, et c'est ce qui rend la fenetre
        # exploitable sur les PETITS pools ou une correlation sur 4 longueurs ne distingue
        # plus rien (tous les candidats sortent a 1,0000).
        lo_i = bisect.bisect_left(itoffs, a - 200000)
        hi_i = bisect.bisect_left(itoffs, a + 200000)
        if hi_i - lo_i >= 5:
            med = int(statistics.median([delts[t][1] for t in range(lo_i, hi_i)]))
        else:
            med = (d1 + d2) // 2
        marge = max(3000, (b - a) // 2)
        if WIDE:
            marge = max(marge, 30000)
        lo = max(0, a + med - marge)
        hi = min(len(rom), b + med + marge)
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
                z = rom.find(b'\xff', q, q + MAXLEN)
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
            res.append((num / (dx * dy) if dx and dy else 0.0, p))
        if not res:
            continue
        res.sort(reverse=True)
        final = None
        for c, s in res[:25]:
            k2 = s
            ok = 0
            for i in range(n):
                z = rom.find(b'\xff', k2, k2 + MAXLEN)
                if z < 0:
                    break
                if clean(CM.decode(rom[k2:z])):
                    ok += 1
                k2 = z + 1
            if ok / n >= 0.90:
                final = (c, s)
                break
        if final is None:
            continue
        # RAFFINEMENT DU DECALAGE : un pool peut etre place k objets TROP LOIN (mesure :
        # MagmaHideout_3F_1R, DE[i] = IT[i-1]) ; la correlation est alors presque la meme et
        # l'appariement par texte ne le voit pas (tout est allemand). On essaie donc, pour les
        # meilleurs candidats, toutes les tetes a 0xFF jusqu'a 400 octets EN ARRIERE et on
        # garde l'appariement de correlation maximale.
        ext = list(res[:30])
        seen = {c[1] for c in res[:30]}
        for c0, s0 in res[:30]:
            p0 = s0 - 1
            lim = max(0, s0 - 400)
            while p0 > lim:
                z = rom.rfind(b'\xff', lim, p0)
                if z < 0:
                    break
                cand_p = z + 1
                if cand_p not in seen:
                    seen.add(cand_p)
                    q = cand_p
                    lens = []
                    ok2 = True
                    for _ in range(n):
                        zz = rom.find(b'\xff', q, q + MAXLEN)
                        if zz < 0:
                            ok2 = False
                            break
                        lens.append(zz + 1 - q)
                        q = zz + 1
                    if ok2:
                        mx = sum(itlens) / n
                        my = sum(lens) / n
                        num = sum((itlens[i] - mx) * (lens[i] - my) for i in range(n))
                        dx = sum((x - mx) ** 2 for x in itlens) ** 0.5
                        dy = sum((y - my) ** 2 for y in lens) ** 0.5
                        ext.append((num / (dx * dy) if dx and dy else 0.0, cand_p))
                p0 = z
        ext.sort(reverse=True)
        final = None
        for c, s in ext[:25]:
            k2 = s
            ok = 0
            for i in range(n):
                z = rom.find(b'\xff', k2, k2 + MAXLEN)
                if z < 0:
                    break
                if clean(CM.decode(rom[k2:z])):
                    ok += 1
                k2 = z + 1
            if ok / n >= 0.90:
                final = (c, s)
                break
        if final is None:
            continue
        top = max(c[0] for c in ext)
        elig = [c for c in ext if c[0] >= top - 0.02]
        # TETE DU POOL : dans un pool, demarrer quelques octets DANS le premier objet rend
        # exactement la meme marche (meme 0xFF suivant), donc la meme correlation : la tete
        # n'est decidale que si l'objet precedent se TERMINE juste avant elle. L'ancre sure
        # est donc un 0xFF immediatement avant (0x00 = ESPACE dans ce charmap, il ne vaut
        # rien comme ancre : mesure a l'oracle, il faisait demarrer la tete 7 a 21 octets
        # trop tard). Sans cette ancre on RETIRE la tete : le reste de la marche est
        # deterministe une fois le premier 0xFF fixe.
        strict = [c for c in elig if rom[c[1] - 1] == 0xFF]
        drop_head = False
        if strict:
            final = min(strict, key=lambda c: c[1])
        else:
            final = min(elig, key=lambda c: c[1])
            drop_head = True
        c, s = final
        p = s
        first = i0 + 1 if drop_head else i0
        if drop_head:
            z = rom.find(b'\xff', s, s + MAXLEN)
            if z < 0:
                continue
            p = z + 1
        chunk_out = {}
        for i in range(first, i1 + 1):
            q = rom.find(b'\xff', p, p + MAXLEN)
            if q < 0:
                break
            # chaque objet place doit se DECODER (un offset qui tombe sur des octets de
            # structure, un blob fusionne ou un reste de kana est rejete ici, objet par
            # objet : le pas de la marche reste aligne, on perd seulement la ligne fautive)
            if clean(CM.decode(rom[p:q])):
                chunk_out[i] = p
            p = q + 1
        # GARDE-FOU DE COLLISION : si un objet de ce bloc tombe sur un offset DEJA mappe dans
        # le meme fichier, la marche a derive (mesure : text_input_strings [31..43] qui
        # recouvre les editions deja resolues par contenu). On jette le bloc entier.
        used = set(off for _, off in cur.get(rel, [])) | set(out.values())
        if any(o in used for o in chunk_out.values()):
            if VERBOSE:
                print('   %s [%d..%d] COLLISION avec un offset deja mappe : bloc rejete'
                      % (rel, i0, i1), flush=True)
            continue
        out.update(chunk_out)
        if VERBOSE:
            print('   %s [%d..%d] n=%d corr=%.4f start=%d delta=%d tete=%s retenus=%d'
                  % (rel, i0, i1, n, c, s, s - a, 'RETIREE' if drop_head else 'gardee',
                     sum(1 for i in out if i0 <= i <= i1)), flush=True)
    return out


files = [f for f in man if (only is None or f in only)]
allout = {}
t0 = time.time()
if ORACLE:
    allout = {f: sorted([i, o] for i, o in cur[f]) for f in cur}
for rel in files:
    if ORACLE:
        cur = {k: v for k, v in allout.items() if k != rel}
    o = do(rel)
    if o:
        allout[rel] = sorted([i, p] for i, p in o.items())
        print('%-58s %3d editions' % (rel, len(o)), flush=True)

if ORACLE:
    tot = good = 0
    bad = []
    for f, lst in allout.items():
        ed = sorted(truth[f]['edits'])
        for i, p in lst:
            tot += 1
            if ed[i][2] == p:
                good += 1
            else:
                bad.append((f, i, ed[i][2], p))
    print('\nORACLE GLOBAL : %d/%d offsets exacts (%.2f%%)' % (good, tot, 100.0 * good / max(1, tot)))
    for b in bad[:20]:
        print('   ecart %s [%d] verite=%d place=%d' % b)
else:
    tot = sum(len(v) for v in allout.values())
    print('\n%d fichiers, %d editions' % (len(allout), tot))
    if EMIT:
        (WORK / 'chunk_DE.json').write_text(json.dumps(allout))
        print('-> chunk_DE.json')
print('%.1fs' % (time.time() - t0))
