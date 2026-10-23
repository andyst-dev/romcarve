# Manifest format

A language manifest says, for every place a port has to localize, *where the
localized bytes are in the retail cartridge*. The port's stager verifies the tree
it is given, reads the cartridge at each `rom_offset`, and writes those bytes into
the corresponding source span. That is the whole contract: a manifest is a list of
`(source span -> cartridge offset)` rows plus the bookkeeping that makes it
refuse to be applied to the wrong tree.

Everything is measured, nothing is inferred at apply time.

## Top level

| key | type | meaning |
|---|---|---|
| `version` | string | manifest schema/language tag, e.g. `"0.1-de"`. Older manifests in the wild carry `1`. |
| `rom_sha1` | string | SHA-1 of the cartridge every offset was measured against. A stager should refuse a different dump. |
| `status` | string | `"experimental"` for a language still being verified. |
| `files` | object | source path -> file entry, see below. |
| `graphics` | array | `[path, rom_offset, size]`, one row per located asset. |
| `credits` | integer | cartridge offset of the credits pointer table. |
| `credits_entries` | integer | how many pointers that table holds (275 for Emerald). |
| `floors` | array | `[symbol, rom_offset, size]` for tables that are `static` in source and must be located by content. |
| `unmapped_source_texts` | integer or array | how many source texts could **not** be located. Listed, never guessed. |
| `source_text_decisions` | array | explicit dispositions and reasons for reviewed source gaps; an accepted placement, a retail-table adaptation or a retained invariant. |
| `id_lists` | object | symbol -> `[rom_offset, size]` for complete identifier lists whose cartridge order must also be staged. |
| `checks` | object | free-form audit results recorded at build time. |

## A file entry

```json
"data/event_scripts.s": {
  "sha256": "9663b32fac5cdff9d4728ff7ce31d0ef4ce480fe50f64ddde21f23097054d870",
  "edits": [[37060, 37135, 2613908, 59, "asm"]]
}
```

- `sha256` pins the source file the spans were measured against, so a drifted tree
  is rejected instead of silently mis-localized. This is the single most important
  field in the format: source spans are character indices in decoded text.
  Inserting characters above them invalidates them; the hash covers UTF-8 bytes.
- `edits` is a list of `[source_start, source_end, rom_offset, size, kind]`:
  - `source_start`, `source_end` - character span inside the decoded source file, `end` exclusive;
  - `rom_offset` - offset in the cartridge image (0-based, as read from the file);
  - `size` - how many bytes the localized data occupies in the cartridge;
  - `kind` - the shape of the data, see below.

`size` is not redundant with the span length: German text is generally longer than
Italian, and the ratio between the two is what `ratio_audit` checks.

## Kinds

| kind | what it is |
|---|---|
| `c` | text inside a C string literal |
| `asm` | text inside `.string`/label data in an assembly file |
| `u16s` | a `u16` string table entry (each character one `u16`) |
| `u32` | numeric fields, typically easy-chat word indices |
| `u16array` | an array of `u16` identifiers |
| `bard` | a fixed 22-row table (the Lilycove quiz answers) |
| `u8rows22`, `u16rows10`, ... | fixed-stride row tables, named by element width and row count |
| `u8pages4x9`, `u8rows9` | grouped raw keyboard tables; explicit row/page dimensions, without an implicit string terminator |

A stager needs the kind because a `u16s` string is decoded differently from a `c`
string, and a `u32` field is a number, not text.

## Applying a manifest

1. Hash-verify every file the manifest mentions against its `sha256`; refuse on
   any mismatch. Re-derive spans rather than "fixing" a drifted file by arithmetic:
   an insertion above a span moves every span below it.
2. For each edit, read `size` bytes at `rom_offset`, decode them for the kind
   using the decompilation's charmap, and write the result into the source span.
3. For `graphics`, copy the cartridge bytes into the asset path.
4. For `credits`, `floors` and `id_lists`, rewrite the tables from the cartridge;
   verify identifier order in the compiled output, not just the manifest.
5. Leave the `unmapped_source_texts` alone and say so. An untranslated string is a
   known gap; a wrongly-located string is a crash or a corrupted line.

## Measuring a manifest this way

The German manifest was assembled by `tools/manifest/build_de_manifest.py` from
the verified mapping and then self-checked by `de_manifest_verify.py`, which
re-verifies every hash, every span bound and every cartridge offset before the
file is written. `docs/method.md` describes how the mapping was produced. The final port also
adds reviewed source decisions and grouped keyboard staging; see
[`german-completion.md`](german-completion.md).

Raw `__()` initializers are not ordinary `_()` strings: they do not gain an EOS
byte automatically. Use the source buffer capacity and the charmap to bound them
before staging. A plausible neighboring text run can otherwise turn a clearing
buffer into a stack overwrite.
