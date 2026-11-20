#!/usr/bin/env python3
"""Builds the Experiments landing's cards (schema/EXPERIMENT_CARDS.md): data/replays/cards.json.

A card's typed parts (its title, what it asks, its band and kind, and which map part, catalogue entry,
verdict file and PROGRESS.md entry it reads) are in data/replays/cards.source.json. Everything a card
says of a standing is read:

- from the Engine map's overlay (data/architecture/overlay.json): a part's status, date, plain words and
  sources, at the revision the scene states (data/architecture/architecture.scene.json);
- from the catalogue's overlay (data/replays/overlay.json), its selection and the model-system entries
  (data/models/): what a replay is, its outcome in the catalogue's words, how many runs it packages;
- from the record, in two places read only when gathering: the saved run folders (a judged run's own
  verdict file: its count, its day, the revision it ran from) and the engine's repository at a named
  revision of main (PROGRESS.md's entries and scope lines, the gap-junction note's paragraph, the
  origin-of-life references' table). What the gathering reads is kept, each reading with the file and
  field it came from, in data/replays/cards.readings.json.

So the cards are built from tracked files alone, and the gathering is the only step that reads the
record:

    python3 tools/build_cards.py                    # writes data/replays/cards.json
    python3 tools/build_cards.py --check            # fails if cards.json is not what it would write
    python3 tools/build_cards.py --gather --evidence DIR --repo DIR
                                                    # reads the record, writes the readings and the cards
    python3 tools/build_cards.py --check --evidence DIR --repo DIR
                                                    # also gathers again, and fails if the readings are stale
    python3 tools/build_cards.py --gather --evidence DIR --repo DIR --revision HEAD
                                                    # moves the record to the checkout's head first

DIR for --evidence holds the saved run folders, each named by its own folder name; --repo is a checkout
of the engine's repository, read with git only (git show, cat-file, rev-parse, merge-base: nothing is
written there, and nothing of the engine is imported or run). Tests give --repo-folders instead: a folder
with one subfolder per revision, each holding that revision's files.

Nothing is computed beyond counting a verdict's own rows, no word is made up for a standing, and the
output holds no clock time, so the same inputs give the same bytes.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
FORMAT = "cells.visualizer.experiment_cards@1"
SOURCE_FORMAT = "cells.visualizer.experiment_cards_source@1"
READINGS_FORMAT = "cells.visualizer.experiment_cards_readings@1"
SOURCE = ROOT / "data" / "replays" / "cards.source.json"
READINGS = ROOT / "data" / "replays" / "cards.readings.json"
OUT = ROOT / "data" / "replays" / "cards.json"
CATALOGUE = ROOT / "data" / "replays" / "overlay.json"
SELECTION = ROOT / "data" / "replays" / "selection.json"
MAP = ROOT / "data" / "architecture" / "overlay.json"
SCENE = ROOT / "data" / "architecture" / "architecture.scene.json"
ENTRIES = ROOT / "data" / "models"

BANDS = ("examples", "judged", "development", "invented")
KINDS = ("replay", "standing", "rows")
FULL = re.compile(r"[0-9a-f]{40}\Z")
SHORT = re.compile(r"[0-9a-f]{7,40}\Z")
NAME = re.compile(r"[A-Za-z0-9._-]+\Z")
MACHINE = re.compile(r"(?:^|[\s(\[`'\"])/(?:mnt|home|tmp|root)/")
DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}")
# A clock time in a heading of the record (a date, then a time of day or a span of them in UTC): left out of every
# string written here, which keeps its date.
CLOCK = re.compile(r",?\s*(?:about\s+|at\s+)?\b\d{1,2}:\d{2}(?:\s*[–-]\s*\d{1,2}:\d{2})?\s*UTC\b")
# A count as the record words one, bare ("24 of 24"); with the verdict's own noun, see counts_said.
COUNT_OF_BARE = re.compile(r"\b(\d+)\s+of\s+(\d+)\b")
# An entry of PROGRESS.md's runs that reports a judged run or a registered qualification, whatever its outcome: its
# bold lead holds one of these words. Every such entry is on a card or left out with a reason (the tests hold it).
JUDGED_LEAD = re.compile(r"\b(?:judged|judge|qualified|qualification|pass|passes|passed|fail|fails|failed|verdicts?|acceptance)\b", re.IGNORECASE)
# The tool's own words for what a card leaves off, for a card's detail: never shown in place of a standing.
SNAPSHOT_NOT_ON_MAIN = "The snapshot this run was made from is not on main, so no revision is named for it."
WITHHELD = "The run's verdict file counts {passed} of {of} and the record's entry says {said}, so the card gives no count."


class Breach(Exception):
    pass


# --------------------------------------------------------------------------- text


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dumps(data) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


def without_clock(text: str) -> str:
    out = CLOCK.sub("", text)
    out = re.sub(r"\(\s*[,;]?\s*\)", "", out)
    out = re.sub(r"\(\s*[,;]\s*", "(", out)
    out = re.sub(r"\s+([),.;:])", r"\1", out)
    return re.sub(r"\s+", " ", out).strip()


def plain(markdown: str) -> str:
    """A line of the record's markdown as words: links keep their label, emphasis and code marks go."""
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", markdown)
    text = text.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def said(text: str, where: str) -> str:
    """A string the cards carry: plain, with no clock time, and refused where it names a path of a machine."""
    out = without_clock(plain(text))
    if MACHINE.search(out):
        raise Breach(f"{where}: the words to carry name a path of a machine: {out!r}")
    return out


def sentences(text: str):
    return [part for part in re.split(r"(?<=[.?!])\s+(?=[A-Z\"(“])", text.strip()) if part]


def dig(data, dotted, where):
    value = data
    for key in [part for part in (dotted.split(".") if isinstance(dotted, str) else dotted)]:
        if isinstance(value, list) and isinstance(key, int):
            value = value[key]
        elif isinstance(value, list) and isinstance(key, str) and key.isdigit():
            value = value[int(key)]
        elif isinstance(value, dict) and key in value:
            value = value[key]
        else:
            raise Breach(f"{where}: no field {dotted!r}")
    return value


# --------------------------------------------------------------------------- the record's bullets


class Bullet:
    def __init__(self, indent: int, first: str):
        self.indent = indent
        self.lines = [first]
        self.children: list[Bullet] = []

    @property
    def raw(self) -> str:
        return " ".join(line.strip() for line in self.lines)

    def lead(self):
        raw = self.raw
        if not raw.startswith("**"):
            return None
        end = raw.find("**", 2)
        return raw[2:end] if end > 2 else None

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def full(self) -> str:
        return " ".join([self.raw] + [child.full() for child in self.children])


def bullets(text: str):
    """The bullets of a markdown file as a tree, by indentation: a line indented under a bullet continues it."""
    roots: list[Bullet] = []
    stack: list[Bullet] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        match = re.match(r"( *)- (.*)\Z", line)
        if match:
            while stack and stack[-1].indent >= indent:
                stack.pop()
            node = Bullet(indent, match.group(2))
            (stack[-1].children if stack else roots).append(node)
            stack.append(node)
            continue
        while stack and indent <= stack[-1].indent:
            stack.pop()
        if stack:
            stack[-1].lines.append(line)
    return roots


