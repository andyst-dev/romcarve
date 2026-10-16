#!/usr/bin/env python3
"""form12.py - branchement des deux formes DEJA prouvees dans le mapping allemand,
avec l'oracle italien comme garde-fou.

Forme 1 (tables a pas fixe) : especes 412x11, capacites 355x13, classes 66x13.
Forme 2 (tables de structures) : dresseurs 855x40 (champ 4), objets 377x44 (champ 0),
                                 Pokedex 387x32 (champ 0), decorations 121x32 (champ 5).

Le manifeste italien verifie la formule  offset_i = base + champ + i*pas  sur 2571/2573
lignes ; les 2 exceptions sont les enregistrements 0 de gTrainers (nom vide) et de
gItems, ou le generateur de reference a laisse un artefact de recherche de contenu
(offset 5 dans l'en-tete de ROM, offset dans la table des especes). Ces artefactes ne
sont PAS reproduits : la formule donne le bon objet, et la taille se releve sur la ROM.

Usage: form12.py <manifeste_ref.json.gz> <CIBLE> [--emit fichier.json]
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

import gzip, json, itertools, math, re, sys
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

FIXED = {
    'src/data/text/species_names.h': 'gSpeciesNames',
    'src/data/text/move_names.h': 'gMoveNames',
    'src/data/text/trainer_class_names.h': 'gTrainerClassNames',
}
STRUCT = {
    'src/data/trainers.h': 'gTrainers',
    'src/data/items.h': 'gItems',
    'src/data/pokemon/pokedex_entries.h': 'gPokedexEntries',
    'src/data/decoration/header.h': 'gDecorations',
}
WIN = 150000

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
        CHAR.setdefault(bs[0], tok.strip("'").replace("\\'", "'"))
VALID.discard(0xFF)
FIELD_BYTES = {b for b, t in CHAR.items() if len(t) == 1 and not t.startswith('{')}
TEXT_START = {b for b, t in CHAR.items() if len(t) == 1 and (t.isalnum() or t in '?♂♀')}
PLAIN = {b for b, t in CHAR.items() if len(t) == 1 and t.isascii() and t.isalnum()}
# table de traduction : 1 = octet absent du charmap (test C plutot qu'une boucle Python)
TR = bytes(0 if b in VALID else 1 for b in range(256))
TRF = bytes(0 if b in FIELD_BYTES else 1 for b in range(256))


def stride_of(offs):
    """pas = difference consecutive la plus frequente (le gcd est casse par un artefact)."""
    diffs = [b - a for a, b in zip(offs, offs[1:]) if b > a]
    if not diffs:
        return None
    return max(set(diffs), key=diffs.count)


def record_ok_pool(data, r, stride, f):
    """forme 1 : chaine au champ, terminee par 0xFF, reste du champs nul (remplissage a zero)."""
    e = data.find(b'\xff', r + f, r + stride)
    if e < 0 or e == r + f:
        return False
    if 1 in data[r + f:e].translate(TR):
        return False
    return not any(data[e + 1:r + stride])


def record_ok_struct(data, r, stride, f, maxlen, first=False):
    """forme 2 : texte (tout octet du charmap), borne par la longueur max relevée en EN."""
    s = r + f
    if data[s] not in TEXT_START:
        return False
    if not first and data[s - 1] in PLAIN:
        return False        # alias a +-1 : on lirait la meme chaine tronquee d'un caractere
    e = data.find(b'\xff', s, r + stride)
    if e < 0 or e == s or (maxlen and e - s > maxlen):
        return False
    return 1 not in data[s:e].translate(TRF)


def score(data, base, stride, f, n, kind, maxlen=0, probes=None):
    if probes is not None:
        for i in probes:
            r = base + i * stride
            good = (record_ok_pool(data, r, stride, f) if kind == 'pool'
                    else record_ok_struct(data, r, stride, f, maxlen, first=(i == 0)))
            if not good:
                return -1
        return len(probes)
    ok = 0
    for i in range(n):
        r = base + i * stride
        good = (record_ok_pool(data, r, stride, f) if kind == 'pool'
                else record_ok_struct(data, r, stride, f, maxlen, first=(i == 0)))
        ok += 1 if good else 0
    return ok


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


def symbol_offset(name):
    for line in MAP.read_text(errors='replace').splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == name and parts[0].startswith('0x'):
            return int(parts[0], 16) - 0x08000000
    return None


def decode_at(data, off, limit=48):
    e = data.find(b'\xff', off, off + limit)
    return ''.join(CHAR.get(x, '?') for x in data[off:e if e > 0 else off])


def best_field(en, base_en, stride, n, kind):
    best = (0, -1)
    for f in range(stride):
        s = score(en, base_en, stride, f, n, kind)
        if s > best[1]:
            best = (f, s)
    return best


def size_of(data, off, stride, field):
    """taille de l'objet = texte + terminateur (convention mesuree sur le manifeste IT)."""
    e = data.find(b'\xff', off, off + stride - field)
    return (e - off + 1) if e >= 0 else None


