#!/usr/bin/env python3
"""carve3.py - recuperer les offsets d'une langue cible sans son manifeste (v3).

Deux idees qui debloquent tout :

1. SQUELETTE ETENDU. Un objet candidat ne commence pas forcement juste apres un 0xFF :
   les tableaux a pas fixe remplissent avec des ZEROS (especes : 11 octets, capacites : 13,
   dresseurs : 40...). Donc : apres un 0xFF, on saute les zeros et on prend la premiere
   position non nulle. C'est ce qui fait apparaitre les champs texte des tableaux.

2. MAPPING PAR CONTENANT. Un texte appartient a un "contenant" = l'objet du squelette qui
   le couvre. Comme la mise en page des enregistrements est invariante de langue, le
   decalage du texte DANS son contenant se transporte tel quel :
       offset_cible = debut_contenant_cible + (offset_EN - debut_contenant_EN)

Etage 1 : pour chaque region (suite d'objets contigus cote EN), on cherche dans la ROM
          cible la marche de N objets dont le profil de tailles est correle -> debut.
Etage 2 : les objets isoles/small se placent entre deux ancres resolues.

Modes:
  carve3.py map    <manifeste_ref.json.gz> <CIBLE>
  carve3.py oracle <manifeste_ref.json.gz> <CIBLE> [manifeste_cible.json.gz]
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

import bisect, gzip, json, re, sys, time
from pathlib import Path

TREE = Path(f"{REF_TREE}")
ROMS = {
    'EN': Path(f"{ROMS}/emeraude_en.gba"),
    'FR': Path(f"{ROMS}/emeraude_fr.gba"),
    'IT': Path(f"{WORK}/roms/it_bpei.gba"),
    'DE': Path(f"{ROMS}/Pokemon - Smaragd-Edition (Germany).gba"),
}
LOCALES = Path(f"{REF_DIR}")
WORK = Path(f"{WORK}")
sys.path.insert(0, f"{VFWORK}")
from charmap import Charmap  # noqa: E402

_CM = Charmap(str(TREE / 'charmap.txt'))


def encode(text):
    try:
        return _CM.encode(text)
    except Exception:
        return None


def object_bytes(snippet):
    """(octets complets, prefixe utilisable)."""
    lits = re.findall(r'"((?:[^"\\]|\\.)*)"', snippet)
    if not lits:
        return None, None
    out = bytearray()
    for lit in lits:
        b = encode(lit)
        if b is None:
            for cut in range(len(lit) - 1, 0, -1):
                b = encode(lit[:cut])
                if b is not None:
                    out += b
                    return None, bytes(out) if len(out) >= 6 else None
            return None, bytes(out) if len(out) >= 6 else None
        out += b
    return bytes(out), bytes(out)


# ---------------------------------------------------------------- squelette
class Skeleton:
    """objets candidats : apres un 0xFF, on saute les zeros de remplissage."""

    def __init__(self, data: bytes, maxsize=400):
        self.data = data
        self.maxsize = maxsize
        starts, i = [0], data.find(b'\xff')
        pos = []
        while i >= 0:
            pos.append(i)
            j = i + 1
            while j < len(data) and data[j] == 0x00:
                j += 1
            if j == 0 or not starts or j != starts[-1]:
                starts.append(j)
            i = data.find(b'\xff', i + 1)
        self.ff = pos
        self.starts = starts
        n = len(starts)
        self.sizes = [starts[k + 1] - starts[k] for k in range(n - 1)] + [0]
        # fin "texte" de chaque objet : premier 0xFF a partir du debut
        self.text_end = []
        for k in range(n - 1):
            e = data.find(b'\xff', starts[k])
            self.text_end.append(e - starts[k] + 1 if 0 <= e < starts[k + 1] else 0)
        self.text_end.append(0)
        self.run = [0] * (n + 1)
        for k in range(n - 1, -1, -1):
            self.run[k] = self.run[k + 1] + 1 if 1 <= self.sizes[k] <= maxsize else 0

    def container(self, p):
        """index de l'objet qui contient la position p."""
        k = bisect.bisect_right(self.starts, p) - 1
        return k if k >= 0 else 0


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


