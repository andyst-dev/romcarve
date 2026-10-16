#!/usr/bin/env python3
"""degerman.py - le texte ALLEMAND EN SOURCE de la branche amont est-il celui de la
cartouche ?

La branche `pret_europe_german` (AsparagusEduardo/pokeemerald) ne contient pas de
`data/text/german/*.inc`, mais elle porte des bras `#elif GERMAN` dans quelques
fichiers .c/.h, avec du VRAI texte allemand. Si ce texte est celui de la ROM
Smaragd, on peut l'encoder avec le charmap et le RETROUVER par recherche de
contenu : l'offset cible tombe alors sans aucun alignement.

Sortie : de_german_source.json  { "<fichier>": [[nom, texte, offset_rom|None], ...] }
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

sys.path.insert(0, f"{VFWORK}")
from charmap import Charmap

BASE = Path(f"{WORK}/debranch_src")
BASEH = Path(f"{WORK}/debranch_include")
DE_ROM = Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba")
EN_ROM = Path(f"{ROMS}/emeraude_en.gba")
TREE = Path(f"{REF_TREE}")
CM = Charmap(str(TREE / 'charmap.txt'))

FILES = ['src/strings.c', 'src/battle_message.c', 'src/battle_main.c', 'src/battle_pike.c',
         'src/international_string_util.c', 'src/data/credits.h', 'src/graphics.c']

DECL = re.compile(r'([A-Za-z_][A-Za-z_0-9]*)\s*(\[\s*\])?\s*=|;\s*$')


def german_arms(text: str):
    """[(ligne_debut, ligne_fin, contenu)] des bras GERMAN (selectionnes quand
    GAME_LANGUAGE == LANGUAGE_GERMAN)."""
    lines = text.splitlines()
    out = []
    depth = 0            # profondeur de #if dans le bras courant
    start = None
    in_arm = False
    for i, ln in enumerate(lines):
        s = ln.lstrip()
        if s.startswith('#'):
            tok = s[1:].split()[0] if len(s) > 1 else ''
            if tok in ('if', 'ifdef', 'ifndef'):
                if in_arm:
                    depth += 1
                continue
            if tok == 'endif':
                if in_arm:
                    if depth == 0:
                        out.append((start, i, '\n'.join(lines[start:i])))
                        in_arm = False
                    else:
                        depth -= 1
                continue
            if tok in ('elif', 'else'):
                if in_arm:
                    if depth == 0:
                        out.append((start, i, '\n'.join(lines[start:i])))
                        in_arm = False
                    else:
                        continue
                    # bas de la chaine : on regarde si le nouvel arm est GERMAN
                if re.search(r'\bGERMAN\b', s) and tok == 'elif':
                    in_arm = True
                    start = i + 1
                    depth = 0
                continue
    if in_arm:
        out.append((start, len(lines), '\n'.join(lines[start:])))
    return out


def extract_literals(chunk: str):
    """[(nom, texte)] des declarations `<nom>[] = _("...");` du bloc."""
    out = []
    for m in re.finditer(r'\b([A-Za-z_][A-Za-z_0-9]*)\s*(\[[^\]]*\])?\s*=\s*_\(', chunk):
        name = m.group(1)
        j = m.end()                      # juste apres _(
        depth = 1
        buf = []
        k = j
        while k < len(chunk) and depth:
            c = chunk[k]
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    break
            buf.append(c)
            k += 1
        body = ''.join(buf)
        lits = re.findall(r'"((?:[^"\\]|\\.)*)"', body)
        if lits:
            out.append((name, ''.join(lits)))
    return out


def main():
    de = DE_ROM.read_bytes()
    en = EN_ROM.read_bytes()
    report = {}
    tot = hit = 0
    rows = []
    for rel in FILES:
        p = BASE / rel[len('src/'):] if rel.startswith('src/') else BASEH / rel
        if not p.exists():
            p = Path(f"{WORK}/debranch_src") / rel.split('/', 1)[1]
        if not p.exists():
            print("absent :", rel)
            continue
        txt = p.read_text(encoding='utf-8', errors='replace')
        arms = german_arms(txt)
        items = []
        for (a, b, chunk) in arms:
            for name, lit in extract_literals(chunk):
                try:
                    enc = CM.encode(lit)
                except Exception as e:
                    items.append([name, lit, None, 'encode:%s' % e])
                    continue
                if len(enc) < 4:
                    items.append([name, lit, None, 'court'])
                    continue
                off = de.find(enc)
                en_off = en.find(enc)
                tot += 1
                if off >= 0:
                    hit += 1
                    items.append([name, lit, off + 0x08000000, None])
                else:
                    items.append([name, lit, None,
                                  ('aussi_en_EN' if en_off >= 0 else 'introuvable')])
        report[rel] = items
        n_ok = sum(1 for it in items if it[2])
        rows.append((n_ok, len(items), rel, len(arms)))
    print("litteraux allemands extraits : %d | retrouves dans la ROM DE : %d (%.1f%%)"
          % (tot, hit, 100.0 * hit / max(1, tot)))
    for n_ok, n, rel, na in rows:
        print("   %-40s %4d/%4d  (%d bras GERMAN)" % (rel, n_ok, n, na))
    out = Path(f"{WORK}/de_german_source.json")
    out.write_text(json.dumps(report, ensure_ascii=False))
    print("->", out)
    print("\nexemples retrouves :")
    shown = 0
    for rel, items in report.items():
        for name, lit, off, why in items:
            if off and shown < 12:
                print("   %-46s @%08X  %r" % (name, off, lit[:60]))
                shown += 1
    print("\nexemples NON retrouves :")
    shown = 0
    for rel, items in report.items():
        for name, lit, off, why in items:
            if not off and shown < 10:
                print("   %-46s %-14s %r" % (name, why, lit[:60]))
                shown += 1


if __name__ == '__main__':
    main()
