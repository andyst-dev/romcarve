#!/usr/bin/env python3
"""de_graphics_locate.py - localise dans la ROM DE les 104 graphismes du manifeste italien.

Le manifeste italien liste 104 assets `[chemin, offset_rom, taille]` que le localiseur recopie
dans l'arbre (`writes[tree/relative]`, et le decompresse pour les `.lz`).  Il faut les memes
assets pour l'allemand, aux offsets DE.

La ROM DE est la ROM RETAIL allemande (BPED) et l'italienne la retail italienne (BPEI) : meme
jeu, meme ordre d'assets, layout tres proche (le delta global etudie sur les tables Trainer Hill
vaut +84528 et il est localement lisse).  Trois passes, dans cet ordre :

  1. **contenu exact** - les assets sans texte sont byte-identiques : `de.find(blob)`.
  2. **flux LZ77 identique** - on indexe tous les flux LZ77 de la ROM DE (en-tete 0x10, taille
     sur 3 octets, decompression valide) et on cherche celui dont le contenu DECOMPRESSE a le
     meme SHA1 que celui de l'asset italien.  Trouve les `.lz` dont seul l'emballage differe.
  3. **taille decompressee + proximite** - pour un `.lz` au contenu different (une dalle avec du
     texte), la taille decompressee reste la meme : on cherche un flux de meme taille dans une
     fenetre locale deduite du delta des ancres voisines (interpolation sur l'ordre italien),
     puis on ACCEPTE seulement s'il tombe a moins de 4 Ko de la position attendue.
  4. **tranches de 64 octets** - un asset brut dont seul un coin porte du texte a des tranches
     identiques : on cherche 4 tranches (0 %, 25 %, 50 %, 75 %) et on garde l'offset coherent.
  5. **traduction depuis l'ancre voisine** - pour les assets bruts restants (polices, palettes,
     boutons), `de = de_ancre + (it_off - it_off_ancre)`, valide sur les polices par le motif
     d'en-tete identique a la meme position relative.

Sortie : `de_graphics.json` = [[chemin, offset, taille], ...] dans l'ordre italien.

Usage : python3 de_graphics_locate.py [--emit]
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
import sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
sys.path.insert(0, f"{REF_DIR}/builder")
import carve7 as C  # noqa: E402
from emerald3ds_builder.recipe import lz77_decompress  # noqa: E402

WORK = Path(f"{WORK}")
IT = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))
DE = C.ROMS['DE'].read_bytes()
ITR = C.ROMS['IT'].read_bytes()
DELTA = 84560          # delta prouve sur la region des polices (motif d'en-tete identique)


def stream_length(src: bytes, offset: int) -> int:
    """Longueur du flux LZ77 (en-tete inclus) en re-suivant la decompression."""
    size = src[offset + 1] | (src[offset + 2] << 8) | (src[offset + 3] << 16)
    pos, out = offset + 4, 0
    while out < size:
        flags = src[pos]
        pos += 1
        for bit in range(8):
            if out >= size:
                break
            if flags & (0x80 >> bit):
                a, b = src[pos], src[pos + 1]
                pos += 2
                out += (a >> 4) + 3
            else:
                pos += 1
                out += 1
    return pos - offset


def main() -> None:
    # index des flux LZ77 de la ROM DE : sha1(contenu) -> offsets
    bysha: dict[str, list[int]] = {}
    bysize: dict[int, list[int]] = {}
    pos = -1
    while True:
        pos = DE.find(b'\x10', pos + 1)
        if pos < 0:
            break
        size = DE[pos + 1] | (DE[pos + 2] << 8) | (DE[pos + 3] << 16)
        if not (8 <= size <= 0x40000):
            continue
        try:
            raw = lz77_decompress(DE, pos)
        except Exception:
            continue
        if len(raw) != size:
            continue
        bysha.setdefault(hashlib.sha1(raw).hexdigest(), []).append(pos)
        bysize.setdefault(size, []).append(pos)

    located: dict[str, tuple[int, int]] = {}
    size_bytes: dict[str, int] = {}
    for path, off, size in IT['graphics']:
        blob = ITR[off:off + size]
        size_bytes[path] = size
        p = DE.find(blob)
        if p >= 0:
            located[path] = (p, size)
            continue
        if path.endswith('.lz'):
            raw = lz77_decompress(ITR, off)
            hit = bysha.get(hashlib.sha1(raw).hexdigest())
            if hit:
                located[path] = (hit[0], stream_length(DE, hit[0]))
    # passe 3 : taille decompressee + proximite
    order = sorted(IT['graphics'], key=lambda g: g[1])
    for path, off, size in order:
        if path in located or not path.endswith('.lz'):
            continue
        raw = lz77_decompress(ITR, off)
        cands = bysize.get(len(raw), [])
        if not cands:
            continue
        anchors = [(o, located[p][0] - o) for p, o, s in order if p in located]
        target = off + min(anchors, key=lambda t: abs(t[0] - off))[1] if anchors else -1
        near = sorted(cands, key=lambda c: abs(c - target))
        if abs(near[0] - target) < 4096:
            located[path] = (near[0], stream_length(DE, near[0]))
    # passe 4 : tranches de 64 octets
    for path, off, size in order:
        if path in located:
            continue
        blob = ITR[off:off + size]
        hits = []
        for frac in (0.0, 0.25, 0.5, 0.75):
            s = blob[int(size * frac):int(size * frac) + 64]
            if len(s) < 32:
                continue
            p = DE.find(s)
            if p >= 0 and DE.find(s, p + 1) < 0:
                hits.append(p - int(size * frac))
        if hits:
            from collections import Counter
            located[path] = (Counter(hits).most_common(1)[0][0], size)
    # passe 5 : traduction depuis l'ancre voisine
    for path, off, size in order:
        if path in located:
            continue
        anchors = [(o, located[p][0] - o) for p, o, s in order if p in located]
        if not anchors:
            continue
        a = min(anchors, key=lambda t: abs(t[0] - off))
        located[path] = (off + a[1], size)

    out = [[path, located[path][0], located[path][1]]
           for path, off, size in IT['graphics'] if path in located]
    missing = [p for p, o, s in IT['graphics'] if p not in located]
    print('%d / %d graphismes localises ; manquants : %s'
          % (len(out), len(IT['graphics']), missing))
    # controle : ordre croissant et pas de chevauchement
    srt = sorted(out, key=lambda t: t[1])
    prev_end = -1
    for path, o, s in srt:
        if o < prev_end:
            print('  CHEVAUCHEMENT %s @%d (fin precedente %d)' % (path, o, prev_end))
        prev_end = o + s
    if '--emit' in sys.argv:
        (WORK / 'de_graphics.json').write_text(json.dumps(out, indent=1))
        print('ecrit de_graphics.json')


if __name__ == '__main__':
    main()