# ---------------------------------------------------------------- cote EN
def locate_file(manifest, rel, en_rom, en_sk, cap=60):
    """[(index_edition, offset EN du texte, taille texte EN, container EN)]."""
    text = (TREE / rel).read_text(encoding='utf-8', errors='replace')
    items = []
    for idx, e in enumerate(sorted(manifest['files'][rel]['edits'])):
        start, end, _off, _size, kind = e
        if kind not in ('asm', 'c', 'u8array'):
            continue
        full, pref = object_bytes(text[start:end])
        key = full or pref
        if key:
            items.append((idx, key, _size))
    if not items:
        return []

    def find_at(key, lo, cap_=cap):
        p = en_rom.find(key, lo)
        tries = 0
        while p >= 0 and tries < cap_:
            yield p
            p = en_rom.find(key, p + 1)
            tries += 1

    def chain(first_p):
        out, k_prev = [], -1
        for n, (idx, key, size) in enumerate(items):
            p = first_p if n == 0 else None
            if p is None:
                for q in find_at(key, en_sk.starts[k_prev] + 1):
                    if en_sk.container(q) > k_prev:
                        p = q
                        break
            if p is None:
                continue
            k = en_sk.container(p)
            out.append((idx, p, size, k))
            k_prev = k
        return out

    first_key = items[0][1]
    best = []
    tried = 0
    for p in find_at(first_key, 0):
        got = chain(p)
        if len(got) > len(best):
            best = got
        tried += 1
        if tried > 40:
            break
    return best


