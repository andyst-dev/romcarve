#!/usr/bin/env python3
"""merge_gap.py - integre les editions recuperees par `gap_fill.py` (trous
encadres par un voisin place : tetes de pool, queues, trous du milieu).

La liste ACCEPT est lue une par une : chaque entree a ete comparee au texte
italien de la meme edition (un candidat dont le texte allemand parle d'autre
chose est REJETE, meme s'il est parfaitement lisible). Les corrections de
1-2 octets correspondent aux codes de controle de tete :
  * un texte qui commence par un glyphe de controle cote italien (ex. «ワ»)
    doit le garder cote allemand ;
  * un placeholder ({FD}Â) doit rester dans l'offset.

Usage : python3 merge_gap.py [--emit]
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

import json, sys
from pathlib import Path

WORK = Path(f"{WORK}")
cur = json.loads((WORK / 'mapping_de_verifie.json').read_text())

M = 'data/maps/'
ACCEPT = [
    (M + 'FallarborTown_CozmosHouse/scripts.inc', 0, 2112074),
    (M + 'EverGrandeCity_GlaciasRoom/scripts.inc', 0, 2288593),
    (M + 'FortreeCity_PokemonCenter_1F/scripts.inc', 0, 2212292),
    (M + 'PacifidlogTown_House4/scripts.inc', 0, 2125034),
    (M + 'SSTidalCorridor/scripts.inc', 0, 2377833),
    (M + 'AquaHideout_1F/scripts.inc', 0, 2338594),
    (M + 'BattleFrontier_Lounge8/scripts.inc', 0, 2564803),
    (M + 'BattleFrontier_PokemonCenter_1F/scripts.inc', 0, 2565554),
    (M + 'EverGrandeCity_DrakesRoom/scripts.inc', 0, 2289336),
    (M + 'EverGrandeCity_PokemonCenter_1F/scripts.inc', 0, 2294557),
    (M + 'EverGrandeCity_SidneysRoom/scripts.inc', 0, 2287214),
    (M + 'FortreeCity_House2/scripts.inc', 0, 2213599),
    (M + 'LilycoveCity_DepartmentStore_3F/scripts.inc', 0, 2250691),
    (M + 'LilycoveCity_PokemonCenter_1F/scripts.inc', 0, 2235675),
    (M + 'LittlerootTown/scripts.inc', 5, 2004587),
    (M + 'MauvilleCity_House1/scripts.inc', 0, 2177226),
    (M + 'MauvilleCity_Mart/scripts.inc', 0, 2183916),
    (M + 'MossdeepCity_House3/scripts.inc', 0, 2262390),
    (M + 'MossdeepCity_Mart/scripts.inc', 0, 2261819),
    (M + 'PetalburgCity_Mart/scripts.inc', 0, 2142643),
    (M + 'Route116_TunnelersRestHouse/scripts.inc', 0, 2302725),
    (M + 'Route118/scripts.inc', 0, 2054824),
    (M + 'Route120/scripts.inc', 0, 2061544),
    (M + 'RustboroCity_CuttersHouse/scripts.inc', 0, 2205447),
    (M + 'RustboroCity_House3/scripts.inc', 0, 2207062),
    (M + 'SootopolisCity_House3/scripts.inc', 0, 2281625),
    (M + 'SootopolisCity_Mart/scripts.inc', 0, 2280637),
    (M + 'SootopolisCity_PokemonCenter_1F/scripts.inc', 0, 2279825),
    (M + 'VerdanturfTown/scripts.inc', 0, 2016809),
    (M + 'VerdanturfTown_BattleTentLobby/scripts.inc', 0, 2115338),
    (M + 'VerdanturfTown_Mart/scripts.inc', 0, 2118049),
    (M + 'VerdanturfTown_PokemonCenter_1F/scripts.inc', 0, 2118455),
    (M + 'VictoryRoad_1F/scripts.inc', 0, 2350442),
    ('data/scripts/secret_power_tm.inc', 0, 2629418),
    ('data/text/pc_transfer.inc', 0, 2615902),          # -2 : garde le {FD}Â
    ('src/battle_message.c', 473, 6152389),
    (M + 'BattleFrontier_BattleFactoryBattleRoom/scripts.inc', 0, 2511453),
    (M + 'FallarborTown_Mart/scripts.inc', 0, 2107017),
    (M + 'LilycoveCity_DepartmentStore_5F/scripts.inc', 0, 2251813),
    (M + 'LittlerootTown/scripts.inc', 0, 2003676),
    (M + 'LittlerootTown_BrendansHouse_2F/scripts.inc', 0, 2073909),
    (M + 'MauvilleCity_PokemonCenter_1F/scripts.inc', 0, 2183098),
    (M + 'MtPyre_1F/scripts.inc', 0, 2327750),
    (M + 'MtPyre_5F/scripts.inc', 0, 2331646),
    (M + 'MtPyre_5F/scripts.inc', 2, 2331775),
    (M + 'NewMauville_Inside/scripts.inc', 2, 2357683),
    (M + 'PacifidlogTown/scripts.inc', 0, 2018241),
    (M + 'Route104_MrBrineysHouse/scripts.inc', 0, 2295467),
    (M + 'Route110_TrickHouseEnd/scripts.inc', 0, 2580432),
    (M + 'Route110_TrickHouseEnd/scripts.inc', 12, 2582329),
    (M + 'Route110_TrickHousePuzzle1/scripts.inc', 0, 2583164),
    (M + 'Route110_TrickHousePuzzle2/scripts.inc', 0, 2584077),
    (M + 'Route110_TrickHousePuzzle3/scripts.inc', 0, 2586528),
    (M + 'Route110_TrickHousePuzzle4/scripts.inc', 0, 2587367),
    (M + 'Route111/scripts.inc', 29, 2045360),          # -1 : garde le glyphe «ワ»
    (M + 'Route114_FossilManiacsTunnel/scripts.inc', 0, 2300207),
    (M + 'SeafloorCavern_Room3/scripts.inc', 0, 2344546),
    (M + 'SkyPillar_Outside/scripts.inc', 1, 2365043),
    (M + 'SootopolisCity_House2/scripts.inc', 0, 2281347),
    (M + 'SootopolisCity_House4/scripts.inc', 0, 2282094),
    ('data/text/abnormal_weather.inc', 1, 2617083),
    ('data/text/surf.inc', 1, 2615278),
    ('src/berry_fix_program.c', 0, 6460224),
    ('src/data/text/ribbon_descriptions.h', 0, 6506724),
    # 2e passe (apres retrait des 3 faux) :
    ('src/battle_message.c', 474, 6152430),             # 'A former CHAMPION!' (non traduit)
    (M + 'DewfordTown_House2/scripts.inc', 0, 2099612),
    (M + 'MossdeepCity_House1/scripts.inc', 1, 2260670),
    (M + 'SkyPillar_Outside/scripts.inc', 0, 2365027),
    # battle_message.c : la famille des libelles COURONNE et du message d'evolution,
    # alignee par continuite dans le pool (le ve voisin est exact a chaque fois).
    ('src/battle_message.c', 422, 6151328),
    ('src/battle_message.c', 475, 6152450),
    ('src/battle_message.c', 476, 6152474),
    ('src/battle_message.c', 477, 6152498),
    ('src/battle_message.c', 478, 6152501),
    ('src/battle_message.c', 479, 6152505),
    ('src/battle_message.c', 480, 6152508),
    # 3e passe : candidats trouves par CONTENU (content_find.py : jetons invariants du
    # texte italien - noms propres, POKéMON, objets - encodes avec le charmap, puis
    # relus un a un).
    (M + 'Route114_LanettesHouse/scripts.inc', 0, 2301185),
    (M + 'Route114_LanettesHouse/scripts.inc', 1, 2301384),
    (M + 'Route119_House/scripts.inc', 1, 2605321),
    (M + 'SeafloorCavern_Entrance/scripts.inc', 0, 2343297),
    (M + 'SeafloorCavern_Entrance/scripts.inc', 1, 2343740),
    (M + 'SkyPillar_Top/scripts.inc', 0, 2366198),
    (M + 'SlateportCity_Mart/scripts.inc', 1, 2169231),
    (M + 'LilycoveCity_House1/scripts.inc', 1, 2246405),
    (M + 'PetalburgCity_House2/scripts.inc', 0, 2141309),
    (M + 'Route105/scripts.inc', 0, 2029441),
    (M + 'Route105/scripts.inc', 1, 2029785),
    # 4e passe : fichiers SANS ancre, retrouves par l'intervalle allemand encadrant
    # (les voisins du fichier dans l'ordre italien donnent la fenetre, puis lecture).
    (M + 'OldaleTown_House1/scripts.inc', 0, 2089490),
    (M + 'OldaleTown_House2/scripts.inc', 0, 2089733),
    (M + 'OldaleTown_House2/scripts.inc', 1, 2089824),
    (M + 'LavaridgeTown_House/scripts.inc', 0, 2105914),
    (M + 'LavaridgeTown_House/scripts.inc', 1, 2106067),
    (M + 'LavaridgeTown_Mart/scripts.inc', 0, 2106148),
    (M + 'LavaridgeTown_Mart/scripts.inc', 1, 2106284),
    (M + 'AbandonedShip_Rooms_B1F/scripts.inc', 0, 2359654),
    (M + 'AbandonedShip_Rooms2_B1F/scripts.inc', 0, 2359753),
    (M + 'InsideOfTruck/scripts.inc', 0, 2377036),
    # 5e passe (meme methode d'intervalle) :
    (M + 'EverGrandeCity_HallOfFame/scripts.inc', 0, 2294081),
    (M + 'EverGrandeCity_HallOfFame/scripts.inc', 1, 2294241),
    (M + 'DewfordTown_PokemonCenter_1F/scripts.inc', 0, 2091384),
    (M + 'DewfordTown_PokemonCenter_1F/scripts.inc', 1, 2091483),
    (M + 'FortreeCity_House3/scripts.inc', 0, 2214357),
    (M + 'FortreeCity_House3/scripts.inc', 1, 2214677),
    (M + 'MossdeepCity_PokemonCenter_2F/scripts.inc', 0, 2261632),
    # 6e passe :
    (M + 'MossdeepCity_PokemonCenter_1F/scripts.inc', 0, 2261332),
    (M + 'MossdeepCity_PokemonCenter_1F/scripts.inc', 1, 2261455),
    (M + 'GraniteCave_1F/scripts.inc', 0, 2312355),
    (M + 'GraniteCave_1F/scripts.inc', 1, 2312676),
    (M + 'FortreeCity_DecorationShop/scripts.inc', 0, 2215884),
    (M + 'FortreeCity_DecorationShop/scripts.inc', 1, 2216038),
    (M + 'PetalburgCity_House1/scripts.inc', 0, 2140921),
    (M + 'PetalburgCity_House1/scripts.inc', 1, 2141017),
    # 7e passe :
    (M + 'LilycoveCity_House2/scripts.inc', 0, 2246488),
    (M + 'LilycoveCity_House2/scripts.inc', 1, 2246561),
    (M + 'LilycoveCity_House4/scripts.inc', 0, 2248809),
    (M + 'LilycoveCity_House4/scripts.inc', 1, 2248917),
    (M + 'RustboroCity_Flat2_1F/scripts.inc', 0, 2206432),
    (M + 'RustboroCity_Flat2_1F/scripts.inc', 1, 2206493),
    (M + 'RustboroCity_Flat2_3F/scripts.inc', 0, 2206888),
    (M + 'RustboroCity_Flat2_3F/scripts.inc', 1, 2206959),
    (M + 'SlateportCity_House/scripts.inc', 0, 2168277),
    (M + 'SlateportCity_House/scripts.inc', 1, 2168456),
    (M + 'SlateportCity_PokemonCenter_1F/scripts.inc', 0, 2168614),
    (M + 'SlateportCity_PokemonCenter_1F/scripts.inc', 1, 2168887),
    (M + 'SootopolisCity_House5/scripts.inc', 0, 2282445),
    (M + 'SootopolisCity_House5/scripts.inc', 1, 2282610),
    (M + 'MauvilleCity_PokemonCenter_2F/scripts.inc', 0, 2183630),
    # 8e passe (recherche par contenu) :
    (M + 'SootopolisCity_House7/scripts.inc', 0, 2283101),
    (M + 'ShoalCave_LowTideLowerRoom/scripts.inc', 1, 2355949),   # debut du texte, pas le mot
    (M + 'Route124/scripts.inc', 0, 2065272),
    # 9e passe : les 19 tables BARD (src/data/bard_music/*.h). Bloc allemand trouve par
    # STRUCTURE : blocs de 8 octets dont les 7 derniers sont nuls, valeur <= 0x40 ou 0xFF
    # (NULL_BARD_SOUND). Le bloc 6338208..6403632 = exactement la somme des tailles
    # italiennes a partir de moves.h ; pokemon.h est juste avant (6318428, decale de 4),
    # conditions.h (hors manifeste, 3312 o) occupe le trou entre feelings et actions -
    # l'ordre est confirme par les #include de src/bard_music.c.
    ('src/data/bard_music/pokemon.h', 0, 6318428),
    ('src/data/bard_music/moves.h', 0, 6338208),
    ('src/data/bard_music/trainer.h', 0, 6355248),
    ('src/data/bard_music/status.h', 0, 6356544),
    ('src/data/bard_music/battle.h', 0, 6361776),
    ('src/data/bard_music/greetings.h', 0, 6364800),
    ('src/data/bard_music/people.h', 0, 6366816),
    ('src/data/bard_music/voices.h', 0, 6370416),
    ('src/data/bard_music/speech.h', 0, 6373440),
    ('src/data/bard_music/endings.h', 0, 6376320),
    ('src/data/bard_music/feelings.h', 0, 6379632),
    ('src/data/bard_music/actions.h', 0, 6386256),
    ('src/data/bard_music/lifestyle.h', 0, 6390000),
    ('src/data/bard_music/hobbies.h', 0, 6392160),
    ('src/data/bard_music/time.h', 0, 6394752),
    ('src/data/bard_music/misc.h', 0, 6396912),
    ('src/data/bard_music/adjectives.h', 0, 6398928),
    ('src/data/bard_music/events.h', 0, 6400656),
    ('src/data/bard_music/trendysaying.h', 0, 6402048),
]

before = sum(len(v) for v in cur.values())
# Faux constates en relisant les paquets d'offsets partages restants (applique
# AVANT les ajouts, sinon on effacerait un placement qu'on vient de poser) :
#  - event_scripts.s [15] pointe sur le texte de SURF (surf.inc [1] est le bon) ;
#  - MossdeepCity_House1 [1] et DewfordTown_House2 [0] pointaient sur le texte de
#    leur VOISIN d'index (l'allemand relu y est celui de [0] / de [1]).
FAUX = [('data/event_scripts.s', 15),
        (M + 'MossdeepCity_House1/scripts.inc', 1),
        (M + 'DewfordTown_House2/scripts.inc', 0)]
for f, i in FAUX:
    if f in cur:
        cur[f] = [[a, b] for a, b in cur[f] if a != i]
        if not cur[f]:
            del cur[f]
        print('retire (faux) : %s [%d]' % (f, i))
for rel, i, o in ACCEPT:
    have = dict(cur.get(rel, []))
    if i in have:
        print('deja place : %s [%d]' % (rel, i))
        continue
    have[i] = o
    cur[rel] = sorted([a, b] for a, b in have.items())
after = sum(len(v) for v in cur.values())
print('%d editions acceptees (avant %d, apres %d, %d fichiers)'
      % (len(ACCEPT), before, after, len(cur)))
# Corrections d'offsets FAUX constates en relisant battle_message.c : ses [481..509]
# pointaient tous dans le pool des « -Att. » / des libelles de couronne, alors que
# leur vrai texte allemand est plus loin (relu un par un, dans l'ordre).
CORR = [
    ('src/battle_message.c', 481, 6152517),          # 'Abilità' -> Geschick
    ('src/battle_message.c', 482, 6152526),          # 'Corpo'   -> Körper
    ('src/battle_message.c', 483, 6152533),          # 'Voto'    -> Bewertung
    ('src/battle_message.c', 484, 6152553),
    ('src/battle_message.c', 485, 6152637),
    ('src/battle_message.c', 486, 6152679),
    ('src/battle_message.c', 487, 6152713),
    ('src/battle_message.c', 488, 6152764),
    ('src/battle_message.c', 489, 6152795),
    ('src/battle_message.c', 490, 6152798),
    ('src/battle_message.c', 491, 6152835),
    ('src/battle_message.c', 492, 6152861),
    ('src/battle_message.c', 493, 6152889),
    ('src/battle_message.c', 494, 6152911),
    ('src/battle_message.c', 495, 6152938),
    ('src/battle_message.c', 496, 6153008),
    ('src/battle_message.c', 497, 6153064),
    ('src/battle_message.c', 498, 6153129),
    ('src/battle_message.c', 499, 6153199),
    ('src/battle_message.c', 500, 6153262),
    ('src/battle_message.c', 501, 6153317),
    ('src/battle_message.c', 502, 6153372),
    ('src/battle_message.c', 503, 6153420),
    ('src/battle_message.c', 504, 6153465),
    ('src/battle_message.c', 505, 6153513),
    ('src/battle_message.c', 506, 6153562),
    ('src/battle_message.c', 507, 6153648),
    ('src/battle_message.c', 508, 6153686),
    ('src/battle_message.c', 509, 6153709),
    ('src/battle_message.c', 510, 6153712),
    ('src/battle_message.c', 511, 6153715),
    ('src/battle_message.c', 512, 6153731),
    ('src/battle_message.c', 513, 6153759),
    ('src/battle_message.c', 514, 6153792),
    ('src/battle_message.c', 515, 6153856),
    ('src/battle_message.c', 516, 6153919),
    ('src/battle_message.c', 517, 6153951),
]
for rel, i, o in CORR:
    have = dict(cur.get(rel, []))
    if i in have:
        have[i] = o
        cur[rel] = sorted([a, b] for a, b in have.items())
print('%d offsets corriges' % len(CORR))
if '--emit' in sys.argv:
    import shutil
    shutil.copy(WORK / 'mapping_de_verifie.json', WORK / 'mapping_de_verifie.json.bak-gap')
    (WORK / 'mapping_de_verifie.json').write_text(json.dumps(cur))
    print('ecrit (sauvegarde .bak-gap)')
