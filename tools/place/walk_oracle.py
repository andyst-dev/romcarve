#!/usr/bin/env python3
"""walk_oracle.py - validation de la MARCHE sur l'oracle ITALIEN.

On refait exactement la procedure utilisee pour l'allemand, mais sur l'italien ou
l'on dispose de la verite terrain (italian.json.gz) :
  1. le texte italien vient de la vue mono-langue `~/it_work/it_view` ;
  2. on encode les declarations, on prend une ancre de CONTENU (premiere declaration
     a occurrence unique, encore un objet) ;
  3. on deroule le fichier par la marche + resynchronisation ;
  4. on compare chaque position au rom_offset du manifeste italien.

C'est le seul controle qui vaille avant de faire confiance a la marche allemande.

Usage : walk_oracle.py <fichier> [...]
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

import bisect, gzip, json, re, sys
from pathlib import Path

sys.path.insert(0, f"{VFWORK}")
sys.path.insert(0, f"{WORK}")
from charmap import Charmap

WORK = Path(f"{WORK}")
ITVIEW = Path(f"{VFWORK}/it_view")
TREE = Path(f"{REF_TREE}")
CM = Charmap(str(TREE / 'charmap.txt'))
IT = Path(f"{WORK}/roms/it_bpei.gba").read_bytes()
MAXLEN = 400
LOOK = 12
STEP = 400000

DECL_RE = re.compile(r'\b([A-Za-z_][A-Za-z_0-9]*)\s*(?:\[[^\]]*\])?\s*=\s*_\(')


def all_text_bytes(rom_tree):
    import re as _re
    out = set()
    for line in (rom_tree / 'charmap.txt').read_text(encoding='utf-8', errors='replace').splitlines():
        line = line.split('@')[0].rstrip()
        if '=' not in line:
            continue
        _l, _, rhs = line.partition('=')
        for x in _re.findall(r'(?:0x)?([0-9A-Fa-f]{2})', rhs):
            out.add(int(x, 16))
    return out


TBT = all_text_bytes(TREE)


def extract(rel):
    """[(nom, texte)] des declarations `NAME[] = _("...")` du fichier, en ordre."""
    src = (ITVIEW / rel).read_text(encoding='utf-8', errors='replace')
    out = []
    for m in DECL_RE.finditer(src):
        name = m.group(1)
        j = m.end()
        depth, buf, k = 1, [], j
        while k < len(src) and depth:
            c = src[k]
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    break
            buf.append(c)
            k += 1
        lits = re.findall(r'"((?:[^"\\]|\\.)*)"', ''.join(buf))
        if lits:
            out.append((name, ''.join(lits)))
    return out


def obj(q):
    if q <= 0 or q >= len(IT):
        return None
    if IT[q] == 0xFF:
        return b'', q + 1
    e = IT.find(b'\xff', q, q + MAXLEN)
    if e < 0:
        return None
    body = IT[q:e]
    if any(x not in TBT for x in body):
        return None
    return body, e + 1


def prev_start(q):
    if q <= 0 or IT[q - 1] != 0xFF:
        return None
    r = IT.rfind(b'\xff', 0, q - 1)
    return r + 1 if r >= 0 else None


def cands(enc, lo, hi, cap=16):
    out = []
    if not enc or len(enc) < 3:
        return out
    p = IT.find(enc, max(0, lo), hi)
    while p >= 0 and len(out) < cap:
        if p > 0 and IT[p - 1] == 0xFF and IT[p + len(enc)] == 0xFF:
            out.append(p)
        p = IT.find(enc, p + 1, hi)
    return out


def main():
    rel = sys.argv[1]
    decls = extract(rel)
    n = len(decls)
    enc = []
    for name, lit in decls:
        try:
            e = CM.encode(lit)
        except Exception:
            e = None
        enc.append(e)
    # ancre : premiere declaration dont l'objet est unique dans la ROM
    ai = ap = None
    for i, e in enumerate(enc):
        if not e or len(e) < 6:
            continue
        c = cands(e, 0, len(IT), cap=4)
        if len(c) == 1:
            ai, ap = i, c[0]
            break
    print("%s : %d declarations italiennes | ancre de contenu : index %d @%d" % (rel, n, ai, ap))
    pos = [None] * n
    resync = 0
    i, q = ai, ap
    while i < n:
        got = obj(q) if q is not None else None
        if got is not None:
            pos[i] = q
            i += 1
            q = got[1]
            continue
        done = False
        for k in range(1, LOOK + 1):
            if i + k >= n or not enc[i + k]:
                continue
            c = cands(enc[i + k], (q or ap) + 1, (q or ap) + STEP, cap=6)
            if c:
                pos[i + k] = c[0]
                i = i + k + 1
                q = IT.find(b'\xff', c[0], c[0] + MAXLEN) + 1
                resync += 1
                done = True
                break
        if not done:
            break
    first = next((j for j in range(n) if pos[j] is not None), None)
    i, q = first - 1, prev_start(pos[first])
    while i >= 0:
        got = obj(q) if q is not None else None
        if got is not None:
            pos[i] = q
            i -= 1
            q = prev_start(q)
            continue
        done = False
        for k in range(1, LOOK + 1):
            if i - k < 0 or not enc[i - k]:
                continue
            hi = (q or pos[first]) - 1
            c = cands(enc[i - k], max(0, hi - STEP), hi, cap=6)
            if c:
                x = max(c)
                pos[i - k] = x
                i = i - k - 1
                q = prev_start(x)
                resync += 1
                done = True
                break
        if not done:
            break
    placed = sum(1 for x in pos if x is not None)
    print("   placees : %d/%d (%.1f%%) | resynchronisations : %d" % (placed, n, 100.0 * placed / n, resync))

    # verification contre le manifeste italien
    man = json.loads(gzip.decompress(Path(f"{REF_DIR}/italian.json.gz").read_bytes()))
    if rel not in man['files']:
        print("   fichier absent du manifeste")
        return
    # nom -> index d'edition : on passe par l'arbre epingle (meme ordre)
    src = (TREE / rel).read_text(encoding='utf-8', errors='replace')
    names = [(m.start(), m.group(1)) for m in DECL_RE.finditer(src)]
    idx_of = {}
    for i2, (p2, nm) in enumerate(names):
        idx_of.setdefault(nm, i2)
    edits = sorted(man['files'][rel]['edits'])
    checked = ok = bad = 0
    for j, (name, _lit) in enumerate(decls):
        if pos[j] is None:
            continue
        e2 = idx_of.get(name)
        if e2 is None or e2 >= len(edits):
            continue
        checked += 1
        if pos[j] == edits[e2][2]:
            ok += 1
        else:
            bad += 1
            if bad <= 4:
                print("      {} : marche {} / manifeste {}".format(name, pos[j], edits[e2][2]))
    print("   ORACLE : %d/%d positions confirmees par le manifeste italien (%.2f%%)"
          % (ok, checked, 100.0 * ok / max(1, checked)))


if __name__ == '__main__':
    main()
