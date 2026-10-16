#!/usr/bin/env python3
"""objalign.py - alignement AU NIVEAU OBJET (DP) entre declarations et objets de la ROM.

Pourquoi : la ROM peut decouper un message en plusieurs objets (objet vide de 1 octet,
fragment de 11-16 octets), donc le nombre d'objets d'un fichier n'est pas le nombre de
declarations et une marche pilotee par le compteur de declarations glisse d'un objet.

Methode :
  1. on collecte la LISTE DES OBJETS de la ROM autour d'une ancre de contenu (marche
     0xFF, en avant et en arriere) ;
  2. on apparie la liste des declarations a la liste des objets par programmation
     dynamique (bande +-BAND), avec :
        - appariement dont le texte allemand/italien est EXACT : cout 0 (c'est l'ancre) ;
        - declaration sans texte connu : cout faible (placee par continuite) ;
        - texte different (la branche amont n'est pas la cartouche) : cout moyen ;
        - objet EN PLUS (fragment) : cout fixe -> le DP choisit ou placer le saut ;
        - declaration sans objet : cout plus fort ;
  3. la position d'une declaration = l'offset de son objet apparie.

Usage : objalign.py ITALIAN|GERMAN <fichier> [--band N]
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

sys.path.insert(0, f"{VFWORK}")
sys.path.insert(0, f"{WORK}")
from charmap import Charmap
from hybrid import (extract_it, extract_de, TBT, DECL_RE, WORK, TREE, ROMS, MAXLEN, CM)

BAND = 60
SUB_EXACT, SUB_UNKNOWN, SUB_DIFF = 0, 3, 7
SKIP_OBJ, SKIP_DECL = 5, 14


def collect_objects(rom, p0, n, pad=400):
    """objets (offset, corps) en avant et en arriere depuis p0 ; s'arrete a un trou."""
    def obj(q):
        if q <= 0 or q >= len(rom):
            return None
        if rom[q] == 0xFF:
            return b'', q + 1
        e = rom.find(b'\xff', q, q + MAXLEN)
        if e < 0:
            return None
        body = rom[q:e]
        if any(x not in TBT for x in body):
            return None
        return body, e + 1

    fwd, q = [], p0
    while len(fwd) < n + pad:
        got = obj(q)
        if got is None:
            break
        fwd.append((q, got[0]))
        q = got[1]
    back, q = [], None
    if p0 > 0 and rom[p0 - 1] == 0xFF:
        r = rom.rfind(b'\xff', 0, p0 - 1)
        q = r + 1 if r >= 0 else None
    while q is not None and len(back) < n + pad:
        got = obj(q)
        if got is None:
            break
        back.append((q, got[0]))
        if q > 0 and rom[q - 1] == 0xFF:
            r = rom.rfind(b'\xff', 0, q - 1)
            q = r + 1 if r >= 0 else None
        else:
            q = None
    back.reverse()
    return back, fwd


def align(enc, bodies):
    """DP borne : rend pour chaque declaration l'indice d'objet apparie (ou None).

    Une declaration peut consommer 1 a 3 objets SUCCESSIFS : la ROM scinde parfois un
    message en plusieurs objets (fragment + reste), et c'est ce qui faisait glisser la
    suite d'un objet. Le cout d'un appariement multiple = 0 si la CONCATENATION des corps
    egale le texte attendu, plus une petite penalite par objet supplementaire.
    """
    n, m = len(enc), len(bodies)
    if n == 0 or m == 0:
        return [None] * n
    extra = max(0, m - n) + 8
    INF = 1 << 30
    prev = [INF] * (m + 1)
    prev[0] = 0
    for j in range(1, min(m, extra) + 1):
        prev[j] = prev[j - 1] + SKIP_OBJ
    bps = []
    for i in range(1, n + 1):
        cur = [INF] * (m + 1)
        pnt = [None] * (m + 1)
        e = enc[i - 1]
        lo = max(1, i - 8)
        hi = min(m, i + extra)
        for j in range(lo, hi + 1):
            cands = [('O', cur[j - 1] + SKIP_OBJ)]
            if e is None:
                cands.append(('M1', prev[j - 1] + SUB_UNKNOWN))
            else:
                for k in range(1, 4):
                    if j - k < 0:
                        break
                    joined = bodies[j - 1] if k == 1 else b''.join(bodies[j - k:j])
                    if len(joined) > len(e) + 8:
                        break
                    if joined == e:
                        cands.append(('M%d' % k, prev[j - k] + (0 if k == 1 else 3 * (k - 1))))
                    elif k == 1:
                        cands.append(('M1', prev[j - 1] + SUB_DIFF))
            cands.append(('D', prev[j] + SKIP_DECL))
            best = min(cands, key=lambda c: c[1])
            cur[j] = best[1]
            pnt[j] = best[0]
        bps.append(pnt)
        prev = cur
    assign = [None] * n
    i, j = n, m
    if prev[m] >= INF:
        j = min(range(m + 1), key=lambda x: prev[x])
    while i > 0 and j > 0:
        t = bps[i - 1][j]
        if t is None:
            break
        if t.startswith('M'):
            k = int(t[1])
            assign[i - 1] = j - k
            i -= 1
            j -= k
        elif t == 'O':
            j -= 1
        else:
            i -= 1
    return assign


