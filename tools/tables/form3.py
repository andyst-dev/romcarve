#!/usr/bin/env python3
"""form3.py - forme 3 : tables de structures a PLUSIEURS champs par enregistrement
(dresseurs de la Zone de Combat, tentes de combat).

Ces tables ne se resument pas a "un texte par enregistrement" : chaque enregistrement
porte un nom ET trois tableaux d'indices de mots (fenetres de discours). Le motif
INTRA-enregistrement (decalage de chaque champ depuis le debut de l'enregistrement) est
invariant de langue - verifie : identique dans les manifestes espagnol et italien
([4, 12, 24, 36]) - donc il s'apprend sur le manifeste de reference et se transporte.
Ce qui NE se transporte PAS, c'est le contenu des tableaux d'indices : mesure 0/300
identiques entre EN et IT (l'index stocke est la position alphabetique du mot DANS SA
LANGUE). L'ancre est donc le seul champ texte : le nom, a +4, sur 8 octets.

Les bases anglaises viennent de la carte de symboles (`gFrontierTrainers` 15600 o =
300 x 52 ; les trois `g*BattleTentTrainers` = 1560 o = 30 x 52 chacun). Un fichier peut
couvrir PLUSIEURS tables a la suite (tentes : 3 x 30, avec des trous entre elles) : on
decoupe en BLOCS de pas constant et chaque bloc se localise tout seul.

Usage: form3.py <manifeste_ref.json.gz> <CIBLE> [--emit fichier.json]
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

import gzip, json, re, sys
from pathlib import Path

TREE = Path(f"{REF_TREE}")
ROMS = {
    'EN': Path(f"{ROMS}/emeraude_en.gba"),
    'FR': Path(f"{ROMS}/emeraude_fr.gba"),
    'IT': Path(f"{WORK}/roms/it_bpei.gba"),
    'DE': Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba"),
}
LOCALES = Path(f"{REF_DIR}")
SYMBOLS = Path(f"{WORK}/en_symbols.json")

# fichier -> (symboles EN, un par bloc, en ordre d'adresse ; pas ; champ du nom ; largeur)
TABLES = {
    'src/data/battle_frontier/battle_frontier_trainers.h':
        (['gBattleFrontierTrainers'], 52, 4, 8),
    'src/data/battle_frontier/battle_tent.h':
        (['gSlateportBattleTentTrainers', 'gVerdanturfBattleTentTrainers', 'gFallarborBattleTentTrainers'],
         52, 4, 8),
}
WIN = 150000

CHAR, FIELD_BYTES, TEXT_START, PLAIN = {}, set(), set(), set()
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
for b, t in CHAR.items():
    if len(t) == 1 and not t.startswith('{'):
        FIELD_BYTES.add(b)
        if t.isalnum() or t in '?♂♀':
            TEXT_START.add(b)
        if t.isascii() and t.isalnum():
            PLAIN.add(b)
TRF = bytes(0 if b in FIELD_BYTES else 1 for b in range(256))


def name_ok(data, b, field, width):
    """champ nom : premier octet texte, terminateur dans la largeur du champ, octet
    precedent non-lettre (ce dernier point tue les alias a +-1)."""
    s = b + field
    if data[s] not in TEXT_START or data[s - 1] in PLAIN:
        return False
    e = data.find(b'\xff', s, b + field + width)
    if e < 0 or e == s:
        return False
    return not (data[s:e].translate(TRF).count(1))


def blocks_of(edits, field, stride):
    """decoupe les editions en blocs de pas constant (les tentes en comptent trois)."""
    names = [(j, e[2] - field) for j, e in enumerate(edits) if e[4] == 'c']
    blocks, cur = [], [names[0]]
    for prev, nxt in zip(names, names[1:]):
        if nxt[1] - prev[1] == stride:
            cur.append(nxt)
        else:
            blocks.append(list(cur))
            cur = [nxt]
    blocks.append(list(cur))
    return [[j for j, _ in b] for b in blocks]


def decode_at(data, off, limit=24):
    e = data.find(b'\xff', off, off + limit)
    return ''.join(CHAR.get(x, '?') for x in data[off:e if e > 0 else off])


def main():
    ref = json.loads(gzip.decompress(Path(sys.argv[1]).read_bytes()))['files']
    target = sys.argv[2]
    emit = Path(sys.argv[sys.argv.index('--emit') + 1]) if '--emit' in sys.argv else None
    data = ROMS[target].read_bytes()
    syms = {k: v[0][0] for k, v in json.load(open(SYMBOLS)).items() if v}
    truth = (json.loads(gzip.decompress((LOCALES / 'italian.json.gz').read_bytes()))['files']
             if target == 'IT' else None)

    out = {}
    known = {}
    print('cible = %s' % target)
    for rel, (symbols, stride, field, width) in TABLES.items():
        edits = sorted(ref[rel]['edits'])
        blocks = blocks_of(edits, field, stride)
        print('\n%s  n=%d  pas=%d  nom +%d sur %d o  %d bloc(s) %s'
              % (rel.split('/')[-1], len(edits), stride, field, width, len(blocks),
                 [len(b) for b in blocks]))
        assert len(symbols) == len(blocks), 'autant de symboles que de blocs attendu'
        # 1) on localise chaque bloc independamment ; 2) les blocs courts (30 enregistrements)
        #    sont ambigus dans un voisinage qui contient la table de 300 -> on les tranche par
        #    la COHERENCE DE DELTA avec le bloc le plus long, jamais par un seuil.
        rows = {}
        info = []
        for bi, blk in enumerate(blocks):
            cnt = len(blk)
            base_en = syms[symbols[bi]]
            cands = [b for b in range(max(0, base_en - WIN), min(len(data) - stride * 2, base_en + WIN))
                     if all(name_ok(data, b + i * stride, field, width) for i in range(cnt))]
            info.append(dict(bi=bi, blk=blk, cnt=cnt, base_en=base_en, cands=cands))
            print('   bloc %d : %d enregistrements | base EN %d | %d candidat(s)'
                  % (bi, cnt, base_en, len(cands)))
        known, chosen = known, {}
        for it in sorted(info, key=lambda x: -x['cnt']):
            deltas = sorted(set(b - it['base_en'] for b in it['cands']))
            pick = None
            if len(deltas) == 1:
                pick, why = it['cands'][0], 'candidat unique'
            else:
                hit = [d for d in deltas if d in known]
                if len(hit) == 1:
                    pick = it['base_en'] + hit[0]
                    why = 'delta %+d impose par le bloc %d' % (hit[0], known[hit[0]])
                else:
                    why = 'ambigu (%d deltas candidats, %s)' % (
                        len(deltas), 'aucun connu' if not hit else 'plusieurs connus')
            if pick is None:
                print('   bloc %d (EN %d) : PAS DE BASE - %s' % (it['bi'], it['base_en'], why))
                continue
            known[pick - it['base_en']] = it['bi']
            chosen[it['bi']] = pick
            print('   bloc %d retenu : base %d (delta %+d vs EN, %s) -> %r / %r / %r'
                  % (it['bi'], pick, pick - it['base_en'], why, decode_at(data, pick + field),
                     decode_at(data, pick + stride + field), decode_at(data, pick + 2 * stride + field)))
        for it in info:
            if it['bi'] not in chosen:
                continue
            best = chosen[it['bi']]
            blk = it['blk']
            step = blk[1] - blk[0]                       # editions par enregistrement
            for i, nj in enumerate(blk):
                ref_rec = edits[nj][2] - field           # base de l'enregistrement, cote reference
                for j in range(nj, nj + step):
                    rows[j] = best + i * stride + (edits[j][2] - ref_rec)
        out[rel] = [[j, rows[j]] for j in sorted(rows)]

    tot = sum(len(v) for v in out.values())
    print('\nbranchement forme 3 : %d editions dans %d fichiers' % (tot, len(out)))
    if truth:
        ex = tot2 = 0
        for rel, lst in out.items():
            tref = sorted(truth[rel]['edits'])
            for j, o in lst:
                tot2 += 1
                ex += (o == tref[j][2])
        print('ORACLE IT : %d/%d exacts' % (ex, tot2))
    if emit:
        emit.write_text(json.dumps(out))
        print('-> %s' % emit)


if __name__ == '__main__':
    main()