def main():
    mode = sys.argv[1]
    man_ref = json.loads(gzip.decompress(Path(sys.argv[2]).read_bytes()))
    target = sys.argv[3]
    en_rom = ROMS['EN'].read_bytes()
    en_sk = Skeleton(en_rom)
    sk = Skeleton(ROMS[target].read_bytes())

    loc, lost = {}, 0
    for rel in man_ref['files']:
        got = locate_file(man_ref, rel, en_rom, en_sk)
        loc[rel] = got
    tot_man = sum(len(v['edits']) for v in man_ref['files'].values())
    got_n = sum(len(v) for v in loc.values())
    print("EN: %d/%d editions placees (%.1f%%)" % (got_n, tot_man, 100.0 * got_n / tot_man))
    print("squelette EN: %d objets ; cible: %d objets" % (len(en_sk.starts), len(sk.starts)))

    glob = []
    for rel, lst in loc.items():
        for idx, p, size, k in lst:
            glob.append((p, k, rel, idx, size))
    glob.sort()
    regs, cur = [], [glob[0]]
    for it in glob[1:]:
        if it[1] - cur[-1][1] > 1:      # objets non adjacents -> nouvelle region
            regs.append(cur)
            cur = []
        cur.append(it)
    regs.append(cur)
    big = [r for r in regs if len(r) >= 6]
    small = [r for r in regs if len(r) < 6]
    print("%d regions (%d >= 6 objets -> %d objets, %d petites -> %d objets)"
          % (len(regs), len(big), sum(len(r) for r in big), len(small), sum(len(r) for r in small)))

    mapping, anchors = [], []
    for rg in big:
        en_start = rg[0][0]
        k_first = rg[0][1]
        k_last = rg[-1][1]
        cnt_n = k_last - k_first + 1
        en_sizes = en_sk.sizes[k_first:k_last + 1]
        en_span = en_sk.starts[k_first + cnt_n] - en_sk.starts[k_first]
        cands = []
        # La contrainte `run[k] >= cnt_n` de carve3 rejette la BONNE position des qu'un
        # objet du run est plus long que maxsize ou nul : sur l'oracle, la verite de
        # `move_descriptions.h` a une correlation de 0,997 et un span a 0,993 mais run=354
        # pour 379 objets demandes. On balaie donc les DEBUTS D'OBJET de la fenetre (pas
        # les octets), et le profil de tailles + le span font le tri.
        lo_k = bisect.bisect_left(sk.starts, max(1, en_start - 250000))
        hi_k = bisect.bisect_right(sk.starts, min(len(sk.data) - 400, en_start + 250000))
        for k in range(lo_k, min(hi_k, len(sk.starts) - cnt_n - 1)):
            off = sk.starts[k]
            if off <= 0:
                continue
            span = sk.starts[k + cnt_n] - off
            if not 0.5 * en_span <= span <= 1.6 * en_span:
                continue
            c = corr(sk.sizes[k:k + cnt_n], en_sizes)
            if c < 0.45:
                continue
            cands.append((c, off, k, span))
        if not cands:
            continue
        # CARVE4 PRENAIT `(near or cands)[0]` SANS TRIER : cands est construit dans l'ordre du
        # balayage, donc c'est le candidat de plus PETIT offset de la fenetre qui gagnait - la
        # correlation calculee n'etait jamais utilisee. On trie par correlation decroissante
        # AVANT le filtre de proximite.
        cands.sort(key=lambda t: -t[0])
        near = [c for c in cands if abs(c[1] - en_start) <= 200000]
        c, off, k, span = (near or cands)[0]
        anchors.append((en_start, off, span, cnt_n, k_first, k))
        for (p, kk, rel, idx, size) in rg:
            dk = kk - k_first
            de_start = sk.starts[k + dk] if k + dk < len(sk.starts) else None
            if de_start is None:
                continue
            off_in = p - en_sk.starts[kk]
            mapping.append({'file': rel, 'edit': idx, 'en_offset': p, 'en_size': size,
                            'target_offset': de_start + off_in,
                            'target_size': sk.text_end[k + dk] or size,
                            'target_container': de_start, 'stage': 1, 'corr': round(c, 3)})
    anchors.sort()
    print("etage 1: %d regions ancrees, %d objets places" % (len(anchors), len(mapping)))

    placed2 = 0
    for rg in small:
        p, kk, rel, idx, size = rg[0]
        before = [a for a in anchors if a[0] < p]
        after = [a for a in anchors if a[0] > p]
        lo = before[-1][1] if before else 1
        hi = after[0][1] if after else len(sk.data) - 400
        if hi <= lo:
            continue
        # on saute depuis l'ancre precedente : autant d'objets que l'ecart EN
        k_target = None
        if before:
            k_prev_en, k_prev_de = before[-1][4], before[-1][5]
            k_de_at_lo = bisect.bisect_right(sk.starts, lo) - 1
            k_env = bisect.bisect_right(en_sk.starts, before[-1][0]) - 1
            k_target = k_de_at_lo + (kk - k_env)
        for (pp, k2, rel2, idx2, size2) in rg:
            if k_target is None or k_target >= len(sk.starts):
                continue
            off_in = pp - en_sk.starts[k2]
            mapping.append({'file': rel2, 'edit': idx2, 'en_offset': pp, 'en_size': size2,
                            'target_offset': sk.starts[k_target] + off_in,
                            'target_size': sk.text_end[k_target] or size2,
                            'target_container': sk.starts[k_target], 'stage': 2, 'corr': 0.0})
            placed2 += 1
            k_target += 1
    print("etage 2: %d objets places" % placed2)

    out = WORK / ('mapping_%s.json' % target)
    out.write_text(json.dumps(mapping))
    print("mapping: %s (%d objets)" % (out, len(mapping)))

    if mode == 'oracle':
        default = {'IT': 'italian.json.gz', 'FR': 'french.json.gz', 'ES': 'spanish.json.gz'}[target]
        man_t = json.loads(gzip.decompress(Path(sys.argv[4]).read_bytes())) if len(sys.argv) > 4 else \
            json.loads(gzip.decompress((LOCALES / default).read_bytes()))
        by_file = {}
        for m in mapping:
            by_file.setdefault(m['file'], {})[m['edit']] = (m['target_offset'], m['target_size'], m['stage'])
        ok = miss = 0
        per_file, by_stage = [], {}
        for rel, entry in man_t['files'].items():
            got = by_file.get(rel)
            if not got:
                continue
            good = 0
            for i, e in enumerate(sorted(entry['edits'])):
                g = got.get(i)
                if g and g[0] == e[2] and g[1] == e[3]:
                    good += 1
                    by_stage[g[2]] = by_stage.get(g[2], 0) + 1
            per_file.append((good, len(entry['edits']), rel))
            ok += good
            miss += len(entry['edits']) - good
        per_file.sort(reverse=True)
        print("\nORACLE %s: %d/%d couples exacts (%.2f%%) | par etage %s"
              % (target, ok, ok + miss, 100.0 * ok / max(1, ok + miss), by_stage))
        print("   fichiers parfaits: %d/%d" % (sum(1 for g, n, _ in per_file if g == n), len(per_file)))
        print("   meilleurs:")
        for g, n, rel in per_file[:6]:
            print("      %-56s %d/%d" % (rel, g, n))
        print("   pires:")
        for g, n, rel in per_file[-6:][::-1]:
            print("      %-56s %d/%d" % (rel, g, n))


if __name__ == '__main__':
    t0 = time.time()
    main()
    print("duree %.1f s" % (time.time() - t0))
