#!/usr/bin/env python3
"""merge_de.py - fusionne les resolutions par marche dans le mapping allemand.

Sources :
  - objalign_strings.c.json      (DP au niveau objet, src/strings.c)
  - hybrid_battle_message.c.json (marche + re-ancrage, src/battle_message.c)
  - mapping_de_verifie.json      (fitter de pools + ancres de contenu, le reste)

L'appariement nom -> indice d'edition suit la regle verifiee : le `_(` du litteral est
AU char_start de l'edition, donc la declaration qui la contient est le dernier match de
`NAME[] = _(` dans src[:char_start + 3].

Usage : merge_de.py
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

import collections, gzip, json, re, sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
sys.path.insert(0, f"{VFWORK}")
from charmap import Charmap
from hybrid import DECL_RE, TREE, WORK
from place4 import TB

CM = Charmap(str(TREE / 'charmap.txt'))
DE = Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba").read_bytes()
SOURCES = {
    'src/strings.c': 'objalign_strings.c.json',
    'src/battle_message.c': 'hybrid_battle_message.c.json',
}
# formes 1 et 2 (tables a pas fixe et tables de structures) : lignes [indice, offset] directes,
# produites par form12.py (oracle italien 2571/2573, 2 artefacts documentes du manifeste de ref)
SOURCES_ROWS = ['form12_DE.json', 'form3_DE.json']


def main():
    man = json.loads(gzip.decompress(Path(f"{REF_DIR}/italian.json.gz").read_bytes()))
    mapping = json.loads((WORK / 'mapping_de_verifie.json').read_text())
    mapping = {k: {i: o for i, o in v} for k, v in mapping.items()}
    added = 0
    for f in SOURCES_ROWS:
        rows = json.loads((WORK / f).read_text())
        for rel, lst in rows.items():
            d = mapping.setdefault(rel, {})
            n_add = sum(1 for i, o in lst if i not in d)
            for i, o in lst:
                d[i] = o
            print("%-42s %d editions attribuees par %s (%d nouvelles)" % (rel, len(lst), f, n_add))
            added += n_add
    for rel, f in SOURCES.items():
        rows = json.loads((WORK / f).read_text())
        byname = {}
        for nm, off in rows:
            byname.setdefault(nm, off)
        src = (TREE / rel).read_text(encoding='utf-8', errors='replace')
        d = mapping.setdefault(rel, {})
        n_add = 0
        for idx, e in enumerate(sorted(man['files'][rel]['edits'])):
            m = None
            for mm in DECL_RE.finditer(src[:e[0] + 3]):
                m = mm
            if not m:
                continue
            off = byname.get(m.group(1))
            if off is None:
                continue
            if idx not in d:
                n_add += 1
            d[idx] = off
        print("%-28s %d editions du manifeste | %d attribuees par la marche (%d nouvelles)"
              % (rel, len(man['files'][rel]['edits']), sum(1 for i in d), n_add))
        added += n_add

    out = {k: [[i, o] for i, o in sorted(v.items())] for k, v in mapping.items()}
    (WORK / 'mapping_de_verifie.json').write_text(json.dumps(out))
    tot = sum(len(v) for v in out.values())
    alled = sum(len(v['edits']) for v in man['files'].values())
    print("\nmapping allemand consolide : %d/%d editions (%.1f%%) dans %d fichiers"
          % (tot, alled, 100.0 * tot / alled, sum(1 for v in out.values() if v)))

    # controles allemands, par forme : les tables a pas fixe / structures n'obesissent pas a
    # la regle du pool (l'objet n'y est pas precede d'un 0xFF), il faut la leur.
    TEXT_START = {b for b, t in ((b, CM.decode(bytes([b]))) for b in range(256))
                  if len(t) == 1 and (t.isalnum() or t in '?♂♀')}
    rows_form12 = json.loads((WORK / 'form12_DE.json').read_text())
    rows_form3 = json.loads((WORK / 'form3_DE.json').read_text())
    n_shape = n_text = n_dec = 0
    for rel, lst in rows_form12.items():
        offs = [o for _, o in lst]
        gap = max(4, offs[1] - offs[0])
        for _, off in lst:
            e = DE.find(b'\xff', off, off + gap)
            if e < 0:
                continue
            n_shape += 1
            body = DE[off:e]
            if body and body[0] in TEXT_START and all(x in TB for x in body):
                n_text += 1
            t = CM.decode(body)
            if '?' not in t[:120]:
                n_dec += 1
    print("   formes 1/2 : objets termines dans leur enregistrement %d/%d | texte valide %d | "
          "decodables %d" % (n_shape, sum(len(v) for v in rows_form12.values()), n_text, n_dec))

    # forme 3 (structures multi-champs) : seul le champ nom est du texte ; le controle propre a
    # cette forme est le POINTEUR de fin d'enregistrement (4 octets a +48, donc offset+44 depuis
    # le nom), qui doit tomber dans la ROM - 390/390 en allemand, ce qu'aucune base fausse ne fait.
    n3_name = n3_ptr = n3_tot = 0
    for rel, lst in rows_form3.items():
        kinds = man['files'][rel]['edits']
        for j, off in lst:
            if kinds[j][4] != 'c':
                continue
            n3_tot += 1
            e = DE.find(b'\xff', off, off + 8)
            if e > off and all(x in TB for x in DE[off:e]):
                n3_name += 1
            p = int.from_bytes(DE[off + 44:off + 48], 'little')
            if 0x08000000 <= p < 0x09000000:
                n3_ptr += 1
    print("   forme 3 : noms lisibles %d/%d | pointeur de fin d'enregistrement valide %d/%d"
          % (n3_name, n3_tot, n3_ptr, n3_tot))

    ok_shape = ok_text = ok_dec = 0
    n_pool = 0
    for rel, lst in out.items():
        if rel in rows_form12 or rel in rows_form3:
            continue
        for idx, off in lst:
            n_pool += 1
            if off <= 0 or off >= len(DE) or DE[off - 1] != 0xFF:
                continue
            en = DE.find(b'\xff', off, off + 400)
            if en < 0:
                continue
            ok_shape += 1
            body = DE[off:en]
            if all(x in TB for x in body):
                ok_text += 1
            t = CM.decode(body)
            if '?' not in t[:120]:
                ok_dec += 1
    print("   objets bien formes : %d/%d | octets dans la table de texte : %d | decodables : %d"
          % (ok_shape, n_pool, ok_text, ok_dec))
    grp = collections.Counter()
    for rel, v in out.items():
        g = ('data/maps' if rel.startswith('data/maps/') else
             'easy_chat' if rel.startswith('src/data/easy_chat/') else
             'data/text' if rel.startswith('data/text/') else rel)
        grp[g] += len(v)
    print("   principaux groupes :", grp.most_common(6))


if __name__ == '__main__':
    main()
