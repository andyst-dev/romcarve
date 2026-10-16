#!/usr/bin/env python3
"""struct_table.py - forme 2 : tableaux de structures a champ texte (dresseurs, objets,
Pokedex, decorations).

Recette :
  1. pas S et nombre d'enregistrements N viennent du manifeste de reference (les ecarts entre
     editions d'un meme fichier sont invariants de langue) ;
  2. base ANGLAISE prise dans la carte de symboles ; le champ texte dans l'enregistrement
     est celui qui rend 100 % des enregistrements anglais valides ;
  3. sa longueur MAXIMALE est relevee cote EN : c'est la borne du champ dans l'enregistrement ;
  4. base CIBLE : position ou le champ est valide (demarre sur un caractere, lettres/chiffres
     seulement, termine par 0xFF dans la borne) dans 100 % des enregistrements ;
  5. alias a +-S : le delta doit rester proche de celui des tables deja resolues.

Usage: struct_table.py <manifeste_ref.json.gz> <CIBLE>
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

import gzip, json, math, re, string as _string, sys
from pathlib import Path

TREE = Path(f"{REF_TREE}")
ROMS = {
    'EN': Path(f"{ROMS}/emeraude_en.gba"),
    'FR': Path(f"{ROMS}/emeraude_fr.gba"),
    'IT': Path(f"{WORK}/roms/it_bpei.gba"),
    'DE': Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba"),
}
LOCALES = Path(f"{REF_DIR}")
MAP = Path(f"{WORK}/en.map")

TABLES = {
    'src/data/trainers.h': 'gTrainers',
    'src/data/items.h': 'gItems',
    'src/data/pokemon/pokedex_entries.h': 'gPokedexEntries',
    'src/data/decoration/header.h': 'gDecorations',
}
REF_DELTA = int(sys.argv[3]) if len(sys.argv) > 3 else 84336
WIN = 300000

CHAR = {}
for line in (TREE / 'charmap.txt').read_text(encoding='utf-8', errors='replace').splitlines():
    line = line.split('@')[0].rstrip()
    if '=' not in line:
        continue
    lhs, _, rhs = line.partition('=')
    tok, rhs = lhs.strip(), rhs.strip()
    try:
        bs = bytes(int(x, 16) for x in re.findall(r'(?:0x)?([0-9A-Fa-f]{2})', rhs))
    except ValueError:
        continue
    if len(bs) == 1:
        CHAR.setdefault(bs[0], tok.strip("'").replace("\\'", "'"))
# contenu d'un champ texte : tout octet dont le charmap est un glyphe simple
FIELD_BYTES = {b for b, t in CHAR.items() if len(t) == 1 and not t.startswith('{')}
# premier octet : une lettre ou un chiffre (y compris accentues), ou '?' de remplissage
TEXT_START = {b for b, t in CHAR.items() if len(t) == 1 and (t.isalnum() or t in "?♂♀")}
# lettres/chiffres ASCII : ce qu'on trouve au milieu d'une chaine (pour rejeter les alias +-1)
PLAIN = {b for b, t in CHAR.items() if len(t) == 1 and t.isascii() and t.isalnum()}


def field_ok(data, r, stride, f, maxlen, first=False):
    s = r + f
    if data[s] not in TEXT_START:
        return False
    # le champ ne doit pas commencer au milieu d'une chaine (alias a +-1) : l'octet precedent
    # ne peut pas etre une lettre (il vient d'un champ numerique ou d'un remplissage)
    if not first and data[s - 1] in PLAIN:
        return False
    e = data.find(b'\xff', s, r + stride)
    if e < 0 or e == s or e - s > maxlen:
        return False
    return all(b in FIELD_BYTES for b in data[s:e])


def count_ok(data, base, stride, f, n, maxlen):
    """nombre d'enregistrements valides (comptage complet)."""
    ok = 0
    for i in range(n):
        if field_ok(data, base + i * stride, stride, f, maxlen, first=(i == 0)):
            ok += 1
    return ok


def all_ok(data, base, stride, f, n, maxlen, min_ok):
    """sort des le premier echec au-dela de la tolerance."""
    ok = 0
    for i in range(n):
        if field_ok(data, base + i * stride, stride, f, maxlen, first=(i == 0)):
            ok += 1
            if ok >= min_ok:
                return True
        elif n - i - 1 < min_ok - ok:      # meme en reussissant tout le reste, insuffisant
            return False
    return ok >= min_ok


