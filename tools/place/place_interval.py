#!/usr/bin/env python3
"""place_interval.py - placer une suite manquante dans un INTERVALLE EXACT.

Fait mesure : l'ordre des editions est le meme dans toutes les langues, donc deux editions
resolues qui ENCADRENT la suite dans l'ordre IT l'encadrent aussi dans la ROM allemande. On
connait donc un intervalle EXACT [Lo, Hi] ou le pool doit tenir entierement. Mesure sur les
fichiers qui resistent : 1 034 a 7 354 octets, contre les +/- 60 000 d'une fenetre de delta -
c'est ce qui fait tomber a presque rien le nombre de candidats qui se ressemblent.

Contraintes : le debut cherche est dans [Lo, Hi-1], la marche de n objets doit se TERMINER
avant Hi, et le bloc ne doit pas recouvrir un offset deja mappe dans le meme fichier.

Usage : place_interval.py [--min N] [--emit] [--verbose] [--files f1,f2]
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
MINCH = int(sys.argv[sys.argv.index('--min') + 1]) if '--min' in sys.argv else 3
EMIT = '--emit' in sys.argv
VERBOSE = '--verbose' in sys.argv
only = set(sys.argv[sys.argv.index('--files') + 1].split(',')) if '--files' in sys.argv else None
MAXLEN = 1200

man = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
de = C.ROMS['DE'].read_bytes()
CM = C._CM
GOODSET = {b[0] for k, b in CM.enc.items() if len(b) == 1 and k.isascii() and k.isalpha()}

seq = []
for f, v in man.items():
    ed = sorted(v['edits'])
    got = dict(cur.get(f, []))
    for i, e in enumerate(ed):
        seq.append((e[2], f, i, got.get(i, -1)))
seq.sort()
itofs = [s[0] for s in seq]
RES = [g for g, s in enumerate(seq) if s[3] >= 0]
ITROM = C.ROMS['IT'].read_bytes()
IED = {f: sorted(v['edits']) for f, v in man.items()}


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
        t = CM.decode(de[p:p + 64])
    except Exception:
        return None
    return t if clean(t) else None


def interval(a, b):
    k = bisect.bisect_left(RES, bisect.bisect_left(itofs, a)) - 1
    if k < 0:
        k = 0
    while k >= 0 and seq[RES[k]][0] >= a:
        k -= 1
    j = bisect.bisect_left(RES, bisect.bisect_left(itofs, b))
    while j < len(RES) and seq[RES[j]][0] <= b:
        j += 1
    if k < 0 or j >= len(RES):
        return None
    return seq[RES[k]][3], seq[RES[j]][3], seq[RES[k]], seq[RES[j]]


out = {}
for rel in sorted(man):
    if only and rel not in only:
        continue
    ed = sorted(man[rel]['edits'])
    have = {i for i, _ in cur.get(rel, [])}
    miss = [i for i in range(len(ed)) if i not in have]
    if not miss:
        continue
    chunks = []
    s = miss[0]
    for k in range(1, len(miss)):
        if miss[k] != miss[k - 1] + 1 or ed[miss[k]][2] != ed[miss[k - 1]][2] + ed[miss[k - 1]][3]:
            chunks.append((s, miss[k - 1])); s = miss[k]
    chunks.append((s, miss[-1]))
    for i0, i1 in chunks:
        n = i1 - i0 + 1
        if n < MINCH:
            continue
        kinds = {ed[i][4] for i in range(i0, i1 + 1)}
        if not kinds <= {'asm', 'c', 'text'}:
            continue
        a = ed[i0][2]
        b = ed[i1][2] + ed[i1][3]
        iv = interval(a, b)
        if iv is None:
            if VERBOSE:
                print('   %s [%d..%d] : pas d\'encadrement' % (rel, i0, i1), flush=True)
            continue
        lo, hi, sa, sb = iv
        if hi - lo < 100 or hi - lo > 60000:
            if VERBOSE:
                print('   %s [%d..%d] : intervalle %d o inexploitable' % (rel, i0, i1, hi - lo), flush=True)
            continue
        itlens = [e[3] for e in ed[i0:i1 + 1]]

        def dg_of(t):
            return ''.join(c for c in t if c.isdigit())

        # FILTRE PAR LES CHIFFRES DE LA PREMIERE EDITION : les nombres sont independants de la
        # langue, donc si l'edition IT de tete en contient, le premier objet allemand doit
        # porter EXACTEMENT les memes (mesure AbandonedShip_HiddenFloorCorridors : "CABINA 1"
        # ne peut tomber que sur "K. 1", ce qui ecarte le pool voisin et le decalage d'un cran).
        dg0 = dg_of(CM.decode(ITROM[ed[i0][2]:ed[i0][2] + ed[i0][3] - 1]))
        res = []
        for p in range(max(0, lo), min(len(de), hi)):
            if de[p] not in GOODSET:
                continue
            if head_ok(p) is None:
                continue
            if dg0:
                z0 = de.find(b'\xff', p, p + MAXLEN)
                if z0 < 0 or dg_of(CM.decode(de[p:z0])) != dg0:
                    continue
            q = p
            lens = []
            ok = True
            for _ in range(n):
                z = de.find(b'\xff', q, q + MAXLEN)
                if z < 0 or z + 1 > hi:
                    ok = False
                    break
                lens.append(z + 1 - q)
                q = z + 1
            if not ok:
                continue
            mx = sum(itlens) / n
            my = sum(lens) / n
            num = sum((itlens[i] - mx) * (lens[i] - my) for i in range(n))
            dx = sum((x - mx) ** 2 for x in itlens) ** 0.5
            dy = sum((y - my) ** 2 for y in lens) ** 0.5
            res.append((num / (dx * dy) if dx and dy else 0.0, p, q))
        if not res:
            if VERBOSE:
                print('   %s [%d..%d] : aucun candidat dans %d o' % (rel, i0, i1, hi - lo), flush=True)
            continue
        res.sort(reverse=True)
        final = None
        for c, s0, e0 in res[:20]:
            k2 = s0
            nok = 0
            for i in range(n):
                z = de.find(b'\xff', k2, k2 + MAXLEN)
                if z < 0:
                    break
                if clean(CM.decode(de[k2:z])):
                    nok += 1
                k2 = z + 1
            if nok / n >= 0.90:
                final = (c, s0)
                break
        if final is None:
            if VERBOSE:
                print('   %s [%d..%d] : candidats mais texte non lisible' % (rel, i0, i1), flush=True)
            continue
        strict = [c for c in res if c[0] >= final[0] - 0.02 and de[c[1] - 1] == 0xFF]
        drop = False
        if strict:
            c, s0, _ = min(strict, key=lambda c: c[1])
        else:
            c, s0, _ = min([c for c in res if c[0] >= final[0] - 0.02], key=lambda c: c[1])
            drop = True
        p = s0
        first = i0 + 1 if drop else i0
        if drop:
            z = de.find(b'\xff', s0, s0 + MAXLEN)
            if z < 0:
                continue
            p = z + 1
        chunk_out = {}
        for i in range(first, i1 + 1):
            q = de.find(b'\xff', p, p + MAXLEN)
            if q < 0:
                break
            if clean(CM.decode(de[p:q])):
                chunk_out[i] = p
            p = q + 1
        # REALIGNEMENT PAR LES CHIFFRES. Motif dominant des fichiers qui resistent : le bloc
        # est entier mais decale d'un objet (mesure AbandonedShip_HiddenFloorCorridors :
        # IT "CABINA 1" <-> DE "K. 2"). Les nombres sont INDEPENDANTS de la langue, donc on
        # essaie les decalages -2..+2 et on garde celui dont les suites de chiffres coincident
        # le mieux. Sans chiffres dans le texte, on garde le placement tel quel.
        def digits(t):
            return ''.join(c for c in t if c.isdigit())

        def obj_start_before(o):
            z = de.rfind(b'\xff', max(0, o - MAXLEN), o)
            if z < 0:
                return None
            z2 = de.rfind(b'\xff', max(0, z - MAXLEN), z)
            return (z2 + 1) if z2 >= 0 else None

        def obj_start_after(o):
            z = de.find(b'\xff', o, o + MAXLEN)
            return (z + 1) if z >= 0 else None

        if chunk_out:
            keys = sorted(chunk_out)
            seq_o = {0: chunk_out[keys[0]]}
            back, cc = [], chunk_out[keys[0]]
            for _ in range(2):
                cc = obj_start_before(cc)
                if cc is None:
                    break
                back.append(cc)
            seq_o.update({-(k + 1): v for k, v in enumerate(back)})
            fwd, cc = [], chunk_out[keys[-1]]
            for _ in range(2):
                cc = obj_start_after(cc)
                if cc is None:
                    break
                fwd.append(cc)
            seq_o.update({(k + 1): v for k, v in enumerate(fwd)})
            itrom = ITROM
            ited = IED[rel]
            base = None
            for i in keys:
                t = CM.decode(itrom[ited[i][2]:ited[i][2] + ited[i][3] - 1])
                if digits(t):
                    base = base or {}
                    base[i] = digits(t)
            if base:
                best = (None, -1)
                for sh in (-2, -1, 0, 1, 2):
                    pos_next = None
                    sc = 0
                    ok = True
                    for t, i in enumerate(keys):
                        gcd = seq_o.get(t + sh)
                        if gcd is None:
                            ok = False
                            break
                        z = de.find(b'\xff', gcd, gcd + MAXLEN)
                        if z < 0:
                            ok = False
                            break
                        dd = digits(CM.decode(de[gcd:z]))
                        idg = base.get(i)
                        if idg is None:
                            continue
                        sc += 1 if dd == idg else -1
                    if ok and sc > best[1]:
                        best = (sh, sc)
                sh = best[0]
                if best[0] not in (None, 0) and best[1] > 0:
                    newmap = {}
                    for t, i in enumerate(keys):
                        gcd = seq_o.get(t + sh)
                        z = de.find(b'\xff', gcd, gcd + MAXLEN)
                        if z >= 0 and clean(CM.decode(de[gcd:z])):
                            newmap[i] = gcd
                    if newmap:
                        chunk_out = newmap
                        if VERBOSE:
                            print('   %-52s REALIGNE de %+d objet(s) (score chiffres %d)'
                                  % (rel, sh, best[1]), flush=True)
        used = set(o for _, o in cur.get(rel, [])) | set(out.get(rel, {}).values() if isinstance(out.get(rel), dict) else [])
        used |= set(v for v in (out.get(rel) or {}))
        if isinstance(out.get(rel), list):
            used |= set(o for _, o in out[rel])
        if any(o in used for o in chunk_out.values()):
            if VERBOSE:
                print('   %s [%d..%d] COLLISION - rejete' % (rel, i0, i1), flush=True)
            continue
        if chunk_out:
            out.setdefault(rel, {})
            out[rel].update(chunk_out)
            if VERBOSE:
                print('   %-52s [%d..%d] intervalle %-6d candidats %-4d retenus %d corr=%.3f'
                      % (rel, i0, i1, hi - lo, len(res), len(chunk_out), c), flush=True)

if EMIT:
    (WORK / 'chunk_DE.json').write_text(json.dumps({k: sorted([i, o] for i, o in v.items()) for k, v in out.items()}))
tot = sum(len(v) for v in out.values())
print('%d editions dans %d fichiers' % (tot, len(out)))
print('total : %d / 19347' % (sum(len(v) for v in cur.values()) + tot))
