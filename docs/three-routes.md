# Three ways a language gets into a port

The port ships five languages and they share one pipeline: a checked-in manifest of
source spans and ROM offsets, staged from the reader's own cartridge at bootstrap
time, carrying no game text. What changes from one language to the next is where the
**two sides of an edit** come from - the text, and the offset it sits at.

| | route A: a language tree exists | route B: no tree at all | route C: a translated ROM |
|---|---|---|---|
| precondition | a language fork or a multi-language branch of the same base | a retail cartridge of that language, and no decompilation of it | a translated or hacked cartridge |
| the text comes from | that tree | the cartridge, decoded with the charmap | the hacked cartridge |
| the offsets come from | that tree's own build, when it reproduces the retail ROM | the cartridge, located by this toolkit | the cartridge, located by this toolkit |
| validated against | its own re-encoding | an already-mapped language, as the oracle | the same |
| used by the port for | French, Italian, Spanish | **German** | not yet |

The distinction that matters is not "easy route versus hard route". It is whether an
**encoder tree** exists, because that decides whether the offsets have to be
searched for at all.

## Route A: the language has a decompilation of its own

[`malahx/pokeemerald`](https://github.com/malahx/pokeemerald/tree/french_enhanced)
branch `french_enhanced` for French, or a multi-language branch that keeps every
language side by side (`data/text/<lang>/*.inc`, `src/data/text/<lang>/*.h`,
`#elif ITALIAN` arms in ~50 C and header files, `.ifdef ITALIAN` plus `.include` in
the assembly) for Italian. It landed as
[port #63](https://github.com/ZallaxDev/pokeemerald-3Ds-dualscreen/pull/63) and
[#34](https://github.com/ZallaxDev/pokeemerald-3Ds-dualscreen/pull/34), completed in
[#43](https://github.com/ZallaxDev/pokeemerald-3Ds-dualscreen/pull/43).

What it buys: the text in source form, and an encoder to re-encode from when the
manifest is self-checked. What it can also buy: the **offsets**, if the tree builds
the retail ROM byte for byte - find the commit whose `rom.sha1` equals the retail
hash, and its linker map and symbol table become a ground truth you do not have to
reconstruct. That is the shortcut this route offers, and why the French work started
by pinning a fork commit rather than by probing a cartridge.

Two traps worth naming:

- **A fork's default branch may not match retail.** `french_enhanced` merged a
  feature branch at its tip and builds a different ROM. Verify with `shasum -a 1`
  before building anything.
- **Structural drift.** Diff against the *same* base version the port pins, and
  align renamed files by symbol and by position inside a run of labels sharing a
  long prefix, not by index alone. The fork's tree is not the port's tree, so the
  spans still have to be re-derived on the port's side whatever the offsets say.

## Route B: the language exists as a cartridge and nowhere else

German. No decompilation of that language exists, so nothing is transplanted and
nothing is re-encoded from a language tree: every text span, table, asset and credit
entry is located in the retail image, and that is what the rest of this repository
does. It landed as
[port #96](https://github.com/ZallaxDev/pokeemerald-3Ds-dualscreen/pull/96), from
[issue #28](https://github.com/ZallaxDev/pokeemerald-3Ds-dualscreen/issues/28).

The one thing this route needs from elsewhere: **a language that has already been
mapped**, to serve as the oracle. Every tool here is scored on that language before
it is pointed at a new one, which is what makes a 97 % placement rate trustworthy
rather than optimistic. Italian and French took route A, so their manifests exist -
which is why they appear in this repository as inputs.

The only German source text anywhere is 2 137 literals in the `pret_europe_german`
branch of `AsparagusEduardo/pokeemerald` (note: `pret/pokeemerald` itself is English
only, and `pret_europe` is a branch of that fork, not of `pret/`). All 2 137 were
found in the retail cartridge, so those edits needed no alignment at all - a
shortcut, not a substitute for the route.

## Route C: a translated ROM exists

A fan translation or hack. The work is route B, with one extra precondition: the
hack must be the same game at the same offsets, with shifts that are constant per
region. A hack that reorders data, grows tables or moves pointers breaks the
assumption, and no tooling repairs that.

The structural test is two minutes and it is in
[`adding-a-language.md`](adding-a-language.md): compare the two cartridges block by
block, then read how many differing regions there are and how many `0xFF`
terminators each holds. Structure shared, differences language-shaped: route C is
open.

## What none of the routes removes

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
