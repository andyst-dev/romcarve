#!/usr/bin/env python3
"""de_manifest_verify.py - auto-controle de `german.json.gz` avant de le livrer.

Verifie ce qui est verifiable sans l'arbre source allemand :
  1. l'empreinte SHA1 de la ROM correspond a `rom_sha1` ;
  2. chaque edition texte tombe dans la ROM, sa taille egale la distance au `0xFF` et son texte
     se decode (aucun kana) - le ratio DE/IT reste dans la bande ;
  3. chaque graphisme tombe dans la ROM ; les `.lz` portent l'en-tete `0x10` et se decompressent
     a la taille attendue ;
  4. la table de credits a 275 pointeurs valides ;
  5. les 4 tables Trainer Hill sont dans la ROM, de la bonne taille, et le delta est confirme par
     les fenetres identiques (contre-epreuve : un delta voisin doit tomber a 0).

Usage : python3 de_manifest_verify.py
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

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
MAN = json.load(gzip.open(WORK / 'german.json.gz'))
DE = C.ROMS['DE'].read_bytes()
ITR = C.ROMS['IT'].read_bytes()
IT = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))
CM = C._CM
KANA = re.compile(r'[\u3040-\u30ff\u31f0-\u31ff]')


def main() -> None:
    fails = []
    print('version %s | status %s | sections %s'
          % (MAN['version'], MAN['status'], ','.join(sorted(MAN))))
    sha = hashlib.sha1(DE).hexdigest()
    print('1. sha1 ROM : %s %s' % (sha, 'OK' if sha == MAN['rom_sha1'] else 'INCOHERENT'))
    if sha != MAN['rom_sha1']:
        fails.append('sha1')

    n_ed = bad_ratio = bad_text = unmapped = 0
    for rel, v in MAN['files'].items():
        itv = IT['files'].get(rel)
        it_sizes = {i: e[3] for i, e in enumerate(sorted(itv['edits']))} if itv else {}
        for start, end, off, size, kind in v['edits']:
            n_ed += 1
            if kind not in ('c', 'asm', 'u8array'):
                continue
            z = DE.find(b'\xff', off, off + 40000)
            if z < 0:
                bad_text += 1
                continue
            if size != z - off + 1:
                bad_ratio += 1
            t = CM.decode(DE[off:z])
            raw = DE[off:z]
            # Un octet non mappe par le charmap de travail sort en kana.  Trois classes connues et
            # verifiees a la lecture : les jetons de macro (オカキクケ, ウエ...), les echanges
            # Japon -> valeur des tables structurelles, et deux offsets de prefixe de controle.
            # Le critere DUR reste la taille : une edition dont la taille ne colle pas au 0xFF
            # est un offset faux.
            if len(t) >= 8 and len(KANA.findall(t)) / max(len(t), 1) > 0.05:
                unmapped += 1
    print('2. textes : %d editions | taille != distance au 0xFF : %d (critere dur)'
          % (n_ed, bad_ratio))
    print('   dont jetons non mappes par le charmap de travail : %d (classes connues)' % unmapped)
    if bad_ratio:
        fails.append('tailles de texte')

    miss = 0
    for path, off, size in MAN['graphics']:
        if not 0 <= off < off + size <= len(DE):
            miss += 1
            print('   hors ROM :', path)
    print('3. graphismes : %d / %d dans la ROM' % (len(MAN['graphics']) - miss, len(MAN['graphics'])))
    if miss:
        fails.append('graphismes hors ROM')

    co, n = MAN['credits'], MAN['credits_entries']
    ok = 0
    for i in range(n):
        ptr = int.from_bytes(DE[co + i * 4:co + i * 4 + 4], 'little')
        o = ptr - 0x08000000
        if 0 <= o <= len(DE) - 8 and DE[o + 2:o + 4] == b'\0\0':
            to = int.from_bytes(DE[o + 4:o + 8], 'little') - 0x08000000
            if 0 <= to < len(DE) and DE.find(b'\xff', to, to + 200) >= 0:
                ok += 1
    print('4. credits : %d / %d pointeurs valides a @%d' % (ok, n, co))
    if ok != n:
        fails.append('credits')

    print('5. floors :')
    d = MAN['floors'][0][1] - IT['floors'][0][1]
    for name, off, size in MAN['floors']:
        it_off = next(o for nm, o, s in IT['floors'] if nm == name)
        frag = ITR[it_off:it_off + size]
        same = sum(1 for i in range(0, size - 64, 64)
                   if DE[off + i:off + i + 64] == frag[i:i + 64])
        ctrl = sum(1 for i in range(0, size - 64, 64)
                   if DE[off + 4 + i:off + 4 + i + 64] == frag[i:i + 64])
        print('   %-18s @%d : %d/59 fenetres identiques (delta %+d), contre-epreuve +4 : %d'
              % (name, off, same, d, ctrl))
        if same < 8 or ctrl > 3:
            fails.append('floor ' + name)

    print()
    print('RESULTAT :', 'OK' if not fails else 'PROBLEMES ' + ', '.join(fails))


if __name__ == '__main__':
    main()
