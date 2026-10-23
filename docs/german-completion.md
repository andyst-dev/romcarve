# German completion record

The German integration is finalized at port commit
[`d45dc3b`](https://github.com/ZallaxDev/emerald-3ds/commit/d45dc3b7c49f4b2ab8926efb25168095fab165a7),
based on public `dev` `0087891`. [PR #96](https://github.com/ZallaxDev/emerald-3ds/pull/96)
is open for maintainer review. Its three [CI jobs](https://github.com/ZallaxDev/emerald-3ds/actions/runs/39972088637)
pass. This is a tested revision, not a guarantee about later upstream changes.
The port manifest still labels the variant `experimental`; completed integration
checks do not substitute for exhaustive playthrough or hardware coverage.

The [JSON record](german-validation.json) contains derived counts, hashes and
public provenance links only. The manifests, reference table, recipes, ROMs,
localized source tree, extracted text, images, packs and test builds are not
redistributed by this repository.

## What happened to the 37 gaps

| Decision | Count | Meaning |
|---|---|---|
| `placement_accepted` | 28 | The retail location was established and included in staging. |
| `retail_keyboard_table` | 8 | The retail nine-column keyboard is staged as a complete table, not forced into eight individual source rows. |
| `retain_source_invariant` | 1 | An unused empty initializer stays unchanged, with an explicit reason. |

The final manifest contains 19,336 operations over 449 files, 105 graphics,
275 credits entries, four Trainer Hill floors and zero unmapped source editions.
Operation counts differ from distinct-sentence counts, so adding 37 to the old
operation count would be wrong.

## Keyboard and KP are different problems

The naming keyboard needs its character table, per-page column counts, cursor
positions and display-row aliases to agree. A host C harness exercised 96 keys
and 420 navigation transitions; negative controls detect bad row lengths, column
counts, positions and aliases. Human checks inserted all six umlauts successfully.

KP is graphical tile data, not a text label. The full bounded retail asset was
identified using the suffix, a pointer reference and its neighboring table; the
staged and compiled bytes match BPED. No replacement letter or extracted render
is included here.

## A partial reference without a German retail ELF

A manifest maps source selections to retail bytes; it is not a reference symbol
table. A 3DS ELF gives 3DS addresses and must not be used as a GBA address map.
An arbitrary GBA link is also only a candidate until matched against retail.

The BPED-derived reference has 48,858 names: 15,087 nonzero addresses established
from cartridge evidence and 33,771 unresolved names left at zero. Structural
maps/layouts/tilesets, localized objects and exact content matches supply the
accepted addresses. Pointer-bearing objects require their pointer fields to be
checked too; matching only the payload is insufficient. This is not a complete
German decompilation or a claim that every symbol has been recovered.

The four Easy Chat identifier lists illustrate why metadata alone is not enough:
source and compiled order must equal BPED, and the reference must identify those
same lists. An English-ordered list with a plausible symbol name is still wrong.

## The production reconstruction gate

| Gate on `d45dc3b` | Verified result |
|---|---|
| Builder suite, macOS and Linux | 219 tests, four skipped, no failures |
| Existing interface languages | 1,105 arguments across 221 calls and 90 indexed cells preserved |
| Strict recipe | 3,361 game-literal bytes, unchanged 4,096-byte limit |
| Recipe output entries | 6,391 exact |
| Generator input entries | 2,202 exact |
| Generated outputs | All five exact |
| Final pack entries | All 6,396 exact on macOS and Linux |
| Engine ABI | `28be5e3c` |
| Repository and engine-only publication audits | Clean against BPED |

The shared pack SHA-256 is
`d03bf788c50978142b1a2eb00a0cb662d4f61eece4aae78719fd07b22fbb3662`.
Optional network asset fetchers were disabled. Counts and ABI differ from earlier
builds because the current upstream revision was integrated; do not combine their
results.

Terrain relief reads building placements. The production runner must finish
buildings before relief, both in-process and with subprocesses, and the Makefile
must express that dependency. A successful recipe extraction does not prove this:
the generated files and final pack must also be compared byte-for-byte. Different
CRCs are not accepted by raising a budget or disabling a check.

## Test boundary

Human Azahar checks on parent `1823759` covered the six inserted umlauts, KP on
both healthbars and completion of the first battle without a crash. The localized
naming-screen, keyboard text and battle-interface sources are byte-identical after
integration. This is not a second full play test of `d45dc3b`. An earlier Tackle-fix
build also passed save/resume and the documented summary/Pokedex checks.

There has been no complete playthrough, physical-console test or full Windows/web
release-packaging run on this revision. The retail translation belongs to its
original authors; romcarve supplies research tooling and the integration method.

## Inspect your own metadata

```sh
python3 romcarve.py report work/german.json.gz --symbols work/german-symbols.s.gz
python3 -m unittest discover -s tests -v
```

The report counts dispositions, identifier lists and reference records. It accepts
only metadata directives and rejects embedded data, duplicate fields, incomplete
records and address expressions. **It does not validate addresses against your
cartridge.** The tests use synthetic fixtures, not extracted game text.
