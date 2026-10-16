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

## Where the 19 310 edits came from

Each lever was measured on the Italian oracle before use, then applied:

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

- **graphics** (104 located): the multi-language source carries per-language asset
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

78 450 symbols in the Italian file, about 7 300 of them at address 0. Produce one
with `nm -S --defined-only <elf>` on a build of the **game**, then
`tools/manifest/emit_symbols.py`.

It cannot be produced from the port's tree, and the blockers are worth knowing
before trying:

1. the pinned upstream is **modern-only** - `tools/agbcc` is not a submodule and
   the tree carries none, so the "`make` in the upstream tree's root" route that
   RELEASING.md documents needs agbcc installed into the tree first
   (`git clone https://github.com/pret/agbcc && ./build.sh && ./install.sh <tree>`;
   `build/container_de_validate.sh` does exactly that). Without it the build stops
   at `tools/agbcc/bin/agbcc: No such file or directory`, and the fallback host
   compiler dies on `stdio.h`;
2. **GCC 14+** turns what the tree relies on into hard errors: the sound table in
   `m4a.c` picks its branch off `__STDC_VERSION__ < 202311L` and the C23 branch
   calls unprototyped names; `stub.c` defines GameCube stubs with no argument
   against a header that declares a pointer;
3. the port's makefile **dropped `ASM_PSEUDO_OP_CONV` and `FIX_UNDERSCORE`** while
   its own data rules still call them (`3ds_port/full.mk` has the conversion;
   `FIX_UNDERSCORE` is a no-op on an EABI toolchain);
4. even with (1)-(3) unblocked the link **overflows GBA IWRAM** - 87 108 bytes
   into 32 KiB, 265 % - and misses `__getreent`. The port's tree is a 3DS tree;
   the game is built by `3ds_port/full.mk`, not by the upstream Makefile.

So build the game from a **pristine pinned upstream plus the localization patches
for that language**, and take the symbol table from that ELF.

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