def find_entry(roots, prefix: str, where: str) -> Bullet:
    key = plain(prefix)
    top = [node for node in roots if node.lead() is not None and plain(node.lead()).startswith(key)]
    found = top or [node for root in roots for node in root.walk() if node.lead() is not None and plain(node.lead()).startswith(key)]
    if len(found) != 1:
        raise Breach(f"{where}: PROGRESS.md has {len(found)} entries whose lead starts with {prefix!r}")
    return found[0]


def find_item(entry: Bullet, prefix: str, where: str) -> Bullet:
    key = plain(prefix)
    found = [node for child in entry.children for node in child.walk() if plain(node.raw).startswith(key)]
    if len(found) != 1:
        raise Breach(f"{where}: the entry {plain(entry.lead() or '')!r} has {len(found)} items starting with {prefix!r}")
    return found[0]


def own_words(node: Bullet, where: str) -> str:
    """A bullet's own words (not its children's). Where they end on a colon that opens a list of children, the
    words that open the list are left off ("21 of 21 judged criteria. Examples:" reads "21 of 21 judged
    criteria."); a list item's closing ';' becomes a full stop."""
    text = said(node.raw, where)
    if text.endswith(":"):
        parts = sentences(text)
        text = " ".join(parts[:-1]) if len(parts) > 1 else text[:-1].rstrip()
    elif text.endswith(";"):
        text = text[:-1].rstrip() + "."
    return text


def with_children(node: Bullet, where: str) -> str:
    """A bullet with its list: "The scope: CPU only, in version 1; ...; A10 is out of scope."."""
    if not node.children:
        return own_words(node, where)
    head = said(node.raw, where)
    items = [own_words(child, where).rstrip(".") for child in node.children]
    return f"{head} {'; '.join(items)}."


def place_found(text: str, where: str) -> bool:
    """Whether a source's place can be found in its file: its words, or one of their parts of 12 letters or more
    before a ';', a ':' or a '(' (a place is often worded as a section and what is read there)."""
    def norm(value):
        value = plain(value).lower().replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
        return re.sub(r"\s+", " ", value)
    body = norm(text)
    wanted = re.sub(r"^runs: ", "", norm(where))
    if wanted in body:
        return True
    parts = [part.strip(" ,.") for part in re.split(r"[;:(]", wanted)]
    return any(len(part) >= 12 and part in body for part in parts)


# --------------------------------------------------------------------------- reading the record


class Repository:
    """The engine's repository at named revisions, read only: git show, cat-file, rev-parse and merge-base."""

    def __init__(self, repo: Path | None = None, folders: Path | None = None):
        self.repo = repo
        self.folders = folders
        self.cache: dict[tuple[str, str], str] = {}

    def git(self, *args, check=True):
        run = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True)
        if check and run.returncode != 0:
            raise Breach(f"git {' '.join(args)}: {run.stderr.strip()}")
        return run

    def full(self, revision: str) -> str:
        if not SHORT.match(revision or ""):
            raise Breach(f"not a revision: {revision!r}")
        if self.folders is not None:
            if FULL.match(revision):
                return revision
            found = [path.name for path in self.folders.iterdir() if path.is_dir() and path.name.startswith(revision)]
            if len(found) != 1 or not FULL.match(found[0]):
                raise Breach(f"the revision folders hold {len(found)} for {revision}")
            return found[0]
        return self.git("rev-parse", "--verify", f"{revision}^{{commit}}").stdout.strip()

    def read(self, revision: str, path: str) -> str:
        key = (revision, path)
        if key not in self.cache:
            if self.folders is not None:
                file = self.folders / revision / path
                if not file.is_file():
                    raise Breach(f"{path} is not at {revision[:8]}")
                self.cache[key] = file.read_text(encoding="utf-8")
            else:
                run = self.git("show", f"{revision}:{path}", check=False)
                if run.returncode != 0:
                    raise Breach(f"{path} is not at {revision[:8]}")
                self.cache[key] = run.stdout
        return self.cache[key]

    def exists(self, revision: str, path: str) -> bool:
        if self.folders is not None:
            return (self.folders / revision / path).is_file()
        return self.git("cat-file", "-e", f"{revision}:{path}", check=False).returncode == 0

    def on_main(self, revision: str, main: str) -> bool:
        if self.folders is not None:
            return (self.folders / revision).is_dir()
        return self.git("merge-base", "--is-ancestor", revision, main, check=False).returncode == 0


class Evidence:
    """The saved run folders, each named by its own folder name and reached folder by folder."""

    def __init__(self, root: Path):
        self.root = root

    def path(self, folder: str, within, file=(), where="") -> Path:
        parts = [folder, *within, *file]
        if not parts or not all(isinstance(part, str) and NAME.match(part) and part not in (".", "..") for part in parts):
            raise Breach(f"{where}: an evidence folder and its files are named folder by folder: {parts!r}")
        path = self.root.joinpath(*parts)
        if not path.exists():
            raise Breach(f"{where}: {'/'.join(parts)} is not in the evidence")
        return path


# --------------------------------------------------------------------------- tracked inputs


class Tracked:
    def __init__(self, catalogue=CATALOGUE, selection=SELECTION, map_overlay=MAP, scene=SCENE, entries=ENTRIES):
        self.catalogue = read_json(catalogue)
        self.selection = read_json(selection)
        self.map = read_json(map_overlay)
        self.scene_meta = read_json(scene)["meta"]
        self.entries_dir = entries
        self.statuses = {status["id"]: status for status in self.map["statuses"]}
        self.components = {part["id"]: part for part in self.map["components"]}
        base = self.scene_meta.get("source_base_url") or ""
        match = re.search(r"/blob/([0-9a-f]{40})/\Z", base)
        if not match:
            raise Breach(f"the scene states no revision for the map's sources (source_base_url {base!r})")
        self.map_revision = match.group(1)

    def experiment(self, identifier: str, where: str):
        found = self.catalogue["experiments"].get(identifier)
        if found is None:
            raise Breach(f"{where}: the catalogue has no experiment {identifier!r}")
        return found

    def entry(self, identifier: str, where: str):
        path = self.entries_dir / f"{identifier}.json"
        if not path.is_file():
            raise Breach(f"{where}: no model-system entry {identifier!r}")
        return read_json(path)

    def part(self, identifier: str, where: str):
        if identifier.startswith("op."):
            item = (self.map.get("operators") or {}).get("items", {}).get(identifier[3:])
            if item is None:
                raise Breach(f"{where}: the map has no operator {identifier!r}")
            return {"id": identifier, **item}
        if identifier not in self.components:
            raise Breach(f"{where}: the map has no part {identifier!r}")
        return self.components[identifier]


def needs_stamp(sources):
    return [source for source in sources if not source.get("revision")]