def main():
    ref = json.loads(gzip.decompress(Path(sys.argv[1]).read_bytes()))['files']
    target = sys.argv[2]
    emit = Path(sys.argv[sys.argv.index('--emit') + 1]) if '--emit' in sys.argv else None
    data = ROMS[target].read_bytes()
    en = ROMS['EN'].read_bytes()
    truth = None
    if target in ('IT', 'FR'):
        truth = json.loads(gzip.decompress((LOCALES / {'IT': 'italian.json.gz', 'FR': 'french.json.gz'}[target]).read_bytes()))['files']

    plan = {}
    for kind, tables in (('pool', FIXED), ('struct', STRUCT)):
        for rel, sym in tables.items():
            if rel not in ref:
                continue
            offs = sorted(e[2] for e in ref[rel]['edits'])
            n = len(offs)
            stride = stride_of(offs)
            base_en = symbol_offset(sym)
            f, s_en = best_field(en, base_en, stride, n, kind)
            maxlen = max(field_lengths(en, base_en, stride, f, n)) if kind == 'struct' else 0
            min_ok = n - max(1, n // 100)
            # balayage en deux passes : quelques enregistrements sondes d'abord (le score
            # complet est O(positions x n), la sonde le ramene a O(positions x 3))
            probes = sorted({1, n // 3, 2 * n // 3, n - 1})
            lo, hi = max(0, base_en - WIN), min(len(data) - stride * 2, base_en + WIN)
            cands = []
            for b in range(lo, hi):
                if score(data, b, stride, f, n, kind, maxlen, probes=probes) < 0:
                    continue
                if score(data, b, stride, f, n, kind, maxlen) >= min_ok:
                    cands.append(b)
            en_len = field_lengths(en, base_en, stride, f, n)
            scored = sorted(((-corr(field_lengths(data, b, stride, f, n), en_len), abs(b - base_en), b)
                             for b in cands))
            plan[rel] = dict(kind=kind, n=n, stride=stride, field=f, base_en=base_en,
                             s_en=s_en, maxlen=maxlen, min_ok=min_ok, cands=scored)

    # forme 1 : les trois tables doivent partager le MEME delta (departage des alias +-pas)
    coh = None
    fixed = [r for r in plan if plan[r]['kind'] == 'pool']
    if fixed:
        sets = [{b - plan[r]['base_en']: b for _, _, b in plan[r]['cands'][:8]} for r in fixed]
        common = set(sets[0])
        for s in sets[1:]:
            common &= set(s)
        if common:
            coh = sorted(common)[0]
            print('delta commun aux trois tables a pas fixe : %+d' % coh)

    out, sizes = {}, {}
    for rel, p in plan.items():
        n, stride, f = p['n'], p['stride'], p['field']
        cands = p['cands']
        if p['kind'] == 'pool' and coh is not None:
            pick = next((b for _, _, b in cands if b - p['base_en'] == coh), cands[0][2] if cands else None)
        elif p['kind'] == 'struct' and coh is not None:
            same = [b for _, _, b in cands if b - p['base_en'] == coh]
            pick = same[0] if same else (cands[0][2] if cands else None)
        else:
            pick = cands[0][2] if cands else None
        print('\n%-42s n=%d pas=%d champ=%d (EN %d/%d%s)'
              % (rel, n, stride, f, p['s_en'], n,
                 ', len max %d' % p['maxlen'] if p['maxlen'] else ''))
        if pick is None:
            print('   AUCUNE base')
            continue
        pred = [pick + f + i * stride for i in range(n)]
        tag = ''
        if truth and rel in truth:
            ref_off = sorted(e[2] for e in truth[rel]['edits'])
            exact = sum(1 for a, b in zip(pred, ref_off) if a == b)
            tag = ' | ORACLE %d/%d' % (exact, n)
        c = corr(field_lengths(data, pick, stride, f, n), field_lengths(en, p['base_en'], stride, f, n))
        print('   base %d delta %+d corr %.3f  (%d candidats)%s'
              % (pick, pick - p['base_en'], c, len(cands), tag))
        for b in [b for _, _, b in cands[:4]]:
            print('      alias base %d delta %+d -> %r / %r'
                  % (b, b - p['base_en'], decode_at(data, b + f + stride), decode_at(data, b + f + 2 * stride)))
        out[rel] = [pick, n, stride, f]
        sizes[rel] = [size_of(data, o, stride, f) for o in pred]
        print('   tailles : min %s max %s | 5 exemples %s'
              % (min(sizes[rel]), max(sizes[rel]), [decode_at(data, o) for o in pred[1:4]]))

    rows = {}
    for rel, (base, n, stride, f) in out.items():
        rows[rel] = [[i, base + f + i * stride] for i in range(n)]
    tot = sum(len(v) for v in rows.values())
    print('\nbranchement : %d editions dans %d fichiers' % (tot, len(rows)))
    print('tailles : %s' % {r: (min(v), max(v)) for r, v in sizes.items()})
    if emit:
        emit.write_text(json.dumps(rows))
        print('-> %s' % emit)


if __name__ == '__main__':
    main()
