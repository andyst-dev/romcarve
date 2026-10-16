#!/usr/bin/env python3
"""dup_fix.py - retirer du mapping les entrees FAUSSES du controle de doublon.

Pour chaque paquet de dup_audit.py (une paire/trio de fichiers + une suite contigue
d'offsets partages avec des textes IT differents), le proprietaire allemand du pool a ete
determine PAR LECTURE (le texte allemand est la traduction du texte IT d'UN seul des
candidats). Toutes les autres entrees du paquet sont fausses : elles feraient patcher la
mauvaise zone de la ROM.

OWNERS : cle = tuple trie des fichiers du paquet, valeur = fichier(s) proprietaire(s).
  - un seul fichier : lui gagne, tous les autres perdent ;
  - ('__SAME__', fichier) : collision INTERNE a un fichier -> INDEX_WINNERS tranche ;
  - None : ambigu, on garde tel quel (a trancher plus tard).

Usage : dup_fix.py [--emit]
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

import collections, gzip, json, shutil, sys
from pathlib import Path

sys.path.insert(0, f"{WORK}")
import carve7 as C  # noqa: E402

WORK = Path(f"{WORK}")
M = 'data/maps/'
OWNERS = {
    (M + 'LavaridgeTown_Gym_1F/scripts.inc', M + 'Route110/scripts.inc'): M + 'LavaridgeTown_Gym_1F/scripts.inc',
    (M + 'BattleFrontier_Lounge1/scripts.inc', 'data/scripts/berry_blender.inc'): M + 'BattleFrontier_Lounge1/scripts.inc',
    (M + 'BattleFrontier_ExchangeServiceCorner/scripts.inc', M + 'Route110_TrickHousePuzzle7/scripts.inc', 'data/scripts/day_care.inc'): M + 'BattleFrontier_ExchangeServiceCorner/scripts.inc',
    (M + 'BattleFrontier_ExchangeServiceCorner/scripts.inc', 'data/scripts/day_care.inc'): M + 'BattleFrontier_ExchangeServiceCorner/scripts.inc',
    (M + 'BattleFrontier_ExchangeServiceCorner/scripts.inc', M + 'Route110_TrickHousePuzzle7/scripts.inc'): M + 'BattleFrontier_ExchangeServiceCorner/scripts.inc',
    (M + 'SSTidalCorridor/scripts.inc', M + 'SSTidalRooms/scripts.inc'): M + 'SSTidalRooms/scripts.inc',
    (M + 'VictoryRoad_1F/scripts.inc', M + 'VictoryRoad_B1F/scripts.inc'): M + 'VictoryRoad_B1F/scripts.inc',
    (M + 'VictoryRoad_1F/scripts.inc', M + 'VictoryRoad_B2F/scripts.inc'): M + 'VictoryRoad_B2F/scripts.inc',
    (M + 'SootopolisCity_Gym_1F/scripts.inc', M + 'SootopolisCity_Gym_B1F/scripts.inc'): M + 'SootopolisCity_Gym_B1F/scripts.inc',
    (M + 'SootopolisCity_LotadAndSeedotHouse/scripts.inc', M + 'SootopolisCity_MysteryEventsHouse_1F/scripts.inc'): M + 'SootopolisCity_MysteryEventsHouse_1F/scripts.inc',
    (M + 'AquaHideout_B2F/scripts.inc', M + 'MtPyre_Summit/scripts.inc'): M + 'MtPyre_Summit/scripts.inc',
    ('data/scripts/mauville_man.inc', 'data/text/pokemon_news.inc'): 'data/scripts/mauville_man.inc',
    (M + 'Route119/scripts.inc', M + 'Route120/scripts.inc'): M + 'Route119/scripts.inc',
    (M + 'BattleFrontier_BattleFactoryBattleRoom/scripts.inc', M + 'BattleFrontier_BattlePikeLobby/scripts.inc'): M + 'BattleFrontier_BattlePikeLobby/scripts.inc',
    (M + 'LittlerootTown/scripts.inc', M + 'OldaleTown/scripts.inc'): M + 'OldaleTown/scripts.inc',
    (M + 'Route110_TrickHouseEnd/scripts.inc', M + 'Route110_TrickHouseEntrance/scripts.inc', M + 'Route110_TrickHousePuzzle1/scripts.inc', M + 'Route110_TrickHousePuzzle2/scripts.inc', M + 'Route110_TrickHousePuzzle3/scripts.inc'): M + 'Route110_TrickHouseEntrance/scripts.inc',
    (M + 'Route110_TrickHouseEnd/scripts.inc', M + 'Route110_TrickHouseEntrance/scripts.inc'): M + 'Route110_TrickHouseEntrance/scripts.inc',
    (M + 'Route110_TrickHouseEnd/scripts.inc', M + 'Route110_TrickHouseEntrance/scripts.inc', M + 'Route110_TrickHousePuzzle4/scripts.inc'): M + 'Route110_TrickHouseEntrance/scripts.inc',
    (M + 'Route110_TrickHouseEntrance/scripts.inc', M + 'Route110_TrickHousePuzzle4/scripts.inc'): M + 'Route110_TrickHouseEntrance/scripts.inc',
    (M + 'BattleFrontier_BattlePikeRoomNormal/scripts.inc', 'data/scripts/berry_blender.inc'): M + 'BattleFrontier_BattlePikeRoomNormal/scripts.inc',
    (M + 'Route116/scripts.inc', M + 'Route118/scripts.inc'): M + 'Route116/scripts.inc',
    (M + 'FallarborTown_CozmosHouse/scripts.inc', M + 'FallarborTown_MoveRelearnersHouse/scripts.inc'): M + 'FallarborTown_MoveRelearnersHouse/scripts.inc',
    (M + 'FortreeCity_Gym/scripts.inc', M + 'FortreeCity_House2/scripts.inc'): M + 'FortreeCity_Gym/scripts.inc',
    (M + 'BattleFrontier_RankingHall/scripts.inc', 'data/scripts/berry_blender.inc'): M + 'BattleFrontier_RankingHall/scripts.inc',
    (M + 'LilycoveCity_DepartmentStore_1F/scripts.inc', M + 'LilycoveCity_MoveDeletersHouse/scripts.inc'): M + 'LilycoveCity_MoveDeletersHouse/scripts.inc',
    (M + 'MossdeepCity_GameCorner_1F/scripts.inc', M + 'SootopolisCity_Gym_B1F/scripts.inc'): M + 'SootopolisCity_Gym_B1F/scripts.inc',
    (M + 'MossdeepCity_GameCorner_1F/scripts.inc', M + 'SootopolisCity_Gym_1F/scripts.inc', M + 'SootopolisCity_Gym_B1F/scripts.inc'): M + 'SootopolisCity_Gym_B1F/scripts.inc',
    (M + 'DewfordTown_Hall/scripts.inc', M + 'Route110/scripts.inc'): M + 'DewfordTown_Hall/scripts.inc',
    (M + 'FortreeCity_House1/scripts.inc', M + 'RustboroCity_House1/scripts.inc'): M + 'RustboroCity_House1/scripts.inc',
    (M + 'PacifidlogTown_House2/scripts.inc', M + 'PacifidlogTown_House4/scripts.inc'): M + 'PacifidlogTown_House4/scripts.inc',
    (M + 'EverGrandeCity_ChampionsRoom/scripts.inc', M + 'Route111_OldLadysRestStop/scripts.inc'): M + 'Route111_OldLadysRestStop/scripts.inc',
    (M + 'AquaHideout_B1F/scripts.inc', M + 'MtPyre_3F/scripts.inc'): M + 'MtPyre_3F/scripts.inc',
    (M + 'AquaHideout_B1F/scripts.inc', M + 'MtPyre_4F/scripts.inc'): M + 'MtPyre_4F/scripts.inc',
    (M + 'AquaHideout_B1F/scripts.inc', M + 'MtPyre_5F/scripts.inc'): M + 'MtPyre_5F/scripts.inc',
    (M + 'AquaHideout_B1F/scripts.inc', M + 'MtPyre_6F/scripts.inc'): M + 'MtPyre_6F/scripts.inc',
    (M + 'DewfordTown_House2/scripts.inc', M + 'Route110/scripts.inc'): M + 'DewfordTown_House2/scripts.inc',
    (M + 'LavaridgeTown_HerbShop/scripts.inc', M + 'Route110/scripts.inc'): M + 'LavaridgeTown_HerbShop/scripts.inc',
    (M + 'PacifidlogTown/scripts.inc', M + 'Route102/scripts.inc'): M + 'PacifidlogTown/scripts.inc',
    (M + 'EverGrandeCity_ChampionsRoom/scripts.inc', M + 'MtChimney_CableCarStation/scripts.inc', M + 'Route112_CableCarStation/scripts.inc'): (M + 'MtChimney_CableCarStation/scripts.inc', M + 'Route112_CableCarStation/scripts.inc'),
    (M + 'Route114_LanettesHouse/scripts.inc', M + 'Route116_TunnelersRestHouse/scripts.inc'): M + 'Route116_TunnelersRestHouse/scripts.inc',
    (M + 'MauvilleCity_GameCorner/scripts.inc', M + 'MauvilleCity_House2/scripts.inc'): M + 'MauvilleCity_House2/scripts.inc',
    (M + 'AbandonedShip_Corridors_B1F/scripts.inc', M + 'AbandonedShip_Rooms_1F/scripts.inc'): M + 'AbandonedShip_Corridors_B1F/scripts.inc',
    (M + 'BattleFrontier_Lounge3/scripts.inc', M + 'BattleFrontier_Lounge4/scripts.inc'): M + 'BattleFrontier_Lounge4/scripts.inc',
    ('data/event_scripts.s', 'data/text/surf.inc'): 'data/text/surf.inc',
    ('data/text/pc_transfer.inc', 'data/text/questionnaire.inc'): 'data/text/questionnaire.inc',
    ('data/text/mauville_man.inc', 'data/text/trainers.inc'): 'data/text/trainers.inc',
    ('data/text/braille.inc', 'data/text/event_ticket_1.inc'): 'data/text/event_ticket_1.inc',
    ('src/battle_message.c', 'src/data/text/match_call_messages.h'): 'src/data/text/match_call_messages.h',
    # ambigu : on garde (le texte allemand ne tranche pas)
    (M + 'PacifidlogTown_House2/scripts.inc', M + 'VerdanturfTown_FriendshipRatersHouse/scripts.inc'): None,
}
INDEX_WINNERS = {}
# corrections : la bonne position est le DEBUT de l'objet allemand, pas un sous-offset.
# Mesure : strings.c [1414..1416] = '1º','2º','3º' sont bien 3 objets allemands distincts
# a 6289387 / 6289391 / 6289395 ; MossdeepCity_House1 [0] et [1] sont FUSIONNES en un seul
# objet allemand a 2260656 (cas accepte : un objet DE peut couvrir deux editions IT).
CORRECTIONS = {
    ('src/strings.c', 1414): 6289387, ('src/strings.c', 1415): 6289391, ('src/strings.c', 1416): 6289395,
    ('data/maps/MossdeepCity_House1/scripts.inc', 0): 2260656,
    ('data/maps/MossdeepCity_House1/scripts.inc', 1): 2260656,
}
INDEX_FALSE = {('src/battle_message.c', 6151902): [465, 466], ('src/battle_message.c', 6152007): [473, 477],
               ('src/battle_message.c', 6152032): [474, 478], ('src/battle_message.c', 6152051): [475, 479],
               ('src/battle_message.c', 6152073): [476, 480]}
# faux verifies HORS collision (le fichier etait absent du mapping, donc aucune collision ne
# pouvait le signaler) : PacifidlogTown_House3 [1..5] pointaient sur les textes de la maison de
# TIM/HEIKO a CLERMONT. Leur texte IT (echange de BAGON) n'a rien a voir avec l'allemand lu la-bas.
EXPLICIT_FALSE = [(M + 'PacifidlogTown_House3/scripts.inc', i) for i in (1, 2, 3, 4, 5)]
# meme cas, revele par le REMPLISSAGE : Route110_TrickHousePuzzle6 [1..9] occupaient les
# offsets 2587490.. du pool que Puzzle4 revendique et qui est bien le sien par lecture
# ("Ich habe keine Zeit, das zu verstehen. Ich will nur kämpfen!" <-> "Troppa fatica
# risolvere questo rompicapo. Voglio solo lottare!"). Aucune collision ne le signalait, car
# Puzzle4 n'avait alors aucun offset a cet endroit.
EXPLICIT_FALSE += [(M + 'Route110_TrickHousePuzzle6/scripts.inc', i) for i in range(1, 10)]
# placements verifies a la main dans cette session (edition [0] recuperee par lecture du prefixe
# de codes de controle devant l'ancre droite) : 19 editions.
ADDITIONS = {
    M + 'PetalburgCity_WallysHouse/scripts.inc': [[0, 2125944], [1, 2126288], [2, 2126331], [3, 2126857],
                                                  [4, 2126930], [5, 2126997], [6, 2127187], [7, 2127339]],
    M + 'PetalburgCity_PokemonCenter_1F/scripts.inc': [[0, 2141679], [1, 2141791], [2, 2141856],
                                                      [3, 2142020], [4, 2142171], [5, 2142320]],
    M + 'SootopolisCity_House6/scripts.inc': [[0, 2282752], [1, 2282898], [2, 2282920], [3, 2282998],
                                              [4, 2283054]],
}

man = json.load(gzip.open(f"{REF_DIR}/italian.json.gz"))['files']
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())
it = C.ROMS['IT'].read_bytes()
de_rom = C.ROMS['DE'].read_bytes()
CM = C._CM
ied = {f: sorted(v['edits']) for f, v in man.items()}


def itxt(f, i):
    e = ied[f][i]
    return CM.decode(it[e[2]:e[2] + e[3] - 1])


off2ent = collections.defaultdict(list)
for f, rows in cur.items():
    for i, o in rows:
        off2ent[o].append((f, i))

false = []
for o, v in sorted(off2ent.items()):
    if len(v) < 2 or len({itxt(f, i) for f, i in v}) < 2:
        continue
    files = tuple(sorted({f for f, i in v}))
    if len(files) == 1:
        if (files[0], o) in INDEX_FALSE:
            false += [(files[0], i) for i in INDEX_FALSE[(files[0], o)]]
        else:
            win = INDEX_WINNERS.get((files[0], o))
            if win is None:
                continue
            false += [(f, i) for f, i in v if i != win]
        continue
    if files in OWNERS:
        own = OWNERS[files]
        if own is None:
            continue
        owns = (own,) if isinstance(own, str) else tuple(own)
        false += [(f, i) for f, i in v if f not in owns]
    else:
        print('!! paquet sans decision : %s @%d' % (files, o))

names = {f: 0 for f, _ in false}
false = sorted(set(false) | set(EXPLICIT_FALSE))
for f, _ in false:
    names[f] = names.get(f, 0) + 1
print('%d entrees fausses dans %d fichiers :' % (len(false), len(names)))
for f, n in sorted(names.items(), key=lambda kv: -kv[1]):
    print('   %-62s %d' % (f, n))
(WORK / 'dup_false.json').write_text(json.dumps(sorted(set(false)), indent=1))
if '--emit' in sys.argv:
    before = sum(len(v) for v in cur.values())
    shutil.copy(WORK / 'mapping_de_verifie.json', WORK / 'mapping_de_verifie.json.bak-dup')
    for f, i in sorted(set(false)):
        if f not in cur:
            continue
        cur[f] = [[a, b] for a, b in cur[f] if a != i]
        if not cur[f]:
            del cur[f]
    for (f, i), o in sorted(CORRECTIONS.items()):
        if not (0 < o < len(de_rom)):
            print('!! correction hors ROM %s [%d] @%d' % (f, i, o))
            continue
        cur[f] = [[a, (o if a == i else b)] for a, b in cur[f]]
    nadd = 0
    for f, rows in sorted(ADDITIONS.items()):
        have = dict(cur.get(f, []))
        for i, o in sorted(rows):
            if not (0 < o < len(de_rom)):
                print('!! ajout hors ROM %s [%d] @%d' % (f, i, o))
                continue
            have[i] = o
            nadd += 1
        cur[f] = sorted([i, o] for i, o in have.items())
    (WORK / 'mapping_de_verifie.json').write_text(json.dumps(cur))
    tot = sum(len(v) for v in cur.values())
    print('%d corrections appliquees, %d editions ajoutees' % (len(CORRECTIONS), nadd))
    print('mapping : %d -> %d editions dans %d fichiers (sauvegarde .bak-dup)'
          % (before, tot, len(cur)))