def sources_to_stamp(card, tracked: Tracked):
    """The catalogue's and the entries' sources a card copies that name no revision of their own: the gathering
    finds each at the record's revision and stamps it with that revision."""
    where = f"card {card['id']}"
    found = []
    standing = card.get("standing") or {}
    if standing.get("from") == "catalogue":
        found += needs_stamp((tracked.experiment(standing["experiment"], where).get("outcome") or {}).get("sources") or [])
    if standing.get("from") == "entry":
        found += needs_stamp((tracked.entry(standing["entry"], where).get("modelled") or {}).get("record") or [])
    if standing.get("from") == "catalogue_stop":
        found += needs_stamp(tracked.experiment(standing["experiment"], where).get("sources") or [])
    if card.get("answer"):
        found += needs_stamp((tracked.experiment(card["answer"]["experiment"], where).get("outcome") or {}).get("sources") or [])
    unique = []
    for source in found:
        key = {"path": source["path"], **({"where": source["where"]} if source.get("where") else {})}
        if key not in unique:
            unique.append(key)
    return unique


def named_revisions(card, tracked: Tracked):
    """The revisions a card names that the catalogue already gives: each must be on main."""
    found = set()
    where = f"card {card['id']}"
    for identifier in (card.get("replay") or {}).get("experiments") or []:
        experiment = tracked.experiment(identifier, where)
        for source in (experiment.get("sources") or []) + ((experiment.get("outcome") or {}).get("sources") or []):
            if source.get("revision"):
                found.add(source["revision"])
    return found


# --------------------------------------------------------------------------- the gathering


