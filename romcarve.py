#!/usr/bin/env python3
"""romcarve - drive the language-carving pipeline for one game and one language.

The 86 tools under tools/ each answer one question and share a JSON workspace.
This pilot is the missing entry point: it knows the ORDER the questions have to be
asked in, which tool answers each, what artefact that tool leaves behind, and what
stays a human decision. A per-game profile declares the game-specific facts (its
cartridges, its reference languages, its charmap), so a different game is a new
profile plus whatever table shapes it needs - not a new pipeline.

  python3 romcarve.py languages
  python3 romcarve.py check DE
  python3 romcarve.py plan
  python3 romcarve.py status
  python3 romcarve.py run ref -- DE
  python3 romcarve.py report work/german.json.gz

It never invents an argument: `run` executes the stage's tool with the arguments
you give it, logs everything to LOC_WORK/logs/, and records the result.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = Path(os.environ.get("LOC_WORK", "."))
REF_DIR = Path(os.environ.get("LOC_REF_DIR", str(WORK / "locales")))
PROFILES = HERE / "profiles"

# One entry per question, in the order the questions have to be asked. `artifact`
# is what the tool leaves in the workspace and what `status` can therefore track;
# it is None when the tool only prints, which is stated rather than hidden.
STAGES = [
    dict(key="check", question="which dump is this, and how much of it is shared?",
         tool="tools/check_cartridge.py", artifact=None,
         manual="nothing: a wrong dump invalidates everything downstream"),
    dict(key="ref", question="where does the target stop matching the reference byte for byte?",
         tool="tools/ref/zones.py", artifact=None,
         also="tools/ref/matcher2.py -> matches_*.json (content matches at variable offset)",
         manual="decide which differences are language data and which are relocations"),
    dict(key="carve", question="with no manifest for the target, where are its text objects?",
         tool="tools/carve/carve7.py", artifact="mapping_*.json",
         manual="score the carver on the oracle language before believing it here"),
    dict(key="align", question="which objects correspond, and what offset rule links them?",
         tool="tools/align/anchors_sec.py", artifact="anchors_sec_*.json",
         manual="read the files where the rule produces an inversion"),
    dict(key="tables", question="where do fixed-stride and struct-of-strings tables live?",
         tool="tools/tables/form12.py", artifact=None,
         manual="one descriptor per table shape; the tool is only as right as the shape"),
    dict(key="place", question="where does a pool of strings start when only neighbours are known?",
         tool="tools/place/batch_pool.py", artifact="batch_DE.json",
         manual="adjudicate every placement the audits flag as doubtful"),
    dict(key="merge", question="how does a placement become a mapping entry, and what is refused?",
         tool="tools/merge/merge_de.py", artifact="mapping_de_verifie.json",
         manual="nothing: this is the only place entries enter the mapping"),
    dict(key="audit", question="which entries are false?",
         tool="tools/audit/dup_audit.py", artifact="dup_report.json",
         manual="read what the audits cannot see: files shifted by exactly one record"),
    dict(key="graphics", question="where do the assets live, and is the source text the cartridge's?",
         tool="tools/graphics/de_graphics_locate.py", artifact="de_graphics.json",
         manual="verify each compressed asset by decompressing it"),
    dict(key="manifest", question="assemble, self-check and export the manifest",
         tool="tools/manifest/build_de_manifest.py", artifact="german_files.json",
         manual="one last read of the unmapped list, then ship"),
    dict(key="view", question="read one file, one edit at a time, to adjudicate by hand",
         tool="tools/view/show_file.py", artifact=None,
         manual="this IS the manual step: it exists to make the others possible"),
]
STAGE_BY_KEY = {s["key"]: s for s in STAGES}


def load_profile(name: str) -> dict:
    path = PROFILES / f"{name}.json"
    if not path.is_file():
        known = ", ".join(sorted(p.stem for p in PROFILES.glob("*.json"))) or "none"
        sys.exit(f"no profile {name!r} in {PROFILES} (known: {known})")
    return json.loads(path.read_text())


def profile_name(args) -> str:
    return getattr(args, "profile", None) or "emerald"


def cartridge_path(profile: dict, lang: str) -> Path:
    entry = profile["languages"].get(lang)
    if entry is None:
        sys.exit(f"{lang} is not a language of {profile['game']} "
                 f"(known: {', '.join(sorted(profile['languages']))})")
    roms = Path(os.environ.get("LOC_ROMS", str(WORK / "roms")))
    return roms / entry["cartridge"]


def cmd_languages(args) -> int:
    profile = load_profile(profile_name(args))
    print(f"{profile['game']} - base decompilation "
          f"{profile.get('base_decompilation', 'unknown')}")
    print(f"{'code':<6}{'language':<12}{'sha1':<42}{'reference manifest':<20}cartridge")
    for lang, e in sorted(profile["languages"].items()):
        manifest = e.get("manifest") or "-"
        rom = cartridge_path(profile, lang)
        print(f"{e['code']:<6}{lang:<12}{e['sha1']:<42}{manifest:<20}"
              f"{'found' if rom.is_file() else 'not in LOC_ROMS'}")
    return 0


def cmd_check(args) -> int:
    profile = load_profile(profile_name(args))
    rom = cartridge_path(profile, args.language.upper())
    if not rom.is_file():
        sys.exit(f"cartridge not found: {rom} (set LOC_ROMS)")
    extra = ["--compare", str(cartridge_path(profile, args.compare.upper()))] if args.compare else []
    return subprocess.call([sys.executable, str(HERE / "tools/check_cartridge.py"), str(rom), *extra])


def cmd_plan(args) -> int:
    wanted = getattr(args, "stage", None)
    stages = [STAGE_BY_KEY[wanted]] if wanted else STAGES
    for i, s in enumerate(stages, 1):
        print(f"{i:>2}. {s['key']:<9} {s['question']}")
        print(f"    tool     {s['tool']}")
        print(f"    artefact {s['artifact'] or 'stdout only - not resumable'}")
        if s.get("also"):
            print(f"    also     {s['also']}")
        print(f"    human    {s['manual']}")
    print(f"\n{len(stages)} stages. Each one is a question; `run <stage> -- <args>` "
          f"executes its tool against the workspace in LOC_WORK.")
    return 0


def cmd_status(args) -> int:
    print(f"workspace {WORK}")
    print(f"{'stage':<10}{'artefact':<24}{'state':<10}tool")
    for s in STAGES:
        art = s["artifact"]
        if art is None and not s.get("also"):
            state, shown = "n/a", "-"
        else:
            pattern = art or s["also"].split("-> ")[1].split(" ")[0]
            hits = sorted(WORK.glob(pattern))
            state = "present" if hits else "absent"
            shown = hits[-1].name if hits else pattern
        print(f"{s['key']:<10}{shown:<24}{state:<10}{s['tool']}")
    mapping = WORK / "mapping_de_verifie.json"
    if mapping.is_file():
        data = json.loads(mapping.read_text())
        edits = sum(len(v) if isinstance(v, list) else len(v.get("edits", [])) for v in data.values()) \
            if isinstance(data, dict) else 0
        print(f"\nmapping {mapping.name}: {len(data)} files, {edits} edits")
    return 0


def cmd_run(args) -> int:
    stage = STAGE_BY_KEY.get(args.stage) if args.stage else None
    if stage is None:
        sys.exit(f"unknown stage {args.stage!r} (known: {', '.join(STAGE_BY_KEY)})")
    tool = HERE / stage["tool"]
    if not tool.is_file():
        sys.exit(f"tool missing: {tool}")
    passthrough = list(args.rest)
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]
    logs = WORK / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(tool), *passthrough]
    print(f"$ {' '.join(shlex.quote(c) for c in cmd)}")
    started = time.time()
    proc = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    duration = time.time() - started
    log = logs / f"{stage['key']}-{time.strftime('%Y%m%d-%H%M%S')}.log"
    log.write_text(f"$ {' '.join(shlex.quote(c) for c in cmd)}\nexit {proc.returncode} "
                   f"in {duration:.1f}s\n\n{proc.stdout}\n{proc.stderr}")
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
    state = logs.parent / "state.json"
    history = json.loads(state.read_text()) if state.is_file() else []
    history.append(dict(stage=stage["key"], tool=stage["tool"], args=passthrough,
                        exit=proc.returncode, seconds=round(duration, 1),
                        log=str(log.relative_to(WORK)) if WORK in log.parents else str(log)))
    state.write_text(json.dumps(history, indent=1))
    print(f"[{stage['key']}] exit {proc.returncode} in {duration:.1f}s, log {log}")
    return proc.returncode


def cmd_report(args) -> int:
    import collections
    profile = load_profile(profile_name(args))
    path = Path(args.manifest) if args.manifest else WORK / "german.json.gz"
    if not path.is_file():
        sys.exit(f"no manifest at {path} (build one with `run manifest`, or pass a path)")
    man = json.loads(gzip.decompress(path.read_bytes()))
    edits = [e for f in man["files"].values() for e in f["edits"]]
    kinds = collections.Counter(e[4] for e in edits)
    print(f"manifest   {path}")
    print(f"version    {man.get('version')}  status {man.get('status')}")
    print(f"rom_sha1   {man.get('rom_sha1')}")
    for lang, e in profile["languages"].items():
        if e.get("sha1") == man.get("rom_sha1"):
            print(f"cartridge  {lang} ({e['code']})")
    print(f"files      {len(man['files'])}")
    print(f"edits      {len(edits)}")
    for kind, n in kinds.most_common():
        print(f"    {kind:<12}{n}")
    print(f"graphics   {len(man['graphics'])}   credits {man.get('credits_entries')} "
          f"@ {man.get('credits')}   floors {len(man['floors'])}")
    unmapped = man.get("unmapped_source_texts")
    print(f"unmapped   {len(unmapped) if isinstance(unmapped, (list, dict)) else unmapped} "
          f"source texts")
    if man.get("checks"):
        print(f"checks     {json.dumps(man['checks'])[:200]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Drive the language-carving pipeline for one game and one language.")
    ap.add_argument("--profile", help="game profile in profiles/ (default: emerald)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("languages", help="list the languages this profile knows")

    p = sub.add_parser("check", help="identify a profile cartridge, optionally against another")
    p.add_argument("language")
    p.add_argument("--compare", help="second language of the same profile")

    p = sub.add_parser("plan", help="the stage order, and what each stage leaves to a human")
    p.add_argument("stage", nargs="?", help="show one stage only")

    sub.add_parser("status", help="which artefacts exist in the workspace")

    p = sub.add_parser("run", help="execute one stage's tool")
    p.add_argument("stage")
    p.add_argument("rest", nargs=argparse.REMAINDER, help="arguments passed to the tool")

    p = sub.add_parser("report", help="summarise a manifest")
    p.add_argument("manifest", nargs="?")

    args = ap.parse_args()
    return {"languages": cmd_languages, "check": cmd_check, "plan": cmd_plan,
            "status": cmd_status, "run": cmd_run, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
