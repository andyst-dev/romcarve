#!/usr/bin/env python3
"""Identify a Pokemon Emerald cartridge, and measure how two of them align.

This is the first step of the method, standalone: before any offset can be
trusted you need to know WHICH dump you are looking at, and how much of it is
shared with the dump you already have mapped.

  python3 tools/check_cartridge.py emerald.gba
  python3 tools/check_cartridge.py emerald.gba --compare smeraldo.gba

The first form prints the header fields, the checksums and, when they match a
release this project measured against, which one it is. The second form walks
both files in 4 KiB blocks and reports how much of each file sits at the SAME
offset in the other one, plus the largest regions that do not - which is where
the language-specific data lives.

No dependency, no game data: it only reads the two files you give it.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

BLOCK = 4096

# Retail Pokemon Emerald releases, as this project measured them. The game code
# in the header (BPEE/BPED/BPEF/BPES/BPEI) says which language, the checksums say
# which dump: a re-dump, a patched file or a translation hack will not match.
KNOWN = {
    "BPEE": ("English", "f3ae088181bf583e55daf962a92bb46f4f1d07b7"),
    "BPED": ("German", "61c2eb2b380b1a75f0c94b767a2d4c26cd7ce4e3"),
    "BPEF": ("French", "ca666651374d89ca439007bed54d839eb7bd14d0"),
    "BPES": ("Spanish", "fe1558a3dcb0360ab558969e09b690888b846dd9"),
    "BPEI": ("Italian", "1692db322400c3141c5de2db38469913ceb1f4d4"),
}
TITLE_OFFSET = 0xA0  # 12 bytes, NUL padded
CODE_OFFSET = 0xAC   # 4 bytes


def digest(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def describe(path: Path) -> dict:
    with path.open("rb") as f:
        f.seek(TITLE_OFFSET)
        title = f.read(12).split(b"\x00")[0].decode("ascii", "replace")
        f.seek(CODE_OFFSET)
        code = f.read(4).decode("ascii", "replace")
        f.seek(0xBC)
        rev = f.read(1)
        revision = rev[0] if rev else None
    md5, sha1 = digest(path, "md5"), digest(path, "sha1")
    return {
        "path": path, "size": path.stat().st_size, "title": title, "code": code,
        "revision": revision, "md5": md5, "sha1": sha1,
    }


def report(info: dict) -> None:
    print(f"file        {info['path']}")
    print(f"size        {info['size']} bytes ({info['size'] / 1024 / 1024:.2f} MiB)")
    print(f"header      title {info['title']!r}  code {info['code']!r}  revision {info['revision']}")
    print(f"md5         {info['md5']}")
    print(f"sha1        {info['sha1']}")
    known = KNOWN.get(info["code"])
    if known is None:
        print("verdict     game code not in the measured set (not an Emerald release "
              "this project knows about)")
        return
    language, sha1 = known
    if sha1 == info["sha1"]:
        print(f"verdict     {language} release, byte-identical to the dump this project "
              "measured its offsets against")
    else:
        print(f"verdict     looks like the {language} release, but the dump differs from "
              "the one measured here (redump, patch, or translation hack)")


def compare(a: Path, b: Path) -> None:
    """How much of each file sits at the same offset in the other one."""
    size = min(a.stat().st_size, b.stat().st_size)
    same = diff_runs = 0
    runs, start = [], None
    with a.open("rb") as fa, b.open("rb") as fb:
        for off in range(0, size, BLOCK):
            fa.seek(off); fb.seek(off)
            ba, bb = fa.read(BLOCK), fb.read(BLOCK)
            if ba == bb:
                same += len(ba)
                if start is not None:
                    runs.append((start, off)); start = None
            else:
                diff_runs += len(ba)
                if start is None:
                    start = off
    if start is not None:
        runs.append((start, size))
    big = [(s, e) for s, e in runs if e - s >= 16 * 1024]
    print(f"\nidentical at the same offset : {same} / {size} bytes "
          f"({100.0 * same / size:.1f} %)")
    print(f"differs                      : {diff_runs} bytes")
    print(f"differing regions >= 16 KiB  : {len(big)}")
    for s, e in sorted(big, key=lambda r: r[0] - r[1])[:12]:
        print(f"   0x{s:08X} .. 0x{e:08X}  ({(e - s) / 1024:.1f} KiB)")
    print("\nThe language-specific data lives in those regions. That is what the "
          "carver walks.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", type=Path)
    ap.add_argument("--compare", type=Path, metavar="OTHER",
                    help="second cartridge: report how the two align")
    args = ap.parse_args()
    if not args.rom.is_file():
        print(f"not a file: {args.rom}", file=sys.stderr)
        return 1
    report(describe(args.rom))
    if args.compare:
        if not args.compare.is_file():
            print(f"not a file: {args.compare}", file=sys.stderr)
            return 1
        compare(args.rom, args.compare)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
