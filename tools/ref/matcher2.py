#!/usr/bin/env python3
"""matcher2.py - correspondances EN <-> cible a offset VARIABLE, vectorise.

But : comprendre la STRUCTURE du decalage (le contenu est identique mais deplace).
On indexe toutes les fenetres de W octets de la cible, on interroge des positions
EN informatives echantillonnees, on verifie en bloc, puis on resume le decalage
(de_pos - en_pos) par tranche de 256 Ko.

Usage : matcher2.py <CIBLE> [W] [step] [--save]
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


def build_hashes(arr, w, chunk=1 << 22):
    n = len(arr) - w + 1
    out = np.empty(n, dtype=np.uint64)
    v = np.array([pow(0x100000001B3, i, 2 ** 64) for i in range(w)], dtype=np.uint64)
    for s in range(0, n, chunk):
        e = min(n, s + chunk)
        window = np.lib.stride_tricks.sliding_window_view(arr[s:e + w - 1], w)
        out[s:e] = window.astype(np.uint64) @ v
    return out


def main():
    target = sys.argv[1]
    w = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 16
    step = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 64
    save = '--save' in sys.argv
    A = np.frombuffer(ROMS['EN'].read_bytes(), dtype=np.uint8)
    B = np.frombuffer(ROMS[target].read_bytes(), dtype=np.uint8)
    hb = build_hashes(B, w)
    order = np.argsort(hb, kind='stable').astype(np.int64)
    hb_s = hb[order]
    print("%s : %d fenetres indexees (%d o)" % (target, len(hb), w), flush=True)

    pos = np.arange(0, len(A) - w + 1, step, dtype=np.int64)
    view = np.lib.stride_tricks.sliding_window_view(A, w)[pos]
    nuniq = np.array([len(np.unique(r)) for r in view])
    zfrac = (view == 0).sum(axis=1) / w
    pos = pos[(nuniq >= 6) & (zfrac < 0.5)]
    v = np.array([pow(0x100000001B3, i, 2 ** 64) for i in range(w)], dtype=np.uint64)
    ha = view = None
    ha = np.lib.stride_tricks.sliding_window_view(A, w)[pos].astype(np.uint64) @ v
    lo = np.searchsorted(hb_s, ha, 'left')
    hi = np.searchsorted(hb_s, ha, 'right')
    keep = (hi - lo >= 1) & (hi - lo <= 32)
    print("   requetes EN informatives : %d | avec 1..32 candidats : %d"
          % (len(pos), keep.sum()), flush=True)
    pos, lo, hi = pos[keep], lo[keep], hi[keep]

    qi = np.repeat(np.arange(len(pos)), hi - lo)
    jj = np.concatenate([order[int(lo[t]):int(hi[t])] for t in range(len(pos))])
    print("   couples candidats : %d" % len(qi), flush=True)

    res = []
    offs = np.arange(w)
    CH = 4_000_000
    for s in range(0, len(qi), CH):
        e = min(len(qi), s + CH)
        q, j = qi[s:e], jj[s:e]
        ai = pos[q]
        ka = A[ai[:, None] + offs]
        kb = B[j[:, None] + offs]
        m = (ka == kb).all(axis=1)
        res.append((ai[m], j[m]))
    mi = np.concatenate([r[0] for r in res])
    mj = np.concatenate([r[1] for r in res])
    print("   correspondances verifiees : %d" % len(mi), flush=True)
    # doublons : pour un meme i, garder le meilleur (le plus proche de la diagonale)
    shifts = collections.defaultdict(collections.Counter)
    for i, j in zip(mi.tolist(), mj.tolist()):
        shifts[i // 262144][j - i] += 1
    print("   decalage dominant par tranche de 256 Ko :")
    for k in sorted(shifts):
        print("      %7d K : %s" % (k * 256, ["%+d (%d)" % (d, n)
                                              for d, n in shifts[k].most_common(3)]))
    print("   decalages observes sur toute la ROM :",
          collections.Counter((j - i) for i, j in zip(mi.tolist(), mj.tolist())).most_common(12))
    if save:
        out = Path(f"{WORK}/matches_%s.json" % target)
        out.write_text(json.dumps([[int(i), int(j)] for i, j in zip(mi, mj)]))
        print("->", out)


if __name__ == '__main__':
    main()