def main():
    lang = sys.argv[1]
    rel = sys.argv[2]
    band = int(sys.argv[sys.argv.index('--band') + 1]) if '--band' in sys.argv else BAND
    rom = ROMS[lang].read_bytes()
    if lang == 'ITALIAN':
        decls = extract_it(rel)
    else:
        doc = json.loads((WORK / 'de_german_source.json').read_text())
        decls = extract_de(rel, doc)
    enc = []
    for name, lit in decls:
        try:
            e = CM.encode(lit)
        except Exception:
            e = None
        enc.append(e if e and len(e) >= 1 else (b'' if lit == '' else None))
    n = len(decls)
    # ancre : premiere declaration dont le texte est un objet UNIQUE
    i0 = p0 = None
    for i, e in enumerate(enc):
        if not e or len(e) < 6:
            continue
        p = rom.find(e)
        c = 0
        while p >= 0:
            if p > 0 and rom[p - 1] == 0xFF and rom[p + len(e)] == 0xFF:
                c += 1
                last = p
            p = rom.find(e, p + 1)
            if c > 1:
                break
        if c == 1:
            i0, p0 = i, last
            break
    print("%s %s : %d declarations | ancre index %d @%d" % (lang, rel, n, i0, p0))
    back, fwd = collect_objects(rom, p0, n)
    objs = back + fwd
    print("   objets collectes : %d en arriere, %d en avant (%d au total) pour %d declarations"
          % (len(back), len(fwd), len(objs), n))
    bodies = [b for _o, b in objs]
    assign = align(enc, bodies)
    placed = sum(1 for a in assign if a is not None)
    exact = sum(1 for i2, a in enumerate(assign)
                if a is not None and enc[i2] is not None and enc[i2] == bodies[a])
    skipped = len(objs) - len({a for a in assign if a is not None})
    print("   appariements : %d/%d declarations | texte exact : %d | objets non consommes : %d"
          % (placed, n, exact, skipped))
    pos = [objs[a][0] if a is not None else None for a in assign]
    # contiguite du resultat : les positions doivent croitre
    ok_mono = all(pos[i2] is None or pos[i2 + 1] is None or pos[i2 + 1] > pos[i2]
                  for i2 in range(n - 1))
    print("   ordre croissant : %s" % ok_mono)

    if lang == 'ITALIAN':
        man = json.loads(gzip.decompress(Path(f"{REF_DIR}/italian.json.gz").read_bytes()))
        src = (TREE / rel).read_text(encoding='utf-8', errors='replace')
        man_name = {}
        for e in sorted(man['files'][rel]['edits']):
            m = None
            for mm in DECL_RE.finditer(src[:e[0] + 3]):
                m = mm
            if m:
                man_name.setdefault(m.group(1), e[2])
        ok = bad = 0
        for j, (name, _l) in enumerate(decls):
            if pos[j] is None or name not in man_name:
                continue
            if pos[j] == man_name[name]:
                ok += 1
            else:
                bad += 1
                if bad <= 4:
                    print("      {} : objet {} / manifeste {} (ecart {})"
                          .format(name, pos[j], man_name[name], pos[j] - man_name[name]))
        print("   ORACLE OBJALIGN : %d/%d noms confirmes (%.2f%%) | ecarts %d"
              % (ok, ok + bad, 100.0 * ok / max(1, ok + bad), bad))
    else:
        out = WORK / ('objalign_%s.json' % Path(rel).name)
        out.write_text(json.dumps([[decls[j][0], pos[j]] for j in range(n) if pos[j] is not None]))
        print("-> %s" % out)


if __name__ == '__main__':
    main()
