"""Write the Laws library's list from the engine's declarations manifest.

The list is data/laws/pieces.json, held to schema/LAWS_LIBRARY.md (cells.visualizer.laws@2).
What a piece is, which model holds it and where it is declared are read from the manifest
alone (data/engine/declarations.json, cells.declarations@3, whose format is the engine's page
docs/library/DECLARATIONS_FORMAT.md). Nothing of the engine's source is read, imported or run.

Each piece and model of the manifest is carried unchanged under `declared`; the list adds only
the viewer's layer (data/laws/overlay.json): the family each piece is shelved in, by its
interface and an operator's parts of the step; the models' short names and their Engine view
boxes; the laws design notes name and the manifest does not list. A piece's Engine view box is
the map's own (data/architecture/overlay.json, its components' path globs), matched to the
piece's `module_path`, and carries no level.

The reader refuses a manifest of another major of `cells.declarations`, one whose tree was not
clean (`dirty` not false), and one whose revision is not a full Git revision.

    python3 tools/extract_laws.py [--manifest data/engine/declarations.json] [--overlay data/laws/overlay.json]
                                  [--architecture data/architecture/overlay.json] [--out data/laws/pieces.json | -]

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FORMAT = "cells.visualizer.laws@2"
OVERLAY = "cells.visualizer.laws_overlay@2"
MANIFEST = "cells.declarations"
MAJOR = 3
REVISION = re.compile(r"^[0-9a-f]{40}$")
ID = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*@[0-9]+$")


class Refused(Exception):
    """A manifest or an overlay the reader will not read."""


def namespaced(identifier):
    """D185: a bare ID is in the cells namespace (the format page, "The ID rule")."""
    return identifier if "." in identifier.split("@")[0] else f"cells.{identifier}"


def check_manifest(manifest):
    kind = manifest.get("kind")
    match = re.fullmatch(rf"{re.escape(MANIFEST)}@([0-9]+)", str(kind))
    if not match:
        raise Refused(f"not a {MANIFEST} manifest: kind is {kind!r}")
    if int(match.group(1)) != MAJOR:
        raise Refused(f"{kind} is another major than {MANIFEST}@{MAJOR}, the one this reader knows")
    if manifest.get("dirty") is not False:
        raise Refused(f"the manifest's tree was not clean (dirty is {manifest.get('dirty')!r})")
    if not REVISION.match(str(manifest.get("revision"))):
        raise Refused(f"the manifest's revision is not a full Git revision: {manifest.get('revision')!r}")
    for key in ("pieces", "models", "not_extracted",):
        if not isinstance(manifest.get(key), list):
            raise Refused(f"the manifest has no list {key}")


# ---------------------------------------------------------------- the Engine view's boxes


def glob_regex(pattern):
    """A path glob where * stays inside one directory and ** crosses directories (the map's extractor's rule)."""
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
    return re.compile("^" + "".join(out) + "$")


class Boxes:
    """The Engine view's boxes (the map's overlay components), matched to a file: the first that matches, never the catch-all."""

    def __init__(self, architecture):
        self.components = [(component, [glob_regex(pattern) for pattern in component.get("match", [])]) for component in architecture.get("components", []) if component.get("match")]
        self.labels = {component["id"]: component["label"] for component in architecture.get("components", [])}

    def of(self, path):
        if not path:
            return None
        for component, patterns in self.components:
            if not component.get("catch_all") and any(pattern.match(path) for pattern in patterns):
                return {"id": component["id"], "label": component["label"]}
        return None

    def named(self, ids):
        return [{"id": box, "label": self.labels[box]} for box in ids if box in self.labels]


# ---------------------------------------------------------------- the list


def family_of(piece, families):
    """The first family whose match the piece meets: its piece type, its interface, an operator's parts."""
    for family in families:
        match = family.get("match")
        if not match:
            continue
        if match.get("piece") and match["piece"] != piece["piece"]:
            continue
        if "interface" in match and match["interface"] != piece["interface"]:
            continue
        if "interfaces" in match and piece["interface"] not in match["interfaces"]:
            continue
        if "parts" in match and list((piece.get("fields") or {}).get("parts") or []) != list(match["parts"]):
            continue
        return family["id"]
    raise Refused(f"{piece['id']}: no family of the overlay takes a {piece['piece']} of {piece['interface']}")


