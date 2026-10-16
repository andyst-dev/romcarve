# Three ways a language gets into a port

This repository implements **one** of them. Naming all three is the only honest way
to say what it is for, because the route you take decides the tools you need and
the cost you are signing up for.

| | route 1: the language is in source | route 2: cartridge only | route 3: a translated ROM |
|---|---|---|---|
| precondition | a same-base language fork, or a multi-language branch | a retail cartridge of that language, no decompilation | a translated/hacked cartridge |
| what you do | transplant the strings, wire the `#ifdef` arms | locate every span in the cartridge | same as route 2, if the structure holds |
| offset work | none | all of it | all of it |
| cost, measured | days, mostly mechanical | 449 files, 19 310 edits, one week of sessions, 37 unmapped, 21 repair passes | route 2 plus the structural test |
| implemented here | no | **yes** | yes, with a caveat |

## Route 1: the language already exists in source

A language fork of the same base decompilation (`malahx/pokeemerald` for French,
branch `french_enhanced`) or a multi-language branch that keeps every language side
by side (`data/text/<lang>/*.inc`, `src/data/text/<lang>/*.h`, `#elif ITALIAN` arms
in ~50 C and header files, `.ifdef ITALIAN` plus `.include` in the assembly). The
Italian build of this port came in this way.

What it costs: transplanting strings and wiring the conditional arms. What it does
not cost: any offset work, because the text is already expressed in the same source
spans.

Two traps worth naming:

- **A fork's default branch may not match retail.** `french_enhanced` merged a
  feature branch at its tip and builds a different ROM. Find the commit whose
  `rom.sha1` equals the retail hash, verify with `shasum -a 1`, and build that.
- **Structural drift.** Diff against the *same* base version the port pins, and
  align renamed files by symbol and by position inside a run of labels sharing a
  long prefix, not by index alone.

## Route 2: the language exists as a cartridge and nowhere else

German. No decompilation of that language exists, so nothing is transplanted: every
text span, table, asset and credit entry is located in the retail image. This is
what the rest of this repository does.

The route needs one thing route 1 does not: **a language that has already been
mapped**, to serve as the oracle. Every tool here is scored on that language before
it is pointed at a new one, and that is what makes a 97 % placement rate
trustworthy rather than optimistic. Italian and French took route 1, so their
manifests exist - which is exactly why they appear in this repository as inputs.

## Route 3: a translated ROM exists

A fan translation or hack. The work is route 2, with one extra precondition: the
hack must be the same game at the same offsets, with shifts that are constant per
region. A hack that reorders data, grows tables or moves pointers breaks the
assumption, and no tooling repairs that.

The structural test is two minutes and it is in
[`adding-a-language.md`](adding-a-language.md): compare the two cartridges block by
block, and read how many differing regions there are and how many `0xFF`
terminators each holds. Structure shared, differences language-shaped: route 3 is
open.

## What none of the three routes removes

Per-language work that lives in the port, not here:

- **the charmap and the glyphs.** German umlauts are charset entries plus a font
  that has to map them - the port's touch font did not, and that is a separate job
  from locating the text;
- **display width and layout.** Line lengths, decimal commas, metric units, table
  widths that the compiler has to accept;
- **the reference symbol table** a release wants per language, which needs a build
  of the game itself (see `method.md`).

And in every route, the last step is the same: read the doubtful entries, list what
could not be placed, and ship that list rather than a guess.
