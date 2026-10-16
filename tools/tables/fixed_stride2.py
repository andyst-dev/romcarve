#!/usr/bin/env python3
"""fixed_stride2.py - tableaux a pas fixe : base EN prise dans la carte de symboles,
base cible detectee par signature d'enregistrements, oracle sur le manifeste de la langue.

Usage: fixed_stride2.py <manifeste_ref.json.gz> <CIBLE>
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

import gzip, json, math, re, sys
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

# fichier du manifeste -> symbole de la table dans le .map anglais
SYMBOLS = {
    'src/data/text/species_names.h': 'gSpeciesNames',
    'src/data/text/move_names.h': 'gMoveNames',
    'src/data/text/trainer_class_names.h': 'gTrainerClassNames',
}

VALID, CHAR = set(), {}
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
    VALID.update(bs)
    if len(bs) == 1:
        CHAR.setdefault(bs[0], tok.strip("'"))
VALID.discard(0xFF)


def record_ok(data, r, stride, field):
    e = data.find(b'\xff', r + field, r + stride)
    if e < 0 or e == r + field:
        return False
    if any(b not in VALID for b in data[r + field:e]):
        return False
    return all(b == 0x00 for b in data[e + 1:r + stride])


def score(data, base, stride, field, n):
    return sum(1 for i in range(n) if record_ok(data, base + i * stride, stride, field))


def find_best_field(data, base, stride, n):
    best = None
    for f in range(stride):
        s = score(data, base, stride, f, n)
        if best is None or s > best[1]:
            best = (f, s)
    return best


def detect(data, stride, field, n, lo, hi):
    out = []
    for base in range(max(0, lo), min(len(data) - stride * 2, hi)):
        s = score(data, base, stride, field, n)
        if s == n:
            out.append(base)
    return out


def symbol_offset(name):
    for line in MAP.read_text(errors='replace').splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == name and parts[0].startswith('0x'):
            return int(parts[0], 16) - 0x08000000
    return None


def main():
    man = json.loads(gzip.decompress(Path(sys.argv[1]).read_bytes()))['files']
    target = sys.argv[2]
    data = ROMS[target].read_bytes()
    en = ROMS['EN'].read_bytes()
    _t = {'IT': 'italian.json.gz', 'FR': 'french.json.gz', 'ES': 'spanish.json.gz'}.get(target)
    man_t = json.loads(gzip.decompress((LOCALES / _t).read_bytes()))['files'] if _t else {}
    print("cible =", target)
    for rel, sym in SYMBOLS.items():
        if rel not in man:
            print(f"\n{rel}: absent du manifeste")
            continue
        offs = [e[2] for e in sorted(man[rel]['edits'])]
        n = len(offs)
        stride = offs[1] - offs[0]
        for i in range(2, n):
            stride = math.gcd(stride, offs[i] - offs[0])
        base_en = symbol_offset(sym)
        print(f"\n{rel} ({n} champs, pas {stride}) - symbole {sym} @ {base_en}")
        if base_en is None:
            continue
        field, s = find_best_field(en, base_en, stride, n)
        print(f"   champ dans l'enregistrement = {field} ({s}/{n} enregistrements valides en EN)")
        if s < n:
            print("   base EN incoherente, on saute")
            continue
        cands = detect(data, stride, field, n, max(0, base_en - 250000), base_en + 250000)
        truth = sorted(e[2] for e in man_t[rel]['edits']) if rel in man_t else None
        print(f"   {len(cands)} base(s) cible(s) a 100%")
        for base in cands[:6]:
            pred = [base + field + i * stride for i in range(n)]
            tag = ""
            if truth:
                exact = sum(1 for a, b in zip(pred, truth) if a == b)
                tag = f" | oracle {exact}/{n}"
            rows = [''.join(CHAR.get(x, '?') for x in
                            data[base + i * stride + field:base + i * stride + field +
                                 data[base + i * stride + field:base + i * stride + stride].find(b'\xff')])
                    for i in (1, 2, 3)]
            print(f"      base {base} delta {base-base_en:+d}{tag} -> {rows}")


if __name__ == '__main__':
    main()