def field_maxlen(data, base, stride, f, n):
    m = 1
    for i in range(n):
        r = base + i * stride
        e = data.find(b'\xff', r + f, r + stride)
        if e > r + f:
            m = max(m, e - (r + f))
    return m


def field_lengths(data, base, stride, f, n):
    out = []
    for i in range(n):
        r = base + i * stride
        e = data.find(b'\xff', r + f, r + stride)
        out.append(max(0, e - (r + f)))
    return out


def corr(a, b):
    n = min(len(a), len(b))
    if n < 8:
        return 0.0
    ma, mb = sum(a[:n]) / n, sum(b[:n]) / n
    va = sum((x - ma) ** 2 for x in a[:n])
    vb = sum((x - mb) ** 2 for x in b[:n])
    if va <= 0 or vb <= 0:
        return 0.0
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (va * vb) ** 0.5


def find_field(data, base, stride, n):
    best, bs = 0, -1
    for f in range(stride):
        s = count_ok(data, base, stride, f, n, maxlen=40)
        if s > bs:
            best, bs = f, s
    return best, bs


def symbol_offset(name):
    for line in MAP.read_text(errors='replace').splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == name and parts[0].startswith('0x'):
            return int(parts[0], 16) - 0x08000000
    return None


def decode_at(data, off, limit=40):
    end = data.find(b'\xff', off, off + limit)
    return ''.join(CHAR.get(x, '?') for x in data[off:end if end > 0 else off])


def main():
    man = json.loads(gzip.decompress(Path(sys.argv[1]).read_bytes()))['files']
    target = sys.argv[2]
    data = ROMS[target].read_bytes()
    en = ROMS['EN'].read_bytes()
    _t = {'IT': 'italian.json.gz', 'FR': 'french.json.gz', 'ES': 'spanish.json.gz'}.get(target)
    man_t = json.loads(gzip.decompress((LOCALES / _t).read_bytes()))['files'] if _t else {}
    print("cible =", target)
    for rel, sym in TABLES.items():
        if rel not in man:
            print(f"\n{rel}: absent du manifeste")
            continue
        offs = [e[2] for e in sorted(man[rel]['edits'])]
        n = len(offs)
        stride = offs[1] - offs[0]
        for i in range(2, n):
            stride = math.gcd(stride, offs[i] - offs[0])
        base_en = symbol_offset(sym)
        f, s = find_field(en, base_en, stride, n)
        maxlen = field_maxlen(en, base_en, stride, f, n)
        min_ok = n - max(1, n // 100)
        print(f"\n{rel} ({n} enr., pas {stride}) {sym} @ {base_en} | champ {f} (EN {s}/{n}, "
              f"longueur max {maxlen})")
        print(f"   EN  : {decode_at(en, base_en + stride + f)!r} / {decode_at(en, base_en + 2*stride + f)!r}")
        if s < min_ok:
            print("   champ EN non homogene, on saute")
            continue
        cands = [b for b in range(max(0, base_en - WIN), min(len(data) - stride * 2, base_en + WIN))
                 if all_ok(data, b, stride, f, n, maxlen, min_ok)]
        tried = [(b, min_ok) for b in cands]
        # les alias a +-pas se departagent par la correlation des longueurs de champs avec l'anglais
        en_len = field_lengths(en, base_en, stride, f, n)
        scored = [(corr(field_lengths(data, b, stride, f, n), en_len), req, b) for b, req in tried]
        scored.sort(key=lambda x: (-x[0], abs((x[2] - base_en) - REF_DELTA)))
        truth = sorted(e[2] for e in man_t[rel]['edits']) if rel in man_t else None
        print(f"   {len(scored)} base(s) cible(s) (requis {tried[0][1] if tried else '-'})")
        for c, req, base in scored[:4]:
            pred = [base + f + i * stride for i in range(n)]
            tag = ""
            if truth:
                exact = sum(1 for a, b in zip(pred, truth) if a == b)
                tag = f" | oracle {exact}/{n}"
            print(f"      base {base} delta {base-base_en:+d} corr {c:.3f}{tag} -> "
                  f"{decode_at(data, base + stride + f)!r} / {decode_at(data, base + 2*stride + f)!r}")


if __name__ == '__main__':
    main()