def verdict_word(value):
    """A verdict as its file words it: True for passed or "pass", False for failed or "fail", None for anything else."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in ("pass", "passed"):
        return True
    if isinstance(value, str) and value.lower() in ("fail", "failed"):
        return False
    return None


def item_passed(item):
    """Whether one judged item of a verdict passed, in the words its file uses (passed, pass_ or verdict)."""
    if not isinstance(item, dict):
        return verdict_word(item)
    for key in ("passed", "pass_", "verdict"):
        if key in item and verdict_word(item[key]) is not None:
            return verdict_word(item[key])
    return None


def overall_of(obj):
    for key in ("passed", "verdict"):
        if isinstance(obj, dict) and key in obj and verdict_word(obj[key]) is not None:
            return verdict_word(obj[key])
    return None


READERS = ("criteria", "items", "list", "named", "rows", "tally", "compared", "one")


def counted(data, how: str, at: str | None, where: str, tally=None, tables=None):
    """A verdict's own tally: (passed, of, not evaluable, the field it came from, the run passed). Each reader counts what
    its layout of verdict file holds and nothing else:
    criteria  a list of criteria, those whose judged is true;
    items     a mapping of items, those whose judged is true where any says (else every one);
    list      a list of items (at `at`, else `items`);
    named     a mapping of names to a verdict, each "pass"/"fail" or an object with its verdict (the rest skipped);
    rows      a mapping of rows, with its tally;
    tally     the file's own passed, failed and not evaluable numbers (`tally` names its fields);
    compared  a comparison's own tables (`tables`, dotted paths): each table's `compared` and `failed` numbers, or,
              in a table of quantities, each quantity's; of is their compared, passed their compared less failed;
    one       a single verdict: one judged item."""
    prefix = f"{at}." if at and how not in ("list", "named") else (f"{at}: " if at else "")
    obj = dig(data, at, where) if (at and how not in ("list", "named")) else data
    not_evaluable = 0
    if how == "criteria":
        rows = obj.get("criteria")
        if not isinstance(rows, list):
            raise Breach(f"{where}: no criteria list")
        judged = [row for row in rows if row.get("judged") is True]
        passed = sum(1 for row in judged if row.get("passed") is True)
        field = f"{prefix}criteria: the entries whose judged is true, and those of them whose passed is true"
        overall = overall_of(obj)
    elif how == "items":
        items = obj.get("items")
        if not isinstance(items, dict):
            raise Breach(f"{where}: no items")
        flagged = any(isinstance(item, dict) and "judged" in item for item in items.values())
        judged = [item for item in items.values() if not flagged or item.get("judged") is True]
        passed = sum(1 for item in judged if item_passed(item) is True)
        field = f"{prefix}items: " + ("the items whose judged is true, and those of them that passed" if flagged else "every item, and those that passed")
        overall = overall_of(obj)
    elif how == "list":
        items = dig(data, at or "items", where)
        if not isinstance(items, list):
            raise Breach(f"{where}: no list of items")
        judged = items
        passed = sum(1 for item in judged if item_passed(item) is True)
        field = f"{at or 'items'}: every item, and those that passed"
        overall = overall_of(data)
    elif how == "named":
        named = dig(data, at, where) if at else data
        judged = [value for value in named.values() if item_passed(value) is not None]
        passed = sum(1 for value in judged if item_passed(value) is True)
        field = f"{at + ': ' if at else ''}every name with a verdict, and those that passed"
        overall = overall_of(named) if overall_of(named) is not None else passed == len(judged)
    elif how == "rows":
        rows = obj.get("rows")
        if not isinstance(rows, dict):
            raise Breach(f"{where}: no rows")
        judged = list(rows.values())
        passed = sum(1 for row in judged if row.get("passed") is True)
        counts = obj.get("tally") or {}
        if counts and (counts.get("rows") != len(judged) or counts.get("passed") != passed):
            raise Breach(f"{where}: the rows count {passed} of {len(judged)}, the tally {counts}")
        field = f"{prefix}rows: every row, and those whose passed is true (its tally gives the same)"
        overall = passed == len(judged)
    elif how == "tally":
        names = tally or {}
        passed, failed = obj.get(names.get("passed", "passed")), obj.get(names.get("failed", "failed"))
        not_evaluable = obj.get(names["not_evaluable"], 0) if names.get("not_evaluable") else 0
        if not all(isinstance(value, int) for value in (passed, failed, not_evaluable)):
            raise Breach(f"{where}: the tally's fields are not numbers")
        judged = [None] * (passed + failed + not_evaluable)
        field = f"{prefix}" + ", ".join(names.get(key, key) for key in ("passed", "failed") ) + (f" and {names['not_evaluable']}" if names.get("not_evaluable") else "") + ": the file's own numbers"
        overall = overall_of(obj)
        if overall is True and (failed or not_evaluable):
            raise Breach(f"{where}: the verdict passes with {failed} failed")
    elif how == "compared":
        # A comparison file that states, per table or per quantity of a table, how many rows it compared and how many
        # failed (FR-7's F4: closed.quantities, clamped.quantities, persistence). Only those numbers are counted.
        if not tables:
            raise Breach(f"{where}: the compared reader names its tables")
        compared = failed = 0
        for name in tables:
            table = dig(data, name, where)
            if not isinstance(table, dict):
                raise Breach(f"{where}: {name} is not a table")
            rows = [table] if "compared" in table else list(table.values())
            for row in rows:
                if not (isinstance(row, dict) and all(isinstance(row.get(key), int) and not isinstance(row.get(key), bool) for key in ("compared", "failed"))):
                    raise Breach(f"{where}: {name} states no compared and failed numbers")
                if not 0 <= row["failed"] <= row["compared"]:
                    raise Breach(f"{where}: {name} fails {row['failed']} of {row['compared']}")
                compared += row["compared"]
                failed += row["failed"]
        passed = compared - failed
        judged = range(compared)  # its length is the count; a list of that many items is never built
        field = " and ".join(tables) + ": " + ("each quantity's" if any("compared" not in dig(data, name, where) for name in tables) else "its") + " compared and failed numbers, summed (passed: compared less failed)"
        overall = overall_of(data)
        if overall is True and failed:
            raise Breach(f"{where}: the comparison passes with {failed} rows failed")
    elif how == "one":
        judged = [obj]
        overall = overall_of(obj)
        passed = 1 if overall else 0
        field = f"{prefix}verdict: its one verdict"
    else:
        raise Breach(f"{where}: no reader {how!r}")
    if not isinstance(overall, bool):
        raise Breach(f"{where}: the verdict states no passed")
    if not judged:
        raise Breach(f"{where}: nothing judged")
    if how not in ("tally", "compared") and overall != (passed == len(judged)):
        raise Breach(f"{where}: the verdict says passed {overall} with {passed} of {len(judged)}")
    return passed, len(judged), not_evaluable, field, overall


def counts_said(text: str, noun: str, bare: bool, passed: int, of: int):
    """The counts an entry of the record words in the verdict's own noun ("criteria", "items", "rows" …), against the
    verdict's: (those that give the same, those that differ). "N of M" gives both numbers; "all N" gives the whole,
    and gives the same only where every one passed. Within one bullet (`bare`), "N of M" with no noun counts too."""
    unit = rf"(?:judged\s+)?{re.escape(noun)}"
    same, differ = [], []
    pairs = [(int(match.group(1)), int(match.group(2)), match.group(0)) for match in re.finditer(rf"\b(\d+)\s+of\s+(\d+)\s+{unit}\b", text)]
    if bare:
        pairs += [(int(a), int(b), match.group(0)) for match in COUNT_OF_BARE.finditer(text) for a, b in [match.groups()] if not any(match.group(0) in words for _, _, words in pairs)]
    for a, b, words in pairs:
        (same if (a, b) == (passed, of) else differ).append(words)
    for match in re.finditer(rf"\b[Aa]ll\s+(\d+)\s+(?:of\s+(?:its|their)\s+)?{unit}\b", text):
        whole = int(match.group(1))
        if whole != of:
            differ.append(match.group(0))
        elif passed == of:
            same.append(match.group(0))
    return same, differ


WRITTEN = re.compile(r"\b(\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December) (\d{4})\b")
MONTHS = {name: index + 1 for index, name in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"))}


def date_in(line: str):
    """A line's date: an ISO timestamp's, or one written out ("11 November 2026")."""
    match = DATE.search(line)
    if match:
        return match.group(1)
    match = WRITTEN.search(line)
    return f"{match.group(3)}-{MONTHS[match.group(2)]:02d}-{int(match.group(1)):02d}" if match else None


def parts_gloss(ids):
    """The tool's own words for entries of one numbered criterion judged in parts, from the entries' own names
    ("A6 is judged in 2 parts: A6_timestep_order and A6_resolution.")."""
    groups = {}
    for identifier in ids:
        groups.setdefault(identifier.split("_")[0], []).append(identifier)
    return " ".join(f"{head} is judged in {len(names)} parts: {', '.join(names[:-1])} and {names[-1]}." for head, names in groups.items() if len(names) > 1) or None


def gather_entry(locator, roots, main, evidence: Evidence | None, repository: Repository, where: str):
    progress = locator.get("progress")
    reading = {"read": locator}
    if not progress:
        raise Breach(f"{where}: an entry of the record names its PROGRESS.md entry")
    entry = find_entry(roots, progress["entry"], where)
    lead = said(entry.lead(), where)
    reading["says"] = lead
    reading["source"] = {"path": "PROGRESS.md", "where": sentences(lead)[0].rstrip("."), "revision": main}
    item = None
    if progress.get("item"):
        item = find_item(entry, progress["item"], where)
        reading["item"] = own_words(item, where)
        reading["source"]["where"] += f"; {plain(item.lead() or progress['item']).rstrip(':.')}"
    if progress.get("scope"):
        scope = find_item(entry, progress["scope"], where)
        words = with_children(scope, where)
        reading["scope"] = {"says": words, "source": {"path": "PROGRESS.md", "where": f"{sentences(lead)[0].rstrip('.')}; {plain(scope.lead() or progress['scope']).rstrip(':.')}", "revision": main}}
    verdict = locator.get("verdict")
    if verdict:
        if evidence is None:
            raise Breach(f"{where}: a verdict file is read from the evidence (--evidence)")
        run = {"evidence": verdict["evidence"], "within": list(verdict.get("within") or [])}
        def at_run(sub):
            return {"evidence": run["evidence"], "within": list(sub["within"]) if "within" in sub else run["within"]}
        files = [list(name) for name in verdict["files"]] if verdict.get("files") else [list(verdict["file"])]
        datas = [read_json(evidence.path(run["evidence"], run["within"], name, where)) for name in files]
        if len(datas) == 1:
            data = datas[0]
            passed, of, not_evaluable, field, overall = counted(data, verdict["read"], verdict.get("at"), where, verdict.get("tally"), verdict.get("tables"))
        else:
            # Several files, each one verdict (at `at`): the count is of the files whose verdict passed.
            data = datas[0]
            words = [verdict_word(dig(one, verdict.get("at") or "verdict", where)) for one in datas]
            if any(word is None for word in words):
                raise Breach(f"{where}: a file states no verdict at {verdict.get('at') or 'verdict'}")
            passed, of, not_evaluable = sum(1 for word in words if word), len(words), 0
            field = f"each file's {verdict.get('at') or 'verdict'}, and those that passed"
            overall = passed == of
        count = {"passed": passed, "of": of, "unit": verdict["unit"], "from": {**run, "file": files[0], "field": field}, "confirmed_by": []}
        if len(files) > 1:
            count["from"]["files"] = files
        if not_evaluable:
            count["not_evaluable"] = not_evaluable
        confirm = verdict.get("confirm")
        if confirm:
            other = read_json(evidence.path(run["evidence"], at_run(confirm)["within"], confirm["file"], where))
            if confirm.get("entries"):
                listed = dig(other, confirm["entries"], where)
                if len(listed) != of:
                    raise Breach(f"{where}: {'/'.join(confirm['file'])} lists {len(listed)} {confirm['entries']}, the verdict {of}")
                count["confirmed_by"].append({**at_run(confirm), "file": list(confirm["file"]), "field": f"{confirm['entries']}: its {len(listed)} entries", "says": f"{len(listed)} entries"})
            else:
                if (other.get(confirm["passed"]), other.get(confirm["of"])) != (passed, of):
                    raise Breach(f"{where}: {'/'.join(confirm['file'])} gives {other.get(confirm['passed'])} of {other.get(confirm['of'])}, the verdict {passed} of {of}")
                count["confirmed_by"].append({**at_run(confirm), "file": list(confirm["file"]), "field": f"{confirm['passed']} of {confirm['of']}"})
        scope_text = item.full() if (item is not None and progress.get("count_in") == "item") else entry.full()
        noun = verdict["unit"].split()[-1]
        agreeing, differing = counts_said(plain(scope_text), noun, progress.get("count_in") == "item", passed, of)
        protocol = data.get("protocol_id") if isinstance(data.get("protocol_id"), str) else ((data.get("protocol") or {}).get("id") if isinstance(data.get("protocol"), dict) else None)
        result = {"run": run, "protocol": protocol if isinstance(protocol, str) else None, "passed": overall}
        if differing and not agreeing and not count["confirmed_by"]:
            result["count"] = None
            result["count_withheld"] = WITHHELD.format(passed=passed, of=of, said=" and ".join(f"“{text}”" for text in differing))
            result["count_read"] = count
        else:
            if agreeing:
                count["confirmed_by"].append({**reading["source"], "says": agreeing[0]})
            if differing and not agreeing:
                # The record's entry words the count otherwise, and a file of the run confirms the verdict's: both are
                # kept, the entry's words beside the count, and the parts that explain them in the tool's own words.
                count["differs_from"] = [{**reading["source"], "says": text} for text in differing]
                ids = [row.get("id") for row in (dig(data, verdict["at"], where) if verdict.get("at") else data).get("criteria", []) if isinstance(row, dict) and row.get("judged") is True]
                gloss = parts_gloss([identifier for identifier in ids if isinstance(identifier, str)])
                if gloss:
                    count["note"] = gloss
            result["count"] = count
        day = verdict["day"]
        place = at_run(day)
        text = evidence.path(place["evidence"], place["within"], day["file"], where).read_text(encoding="utf-8")
        lines = [line for line in text.splitlines() if re.search(day["line"], line)] if day.get("line") else text.splitlines()
        dates = [found for line in lines for found in [date_in(line)] if found]
        if not dates:
            raise Breach(f"{where}: {'/'.join(day['file'])} holds no date" + (f" on a line matching {day['line']!r}" if day.get("line") else ""))
        result["day"] = {"date": dates[0], "from": {**place, "file": list(day["file"]), "field": (f"the date of the first line matching {day['line']!r}" if day.get("line") else "the date of its first timestamp")}}
        snapshot = verdict.get("snapshot")
        if snapshot:
            place = at_run(snapshot)
            path = evidence.path(place["evidence"], place["within"], snapshot["file"], where)
            if snapshot.get("text"):
                found = re.search(r"\b[0-9a-f]{7,40}\b", path.read_text(encoding="utf-8"))
                value, field = (found.group(0) if found else None), "its revision, as the file writes it"
            else:
                value, field = dig(read_json(path), snapshot["field"], where), snapshot["field"]
            if not (isinstance(value, str) and SHORT.match(value)):
                raise Breach(f"{where}: {field} is not a revision: {value!r}")
            try:
                full = repository.full(value)
            except Breach:
                full = value if FULL.match(value) else None
            origin = {**place, "file": list(snapshot["file"]), "field": field}
            result["snapshot"] = {"revision": full, "from": origin} if (full and repository.on_main(full, main)) else {"revision": None, "says": SNAPSHOT_NOT_ON_MAIN, "from": origin}
        reading["verdict"] = result
    return reading


def gather_switch(locator, main, repository: Repository, where: str):
    revision = repository.full(locator["revision"])
    if not repository.on_main(revision, main):
        raise Breach(f"{where}: {revision[:8]} is not on main")
    def paragraph(at):
        lines = repository.read(at, locator["path"]).splitlines()
        heading = f"**{locator['heading']}**"
        starts = [index for index, line in enumerate(lines) if line.strip() == heading]
        if len(starts) != 1:
            raise Breach(f"{where}: {locator['path']} at {at[:8]} has {len(starts)} lines {heading!r}")
        items = [node for node in bullets("\n".join(lines[starts[0] + 1:]))]
        if len(items) < locator["items"]:
            raise Breach(f"{where}: fewer than {locator['items']} items under {heading!r}")
        return [said(node.full(), where) for node in items[: locator["items"]]]
    items = paragraph(revision)
    if paragraph(main) != items:
        raise Breach(f"{where}: the paragraph {locator['heading']!r} differs at {main[:8]} from {revision[:8]}")
    return {"read": locator, "heading": locator["heading"].rstrip("."), "items": items, "source": {"path": locator["path"], "where": locator["where"], "revision": revision}, "same_at": main}


def gather_rows(locator, record_readings, evidence: Evidence, repository: Repository, main, where: str):
    verdict_locator = record_readings[locator["record"]]["read"]["verdict"]
    data = read_json(evidence.path(verdict_locator["evidence"], verdict_locator.get("within") or [], verdict_locator["file"], where))
    reference = locator["reference"]
    revision = repository.full(dig(data, reference["revision_field"], where))
    if not repository.on_main(revision, main):
        raise Breach(f"{where}: the references' revision {revision[:8]} is not on main")
    lines = repository.read(revision, reference["path"]).splitlines()
    start = [index for index, line in enumerate(lines) if line.strip() == f"## {reference['table']}"]
    if len(start) != 1:
        raise Breach(f"{where}: {reference['path']} has {len(start)} sections {reference['table']!r}")
    table = {}
    for line in lines[start[0] + 1:]:
        if line.startswith("## "):
            break
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line)]
        if len(cells) > 4 and re.match(r"[A-Z0-9]+-\d+\Z", cells[1]):
            table[cells[1]] = cells
    folder = reference["path"].rsplit("/", 1)[0]
    rows = []
    for identifier, row in data["rows"].items():
        titles = sorted({pair.get("title") for pair in (row.get("by_pairs") or {}).values() if pair.get("title")})
        if len(titles) != 1:
            raise Breach(f"{where}: row {identifier} states {len(titles)} claims")
        if identifier not in table:
            raise Breach(f"{where}: {reference['path']} has no row {identifier}")
        lead = re.match(r"((?:`[^`]+`(?:,\s*|\s+and\s+)?)+)", table[identifier][3])
        modules = re.findall(r"`([^`]+)`", lead.group(1)) if lead else []
        for module in modules:
            if not repository.exists(revision, f"{folder}/{module}"):
                raise Breach(f"{where}: {folder}/{module} is not at {revision[:8]}")
        rows.append({
            "id": identifier,
            "claim": titles[0],
            "passed": row.get("passed") is True,
            "reference": {"path": reference["path"], "where": f"{reference['table']}: row {identifier}", "revision": revision},
            "modules": [{"path": f"{folder}/{module}", "revision": revision} for module in modules],
        })
    return {"read": locator, "rows": rows, "from": {**{"evidence": verdict_locator["evidence"], "within": list(verdict_locator.get("within") or [])}, "file": list(verdict_locator["file"]), "field": "rows: each row's passed, and the claim its pairs state"}}


def gather_runs(identifier, tracked: Tracked, evidence: Evidence, where: str):
    chosen = tracked.selection.get(identifier)
    if not isinstance(chosen, dict) or chosen.get("runs") != "index":
        return None
    sys.path.insert(0, str(TOOLS))
    sys.dont_write_bytecode = True
    import adapt_run  # the viewer's own adapter: its rule for which packages a run folder offers

    within = list(chosen.get("within") or [])
    root = evidence.path(chosen["evidence_folder"], within, (), where)
    names = adapt_run.runs_in_index(root)
    index = root / "index.json"
    if index.is_file():
        rule = "index.json: its selected runs" if isinstance(read_json(index).get("selected"), list) else "index.json: its packages whose view was written"
        file = ["index.json"]
    else:
        rule, file = "every package holding a view.json", []
    return {"count": len(names), "from": {"evidence": chosen["evidence_folder"], "within": within, "file": file, "field": rule}}


def gather(source, tracked: Tracked, repository: Repository, evidence: Evidence | None):
    main = repository.full(source["record"]["revision"])
    if main != source["record"]["revision"]:
        raise Breach("the source names the record's revision in full")
    progress = repository.read(main, "PROGRESS.md")
    roots = bullets(progress)
    if "\n## Runs" not in progress:
        raise Breach("PROGRESS.md has no section Runs")
    # Every entry of the runs that reports a judged run or a registered qualification, by its lead's words: each must be
    # on a card or left out with a reason (tests/experiment_cards.test.mjs holds it).
    judged = [said(node.lead(), "PROGRESS.md") for node in bullets(progress[progress.index("\n## Runs"):]) if node.lead() and JUDGED_LEAD.search(plain(node.lead()))]
    cards = {}
    unplaced = []
    revisions = {tracked.map_revision}
    for card in source["cards"]:
        where = f"card {card['id']}"
        reading = {}
        if card.get("record"):
            reading["record"] = [gather_entry(locator, roots, main, evidence, repository, f"{where}, entry {index + 1}") for index, locator in enumerate(card["record"])]
            for entry in reading["record"]:
                snapshot = (entry.get("verdict") or {}).get("snapshot") or {}
                if snapshot.get("revision"):
                    revisions.add(snapshot["revision"])
        if card.get("switch"):
            reading["switch"] = gather_switch(card["switch"], main, repository, where)
            revisions.add(reading["switch"]["source"]["revision"])
        if card.get("rows"):
            reading["rows"] = gather_rows(card["rows"], reading["record"], evidence, repository, main, where)
            revisions.update(row["reference"]["revision"] for row in reading["rows"]["rows"])
        runs = {}
        for identifier in (card.get("replay") or {}).get("experiments") or []:
            found = gather_runs(identifier, tracked, evidence, where) if evidence is not None else None
            if found:
                runs[identifier] = found
        if runs:
            reading["runs"] = runs
        stamped = []
        for found in sources_to_stamp(card, tracked):
            if not repository.exists(main, found["path"]):
                raise Breach(f"{where}: {found['path']} is not at {main[:8]}")
            if found.get("where") and not place_found(repository.read(main, found["path"]), found["where"]):
                unplaced.append({"card": card["id"], **found, "revision": main})
            stamped.append({**found, "revision": main})
        if stamped:
            reading["stamped"] = stamped
        if card.get("map"):
            # The map's sources are its own, at its revision: only listed here where they are not found there,
            # or not found at the record's revision (for the coordinator; the map's words are not changed here).
            for item in tracked.part(card["map"], where).get("sources") or []:
                for revision in (tracked.map_revision, main):
                    if not repository.exists(revision, item["path"]):
                        unplaced.append({"card": card["id"], "part": card["map"], "path": item["path"], **({"where": item["where"]} if item.get("where") else {}), "revision": revision, "missing": "file"})
                    elif item.get("where") and not place_found(repository.read(revision, item["path"]), item["where"]):
                        unplaced.append({"card": card["id"], "part": card["map"], "path": item["path"], "where": item["where"], "revision": revision, "missing": "place"})
        revisions |= named_revisions(card, tracked)
        cards[card["id"]] = reading
    checked = []
    for revision in sorted(revisions):
        full = repository.full(revision)
        if not repository.on_main(full, main):
            raise Breach(f"{full[:8]} is named on a card and is not on main {main[:8]}")
        checked.append(full)
    return {
        "format": READINGS_FORMAT,
        "note": "What tools/build_cards.py --gather read from the record for the Experiments landing's cards: each reading with the file and field it came from, and the locator it answered (read). Written by the tool; never edited by hand.",
        "record": {"revision": main},
        "map": {"revision": tracked.map_revision},
        "on_main": checked,
        "judged_entries": judged,
        "unplaced": [{key: without_clock(value) if key == "where" else value for key, value in item.items()} for item in unplaced],
        "cards": cards,
    }


# --------------------------------------------------------------------------- the build


def stamp_map_sources(sources, revision):
    out = []
    for source in sources or []:
        item = {"path": source["path"]}
        if source.get("where"):
            item["where"] = without_clock(source["where"])
        item["revision"] = source.get("revision") or revision
        out.append(item)
    return out


def stamped_sources(sources, stamps, where):
    out = []
    for source in sources or []:
        if source.get("revision"):
            out.append({"path": source["path"], **({"where": without_clock(source["where"])} if source.get("where") else {}), "revision": source["revision"]})
            continue
        key = {"path": source["path"], **({"where": source["where"]} if source.get("where") else {})}
        match = [stamp for stamp in stamps if {k: v for k, v in stamp.items() if k != "revision"} == key]
        if not match:
            raise Breach(f"{where}: {source['path']} has no revision and the readings stamp none for it: gather again")
        out.append({"path": source["path"], **({"where": without_clock(source["where"])} if source.get("where") else {}), "revision": match[0]["revision"]})
    return out


def asks_of(card, tracked: Tracked, where):
    asks = card.get("asks")
    if asks is None or isinstance(asks, str):
        return asks
    if "catalogue" in asks:
        text = dig(tracked.experiment(asks["catalogue"], where), asks["path"], where)
    elif "map" in asks:
        text = tracked.part(asks["map"], where)["plain"]
    else:
        raise Breach(f"{where}: asks names neither a catalogue entry nor a map part")
    if asks.get("sentence"):
        text = sentences(text)[asks["sentence"] - 1]
    return text


def standing_of(card, tracked: Tracked, reading, where):
    stamps = reading.get("stamped") or []
    if card.get("map"):
        part = tracked.part(card["map"], where)
        status = part.get("status")
        standing = {
            "from": "map",
            "part": part["id"],
            "label": part["label"],
            "status": status,
            "level": {"label": tracked.statuses[status]["label"], "says": tracked.statuses[status]["description"]} if status else None,
            "as_of": part.get("as_of"),
            "says": part["plain"],
            "sources": stamp_map_sources(part.get("sources"), tracked.map_revision),
        }
        # The tests the map's part names among its sources, as the map names them (none where it names none).
        standing["tests"] = [source["path"] for source in standing["sources"] if source["path"].startswith("tests/")]
        if not status:
            standing["first"] = sentences(part["plain"])[0]
            if not card.get("none"):
                raise Breach(f"{where}: the map states no level for {part['id']}, and the card gives no reason for none")
            standing["none"] = card["none"]
        return standing
    given = card.get("standing") or {}
    if given.get("from") == "catalogue":
        outcome = tracked.experiment(given["experiment"], where).get("outcome")
        if not outcome:
            raise Breach(f"{where}: {given['experiment']} has no outcome in the catalogue")
        return {"from": "catalogue", "experiment": given["experiment"], "status": None, "level": None, "as_of": None, "says": outcome["status"], "text": outcome["text"], "sources": stamped_sources(outcome.get("sources"), stamps, where)}
    if given.get("from") == "catalogue_stop":
        stop = (tracked.experiment(given["experiment"], where).get("stops") or {}).get(given["stop"])
        if not stop:
            raise Breach(f"{where}: {given['experiment']} has no stop {given['stop']!r}")
        sources = tracked.experiment(given["experiment"], where).get("sources") or []
        # The test sheet's sources name their places with the word "example", which never stands beside invented
        # numbers on a card: their paths are carried, their places left out.
        carried = [{"path": item["path"], "revision": item["revision"]} for item in stamped_sources(sources, stamps, where)]
        return {"from": "catalogue", "experiment": given["experiment"], "status": None, "level": None, "as_of": None, "none": stop["label"], "sources": carried}
    if given.get("from") == "entry":
        entry = tracked.entry(given["entry"], where)
        modelled = entry.get("modelled") or {}
        return {"from": "entry", "entry": given["entry"], "label": entry["label"], "status": None, "level": None, "state": modelled.get("state"), "as_of": None, "says": modelled["text"], "sources": stamped_sources(modelled.get("record"), stamps, where)}
    raise Breach(f"{where}: no standing: a card reads a map part, the catalogue or an entry")


def runs_of(identifier, tracked: Tracked, reading, card, where):
    gathered = (reading.get("runs") or {}).get(identifier)
    if gathered:
        return gathered["count"], gathered["from"]
    chosen = tracked.selection.get(identifier)
    if isinstance(chosen, dict) and isinstance(chosen.get("runs"), list):
        return len(chosen["runs"]), {"file": "data/replays/selection.json", "field": f"{identifier}.runs"}
    if isinstance(chosen, dict) and chosen.get("runs") == "index":
        raise Breach(f"{where}: {identifier}'s runs are read from its run folder's index: gather them (--evidence)")
    folder = (card.get("replay") or {}).get("runs_from")
    if folder:
        root = ROOT / folder
        names = sorted(path.name for path in root.iterdir() if path.is_dir() and (path / "summary.json").is_file())
        if not names:
            raise Breach(f"{where}: {folder} holds no run")
        return len(names), {"folder": folder, "field": "its folders holding a summary.json"}
    raise Breach(f"{where}: no count of runs for {identifier}")


def record_of(reading):
    out = []
    for entry in reading.get("record") or []:
        item = {key: entry[key] for key in ("says", "item", "source", "scope") if key in entry}
        verdict = entry.get("verdict")
        if verdict:
            item["verdict"] = {key: verdict[key] for key in ("run", "protocol", "passed", "count", "count_withheld", "day", "snapshot") if key in verdict}
        out.append(item)
    return out


def build(source, readings, tracked: Tracked):
    if source.get("format") != SOURCE_FORMAT:
        raise Breach(f"the source's format is {source.get('format')!r}")
    if readings.get("format") != READINGS_FORMAT:
        raise Breach(f"the readings' format is {readings.get('format')!r}")
    if readings["record"]["revision"] != source["record"]["revision"]:
        raise Breach("the readings were gathered at another revision of the record: gather again")
    bands = []
    for band in source["bands"]:
        if band.get("from_status"):
            status = tracked.statuses[band["from_status"]]
            built = {"id": band["id"], "label": status["label"], "says": status["description"], "status": band["from_status"], "cards": []}
        elif band.get("levels"):
            # A band of several of the map's levels: its words are typed, and each card in it shows its own level.
            levels = [{"id": level, "label": tracked.statuses[level]["label"], "says": tracked.statuses[level]["description"]} for level in band["levels"]]
            built = {"id": band["id"], "label": band["label"], "says": band["says"], "status": None, "levels": levels, "cards": []}
        else:
            built = {"id": band["id"], "label": band["label"], "says": band["says"], "cards": []}
        # The words of the control a band folds behind on the landing (optional, typed): what the band holds, true of every
        # card in it, after the control's "Show" or "Hide"; a band without them gets a plain control from its own label.
        if "control" in band:
            if not isinstance(band["control"], str) or not band["control"].strip() or band["control"] != band["control"].strip():
                raise Breach(f"the band {band['id']}: its control's words are a plain string, or left out")
            built = {**{key: value for key, value in built.items() if key != "cards"}, "control": band["control"], "cards": []}
        bands.append(built)
    if [band["id"] for band in bands] != list(BANDS):
        raise Breach(f"the bands are {[band['id'] for band in bands]}, the format's are {list(BANDS)}")
    by_band = {band["id"]: band for band in bands}
    cards, experiments, entries = [], [], []
    seen = set()
    for card in source["cards"]:
        where = f"card {card['id']}"
        if card["id"] in seen:
            raise Breach(f"{where}: twice")
        seen.add(card["id"])
        if card["band"] not in BANDS or card["kind"] not in KINDS:
            raise Breach(f"{where}: band {card['band']!r} or kind {card['kind']!r} is not the format's")
        reading = readings["cards"].get(card["id"], {})
        for key in ("record", "switch", "rows"):
            typed = card.get(key)
            got = reading.get(key)
            if typed and (not got or (key == "record" and [entry["read"] for entry in got] != typed) or (key != "record" and got["read"] != typed)):
                raise Breach(f"{where}: the readings for {key} answer another locator, or none: gather again")
        out = {"id": card["id"], "band": card["band"], "kind": card["kind"], "title": card["title"], "asks": asks_of(card, tracked, where)}
        if card.get("shows"):
            out["shows"] = card["shows"]
        out["standing"] = standing_of(card, tracked, reading, where)
        band = by_band[card["band"]]
        status = out["standing"].get("status")
        if band.get("status") and status != band["status"]:
            raise Breach(f"{where}: in the band {band['label']!r}, its map part's status is {status!r}")
        if band.get("levels"):
            judged_runs = [entry for entry in reading.get("record") or [] if entry.get("verdict")]
            if out["standing"].get("from") != "map" or status not in [level["id"] for level in band["levels"]]:
                raise Breach(f"{where}: in the band {band['label']!r}, its map part's status is {status!r}")
            if status not in ("qualified", "failed") and not judged_runs:
                raise Breach(f"{where}: in the band {band['label']!r} at the level {status!r}, it reads no judged run's verdict file")
        if card.get("answer"):
            outcome = tracked.experiment(card["answer"]["experiment"], where).get("outcome") or {}
            out["answer"] = {"from": "catalogue", "experiment": card["answer"]["experiment"], "judged": bool(outcome.get("judged")), "answer": outcome.get("answer"), "label": outcome.get("label"), "text": outcome.get("text"), "sources": stamped_sources(outcome.get("sources"), reading.get("stamped") or [], where)}
        if card.get("cite"):
            text = tracked.experiment(card["cite"]["catalogue"], where)["plain"]
            start = text.find(card["cite"]["starts"])
            end = text.find(card["cite"]["ends"], start)
            if start < 0 or end < 0:
                raise Breach(f"{where}: the catalogue's words hold no citation from {card['cite']['starts']!r} to {card['cite']['ends']!r}")
            out["cite"] = {"says": text[start:end + len(card["cite"]["ends"])], "from": {"catalogue": card["cite"]["catalogue"], "field": "plain"}}
        if card.get("switch"):
            switch = reading["switch"]
            out["switch"] = {key: switch[key] for key in ("heading", "items", "source")}
        out["record"] = record_of(reading)
        if card.get("rows"):
            out["rows"] = reading["rows"]["rows"]
            out["rows_from"] = reading["rows"]["from"]
        if card.get("replay"):
            replay = card["replay"]
            given = {"opens": replay["opens"], "experiments": list(replay.get("experiments") or [])}
            parts, total, origins = [], 0, []
            for identifier in given["experiments"]:
                experiment = tracked.experiment(identifier, where)
                count, origin = runs_of(identifier, tracked, reading, card, where)
                total += count
                origins.append({"experiment": identifier, "runs": count, "from": origin})
                parts.append({"experiment": identifier, "label": experiment.get("short") or experiment["label"], "status": (experiment.get("outcome") or {}).get("status"), "runs": count})
            if "entry" in replay["opens"]:
                entry = tracked.entry(replay["opens"]["entry"], where)
                runs = entry.get("runs") or []
                total += len(runs)
                origins.append({"entry": replay["opens"]["entry"], "runs": len(runs), "from": {"file": f"data/models/{replay['opens']['entry']}.json", "field": "runs"}})
                given["run_labels"] = [run["label"] for run in runs]
                entries.append(replay["opens"]["entry"])
            given["runs"] = total
            given["runs_from"] = origins
            if len(parts) > 1:
                given["parts"] = parts
            given["still"] = replay.get("still")
            out["replay"] = given
            experiments += [identifier for identifier in given["experiments"] if identifier not in experiments]
        if card["kind"] == "replay" and not card.get("replay"):
            raise Breach(f"{where}: a replay card names what it opens")
        if card["kind"] == "rows" and not card.get("rows"):
            raise Breach(f"{where}: a rows card names its rows")
        if card["kind"] != "replay":
            out["rerun"] = card.get("rerun")
        by_band[card["band"]]["cards"].append(card["id"])
        cards.append(out)
    for band in bands:
        if not band["cards"]:
            raise Breach(f"the band {band['id']} holds no card")
    # One judged run behind several cards (one run folder): each of its verdicts names the other cards it stands on.
    runs = {}
    for card in cards:
        for entry in card["record"]:
            verdict = entry.get("verdict")
            if verdict:
                runs.setdefault((verdict["run"]["evidence"], tuple(verdict["run"]["within"])), set()).add(card["id"])
    for card in cards:
        for entry in card["record"]:
            verdict = entry.get("verdict")
            if verdict:
                others = sorted(runs[(verdict["run"]["evidence"], tuple(verdict["run"]["within"]))] - {card["id"]})
                if others:
                    verdict["also_on"] = others
    text = dumps(cards)
    if MACHINE.search(text):
        raise Breach("a card names a path of a machine")
    return {
        "format": FORMAT,
        "note": "The Experiments landing's cards, built by tools/build_cards.py from data/replays/cards.source.json (what is typed), the Engine map's overlay, the catalogue's overlay and selection, the model-system entries, and data/replays/cards.readings.json (what was read from the record). Not edited by hand: schema/EXPERIMENT_CARDS.md.",
        "built_from": {"map": {"revision": tracked.map_revision, "as_of": tracked.map.get("as_of")}, "record": {"revision": source["record"]["revision"]}},
        "bands": bands,
        "not_run": source["not_run"],
        "listing": {"experiments": experiments, "entries": entries},
        "cards": cards,
    }


# --------------------------------------------------------------------------- the command


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--readings", type=Path, default=READINGS)
    parser.add_argument("--out", default=str(OUT), help="where the cards are written ('-' for standard output)")
    parser.add_argument("--check", action="store_true", help="fail if the cards (and, with --evidence and --repo, the readings) are stale")
    parser.add_argument("--gather", action="store_true", help="read the record and write the readings, then the cards")
    parser.add_argument("--evidence", type=Path, help="the folder of saved run folders (read only)")
    parser.add_argument("--repo", type=Path, help="a checkout of the engine's repository (read with git only)")
    parser.add_argument("--repo-folders", type=Path, help="for tests: one folder per revision, each holding its files")
    parser.add_argument("--catalogue", type=Path, default=CATALOGUE)
    parser.add_argument("--revision", help="with --gather: the revision of main to read the record at (HEAD: the checkout's own); "
                        "it is written into the source file's record.revision, the one line the tool changes there")
    arguments = parser.parse_args(argv)
    try:
        source = read_json(arguments.source)
        tracked = Tracked(catalogue=arguments.catalogue)
        record = arguments.repo is not None or arguments.repo_folders is not None
        if arguments.gather or (arguments.check and record):
            if not record:
                raise Breach("gathering reads the record: give --repo (and --evidence)")
            repository = Repository(repo=arguments.repo, folders=arguments.repo_folders)
            if arguments.revision:
                if not arguments.gather or arguments.check:
                    raise Breach("--revision moves the record forward: it goes with --gather alone")
                moved = repository.full(arguments.revision if arguments.revision != "HEAD" or arguments.repo is None else repository.git("rev-parse", "HEAD").stdout.strip())
                if moved != source["record"]["revision"]:
                    text = arguments.source.read_text(encoding="utf-8")
                    old = f'"revision": "{source["record"]["revision"]}"'
                    if text.count(old) != 1:
                        raise Breach(f"{arguments.source} names the record's revision more than once")
                    arguments.source.write_text(text.replace(old, f'"revision": "{moved}"'), encoding="utf-8")
                    source = read_json(arguments.source)
                    print(f"the record moves to {moved[:8]} (record.revision in {arguments.source.name})")
            evidence = Evidence(arguments.evidence) if arguments.evidence else None
            readings = gather(source, tracked, repository, evidence)
            written = dumps(readings)
            if arguments.check:
                if not arguments.readings.is_file() or arguments.readings.read_text(encoding="utf-8") != written:
                    print(f"{arguments.readings} is stale against the record: run python3 tools/build_cards.py --gather --evidence ... --repo ...", file=sys.stderr)
                    return 1
            else:
                arguments.readings.write_text(written, encoding="utf-8")
        else:
            if not arguments.readings.is_file():
                raise Breach(f"no readings at {arguments.readings}: gather first")
            readings = read_json(arguments.readings)
        cards = dumps(build(source, readings, tracked))
        if arguments.check:
            target = Path(arguments.out)
            if not target.is_file() or target.read_text(encoding="utf-8") != cards:
                print(f"{target} is stale: run python3 tools/build_cards.py", file=sys.stderr)
                return 1
            print(f"{target.name} is up to date ({len(json.loads(cards)['cards'])} cards)")
            return 0
        if arguments.out == "-":
            sys.stdout.write(cards)
        else:
            Path(arguments.out).write_text(cards, encoding="utf-8")
            print(f"wrote {arguments.out}: {len(json.loads(cards)['cards'])} cards")
        return 0
    except Breach as breach:
        print(f"build_cards: {breach}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
