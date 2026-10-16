#!/usr/bin/env python3
"""ec_chain.py - enchainer TOUTES les tables easy_chat d'une ROM par comptage d'objets.

Mesure (oracle italien) : dans la section easy_chat, la disposition est STRICTEMENT
sequentielle et la MEME dans toutes les langues :

    [mots du groupe G][table de G (N_G enregistrements de 12 o)][mots du groupe G+1][table G+1]...

Donc une seule ancre suffit : depuis la table d'un groupe, on saute N*12 octets, on
COMPTE N_next objets texte (0xFF-terminated) - le nombre d'objets est invariant de
langue - et on retombe sur la table du groupe suivant (a l'alignement 4 pres, plus
parfois jusqu'a 12 octets de remplissage). Chaque table trouvee est verifiee par sa
STRUCTURE (pointeurs dans la ROM, enabled en {0,1}, rangs = permutation de [0,N)) et
par le DECODAGE de ses mots dans la langue cible.

Usage :
  ec_chain.py IT                 -> oracle : compare aux offsets du manifeste italien
  ec_chain.py DE                 -> ecrit ec_edits_DE.json
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

import gzip, json, sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
LOCALES = Path(f"{REF_DIR}")
target = sys.argv[1]

with gzip.open(LOCALES / 'italian.json.gz') as fh:
    man = json.load(fh)['files']

rom = C.ROMS[target].read_bytes()
N_ROM = len(rom)

ORDER = ['trainer', 'status', 'battle', 'greetings', 'people', 'voices', 'speech', 'endings',
         'feelings', 'conditions', 'actions', 'lifestyle', 'hobbies', 'time', 'misc',
         'adjectives', 'events', 'trendy']
FILE = {g: 'src/data/easy_chat/easy_chat_group_%s.h' % g for g in ORDER}
FILE['trendy'] = 'src/data/easy_chat/easy_chat_group_trendy_saying.h'

ANCHOR = {'IT': ('trainer', 5850952), 'DE': ('trainer', 5934612)}


def word_end(off, cap=250):
    if not (0 <= off < N_ROM):
        return None
    z = rom.find(b'\xff', off, off + cap)
    return None if z < 0 else z + 1


def plausible(off, minlen=1):
    e = word_end(off)
    if e is None or e - off - 1 < minlen:
        return False
    try:
        t = C._CM.decode(rom[off:e - 1])
    except Exception:
        return False
    t = t.split('\\')[0].split('\n')[0]
    if len(t) < minlen:
        return False
    al = sum(ch.isalnum() for ch in t)
    if al / max(1, len(t)) < 0.45:
        return False
    return not any('\u3040' <= ch <= '\u30ff' or '\u0400' <= ch <= '\u04ff' for ch in t)


def table_at(B, N):
    """(ok, ptrs, ranks) - None si un enregistrement est invalide."""
    ptrs, ranks = [], []
    for k in range(N):
        o = B + 12 * k
        if o + 12 > N_ROM:
            return None
        p = int.from_bytes(rom[o:o + 4], 'little')
        r = int.from_bytes(rom[o + 4:o + 8], 'little')
        e = rom[o + 8]
        if not (0x08000000 <= p < 0x0A000000) or e not in (0, 1):
            return None
        ptrs.append(p - 0x08000000)
        ranks.append(r)
    if len(set(ranks)) != N or any(not (0 <= r < N) for r in ranks):
        return None
    npl = sum(1 for p in ptrs if plausible(p))
    return (npl, ptrs, ranks)


def find_near(B0, N, back=8, fwd=20):
    best = None
    for B in range(max(0, B0 - back), B0 + fwd + 1, 4):
        t = table_at(B, N)
        if t and (best is None or t[0] > best[1][0]):
            best = (B, t)
    return best


def walk(start, N):
    p = start
    for _ in range(N):
        z = rom.find(b'\xff', p, p + 250)
        if z < 0:
            return None
        p = z + 1
    return p


Nmap, Bmap, trace = {}, {}, {}
for g in ORDER:
    ed = sorted(man[FILE[g]]['edits'])
    Nmap[g] = sum(1 for e in ed if e[4] == 'u32')

g0, B0 = ANCHOR[target]
Bmap[g0] = B0
trace[g0] = (B0, Nmap[g0], 1.0)
for a, b in zip(ORDER, ORDER[1:]):
    Ba = Bmap[a]
    t = walk(Ba + Nmap[a] * 12, Nmap[b])
    if t is None:
        # table binaire entre les deux (easy_chat_words_by_letter) : la marche ne
        # peut pas la traverser, on balaie la suite en exigeant TOUS les mots lisibles.
        start = Ba + Nmap[a] * 12
        Bb = None
        for B in range(start, start + 16384, 4):
            tt = table_at(B, Nmap[b])
            if tt and tt[0] == Nmap[b]:
                Bb = B
                break
        if Bb is None:
            print('!! aucune table pour %s apres %s' % (b, a))
            break
        Bmap[b] = Bb
        trace[b] = (Bb, Nmap[b], 1.0)
        print('%-11s table %7d  N=%3d  (balaie, +%d)' % (b, Bb, Nmap[b], Bb - start))
        continue
    t4 = (t + 3) & ~3
    found = find_near(t4, Nmap[b])
    if not found:
        print('!! aucune table pour %s (arrivee %d)' % (b, t4))
        break
    Bb, (npl, ptrs, ranks) = found
    Bmap[b] = Bb
    trace[b] = (Bb, Nmap[b], npl / Nmap[b])
    print('%-11s table %7d  N=%3d  mots lus %5.2f  decale de %+d' % (b, Bb, Nmap[b], npl / Nmap[b], Bb - t4))

print('\n%d/%d tables' % (len(Bmap), len(ORDER)))

if target == 'IT':
    good = tot = 0
    for g in ORDER:
        if g not in Bmap:
            print('   MISSING', g)
            continue
        ed = sorted(man[FILE[g]]['edits'])
        base_it = min(e[2] for e in ed if e[4] == 'u32') - 4
        okb = Bmap[g] == base_it
        ci = [i for i, e in enumerate(ed) if e[4] in ('c', 'asm', 'u8array')]
        ui = [i for i, e in enumerate(ed) if e[4] == 'u32']
        npl, ptrs, ranks = table_at(Bmap[g], Nmap[g])
        badc = [(j, ed[i][2], ptrs[j]) for j, i in enumerate(ci) if ptrs[j] != ed[i][2]]
        badu = [(j, ed[i][2], Bmap[g] + 12 * j + 4) for j, i in enumerate(ui) if Bmap[g] + 12 * j + 4 != ed[i][2]]
        gc = len(ci) - len(badc)
        gu = len(ui) - len(badu)
        good += gc + gu
        tot += len(ci) + len(ui)
        print('   %-11s base %s (%d) | c %d/%d | u32 %d/%d' % (g, 'OK' if okb else 'NON', base_it, gc, len(ci), gu, len(ui)))
        if badc:
            print('        c ratés (j, manifeste, chaine) :', badc[:6])
        if badu:
            print('        u32 ratés (j, manifeste, chaine) :', badu[:6])
    print('ORACLE easy_chat IT : %d/%d offsets exacts (%.2f%%)' % (good, tot, 100.0 * good / max(1, tot)))
else:
    out = {}
    for g in ORDER:
        if g not in Bmap:
            continue
        rel = FILE[g]
        ed = sorted(man[rel]['edits'])
        ci = [i for i, e in enumerate(ed) if e[4] in ('c', 'asm', 'u8array')]
        ui = [i for i, e in enumerate(ed) if e[4] == 'u32']
        npl, ptrs, ranks = table_at(Bmap[g], Nmap[g])
        rows = [[ci[j], ptrs[j]] for j in range(len(ci))]
        rows += [[ui[j], Bmap[g] + 12 * j + 4] for j in range(len(ui))]
        out[rel] = sorted(rows)
    (WORK / ('ec_edits_%s.json' % target)).write_text(json.dumps(out))
    n = sum(len(v) for v in out.values())
    print('%d editions easy_chat -> ec_edits_%s.json (%d fichiers)' % (n, target, len(out)))
