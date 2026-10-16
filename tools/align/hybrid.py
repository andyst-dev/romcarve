#!/usr/bin/env python3
"""hybrid.py - marche + RE-ANCRAGE PAR CONTENU : supprime la derive.

La marche seule derive a la longue (quelques objets presents dans la ROM mais absents
de la liste de declarations) : mesure sur l'oracle italien, 1544/1752 positions exactes
avec des ecarts residuels de -1 a -3 octets, localises.

Correction : a chaque pas, si le texte de la declaration est retrouve comme OBJET
UNIQUE de la ROM a moins de `tol` octets de la position predite par la marche, on se
RE-ANCRE dessus (le contenu tranche, la marche ne fait que proposer). Sinon on avance
d'un objet.

Usage : hybrid.py ITALIAN|GERMAN <fichier> [tol]
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
TREE = Path(f"{REF_TREE}")
ITVIEW = Path(f"{VFWORK}/it_view")
CM = Charmap(str(TREE / 'charmap.txt'))
ROMS = {
    'ITALIAN': WORK / 'roms/it_bpei.gba',
    'GERMAN': Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba"),
}
MAXLEN = 400
DECL_RE = re.compile(r'\b([A-Za-z_][A-Za-z_0-9]*)\s*(?:\[[^\]]*\])?\s*=\s*_\(')


def text_bytes():
    out = set()
    for line in (TREE / 'charmap.txt').read_text(encoding='utf-8', errors='replace').splitlines():
        line = line.split('@')[0].rstrip()
        if '=' not in line:
            continue
        _l, _, rhs = line.partition('=')
        for x in re.findall(r'(?:0x)?([0-9A-Fa-f]{2})', rhs):
            out.add(int(x, 16))
    return out


TBT = text_bytes()


def extract_it(rel):
    src = (ITVIEW / rel).read_text(encoding='utf-8', errors='replace')
    return _extract(src)


def extract_de(rel, doc):
    """bras #elif GERMAN du fichier de la branche amont."""
    out = []
    for name, lit, off, why in doc.get(rel, []):
        out.append((name, lit))
    return out


def _extract(src):
    out = []
    for m in DECL_RE.finditer(src):
        name = m.group(1)
        j, depth, buf, k = m.end(), 1, [], m.end()
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


class Walk:
    def __init__(self, rom, decls, tol=64):
        self.rom = rom
        self.decls = decls
        self.tol = tol
        self.enc = []
        for name, lit in decls:
            try:
                e = CM.encode(lit)
            except Exception:
                e = None
            self.enc.append(e)
        self.n = len(decls)

    def obj(self, q):
        rom = self.rom
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

    def prev(self, q):
        rom = self.rom
        if q <= 0 or rom[q - 1] != 0xFF:
            return None
        r = rom.rfind(b'\xff', 0, q - 1)
        return r + 1 if r >= 0 else None

    def occ(self, enc, lo, hi, cap=4):
        out = []
        if not enc or len(enc) < 4:
            return out
        p = self.rom.find(enc, max(0, lo), hi)
        while p >= 0 and len(out) < cap:
            if p > 0 and self.rom[p - 1] == 0xFF and self.rom[p + len(enc)] == 0xFF:
                out.append(p)
            p = self.rom.find(enc, p + 1, hi)
        return out

    def unique_anchor(self):
        for i, e in enumerate(self.enc):
            if not e or len(e) < 6:
                continue
            c = self.occ(e, 0, len(self.rom), cap=3)
            if len(c) == 1:
                return i, c[0]
        return None, None

    def run(self):
        i0, q = self.unique_anchor()
        if i0 is None:
            return [None] * self.n, 0, 0
        pos = [None] * self.n
        ren = 0
        # avant
        i = i0
        while i < self.n:
            snapped = False
            if self.enc[i] and len(self.enc[i]) >= 4:
                lo = max(0, q - self.tol)
                c = self.occ(self.enc[i], lo, q + self.tol + 1, cap=2)
                if len(c) == 1:
                    if pos[i] != c[0]:
                        ren += 1
                    pos[i] = c[0]
                    # AVANCER AVEC LA ROM, pas avec ma longueur theorique : c'est
                    # justement l'ecart entre les deux qui cree la derive
                    g2 = self.obj(c[0])
                    q = g2[1] if g2 is not None else c[0] + len(self.enc[i]) + 1
                    i += 1
                    snapped = True
            if snapped:
                continue
            got = self.obj(q) if q is not None else None
            if got is None:
                # saut : prochain candidat unique du texte, dans les declarations suivantes
                moved = False
                for k in range(1, 13):
                    if i + k >= self.n or not self.enc[i + k]:
                        continue
                    c = self.occ(self.enc[i + k], (q or 0) + 1, (q or 0) + 400000, cap=2)
                    if len(c) == 1:
                        pos[i + k] = c[0]
                        q = c[0] + len(self.enc[i + k]) + 1
                        i = i + k + 1
                        moved = True
                        break
                if not moved:
                    break
                continue
            pos[i] = q
            q = got[1]
            i += 1
        # arriere
        first = next((j for j in range(self.n) if pos[j] is not None), None)
        if first is not None:
            i = first - 1
            q = self.prev(pos[first])
            while i >= 0:
                if self.enc[i] and len(self.enc[i]) >= 4:
                    lo = max(0, (q or pos[first]) - self.tol)
                    c = self.occ(self.enc[i], lo, (q or pos[first]) + self.tol + 1, cap=2)
                    if len(c) == 1:
                        pos[i] = c[0]
                        q = self.prev(c[0])
                        i -= 1
                        continue
                got = self.obj(q) if q is not None else None
                if got is None:
                    moved = False
                    for k in range(1, 13):
                        if i - k < 0 or not self.enc[i - k]:
                            continue
                        hi = (q or pos[first]) - 1
                        c = self.occ(self.enc[i - k], max(0, hi - 400000), hi, cap=2)
                        if len(c) == 1:
                            pos[i - k] = c[0]
                            q = self.prev(c[0])
                            i = i - k - 1
                            moved = True
                            break
                    if not moved:
                        break
                    continue
                pos[i] = q
                q = self.prev(q)
                i -= 1
        return pos, ren, i0


