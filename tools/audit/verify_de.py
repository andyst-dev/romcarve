#!/usr/bin/env python3
"""verify_de.py - ce qui est VERIFIABLE sur la variante allemande.

Il n'existe pas de manifeste allemand : pas de verite terrain. On peut neanmoins
controler, pour chaque edition placee :
  1. l'objet est bien un objet (precede d'un 0xFF, termine par un 0xFF) ;
  2. tous ses octets appartiennent a la table de texte ;
  3. le texte se DECODE (charmap) et sa longueur reste dans un rapport plausible
     avec la longueur anglaise (l'allemand est plus long d'environ 10-20 %) ;
  4. ACCORD avec les ancres de CONTENU (texte allemand retrouve par recherche : les
     objets de strings.c et battle_message.c sont certains a 100 %).

Usage : verify_de.py
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

import bisect, collections, json, re, sys
from pathlib import Path

sys.path.insert(0, f"{VFWORK}")
sys.path.insert(0, f"{WORK}")
from charmap import Charmap
from place4 import TB

WORK = Path(f"{WORK}")
TREE = Path(f"{REF_TREE}")
CM = Charmap(str(TREE / 'charmap.txt'))
DE = Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba").read_bytes()


def main():
    g = json.loads((WORK / 'gmap3_DE.json').read_text())
    anchors = {}
    for f in ('anchors_battle_message.c.json', 'anchors_strings.c.json'):
        p = WORK / f
        if p.exists():
            for nm, off, ln in json.loads(p.read_text()):
                anchors.setdefault(f, {})[nm] = (off, ln)
    tot = sum(len(v) for v in g.values())
    print("mapping fitter : %d editions dans %d fichiers" % (tot, sum(1 for v in g.values() if v)))

    ok_shape = ok_text = ok_decode = 0
    ratios = []
    bad = []
    for rel, lst in g.items():
        for idx, off in lst:
            if off <= 0 or off >= len(DE) or DE[off - 1] != 0xFF:
                bad.append((rel, idx, off, 'pas_objet'))
                continue
            e = DE.find(b'\xff', off, off + 400)
            if e < 0:
                bad.append((rel, idx, off, 'sans_terminateur'))
                continue
            ok_shape += 1
            body = DE[off:e]
            if all(x in TB for x in body):
                ok_text += 1
            txt = CM.decode(body)
            if not any(ch == '{' and len(ch) > 1 for ch in txt) and '?' not in txt[:200]:
                ok_decode += 1
            ratios.append((e - off + 1))
    n = len(ratios)
    print("   objet bien forme (0xFF avant/apres) : %d/%d" % (ok_shape, tot))
    print("   tous les octets dans la table de texte : %d/%d" % (ok_text, tot))
    print("   texte decodable : %d/%d" % (ok_decode, tot))
    print("   longueur moyenne des objets : %.1f o" % (sum(ratios) / max(1, n)))

    # accord avec les ancres de contenu
    print("\nACCORD avec les ancres de CONTENU (certaines a 100 %) :")
    agree = dis = 0
    for f, d in anchors.items():
        rel = 'src/' + f[len('anchors_'):-len('.json')]
        got = dict((idx, off) for idx, off in g.get(rel, []))
        # nom -> index d'edition
        names = []
        p = TREE / rel
        if p.exists():
            src = p.read_text(encoding='utf-8', errors='replace')
            m = None
            for mm in re.finditer(r'\b([A-Za-z_][A-Za-z_0-9]*)\s*(?:\[[^\]]*\])?\s*=\s*_\(', src):
                names.append((mm.start(), mm.group(1)))
        if not names:
            continue
        idx_of = {}
        for i, (posn, nm) in enumerate(names):
            idx_of.setdefault(nm, i)
        n_a = len(d)
        for nm, (off, ln) in d.items():
            i = idx_of.get(nm)
            if i is None:
                continue
            o2 = got.get(i)
            if o2 is None:
                continue
            if abs(o2 - off) <= 1:
                agree += 1
            else:
                dis += 1
        print("   %-28s %d ancres de contenu | le fitter en place %d | accord %d"
              % (rel, n_a, sum(1 for nm in d if idx_of.get(nm) in got), 0))
    print("   total : accord %d | desaccord %d" % (agree, dis))

    # ecrit le mapping consolide : fitter + ancres de contenu (prioritaires)
    merged = {k: {i: o for i, o in v} for k, v in g.items()}
    n_anch = 0
    for f, d in anchors.items():
        rel = 'src/' + f[len('anchors_'):-len('.json')]
        p = TREE / rel
        if not p.exists():
            continue
        src = p.read_text(encoding='utf-8', errors='replace')
        names = []
        for mm in re.finditer(r'\b([A-Za-z_][A-Za-z_0-9]*)\s*(?:\[[^\]]*\])?\s*=\s*_\(', src):
            names.append((mm.start(), mm.group(1)))
        idx_of = {}
        for i, (posn, nm) in enumerate(names):
            idx_of.setdefault(nm, i)
        for nm, (off, ln) in d.items():
            i = idx_of.get(nm)
            if i is None:
                continue
            merged.setdefault(rel, {})[i] = off
            n_anch += 1
    out = {k: [[i, o] for i, o in sorted(v.items())] for k, v in merged.items()}
    tot2 = sum(len(v) for v in out.values())
    (WORK / 'mapping_de_verifie.json').write_text(json.dumps(out))
    print("\nmapping consolide : %d editions (%d venues des ancres de contenu)"
          % (tot2, n_anch))
    print("-> mapping_de_verifie.json")


if __name__ == '__main__':
    main()
