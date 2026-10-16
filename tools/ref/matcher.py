#!/usr/bin/env python3
"""matcher.py - correspondances EN <-> cible a offset VARIABLE (contenu decale).

Hachage par fenetre glissante de W octets, vectorise par numpy par tranches :
  - table triee des hachages de la CIBLE (toutes les positions) ;
  - requete sur les positions EN echantillonnees au pas `step`, filtrees par
    "informativite" (>= 6 valeurs distinctes, < moitie de zeros) ;
  - verification octet a octet, extension de la correspondance ;
  - resume du DECALAGE (de_pos - en_pos) en fonction de la position EN.

Usage : matcher.py <CIBLE> [W] [step] [--save]
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

import collections, json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, f"{WORK}")
from zones import ROMS


def build_hashes(arr, w, chunk=1 << 21):
    n = len(arr) - w + 1
    out = np.empty(n, dtype=np.uint64)
    v = np.array([pow(0x100000001B3, i, 2 ** 64) for i in range(w)], dtype=np.uint64)
    for s in range(0, n, chunk):
        e = min(n, s + chunk)
        window = np.lib.stride_tricks.sliding_window_view(arr[s:e + w - 1], w)
        out[s:e] = window.astype(np.uint64) @ v
    return out


def hash_at(arr, pos, w):
    window = np.lib.stride_tricks.sliding_window_view(arr, w)[pos]
    v = np.array([pow(0x100000001B3, i, 2 ** 64) for i in range(w)], dtype=np.uint64)
    return window.astype(np.uint64) @ v


def main():
    target = sys.argv[1]
    w = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 16
    step = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 64
    save = '--save' in sys.argv
    A = np.frombuffer(ROMS['EN'].read_bytes(), dtype=np.uint8)
    B = np.frombuffer(ROMS[target].read_bytes(), dtype=np.uint8)

    hb = build_hashes(B, w)
    order = np.argsort(hb, kind='stable')
    hb_s = hb[order]
    print("%s : table de %d fenetres de %d o" % (target, len(hb), w))

    pos = np.arange(0, len(A) - w + 1, step, dtype=np.int64)
    view = np.lib.stride_tricks.sliding_window_view(A, w)[pos]
    nuniq = np.array([len(np.unique(r)) for r in view])
    zfrac = (view == 0).sum(axis=1) / w
    good = (nuniq >= 6) & (zfrac < 0.5)
    pos = pos[good]
    print("   positions EN informatives : %d / %d" % (len(pos), len(range(0, len(A) - w + 1, step))))
    v = np.array([pow(0x100000001B3, i, 2 ** 64) for i in range(w)], dtype=np.uint64)
    ha = hash_at(A, pos, w)

    lo = np.searchsorted(hb_s, ha, 'left')
    hi = np.searchsorted(hb_s, ha, 'right')
    keep = (hi - lo >= 1) & (hi - lo <= 16)
    pos, ha, lo, hi = pos[keep], ha[keep], lo[keep], hi[keep]
    print("   requetes avec candidats : %d" % len(pos))

    hits = []
    for t in range(len(pos)):
        i = int(pos[t])
        seg = A[i:i + w]
        for k in range(int(lo[t]), int(hi[t])):
            j = int(order[k])
            if not np.array_equal(B[j:j + w], seg):
                continue
            ln = w
            while i + ln < len(A) and j + ln < len(B) and A[i + ln] == B[j + ln]:
                ln += 1
            hits.append((i, j, ln))
    hits.sort()
    # dedoublonnage : on garde les correspondances non redondantes
    clean = []
    for i, j, ln in hits:
        if clean and i < clean[-1][0] + clean[-1][2] and j == clean[-1][1] + (i - clean[-1][0]):
            continue
        clean.append((i, j, ln))
    print("   correspondances : %d (%d apres nettoyage)" % (len(hits), len(clean)))
    shift = collections.defaultdict(collections.Counter)
    for i, j, ln in clean:
        shift[i // 262144][j - i] += ln
    print("   decalage dominant par tranche de 256 Ko :")
    for k in sorted(shift):
        print("      %7d K : %s" % (k * 256, ["%+d (%d o)" % (d, n) for d, n in shift[k].most_common(3)]))
    tot = sum(l for _i, _j, l in clean)
    print("   couverture des correspondances : %.2f Mo (%.1f%%)" % (tot / 1e6, 100.0 * tot / len(A)))
    print("   25 plus longues :")
    for i, j, ln in sorted(clean, key=lambda h: -h[2])[:25]:
        print("      %9d %9d %8d %+d" % (i, j, ln, j - i))
    if save:
        out = Path(f"{WORK}/matches_%s.json" % target)
        out.write_text(json.dumps(clean))
        print("->", out)


if __name__ == '__main__':
    main()
