#!/usr/bin/env python3
"""de_gate.py - porte de qualite COTE ALLEMAND, par fichier.

L'oracle italien prouve la methode, pas le placement allemand : sur la ROM Smaragd un
candidat peut tomber sur un bloc anglais, sur du remplissage ou sur un objet tronque.
On mesure donc, pour chaque fichier, la part d'editions dont le texte decode a l'air
d'une PHRASE (lettres/chiffres/ponctuation, peu de '?', pas d'octets hors table).

Usage : de_gate.py [mapping.json] [seuil]   (defaut 0.90)
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

import json, re, sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
sys.path.insert(0, f"{VFWORK}")
from charmap import Charmap  # noqa: E402

WORK = Path(f"{WORK}")
CM = Charmap(f"{REF_TREE}/charmap.txt")
DE = Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba").read_bytes()
seuil = float(sys.argv[2]) if len(sys.argv) > 2 else 0.90
mapping = json.loads(
    (WORK / (sys.argv[1] if len(sys.argv) > 1 else 'mapping_de_verifie.json')).read_text())

BON = re.compile(r"[A-Za-z0-9À-ÿ ,.;:!?%'/()\[\]«»\-…\n\\|]+")


def plausible(t):
    if not t:
        return False
    if t.count('?') / len(t) > 0.12:
        return False
    # le charmap decode les octets hors table en kana / cyrillique : signature d'un
    # objet tronque ou mal place, jamais d'un texte allemand
    if re.search(r'[\u3000-\u9fff\u3040-\u30ff\u0400-\u04ff]', t):
        return False
    lettres = sum(1 for c in t if c.isalnum())
    return lettres / len(t) >= 0.45


rows = []
for rel, lst in mapping.items():
    n = ok = 0
    for i, off in lst:
        if off <= 0 or off >= len(DE):
            continue
        n += 1
        e = DE.find(b'\xff', off, off + 400)
        if e < 0:
            continue
        if plausible(CM.decode(DE[off:e])):
            ok += 1
    if n:
        rows.append((ok / n, ok, n, rel))

rows.sort()
print('fichiers les moins plausibles (cote allemand) :')
print('%-6s %6s %6s  %s' % ('part', 'ok', 'total', 'fichier'))
for part, ok, n, rel in rows[:25]:
    print('%6.3f %6d %6d  %s' % (part, ok, n, rel))
mauvais = [r for r in rows if r[0] < seuil]
print('\nfichiers sous %.2f : %d | editions concernees : %d'
      % (seuil, len(mauvais), sum(r[2] for r in mauvais)))
Path(WORK / 'de_gate_mauvais.json').write_text(json.dumps(
    [{'file': r[3], 'part': round(r[0], 3), 'n': r[2]} for r in mauvais], ensure_ascii=False))
print('-> de_gate_mauvais.json')
