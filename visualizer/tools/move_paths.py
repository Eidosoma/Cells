#!/usr/bin/env python3
"""Carry the engine map's paths through a move of the engine's source (D188): map, re-form, stop, check.

The engine moves its source by scripted moves, each committed with a path table
(`scripts/moves/<move>-table.json`, `cells.source_moves.path_table@1`): one row per file,
`{old, new, kind, to_legacy, old_module, new_module}`, where `kind` is `move`, `created` (a new
package file) or a declared refactor (`split`, `merge`, with `commit` and `names`). Basenames are
kept. This tool reads such a table as data and carries the overlay (data/architecture/overlay.json)
through it:

  rewrite  Map every part's files and every cited source path through the table, re-form each
           part's patterns, and write the new overlay to --out. It stops, with exit status 2 and a
           list, on what needs a person's eye: a split or merge row; a file a part held that the
           table does not name and that is gone; a cited source that is gone; a part left with no
           file; a file new to the map that no part, or only a catch-all, would take.
  check    Ownership before against after: every file that stood in a part before stands in the
           same part after, at its new path. It names the files that are new to the map and the
           part each falls in, and any catch-all that gains a file. Exit status 1 if anything is
           wrong.

  python3 tools/move_paths.py rewrite --table T --overlay O --before B --after A --out NEW [--report R]
  python3 tools/move_paths.py check --table T --before-overlay O1 --after-overlay O2 --before B --after A [--report R]

An overlay may set a folder of held legacy code (`legacy.folder`, for example src/cells/legacy/):
the extractor leaves the files under it out of the picture, so a file there needs no part, and is
counted as left out, not as unplaced.

B and A are each a checkout (its `git ls-files` is read) or a text file of tracked paths, one per
line. With a checkout, the files the extractor places through the operator registry (not by a
pattern) are read with the extractor's own reader, as it does; with a list, --preplaced-before
and --preplaced-after (JSON objects, path -> part) stand in for them.

Standard library only. It changes nothing but --out and --report, and never imports or runs
engine code (the extractor's reader parses the source with `ast`).
"""

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = "src/cells/"


# ---------------------------------------------------------------- reading


def glob_regex(pattern):
    """A path glob where * stays inside one directory and ** crosses directories (the extractor's rule)."""
    out, index = [], 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            out.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            out.append(".*")
            index += 2
        elif pattern[index] == "*":
            out.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            out.append("[^/]")
            index += 1
        else:
            out.append(re.escape(pattern[index]))
            index += 1
    return re.compile("".join(out) + r"\Z")


def is_glob(pattern):
    return any(mark in pattern for mark in "*?")


def read_table(path):
    """The path table: moves (old -> new), created files, and declared refactors."""
    table = json.loads(Path(path).read_text(encoding="utf-8"))
    if table.get("kind") != "cells.source_moves.path_table@1":
        raise SystemExit(f"{path}: not a path table (kind {table.get('kind')!r})")
    moves, created, refactors = {}, [], []
    for row in table["rows"]:
        if row["kind"] == "move":
            if row["old"] in moves:
                raise SystemExit(f"{path}: {row['old']} is moved twice")
            moves[row["old"]] = row["new"]
        elif row["kind"] == "created":
            created.append(row["new"])
        else:
            refactors.append(row)
    return {"move": table.get("move"), "moves": moves, "created": created, "refactors": refactors}


def read_files(where):
    """Tracked paths of a checkout (git ls-files), or of a text file with one path per line."""
    where = Path(where)
    if where.is_dir():
        done = subprocess.run(["git", "-C", str(where), "ls-files"], capture_output=True, text=True, check=True)
        return set(line for line in done.stdout.splitlines() if line)
    return set(line.strip() for line in where.read_text(encoding="utf-8").splitlines() if line.strip())


def preplaced_of(where, overlay, given):
    """Files placed by the operator registry, not by a pattern: from a checkout, or as given."""
    if given:
        return json.loads(Path(given).read_text(encoding="utf-8"))
    where = Path(where)
    if not where.is_dir():
        return {}
    sys.path.insert(0, str(HERE))
    import extract_architecture  # our own reader: parses the engine's source, never runs it

    build = extract_architecture.Build(where, overlay)
    build.operators()
    return dict(build.owner)


def legacy_folder(overlay):
    """The folder whose files the map leaves out as legacy code, if the overlay sets one."""
    return (overlay.get("legacy") or {}).get("folder")


def owners(overlay, files, preplaced):
    """Each file's part, as the extractor assigns them: the registry's first, then the first matching pattern."""
    owner = {path: part for path, part in preplaced.items() if path in files}
    compiled = [(part, [glob_regex(p) for p in part.get("match", [])]) for part in overlay["components"]]
    for path in sorted(files):
        if path in owner:
            continue
        for part, patterns in compiled:
            if any(p.match(path) for p in patterns):
                owner[path] = part["id"]
                break
    return owner


# ---------------------------------------------------------------- rewriting


def split_glob(pattern):
    """A glob's literal directory (up to the last / before its first wildcard) and the rest."""
    first = min(pattern.index(mark) for mark in "*?" if mark in pattern)
    cut = pattern.rfind("/", 0, first) + 1
    return pattern[:cut], pattern[cut:]


