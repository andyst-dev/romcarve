# The method

## The problem, stated exactly

A Pokemon decompilation expresses its text as named spans in C and assembly
source. A port that ships several languages applies, for each language, a
manifest of `[source_span, rom_offset, size, kind]` rows: "the bytes this span
compiles to are at this offset in *that* cartridge". Producing such a manifest
for a language whose decompilation does not exist means locating every one of
those spans in the retail image, by hand and by tool, with no ground truth.

Ground truth is what makes the difference: for German, the Italian manifest was
available and *the two cartridges are laid out identically*, language data aside.
That is enough to validate every tool before trusting it. Every placement tool
here is scored on Italian first, and only then pointed at German.

## The invariants

1. **Verify what the code does, never what you assume it does.** An offset is not
   accepted because it came out of a tool with a good score. It is accepted when
   the bytes *before* the text match the structure the source implies, and the
   text itself decodes. Score-driven acceptance is how whole files end up shifted
   by one record.
2. **Never pair the k-th missing edit with the k-th object of a pool.** That is
   the single most expensive mistake class in this project. Missing edits are
   located by an anchor, an interval, a neighbour or content - never by rank.
3. **Audits are necessary and not sufficient.** The duplicate audit and the delta
   audit are blind to a file shifted by exactly one record: every entry is unique
   and every delta is locally plausible. Only reading the file catches that.
4. **The ROM delta is not constant.** Measured: `+85996` near 3.8 MiB, `+288` near
   14.5 MiB. Any method that assumes "target = reference + delta" produces
   confidently wrong offsets past the first section boundary. Placement is done
   **by structure**: section by section, table by table.
5. **Rule of the prefix.** When the target object begins slightly before the text
   it contains, `offset_target = object_start + (offset_reference -
   object_start_reference)`. The prefix is an offset rule, not a delta rule.

## Defect classes the audits exist to catch

| class | signal | how it was caught |
|---|---|---|
| file shifted by one record | every entry in the file is plausible, all unique | reading the file; the tests that "pass" are the trap |
| edit placed on the object start instead of the text start | the signal is an order inversion against the reference | `fix_prefix`, then the per-file gate |
| "the text is elsewhere" | the pool contains the text, but not where the rule put it | content search inside the interval the two neighbours define |
| entry pointing at a control table or a blob | decodes to control codes, not prose | reading; `dup_audit` packs, `merge_sense` accepts only read entries |
| an English block inside the German cartridge | an anchor that looks perfect and is English | `langcheck_de` |
| braille text | the object starts 6 bytes into the text | measured once, applied as `offset + 6` |

## Historical first-pass placement levers

The original 19 310-operation pass used the following levers, measured on the
Italian oracle before use. This is a historical breakdown, not a final-coverage
percentage; the final 19 336 operations and 37 decisions are recorded in
[`german-completion.md`](german-completion.md):

| lever | count | oracle |
|---|---|---|
| content-verified anchors (`#elif GERMAN` literals found in the ROM) | 2 137 | 2 137 / 2 137 |
| pool fitter (packed pools, length fitting) | 3 738 | - |
| struct table wiring, form 1 and 2 | 2 573 | 2 571 / 2 573 |
| struct table wiring, form 3 (multi-field records) | 1 560 | 1 560 / 1 560 |
| repaired carver, per-kind acceptance | 4 341 | on the Italian carver |
| easy-chat layout chain (both halves of all 18 groups) | 2 016 | 1 989 / 2 016 |
| run-walk (`move_descriptions.h` 354, `match_call_messages.h` 312, `item_descriptions.h` 309) | 975 | 354/354, 312/312, 309/309 |
| struct scans (`contest_opponents.h`, `apprentice.h`) | 432 | two tables in one file, same delta |
| small pools (`berry.c`, gift ribbons, natures) | 201 | - |
| pool anchored on a neighbour's delta | 197 | - |

Non-text sections resolve differently again:

- **graphics** (105 in the final manifest): the multi-language source carries per-language asset
  files that are byte-identical to the cartridge. Each `.lz` is verified by
  decompressing the cartridge bytes and comparing with the uncompressed sibling.
- **Trainer Hill floors** (4 tables): a charmap-encoded needle, because the tables
  are `static` and absent from the linker map.
- **credits** (275 entries): a scan for a run of consecutive `u32` pointers to
  8-byte records, instead of trusting a symbol.

## Audits

- `ratio_audit` - German/Italian size ratio per placed text edit, accepted band
  `[0.45, 2.6]`. Outside it, the edit is suspect, not the language.
- `dup_audit` - no cartridge offset may serve two edits. It cannot see a
  one-record shift, and it is the fastest way to find a pool placed twice.
- `delta_audit` - local delta plausibility inside a section.
- `de_gate` - per file, the German-side plausibility gate applied to what the
  carver proposed: the oracle proved the method, not the placement.
- `de_manifest_verify` - self-check of the assembled manifest before delivery:
  every `sha256` against the pinned tree, every span inside its file, every
  offset inside the cartridge, sizes consistent.

## The reference symbol table

A port's release flow wants one more artefact per language: a reference symbol
table (`tools/locales/<lang>-symbols.s.gz`), consumed by the recipe generator to
learn where each table lives in the ROM. Format, decoded from the shipped Italian
file - four lines per **defined** symbol, alphabetical, four spaces of indent,
addresses in **decimal**:

```
    .global NAME
    .type NAME, %function      # T t W w ; %object for D d B b R r A S V G
    .equ NAME, 135476640
    .size NAME, 40             # 0 when unknown
```

`tools/manifest/emit_symbols.py` formats an existing GBA ELF's defined symbols.
It does not establish that the ELF matches the target retail ROM. Build identity
and address evidence are separate checks. Never substitute addresses from the
3DS executable, and never certify a German retail reference merely because a
localized GBA link succeeded. The 3DS port's tree is not a retail GBA rebuild;
forcing it through the GBA linker previously overflowed IWRAM and did not prove
retail layout.

The final German reference instead derives addresses directly from BPED evidence:
structural records, verified localization placements and exact content matches.
Pointer-bearing objects are checked as records, not just payloads. It has 48 858
names, of which 15 087 have evidenced nonzero addresses. All remaining names stay
at zero. The assembler file contains metadata directives, not cartridge data.
It is a partial reference, not a complete decompilation.

Use the reference in the real recipe generator, keep the game-literal limit
unchanged, and reconstruct the actual production pack. Check recipe outputs,
generator inputs, every generated output and every final pack entry byte-for-byte.
The integrated German head passes that gate on macOS and Linux; the complete
numbers and limits are in the [completion record](german-completion.md).

`romcarve.py report <manifest> --symbols <reference.s.gz>` reports metadata shape
and the split between nonzero and unresolved addresses. It rejects data
instructions and malformed records, but does not validate cartridge addresses.

## Running the tools

Every tool reads a workspace from the environment:

```
LOC_WORK          scratch workspace (JSON artefacts, caches, outputs)
LOC_ROMS          directory holding your cartridge images
LOC_REF_MANIFEST  the reference-language manifest (e.g. italian.json.gz)
LOC_REF_TREE      the patched decomp tree of the reference language
LOC_VFWORK        workspace of an earlier language pass, if a tool reuses one
LOC_SCRATCH       throwaway directory for dumps
```

Then:

```console
$ export LOC_WORK=$PWD/work LOC_ROMS=$PWD/roms
$ export LOC_REF_MANIFEST=$PWD/work/italian.json.gz LOC_REF_TREE=$PWD/pret_patched
$ python3 tools/ref/zones.py            # what is shared, what is language data
$ python3 tools/carve/carve7.py         # first placement pass, scored on the oracle
$ python3 tools/audit/dup_audit.py      # and the audits that keep it honest
```

The order matters more than the individual tools: each stage writes a JSON
artefact that the next one reads, and the merge stage is the only place entries
are added to the mapping. See the stage table in the README.
