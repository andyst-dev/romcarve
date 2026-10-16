#!/usr/bin/env python3
"""dewake3.py - marche AVEC RESYNCHRONISATION : resoudre tout un fichier.

La marche suit les 0xFF de la ROM et compare chaque objet au texte allemand attendu
(controle octet a octet). Quand elle tombe sur un objet non textuel (trou : donnees
intercalees, objet dans une autre section), elle se RESYNCHRONISE : elle cherche, pour
une declaration voisine, une occurrence du texte allemand APRES la derniere position
placee (et, en arriere, AVANT), puis repart de la.

Sortie : dewake3_<fichier>.json  [[nom, offset], ...]
Usage : dewake3.py <fichier> [--lookahead N]
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

import json, sys
from pathlib import Path
sys.path.insert(0, f"{VFWORK}")
sys.path.insert(0, f"{WORK}")
from charmap import Charmap
from dewake2 import TBT, object_at, prev_start, DE, WORK, CM, GERMAN

MAXLEN = 400
BACKSTEP = 400000


def candidates(enc, lo=0, hi=None, cap=64):
    """occurrences de l'objet (debut d'objet : precede d'un 0xFF)."""
    out = []
    if not enc or len(enc) < 3:
        return out
    hi = len(DE) if hi is None else hi
    p = DE.find(enc, max(0, lo), hi)
    while p >= 0 and len(out) < cap:
        if p > 0 and DE[p - 1] == 0xFF and DE[p + len(enc)] == 0xFF:
            out.append(p)
        p = DE.find(enc, p + 1, hi)
    return out


def main():
    rel = sys.argv[1]
    look = int(sys.argv[sys.argv.index('--lookahead') + 1]) if '--lookahead' in sys.argv else 12
    decls = GERMAN[rel]
    n = len(decls)
    enc = []
    for name, lit, off, why in decls:
        try:
            e = CM.encode(lit)
        except Exception:
            e = None
        enc.append(e)
    idx_of = {}
    for i, (name, _l, _o, _w) in enumerate(decls):
        idx_of.setdefault(name, i)
    anchor = None
    for f in ('anchors_de_%s.json' % Path(rel).name, 'anchors_%s.json' % Path(rel).name):
        p = WORK / f
        if not p.exists():
            continue
        rows = json.loads(p.read_text())
        cand = sorted((idx_of[nm], o) for nm, o, ln in rows if nm in idx_of)
        if cand and (anchor is None or len(cand) > len(anchor[1])):
            anchor = (f, cand)
    if anchor is None:
        print("aucune ancre")
        return
    fname, cand = anchor
    i0, p0 = cand[0]
    pos = [None] * n
    resync = 0
    conf = 0
    # ---------- marche AVANT
    i, q = i0, p0
    while i < n:
        got = object_at(q) if q is not None else None
        if got is not None:
            body, nxt = got
            pos[i] = q
            if enc[i] == body:
                conf += 1
            i += 1
            q = nxt
            continue
        # resynchronisation : chercher en avant, sur les prochaines declarations
        done = False
        for k in range(1, look + 1):
            if i + k >= n or not enc[i + k]:
                continue
            lo = (q if q is not None else p0) + 1
            c = candidates(enc[i + k], lo, lo + BACKSTEP, cap=8)
            if c:
                pos[i + k] = c[0]
                conf += 1
                i = i + k + 1
                q = DE.find(b'\xff', c[0], c[0] + MAXLEN) + 1
                resync += 1
                done = True
                break
        if not done:
            break
    fwd_last = i - 1
    # ---------- marche ARRIERE (depuis la premiere position placee)
    first = next((j for j in range(n) if pos[j] is not None), None)
    if first is not None:
        i, q = first - 1, prev_start(pos[first])
        while i >= 0:
            got = object_at(q) if q is not None else None
            if got is not None:
                body, _nxt = got
                pos[i] = q
                if enc[i] == body:
                    conf += 1
                i -= 1
                q = prev_start(q)
                continue
            done = False
            for k in range(1, look + 1):
                if i - k < 0 or not enc[i - k]:
                    continue
                hi = (q if q is not None else pos[first]) - 1
                c = [x for x in candidates(enc[i - k], max(0, hi - BACKSTEP), hi, cap=8)]
                if c:
                    x = max(c)
                    pos[i - k] = x
                    conf += 1
                    i = i - k - 1
                    q = prev_start(x)
                    resync += 1
                    done = True
                    break
            if not done:
                break
    placed = sum(1 for x in pos if x is not None)
    print("%s : %d declarations | placees par la marche+resync : %d (%.1f%%) | conformes "
          "octet a octet : %d | resynchronisations : %d"
          % (rel, n, placed, 100.0 * placed / n, conf, resync))
    print("   bloc avant jusqu'a l'index %d | bloc arriere jusqu'a l'index %d"
          % (fwd_last, i + 1))
    out = WORK / ('dewake3_%s.json' % Path(rel).name)
    out.write_text(json.dumps([[decls[j][0], pos[j]] for j in range(n) if pos[j] is not None]))
    print("-> %s" % out)


if __name__ == '__main__':
    main()