def reform(pattern, files, moves):
    """New patterns for the files a glob held that moved: its tail kept under each new directory."""
    head, tail = split_glob(pattern)
    groups, literal = defaultdict(list), []
    for path in files:
        new = moves[path]
        rest = path[len(head):]
        if path.startswith(head) and new.endswith(rest):
            groups[new[: len(new) - len(rest)]].append(new)
        else:
            literal.append(new)  # its place inside the glob's tail changed: name it
    return [(prefix + tail, sorted(news)) for prefix, news in sorted(groups.items())], sorted(literal)


def rewrite(overlay, table, before, after, preplaced_before):
    """The overlay carried through the table, and what needs an eye."""
    moves = table["moves"]
    owner = owners(overlay, before, preplaced_before)
    held = defaultdict(list)
    for path, part in owner.items():
        held[part].append(path)
    stops, notes, changed = [], [], []
    new_overlay = json.loads(json.dumps(overlay))
    for part in new_overlay["components"]:
        patterns = part.get("match")
        if not patterns:
            continue
        compiled = [(p, glob_regex(p)) for p in patterns]
        mine = defaultdict(list)
        for path in sorted(held.get(part["id"], [])):
            first = next((p for p, regex in compiled if regex.match(path)), None)
            if first is not None:
                mine[first].append(path)
        out = []
        for pattern in patterns:
            files = mine.get(pattern, [])
            if not is_glob(pattern):
                if pattern in moves:
                    out.append(moves[pattern])
                elif pattern in after or not files:
                    out.append(pattern)
                    if pattern not in after and pattern not in before:
                        notes.append({"part": part["id"], "pattern": pattern, "says": "matched no file before the move, and none after"})
                else:
                    stops.append({"kind": "gone", "part": part["id"], "path": pattern, "says": "the table does not name it, and it is not in the tree after the move"})
                    out.append(pattern)
                continue
            stayed = [path for path in files if path not in moves]
            moved = [path for path in files if path in moves]
            for path in stayed:
                if path not in after:
                    stops.append({"kind": "gone", "part": part["id"], "path": path, "says": "the table does not name it, and it is not in the tree after the move"})
            if stayed or not moved:
                out.append(pattern)
            if moved:
                globs, literal = reform(pattern, moved, moves)
                for new_pattern, news in globs:
                    regex = glob_regex(new_pattern)
                    taken = sorted(path for path in after if regex.match(path))
                    if len(news) == 1 and len(taken) != 1:
                        new_pattern = news[0]  # one file: name it, so the glob takes nothing else
                    out.append(new_pattern)
                out.extend(literal)
        out = list(dict.fromkeys(out))
        if out != patterns:
            changed.append({"part": part["id"], "before": patterns, "after": out})
            part["match"] = out
    # Cited sources, wherever they stand.
    sources = []
    for entry in [*new_overlay["components"], *new_overlay["capabilities"], *new_overlay["operators"]["items"].values(), *new_overlay.get("scales", [])]:
        for source in entry.get("sources", []):
            path = source["path"]
            if path in moves:
                sources.append({"part": entry.get("id"), "before": path, "after": moves[path]})
                source["path"] = moves[path]
            elif path not in after and path in before:
                stops.append({"kind": "source gone", "part": entry.get("id"), "path": path, "says": "a cited source the table does not name, and not in the tree after the move"})
    # Declared refactors: only a person can say where a split's or a merge's new file belongs.
    for row in table["refactors"]:
        stops.append({"kind": row["kind"], "part": owner.get(row["old"]), "path": row["new"], "from": row["old"], "commit": row.get("commit"), "names": row.get("names"), "says": f"a declared {row['kind']}: {row['new']} took {', '.join(row.get('names') or [])} from {row['old']}; choose its part"})
    # The registry's files, carried through the table (the extractor reads the registry where it now is).
    preplaced_after = {moves.get(path, path): part for path, part in preplaced_before.items() if moves.get(path, path) in after}
    after_owner = owners(new_overlay, after, preplaced_after)
    catch_alls = {part["id"] for part in new_overlay["components"] if part.get("catch_all")}
    images = {moves.get(path, path) for path in before}
    refactor_files = {row["new"] for row in table["refactors"]}
    folder = legacy_folder(new_overlay)
    for path in sorted(after - images):
        if not path.startswith(ENGINE) or path in refactor_files or (folder and path.startswith(folder)):
            continue
        part = after_owner.get(path)
        if part is None or part in catch_alls:
            stops.append({"kind": "new file", "part": part, "path": path, "says": "new to the map, and " + ("no part takes it" if part is None else f"only the catch-all {part} takes it") + ("; the table created it" if path in table["created"] else "")})
    for part in new_overlay["components"]:
        if part.get("match") and not part.get("catch_all") and not any(after_owner.get(path) == part["id"] for path in after):
            stops.append({"kind": "empty part", "part": part["id"], "says": "no file is left in it after the move"})
    return new_overlay, {"move": table["move"], "patterns": changed, "sources": sources, "notes": notes, "stops": stops}


