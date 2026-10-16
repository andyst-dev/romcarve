#!/usr/bin/env python3
"""Render docs/cartridge-map.svg (light and dark) from docs/cartridge-map.json.

The data file holds only derived facts: for each 64 KiB block of the 16 MiB
image, whether the English and German cartridges are byte-identical there, and
how many of the 19 310 placed edits fall in it. No game bytes, no text.

  python3 docs/make_cartridge_map.py        # writes both SVGs
  rsvg-convert -w 1800 -b '#ffffff' docs/cartridge-map.svg > docs/cartridge-map.png

Every number printed in the picture is computed from the data file, and the
script parses its own output before returning.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "cartridge-map.json"

W, H = 960, 320
PAD = 40
BAND_TOP, BAND_H = 74, 40
BAR_TOP, BAR_H = 168, 92

PALETTES = {
    "light": {
        "bg": "#ffffff", "tile": "#f6f8fa", "border": "#dbe1e8",
        "text": "#1f2328", "muted": "#8c959f", "accent": "#1a7f37",
        "accent_soft": "#a8dab5",
    },
    "dark": {
        "bg": "#0d1117", "tile": "#161b22", "border": "#30363d",
        "text": "#e6edf3", "muted": "#8b949e", "accent": "#3fb950",
        "accent_soft": "#1f6f34",
    },
}


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build(data: dict, pal: dict, dark: bool) -> str:
    blocks = data["blocks"]
    n = len(blocks)
    cell = (W - 2 * PAD) / n
    peak = max(b["edits"] for b in blocks) or 1
    same_pct = 100.0 * sum(1 for b in blocks if b["same"]) / n
    edits = data["edits_total"]
    in_diff = sum(b["edits"] for b in blocks if not b["same"])
    carrying = sum(1 for b in blocks if b["edits"])
    o = []
    a = o.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
      f'font-family="-apple-system, Segoe UI, Helvetica, Arial, sans-serif">')
    a(f'<rect width="{W}" height="{H}" fill="{pal["bg"]}"/>')
    a(f'<text x="{PAD}" y="34" font-size="19" font-weight="600" fill="{pal["text"]}">'
      f'A 16 MiB cartridge, shared and language-specific</text>')
    a(f'<text x="{PAD}" y="54" font-size="12.5" fill="{pal["muted"]}">'
      f'Pokemon Emerald: English versus German, compared 64 KiB at a time</text>')

    # band: identical at the same offset, or not
    a(f'<rect x="{PAD}" y="{BAND_TOP}" width="{W - 2 * PAD}" height="{BAND_H}" '
      f'fill="{pal["tile"]}" stroke="{pal["border"]}" stroke-width="1"/>')
    for i, b in enumerate(blocks):
        if b["same"]:
            continue
        x = PAD + i * cell
        a(f'<rect x="{x:.2f}" y="{BAND_TOP}" width="{cell + 0.05:.2f}" height="{BAND_H}" '
          f'fill="{pal["accent"]}" fill-opacity="{0.22 if not dark else 0.30}"/>')
    a(f'<text x="{PAD}" y="{BAND_TOP - 6}" font-size="11.5" fill="{pal["muted"]}">'
      f'cartridge, offset 0 to 16 MiB</text>')
    a(f'<text x="{PAD + 6}" y="{BAND_TOP + 25}" font-size="12.5" font-weight="600" '
      f'fill="{pal["text"]}">{same_pct:.1f} % byte-identical</text>')

    # ticks
    for mib in range(0, 17, 4):
        x = PAD + (mib / 16) * (W - 2 * PAD)
        a(f'<line x1="{x:.2f}" y1="{BAND_TOP + BAND_H}" x2="{x:.2f}" y2="{BAND_TOP + BAND_H + 5}" '
          f'stroke="{pal["border"]}"/>')
        if mib < 16:
            a(f'<text x="{x:.2f}" y="{BAND_TOP + BAND_H + 17}" font-size="10.5" '
              f'fill="{pal["muted"]}" text-anchor="middle">{mib} MiB</text>')

    # bars: where the edits landed
    a(f'<text x="{PAD}" y="{BAR_TOP - 8}" font-size="12.5" fill="{pal["text"]}">'
      f'the {edits:,} placed edits, by cartridge offset (peak {peak:,} per 64 KiB block)</text>')
    for i, b in enumerate(blocks):
        c = b["edits"]
        if not c:
            continue
        x = PAD + i * cell
        h = BAR_H * (c / peak) ** 0.5
        a(f'<rect x="{x:.2f}" y="{BAR_TOP + BAR_H - h:.2f}" width="{cell + 0.05:.2f}" '
          f'height="{h:.2f}" fill="{pal["accent"]}"/>')
    a(f'<line x1="{PAD}" y1="{BAR_TOP + BAR_H}" x2="{W - PAD}" y2="{BAR_TOP + BAR_H}" '
      f'stroke="{pal["border"]}"/>')

    # legend
    y = H - 34
    a(f'<rect x="{PAD}" y="{y - 9}" width="11" height="11" fill="{pal["accent"]}" '
      f'fill-opacity="{0.22 if not dark else 0.30}" stroke="{pal["accent"]}" stroke-width="0.6"/>')
    a(f'<text x="{PAD + 18}" y="{y}" font-size="11.5" fill="{pal["text"]}">'
      f'the cartridges differ here: language data</text>')
    a(f'<rect x="{PAD + 250}" y="{y - 9}" width="11" height="11" fill="{pal["tile"]}" '
      f'stroke="{pal["border"]}"/>')
    a(f'<text x="{PAD + 268}" y="{y}" font-size="11.5" fill="{pal["text"]}">'
      f'identical at the same offset</text>')
    a(f'<text x="{PAD}" y="{y + 19}" font-size="11.5" fill="{pal["muted"]}">'
      f'{in_diff:,} of {edits:,} edits ({100.0 * in_diff / edits:.1f} %) sit inside a '
      f'differing block, spread over {carrying} of {n} blocks.</text>')
    a('</svg>')
    return "\n".join(o)


def main() -> int:
    data = json.loads(DATA.read_text())
    for name, pal in PALETTES.items():
        svg = build(data, pal, dark=(name == "dark"))
        ET.fromstring(svg)  # fail loudly if the XML is not valid
        out = HERE / (f"cartridge-map{'-dark' if name == 'dark' else ''}.svg")
        out.write_text(svg)
        print(f"wrote {out.relative_to(HERE.parent)}")
    blocks = data["blocks"]
    n = len(blocks)
    print(f"check: {n} blocks, {sum(1 for b in blocks if b['same'])} identical, "
          f"{data['edits_total']} edits, peak {max(b['edits'] for b in blocks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
