#!/usr/bin/env python3
"""ec_words.py - table id EC_WORD -> mot ALLEMAND, reconstruite depuis la ROM.

Un id easy_chat vaut (EC_GROUP_X << 9) | rang (EC_MASK_BITS = 9). Le rang est
l'index du mot dans la liste de son groupe (ordre du SOURCE, identique dans
toutes les langues) ; le texte, lui, depend de la langue. On recolle donc :

  * groupes de texte (trainer, status, ... trendy_saying) : les mots sont
    EMPILES dans l'ordre des enregistrements -> on trie les placements du
    mapping (ec_edits_DE.json / mapping_de_verifie.json) par offset, l'index
    donne le rang ;
  * groupes de valeurs (pokemon, pokemon2, move_1, move_2) : le rang renvoie a
    un SPECIES_/MOVE_ du source, dont le nom allemand est dans
    species_names.h / move_names.h (eux aussi dans le mapping).

Resultat : $LOC_WORK/ec_words_de.pkl (dict (group, rank) -> texte).
Sert a DECODER un identifiant lu en ROM et donc a verifier un placement de
tableau u16 (cf. lilycove_lady.h : le bloc allemand relit la question du QUIZ).

Usage : python3 ec_words.py [--show GROUPE RANG ...]
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

import gzip, json, pickle, re, sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

SRC = Path(f"{REF_TREE}")
WORK = Path(f"{WORK}")

man = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
de = C.ROMS['DE'].read_bytes()
CM = C._CM

TEXT_GROUPS = {1: 'trainer', 2: 'status', 3: 'battle', 4: 'greetings', 5: 'people', 6: 'voices',
               7: 'speech', 8: 'endings', 9: 'feelings', 10: 'conditions', 11: 'actions',
               12: 'lifestyle', 13: 'hobbies', 14: 'time', 15: 'misc', 16: 'adjectives',
               17: 'events', 20: 'trendy_saying'}


def word_at(off):
    z = de.find(b'\xff', off, off + 200)
    return CM.decode(de[off:z])


def placed_names(rel):
    return [word_at(o) for _, o in sorted(cur.get(rel, []))]


def defines(path, prefix):
    out = {}
    for line in (SRC / path).read_text().splitlines():
        m = re.match(r'#define %s(\w+)\s+(\d+)' % prefix, line.strip())
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def build():
    words = {}
    for g, name in TEXT_GROUPS.items():
        for rank, text in enumerate(placed_names('src/data/easy_chat/easy_chat_group_%s.h' % name)):
            words[(g, rank)] = text
    sp = placed_names('src/data/text/species_names.h')
    mv = placed_names('src/data/text/move_names.h')
    SP = defines('include/constants/species.h', 'SPECIES_')
    MV = defines('include/constants/moves.h', 'MOVE_')

    def fill(group, rel, kind, table, consts):
        toks = re.findall(r'%s_(\w+)' % kind, (SRC / rel).read_text())
        for rank, tok in enumerate(toks):
            idx = consts.get(tok)
            if idx is not None and idx < len(table):
                words[(group, rank)] = table[idx]

    fill(0, 'src/data/easy_chat/easy_chat_group_pokemon.h', 'SPECIES', sp, SP)
    fill(18, 'src/data/easy_chat/easy_chat_group_move_1.h', 'MOVE', mv, MV)
    fill(19, 'src/data/easy_chat/easy_chat_group_move_2.h', 'MOVE', mv, MV)
    fill(21, 'src/data/easy_chat/easy_chat_group_pokemon2.h', 'SPECIES', sp, SP)
    return words


def decode(off, n, words):
    import struct
    v = struct.unpack_from('<%dH' % n, de, off)
    return ' | '.join(words.get((x >> 9, x & 511), '?%d' % x) if x != 0xFFFF else '/'
                      for x in v)


if __name__ == '__main__':
    words = build()
    pickle.dump(words, open(WORK / 'ec_words_de.pkl', 'wb'))
    print('table : %d mots -> ec_words_de.pkl' % len(words))
    if len(sys.argv) > 3 and sys.argv[1] == '--show':
        print(decode(int(sys.argv[2]), int(sys.argv[3]), words))