# ---------------------------------------------------------------- checking


def check(before_overlay, after_overlay, table, before, after, preplaced_before, preplaced_after):
    """Ownership before against after, file by file, through the table."""
    moves = table["moves"]
    old_owner = owners(before_overlay, before, preplaced_before)
    new_owner = owners(after_overlay, after, preplaced_after)
    catch_alls = {part["id"] for part in after_overlay["components"] if part.get("catch_all")}
    moved_parts, lost, changed = defaultdict(int), [], []
    for path, part in sorted(old_owner.items()):
        new = moves.get(path, path)
        if new not in after:
            lost.append({"path": path, "part": part})
        elif new_owner.get(new) != part:
            changed.append({"path": path, "now": new, "was": part, "is": new_owner.get(new)})
        elif new != path:
            moved_parts[part] += 1
    images = {moves.get(path, path) for path in old_owner}
    new_files = [{"path": path, "part": new_owner.get(path)} for path in sorted(after) if path not in images and path in new_owner]
    folder = legacy_folder(after_overlay)
    engine = sorted(path for path in after if path.startswith(ENGINE) and path.endswith(".py"))
    left_out = [path for path in engine if folder and path.startswith(folder)]
    unplaced = [path for path in engine if path not in new_owner and path not in left_out]
    gains = [item for item in new_files if item["part"] in catch_alls] + [
        {"path": item["now"], "part": item["is"]} for item in changed if item["is"] in catch_alls
    ]
    ok = not lost and not changed and not unplaced and not gains
    return {
        "ok": ok,
        "files_before": len(old_owner),
        "files_after": len(new_owner),
        "kept_in_place": sum(1 for path in old_owner if moves.get(path, path) == path and new_owner.get(path) == old_owner[path]),
        "moved_with_their_part": dict(sorted(moved_parts.items())),
        "lost": lost,
        "changed_part": changed,
        "new_to_the_map": new_files,
        "engine_files_unplaced": unplaced,
        # Under the overlay's legacy folder: left out of the picture, with no part needed.
        "engine_files_left_out_as_legacy": len(left_out),
        "left_out_as_legacy_with_no_part": [path for path in left_out if path not in new_owner],
        "catch_all_gains": gains,
    }


# ---------------------------------------------------------------- the command


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("rewrite")
    one.add_argument("--table", required=True)
    one.add_argument("--overlay", required=True)
    one.add_argument("--before", required=True)
    one.add_argument("--after", required=True)
    one.add_argument("--out", required=True)
    one.add_argument("--report")
    one.add_argument("--preplaced-before")
    two = commands.add_parser("check")
    two.add_argument("--table", required=True)
    two.add_argument("--before-overlay", required=True)
    two.add_argument("--after-overlay", required=True)
    two.add_argument("--before", required=True)
    two.add_argument("--after", required=True)
    two.add_argument("--report")
    two.add_argument("--preplaced-before")
    two.add_argument("--preplaced-after")
    arguments = parser.parse_args(argv)
    table = read_table(arguments.table)
    before, after = read_files(arguments.before), read_files(arguments.after)
    if arguments.command == "rewrite":
        overlay = json.loads(Path(arguments.overlay).read_text(encoding="utf-8"))
        new_overlay, report = rewrite(overlay, table, before, after, preplaced_of(arguments.before, overlay, arguments.preplaced_before))
        write_json(arguments.out, new_overlay)
        if arguments.report:
            write_json(arguments.report, report)
        print(f"{table['move']}: {len(report['patterns'])} parts' patterns re-formed, {len(report['sources'])} sources moved, {len(report['stops'])} to look at")
        for stop in report["stops"]:
            print(f"  stop ({stop['kind']}): {stop.get('part')}: {stop.get('path', '')} {stop['says']}")
        return 2 if report["stops"] else 0
    first = json.loads(Path(arguments.before_overlay).read_text(encoding="utf-8"))
    second = json.loads(Path(arguments.after_overlay).read_text(encoding="utf-8"))
    report = check(first, second, table, before, after, preplaced_of(arguments.before, first, arguments.preplaced_before), preplaced_of(arguments.after, second, arguments.preplaced_after))
    if arguments.report:
        write_json(arguments.report, report)
    print(
        f"{table['move']}: {report['files_before']} files placed before, {report['files_after']} after; "
        f"{report['kept_in_place']} in place, {sum(report['moved_with_their_part'].values())} moved with their part; "
        f"{len(report['lost'])} lost, {len(report['changed_part'])} in another part, {len(report['new_to_the_map'])} new to the map, "
        f"{len(report['engine_files_unplaced'])} engine files unplaced, {report['engine_files_left_out_as_legacy']} left out as legacy code, "
        f"{len(report['catch_all_gains'])} gained by a catch-all"
    )
    for item in report["new_to_the_map"]:
        print(f"  new: {item['path']} -> {item['part']}")
    for key in ("lost", "changed_part", "engine_files_unplaced", "catch_all_gains"):
        for item in report[key]:
            print(f"  {key}: {item}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
