# Adding a language

This toolkit locates the text of a language that **already exists in a
cartridge**. It is the second of the three routes described in
[`three-routes.md`](three-routes.md); if the language exists in the decompilation's
source (a language fork, a multi-language branch), take route 1 there instead -
it is days of work rather than weeks, and this file does not apply. It does not translate, and it cannot invent a language. So the first
question is never "which language do we want" but "which cartridge do we have".

## Step 0: the two-minute answer

Run the structural test before anything else:

```console
$ export LOC_ROMS=$PWD/roms LOC_REF_MANIFEST=$PWD/work/italian.json.gz
$ python3 romcarve.py check DE --compare IT
identical at the same offset : 4595712 / 16777216 bytes (27.4 %)
differing regions >= 16 KiB  : 6
```

Then `python3 romcarve.py run ref -- DE`, which reports the differing zones and how
many `0xFF` terminators each holds. If the two cartridges share their structure and
the differences are language data, the method applies. If the identical share
collapses or the zone count explodes, the target is not the same game at the same
offsets - a romhack that reorders data, for instance - and no amount of tooling
will make the shift between them constant.

## What the pipeline needs, per language

| needed | where it comes from | cost |
|---|---|---|
| the cartridge | your own dump, identified by sha1 | - |
| a **reference** language already mapped | its manifest is the oracle and its tree supplies the source spans | free if one exists |
| a decompilation tree at the pinned base | the port's bootstrap | free |
| the charmap | `charmap.txt` in the reference tree | free |
| the language's own text **in source** | a language branch, when one exists | a shortcut, not a requirement |

The last row is the biggest lever and the easiest to miss. The
`pret_europe_german` branch carries 2 137 German literals in `#elif GERMAN` arms;
all 2 137 were found in the retail cartridge, so those edits needed no alignment at
all. Check GitHub for a same-base language fork before writing a single probe.

## What the pilot does, and what stays yours

```console
$ python3 romcarve.py plan
```

`plan` prints the eleven questions in order, the tool that answers each, the
artefact it leaves in the workspace, and **what a human still has to do there**.
That last line is the honest part of the list, and it never becomes empty:

- the carver's output has to be scored on the oracle language before it is
  believed on the target;
- every placement an audit flags has to be read, because the audits are blind to a
  file shifted by exactly one record;
- the unmapped list has to be read once more before shipping.

The first German pass placed 19 310 operations and deliberately left 37 source
editions unresolved. Finalization reviewed every one: 28 proved placements, eight
keyboard rows handled as a complete retail table, and one unused invariant kept.
The final manifest has 19 336 operations and no unmapped source editions. These
counts need not increase by 37: grouped tables replace individual rows. The
[completion record](german-completion.md) separates mapping, runtime and release
proof. Budget for the reading and repair passes, not only for compute.

## Adding a new game

A game is a profile plus whatever table shapes it has that Emerald does not:

1. write `profiles/<game>.json`: the cartridges (game code, sha1, file name), the
   languages with their roles, and where the charmap lives. Nothing in the pipeline
   reads the game's name except for display;
2. check the table shapes the finders know: fixed-stride rows, struct-of-strings
   records, easy-chat group chains and `u32` word indices. A new shape is a new
   descriptor in `tools/tables/`, modelled on `form12.py` and scored the same way,
   on an oracle;
3. map a first language with the pipeline. Once one language of the new game is
   mapped, it becomes the oracle for the next one, exactly as Italian was for
   German.

What does **not** change with the game: the carver, the alignment rules, the
placement logic, the merge discipline, the audits, and the manifest format. What
does change: the charmap, the table descriptors, the asset layout, and the port's
own font and layout work (glyphs, widths, punctuation) which is per language and
lives in the port, not here.

## The checklist, in the order the questions come up

```console
$ python3 romcarve.py languages           # what this profile knows, and what is missing
$ python3 romcarve.py check <LANG>        # is this the dump the offsets will be measured on
$ python3 romcarve.py run ref -- <LANG>   # where does it stop matching the reference
$ python3 romcarve.py run carve -- ...    # first placement pass, scored on the oracle
$ python3 romcarve.py run audit -- ...    # and the pass that decides what to re-read
$ python3 romcarve.py status              # which artefacts exist, which stage is next
$ python3 romcarve.py report <manifest>   # the numbers the manifest claims
```

`run` executes the stage's tool with your arguments, logs stdout and stderr to
`$LOC_WORK/logs/`, and appends the exit code and duration to `$LOC_WORK/state.json`,
so a long language pass leaves a trail of what was run and when.