def build(manifest, overlay, architecture, viewer_ids):
    check_manifest(manifest)
    if overlay.get("format") != OVERLAY:
        raise Refused(f"the overlay is not {OVERLAY}")
    if viewer_ids["revision"] != manifest["revision"]:
        raise Refused("the identifier moves and declarations are from different revisions")
    boxes = Boxes(architecture)
    declared = {piece["id"] for piece in manifest["pieces"]} | {model["id"] for model in manifest["models"]}
    pieces = []
    for piece in manifest["pieces"]:
        pieces.append({"id": piece["declared_id"], "family": family_of(piece, overlay["families"]), "where": "declared", "box": boxes.of(piece.get("module_path")), "declared": piece})
    for item in overlay["designed"]:
        if not ID.match(item["id"]):
            raise Refused(f"a design note's piece has no ID: {item['id']!r}")
        if viewer_ids["aliases"].get(item["id"], namespaced(item["id"])) in declared:
            raise Refused(f"{item['id']} is named in a design note and declared: it is a declared piece now")
        pieces.append({"id": item["id"], "family": item["family"], "where": "design", "box": None, "declared": None, "kind": item["kind"], "named_in": item["named_in"]})
    used = {piece["family"] for piece in pieces}
    families = [{key: family[key] for key in ("id", "label", "short", "shelf", "description") if key in family} for family in overlay["families"] if family["id"] in used]
    shelves_used = {family["shelf"] for family in families}
    shelves = [shelf for shelf in overlay["shelves"] if shelf["id"] in shelves_used]
    models = []
    for model in manifest["models"]:
        words = overlay["models"].get(model["declared_id"], {})
        models.append({"id": model["declared_id"], "short": words.get("short"), "boxes": boxes.named(words.get("boxes", [])), "declared": model})
    revision = manifest["revision"]
    counts = {
        "pieces": len(manifest["pieces"]),
        "by_piece": dict(sorted(Counter(piece["piece"] for piece in manifest["pieces"]).items())),
        "by_interface": dict(sorted(Counter(piece["interface"] for piece in manifest["pieces"]).items())),
        "by_family": {family["id"]: sum(piece["family"] == family["id"] for piece in pieces) for family in families},
        "models": dict(Counter(model["type"] for model in manifest["models"])),
        "designed": len(overlay["designed"]),
        "not_extracted": len(manifest["not_extracted"]),
    }
    return {
        "format": FORMAT,
        "stamp": {
            "generator": "visualizer/tools/extract_laws.py",
            "read": f"Read from the engine's declarations at main {revision[:8]}",
            "manifest": {"path": "data/engine/declarations.json", "kind": manifest["kind"], "revision": revision, "short": revision[:8], "dirty": manifest["dirty"], "origin": manifest.get("origin")},
            "overlay_as_of": overlay["as_of"],
            "boxes": "data/architecture/overlay.json: the Engine view's components, matched to each piece's module_path",
        },
        "shelves": shelves,
        "families": families,
        "pieces": pieces,
        "models": models,
        "not_extracted": manifest["not_extracted"],
        "viewer_ids": viewer_ids,
        "counts": counts,
    }


def refresh_aliases(viewer_ids, moves, revision):
    if moves.get("kind") != "cells.id_moves.map@1" or moves.get("final") is not True:
        raise Refused("the identifier table must be a final cells.id_moves.map@1")
    aliases = {}
    for row in moves["rows"]:
        for old in row["old"]:
            if aliases.setdefault(old, row["new"]) != row["new"]:
                raise Refused(f"the identifier table gives {old} two destinations")
    return {**viewer_ids, "revision": revision, "aliases": dict(sorted(aliases.items()))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--manifest", default=str(ROOT / "data" / "engine" / "declarations.json"))
    parser.add_argument("--overlay", default=str(ROOT / "data" / "laws" / "overlay.json"))
    parser.add_argument("--viewer-ids", default=str(ROOT / "data" / "engine" / "viewer-ids.json"))
    parser.add_argument("--rename-map", help="refresh the viewer IDs from scripts/moves/id-rename-map.json at the manifest revision")
    parser.add_argument("--architecture", default=str(ROOT / "data" / "architecture" / "overlay.json"))
    parser.add_argument("--out", default=str(ROOT / "data" / "laws" / "pieces.json"), help="the list to write, or - for standard output")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(Path(args.manifest).read_text())
        ids_path = Path(args.viewer_ids)
        viewer_ids = json.loads(ids_path.read_text())
        if args.rename_map:
            viewer_ids = refresh_aliases(viewer_ids, json.loads(Path(args.rename_map).read_text()), manifest["revision"])
        data = build(manifest, json.loads(Path(args.overlay).read_text()), json.loads(Path(args.architecture).read_text()), viewer_ids)
        if args.rename_map:
            ids_path.write_text(json.dumps(viewer_ids, indent=2, ensure_ascii=False) + "\n")
    except Refused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 2
    text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    if args.out == "-":
        sys.stdout.write(text)
    else:
        Path(args.out).write_text(text)
        counts = data["counts"]
        print(f"{counts['pieces']} declared pieces ({', '.join(f'{n} {k}s' for k, n in counts['by_piece'].items())}), {len(data['models'])} models, "
              f"{counts['designed']} named in a design note; {data['stamp']['read']} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
