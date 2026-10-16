#!/usr/bin/env python3
"""content_find.py - retrouver une edition manquante par le CONTENU de son texte.

Le texte italien de l'edition contient des jetons qui ne se traduisent pas :
noms de personnes et de lieux, noms de POKéMON, d'objets, de capacites, chiffres.
On les encode avec le CHARMAP de la ROM (jamais en ASCII : la ROM n'est pas en
ASCII) et on cherche leurs occurrences dans la ROM allemande, dans une fenetre
bornee par les offsets deja places du meme fichier (+/- 150 000 octets).

Chaque occurrence remonte a l'OBJET qui la contient (0xFF precedent/suivant),
puis au debut du TEXTE dans cet objet (apres le prefixe de codes de controle).
Un candidat doit etre lisible, de rapport de longueur plausible, et non deja
revendique par une autre edition. Le score (nombre de jetons partages) n'est
qu'un ORDRE DE LECTURE : chaque candidat est relu avant d'etre accepte.

Usage :
    python3 content_find.py [--min-tokens N] [--show N] [--files a,b] [--emit]
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

import gzip, json, re, sys, collections, struct
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
man = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
de = C.ROMS['DE'].read_bytes()
it = C.ROMS['IT'].read_bytes()
CM = C._CM

TXT = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
          " .,!?'\"-:;()/…%+*=&@#<>[]{}~\\éÄÖÜäöüßÁÀÈ’‘“”")
# jetons trop frequents : ils n'identifient rien
STOP = {'POKéMON', 'TRAINER', 'ARENA', 'POKéNAV', 'POKéDEX', 'TEAM', 'ARENALEITER',
        'POKéBALL', 'TRAINERIN', 'MEISTER', 'BESITZER'}


def enc(s):
    out = bytearray()
    for ch in s:
        v = CM.enc.get(ch)
        if v is None:
            return None
        out += bytes(v)
    return bytes(out)


def tokens(t):
    tk = set(re.findall(r'\b[A-ZÄÖÜÉ][A-ZÄÖÜÉ]{2,}\b', t)) | set(re.findall(r'\b\d+\b', t))
    return {x for x in tk if x not in STOP}


def text_start(s, z):
    chars = []
    for k in range(s, z):
        for ch in CM.decode(de[k:k + 1]):
            chars.append((k, ch))
    last_bad = -1
    for idx, (_, ch) in enumerate(chars):
        if ch not in TXT:
            last_bad = idx
    if last_bad < 0:
        return s
    ts = chars[last_bad][0] + 1
    while ts < z:
        ch = CM.decode(de[ts:ts + 1])
        if ch in ('Á', 'À', 'È') and CM.decode(de[ts + 1:ts + 2]) != '}':
            ts += 1
        else:
            break
    return ts


def obj_around(h):
    s = de.rfind(b'\xff', max(0, h - 900), h)
    if s < 0:
        return None
    o = s + 1
    z = de.find(b'\xff', o, o + 1200)
    if z < 0:
        return None
    return o, z


held = collections.defaultdict(list)
for f, l in cur.items():
    for i, o in l:
        held[o].append((f, i))
bounds = {f: (min(o for _, o in l), max(o for _, o in l)) for f, l in cur.items() if l}

min_tokens = int(sys.argv[sys.argv.index('--min-tokens') + 1]) if '--min-tokens' in sys.argv else 1
only = set(sys.argv[sys.argv.index('--files') + 1].split(',')) if '--files' in sys.argv else None

results = []
for rel, v in man.items():
    if only and rel not in only:
        continue
    ed = sorted(v['edits'])
    have = dict(cur.get(rel, []))
    lo, hi = bounds.get(rel, (0, len(de)))
    lo, hi = max(0, lo - 150000), min(len(de), hi + 150000)
    for i, e in enumerate(ed):
        if i in have:
            continue
        tit = CM.decode(it[e[2]:e[2] + e[3] - 1])
        tk = tokens(tit)
        if not tk:
            continue
        cand = collections.Counter()
        for t in sorted(tk, key=len, reverse=True)[:6]:
            b = enc(t)
            if b is None:
                continue
            for m in re.finditer(re.escape(b), de[lo:hi]):
                ob = obj_around(lo + m.start())
                if not ob:
                    continue
                o, z = ob
                ts = text_start(o, z)
                txt = CM.decode(de[ts:z])
                if sum(ch in TXT for ch in txt) < 0.9 * len(txt):
                    continue
                if not (0.25 <= (len(txt) + 1) / max(1, e[3]) <= 3.5):
                    continue
                if held.get(ts) and (rel, i) not in held[ts]:
                    continue
                cand[ts] += 1
        best = []
        for ts, sc in cand.most_common(12):
            if sc < min_tokens:
                continue
            z = de.find(b'\xff', ts, ts + 1200)
            txt = CM.decode(de[ts:z])
            best.append((sc, ts, len(tit), len(txt),
                         tit.replace('\n', '~')[:58], txt.replace('\n', '~')[:58]))
        if best:
            results.append((rel, i, len(tk), best))

print('%d editions manquantes avec candidats' % len(results))
if '--show' in sys.argv:
    n = int(sys.argv[sys.argv.index('--show') + 1])
    for rel, i, ntk, best in results[:n]:
        print('### %s [%d] (%d jetons IT)' % (rel, i, ntk))
        for sc, s, li, ld, ti, td in best[:2]:
            print('   score=%d @%d IT(%d)=%s' % (sc, s, li, ti))
            print('               DE(%d)=%s' % (ld, td))
if '--emit' in sys.argv:
    (WORK / 'content_candidats.json').write_text(json.dumps(
        {'%s|%d' % (rel, i): [b[1] for b in best[:3]] for rel, i, _, best in results}))
    print('%d entrees -> content_candidats.json' % len(results))
