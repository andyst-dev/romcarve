#!/usr/bin/env python3
"""gap_fill.py - proposer les editions MANQUANTES qui sont encadrees par un voisin place.

Idee : dans un pool contigu, l'objet de l'edition i commence juste apres le
0xFF qui termine l'objet de l'edition i-1 (et se termine juste avant l'objet de
i+1). Le placeur d'origine a laisse ces trous pour deux raisons :
  * tete de pool (index 0) : pas de 0xFF devant, il "droppe" le premier objet ;
  * queue de pool (dernier index) / trous : il s'arrete sur son ancre.

Pour chaque trou encadre, on DERIVE donc le candidat de l'offset du voisin
place, et on le soumet a trois controles automatiques :
  1. contiguite : l'objet candidat se termine exactement avant le voisin de
     droite quand il est place ;
  2. lisibilite : le texte decode est majoritairement alphanumerique ;
  3. longueur : rapport longueur(DE)/longueur(IT) dans [0.4, 2.6].

Sortie : gap_candidats.json  (rel -> [[index, offset, it_len, de_len], ...]) et
une liste d'affichage compacte pour relecture humaine (le candidat n'est accepte
QU'APRES lecture du texte allemand).

Usage : python3 gap_fill.py [--emit] [--show N]
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

import json, gzip, sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
man = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
de = C.ROMS['DE'].read_bytes()
it = C.ROMS['IT'].read_bytes()
CM = C._CM


def readable(t, min_ratio=0.45):
    if not t:
        return False
    alnum = sum(ch.isalnum() for ch in t)
    return alnum >= min_ratio * len(t)


TEXTCHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    " .,!?'\"-:;()/…%+*=&@#<>[]{}~\\"
    "éÄÖÜäöüß"                     # allemand reel
    "ÁÀÈ"                          # placeholders {FD}Á {FD}À {FD}È seulement
    "’‘“”")


def text_start(s, z):
    """Debut du TEXTE dans l'objet [s..z] : on se place apres le DERNIER
    caractere qui n'est pas un caractere de texte (le prefixe de codes de
    controle decode en kana/boites). Rend s si tout l'objet est du texte."""
    chars = []
    for k in range(s, z):
        t = CM.decode(de[k:k + 1])
        for ch in t:
            chars.append((k, ch))
    last_bad = -1
    for idx, (_, ch) in enumerate(chars):
        if ch not in TEXTCHARS:
            last_bad = idx
    if last_bad < 0:
        return s
    ts = chars[last_bad][0] + 1
    # les 1-2 octets de code qui precedent le texte se decodent souvent en
    # 'Á'/'À'/'È' (memes glyphes que les placeholders) : on les saute tant que
    # le texte ne commence pas par '{' (placeholder legitime en tete).
    while ts < z:
        ch = CM.decode(de[ts:ts + 1])
        if ch in ('Á', 'À', 'È') and CM.decode(de[ts + 1:ts + 2]) not in ('}',):
            ts += 1
        else:
            break
    return ts


def shared_tokens(a, b):
    """Tokens en MAJUSCULES communs aux deux textes (noms propres, POKéMON,
    objets) : signal que les deux textes parlent de la meme chose."""
    import re as _re
    ta = set(_re.findall(r'[A-ZÄÖÜ][A-Za-zÄÖÜäöüéè]{2,}', a))
    tb = set(_re.findall(r'[A-ZÄÖÜ][A-Za-zÄÖÜäöüéè]{2,}', b))
    return len(ta & tb)


def end_of(o, cap=2200):
    z = de.find(b'\xff', o, o + cap)
    return z if z >= 0 else None


cands = {}
for rel, v in man.items():
    ed = sorted(v['edits'])
    have = dict(cur.get(rel, []))
    n = len(ed)
    for i in range(n):
        if i in have:
            continue
        left = have.get(i - 1)
        right = have.get(i + 1)
        o = None
        if left is not None:
            z = end_of(left)
            if z is not None:
                o = z + 1
        if o is None and right is not None:
            e = de.rfind(b'\xff', max(0, right - 2200), right)
            if e > 0:
                s = de.rfind(b'\xff', max(0, e - 2200), e)
                if s > 0:
                    o = s + 1
        if o is None:
            continue
        z = end_of(o)
        if z is None:
            continue
        # 1. contiguite avec le voisin de droite
        if right is not None and z + 1 != right:
            continue
        tde = CM.decode(de[o:z])
        ts = text_start(o, z)
        tde = CM.decode(de[ts:z])
        it_rel = ed[i]
        tit = CM.decode(it[it_rel[2]:it_rel[2] + it_rel[3] - 1])
        # 2. lisibilite / 3. longueur
        if not readable(tde):
            continue
        if not (0.3 <= (len(tde) + 1) / max(1, it_rel[3]) <= 3.0):
            continue
        cands.setdefault(rel, []).append([i, ts, len(tit), len(tde),
                                          tit.replace('\n', '~')[:70],
                                          tde.replace('\n', '~')[:70],
                                          shared_tokens(tit, tde)])

print('candidats : %d dans %d fichiers' % (sum(len(v) for v in cands.values()), len(cands)))
if len(sys.argv) > 2 and sys.argv[1] == '--show':
    n = int(sys.argv[2])
    k = 0
    rows_all = [(rel, r) for rel, rr in sorted(cands.items()) for r in rr]
    rows_all.sort(key=lambda x: -x[1][6])          # ceux qui partagent des tokens d'abord
    for rel, (i, o, li, ld, ti, td, sh) in rows_all[:n]:
        k += 1
        print('#%-4d tok=%d %s [%d] @%d' % (k, sh, rel.split('/', 1)[1], i, o))
        print('       IT(%d): %s' % (li, ti))
        print('       DE(%d): %s' % (ld, td))
if '--emit' in sys.argv:
    out = {rel: [[i, o] for i, o, _, _, _, _, _ in rows] for rel, rows in cands.items()}
    (WORK / 'gap_candidats.json').write_text(json.dumps(out))
    print('%d candidats -> gap_candidats.json' % sum(len(v) for v in out.values()))