def main():
    lang = sys.argv[1]
    rel = sys.argv[2]
    tol = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    rom = ROMS[lang].read_bytes()
    if lang == 'ITALIAN':
        decls = extract_it(rel)
    else:
        doc = json.loads((WORK / 'de_german_source.json').read_text())
        decls = extract_de(rel, doc)
    w = Walk(rom, decls, tol)
    pos, ren, i0 = w.run()
    placed = sum(1 for x in pos if x is not None)
    conf = sum(1 for j in range(w.n) if pos[j] is not None and w.enc[j]
               and pos[j] + len(w.enc[j]) + 1 <= len(rom)
               and rom[pos[j]:pos[j] + len(w.enc[j])] == w.enc[j])
    print("%s %s : %d declarations | placees %d (%.1f%%) | texte conforme %d | re-ancrages %d"
          % (lang, rel, w.n, placed, 100.0 * placed / w.n, conf, ren))
    if lang == 'ITALIAN':
        man = json.loads(gzip.decompress(Path(f"{REF_DIR}/italian.json.gz").read_bytes()))
        if rel in man['files']:
            # appariement par NOM : les listes de declarations (vue italienne) et
            # d'editions (manifeste) n'ont pas la meme taille, un appariement par INDEX
            # compare des choses differentes
            src = (TREE / rel).read_text(encoding='utf-8', errors='replace')
            man_name = {}
            for e in sorted(man['files'][rel]['edits']):
                m = None
                for mm in DECL_RE.finditer(src[:e[0] + 3]):
                    m = mm
                if m:
                    man_name.setdefault(m.group(1), e[2])
            checked = ok = bad = 0
            for j, (name, _l) in enumerate(decls):
                if pos[j] is None or name not in man_name:
                    continue
                checked += 1
                if pos[j] == man_name[name]:
                    ok += 1
                else:
                    bad += 1
                    if bad <= 3:
                        print("      {} : marche {} / manifeste {} (ecart {})"
                              .format(name, pos[j], man_name[name], pos[j] - man_name[name]))
            print("   ORACLE : %d/%d noms confirmes par le manifeste italien (%.2f%%) | ecarts %d"
                  % (ok, checked, 100.0 * ok / max(1, checked), bad))
    else:
        out = WORK / ('hybrid_%s.json' % Path(rel).name)
        out.write_text(json.dumps([[decls[j][0], pos[j]] for j in range(w.n)
                                   if pos[j] is not None]))
        print("-> %s" % out)


if __name__ == '__main__':
    main()
