#!/usr/bin/env python3
"""How large a ribosome, or any machine, is: measured by the viewer from a Protein Data Bank entry's own coordinates.

The Cell view draws a bacterium's ribosome from this measure (schema/SPECIES_SHAPES.md, `ribosome`),
and a machine's closer view may be drawn from the machine mode below.
A PDB entry states no size: every number here is the viewer's own, worked out from the entry's
polymer atoms (model 1, `ATOM` records of `_atom_site`), and is named so wherever it is written.

What it measures, for the two subunits together and for each one (an entity is in the large
subunit or the small one by its own description: 23S, 5S, 50S or a large-subunit protein; 16S,
30S or a small-subunit protein; anything else, such as a tRNA or a messenger, is reported and
left out; a eukaryote's 28S, 5.8S, 25S, 60S, 18S and 40S and its eL, eS, uL and uS proteins
are named too):

- the centre of its atoms, and its own three axes: the axes of its atoms' spread, longest first;
- across each axis, the ellipsoid of the same spread: a solid ellipsoid whose variance along an
  axis is a fifth of its half-width squared, so each half-width is the square root of five
  times the atoms' variance along that axis. This is the shape the picture draws;
- beside it, the farthest atoms along each axis, and the middle 98% of them;
- the radius of gyration.

And how the small subunit lies on the large one, in a frame fixed by the particle itself: y runs
from the large subunit's centre to the small one's, x is the whole particle's longest axis made
square to y (the next one where the longest runs along y), z completes a right-handed frame;
its origin is the centre of both subunits' atoms. Each
subunit's centre and its axes are given in that frame. An axis's sign is chosen so that its
largest part is positive, and the third axis so that each subunit's frame is right-handed, so
that two entries give comparable numbers and a drawing is never mirrored.

The machine mode (`--machine`) measures any machine. The whole: every polymer atom of model 1
(one place for an atom given in alternatives), but for the entities left out with --exclude (a
ribosome's translocon, a polymerase's DNA). Named parts, each by the entity ids or the author
chain ids the caller states (never by a name's pattern), and each chain's own body: each with
its atoms, centre, own axes, the ellipsoid of the same spread, its farthest atoms and radius of
gyration. A frame: with --frame-from and --frame-to, the origin the whole's centre, y from the
first part's centre to the second's, x the whole's longest axis made square to y, z = x × y;
without them, the whole's own axes. Every centre and axis is given in that frame, signs settled
as above. And how whole each entity is: its copies, the residues modelled against its sequence
(`_entity_poly_seq`) and the atoms to a modelled residue. A biological assembly's file
(`<id>-assembly1.cif.gz`) is taken as the machine, its copies as the chains it holds.

Standard library only. It reads the files it is given (untrusted data: an mmCIF file, gzipped
or not, parsed by the small reader below) and writes only the file named by --out. It refuses,
and writes nothing, where a subunit, a part or a frame's part has no atom.

    python3 -I tools/measure_particle.py ENTRY.cif.gz [MORE.cif.gz ...] [--exclude IDS] [--out FILE]
    python3 -I tools/measure_particle.py --machine ENTRY.cif.gz [--exclude IDS] \
        [--part NAME=ENTITY,ENTITY | --part NAME=chains:A,B ...] [--frame-from PART --frame-to PART] [--out FILE]
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import sys
from pathlib import Path

TOKEN = re.compile(r'"[^"]*"(?=\s|$)|\'[^\']*\'(?=\s|$)|\S+')
DEFINITION = (
    "each subunit as the ellipsoid of the same spread as its polymer atoms (model 1): along each of its own three axes "
    "a half-width of the square root of five times the atoms' variance; the farthest atoms beside it"
)
LARGE = re.compile(r"\b50s\b|\b23s\b|\b5s\b|large ribosomal subunit|large subunit ribosomal protein|ribosomal protein [bu]?l\d"
                   r"|\b60s\b|\b28s\b|\b25s\b|\b5\.8s\b|ribosomal protein [eu]l\d|\b[eu]l\d+[a-z]?\b", re.I)
SMALL = re.compile(r"\b30s\b|\b16s\b|small ribosomal subunit|small subunit ribosomal protein|ribosomal protein [bu]?s\d"
                   r"|\b40s\b|\b18s\b|ribosomal protein [eu]s\d|\b[eu]s\d+[a-z]?\b", re.I)
MACHINE_DEFINITION = (
    "the whole, each named part and each chain as the ellipsoid of the same spread as its polymer atoms (model 1, one place for an atom "
    "given in alternatives): along each of its own three axes a half-width of the square root of five times the atoms' variance; the "
    "farthest atoms beside it"
)


def opened(path):
    """The file's text, gzipped or not."""
    raw = Path(path).read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def categories(text, wanted):
    """Each wanted category's rows, as dicts of its items: from loops, and from items given one a line."""
    out = {name: [] for name in wanted}
    single = {name: {} for name in wanted}
    names, row, mode, block, pending = [], [], None, None, None
    for line in text.splitlines():
        if block is not None:
            if line.startswith(";"):
                tokens, block = [" ".join(block)], None
            else:
                block.append(line)
                continue
        elif line.startswith(";"):
            block = [line[1:]]
            continue
        elif line.startswith("#"):
            mode, names, row = None, [], []
            continue
        else:
            tokens = [t[1:-1] if len(t) > 1 and t[0] in "\"'" and t[-1] == t[0] else t for t in TOKEN.findall(line)]
        if not tokens:
            continue
        if tokens[0] == "loop_":
            mode, names, row = "names", [], []
            continue
        if mode == "names" and tokens[0].startswith("_"):
            names.append(tokens[0])
            continue
        if mode in ("names", "rows") and names:
            mode = "rows"
            category = names[0].split(".")[0][1:]
            if category not in out:
                continue
            row.extend(tokens)
            while len(row) >= len(names):
                out[category].append(dict(zip((name.split(".", 1)[1] for name in names), row[: len(names)])))
                del row[: len(names)]
            continue
        if tokens[0].startswith("_") and "." in tokens[0]:
            category, item = tokens[0][1:].split(".", 1)
            if category in single:
                if len(tokens) > 1:
                    single[category][item] = tokens[1]
                else:
                    pending = (category, item)
            continue
        if pending:
            single[pending[0]][pending[1]] = tokens[0]
            pending = None
    for category, items in single.items():
        if items and not out[category]:
            out[category].append(items)
    return out


def eigen(matrix):
    """The eigenvalues and unit eigenvectors of a symmetric 3 by 3 matrix, largest first (Jacobi's method)."""
    a = [row[:] for row in matrix]
    v = [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
    for _ in range(100):
        p, q = max(((0, 1), (0, 2), (1, 2)), key=lambda pq: abs(a[pq[0]][pq[1]]))
        if abs(a[p][q]) < 1e-14 * max(1.0, abs(a[p][p]) + abs(a[q][q])):
            break
        theta = 0.5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
        c, s = math.cos(theta), math.sin(theta)
        for k in range(3):
            akp, akq = a[k][p], a[k][q]
            a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
        for k in range(3):
            apk, aqk = a[p][k], a[q][k]
            a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
        for k in range(3):
            vkp, vkq = v[k][p], v[k][q]
            v[k][p], v[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    order = sorted(range(3), key=lambda i: -a[i][i])
    return [a[i][i] for i in order], [[v[k][i] for k in range(3)] for i in order]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def unit(a):
    length = math.sqrt(dot(a, a))
    return [x / length for x in a]


def settled(axes):
    """Axes with each sign fixed (its largest part positive) and the third set so that the frame is right-handed."""
    out = []
    for axis in axes[:2]:
        big = max(range(3), key=lambda i: abs(axis[i]))
        out.append(axis if axis[big] >= 0 else [-x for x in axis])
    out.append(cross(out[0], out[1]))
    return out


def spread(points):
    """Centre, own axes, the ellipsoid of the same spread and the farthest atoms of a set of points (in ångström)."""
    n = len(points)
    centre = [sum(p[i] for p in points) / n for i in range(3)]
    cov = [[0.0] * 3 for _ in range(3)]
    for p in points:
        d = [p[i] - centre[i] for i in range(3)]
        for i in range(3):
            for j in range(i, 3):
                cov[i][j] += d[i] * d[j]
    for i in range(3):
        for j in range(i, 3):
            cov[i][j] /= n
            cov[j][i] = cov[i][j]
    values, axes = eigen(cov)
    farthest, middle = [], []
    for axis in axes:
        along = sorted(dot([p[i] - centre[i] for i in range(3)], axis) for p in points)
        farthest.append(along[-1] - along[0])
        middle.append(along[int(0.99 * n) - 1] - along[int(0.01 * n)])
    return {"atoms": n, "centre": centre, "axes": axes, "half": [math.sqrt(5 * max(value, 0.0)) for value in values], "farthest": farthest, "middle": middle, "gyration": math.sqrt(sum(values))}


def nm(value, places=2):
    return round(value / 10, places) + 0.0  # never "-0.0"


def named(path):
    """The entry's id, and the biological assembly its file holds, or None: `1G4A-assembly1.cif.gz` is 1G4A's assembly 1."""
    stem = Path(path).name.split(".")[0]
    match = re.fullmatch(r"(.+?)-assembly(\d+)", stem, re.I)
    return (match.group(1).upper(), match.group(2)) if match else (stem.upper(), None)


def described(data, path):
    """What the file says it is: its id, the assembly it holds, its title, method and resolution."""
    entry, assembly = named(path)
    resolution = data["em_3d_reconstruction"][0].get("resolution") if data["em_3d_reconstruction"] else (data["refine"][0].get("ls_d_res_high") if data["refine"] else None)
    return {
        "entry": entry,
        **({"assembly": assembly} if assembly else {}),
        "title": data["struct"][0].get("title") if data["struct"] else None,
        "method": data["exptl"][0].get("method") if data["exptl"] else None,
        "resolution_A": resolution,
    }


def measure(path, exclude=()):
    """One entry's measure as a ribosome: what the file says it is, and the particle's sizes and the arrangement of its two subunits."""
    data = categories(opened(path), ["entity", "atom_site", "struct", "exptl", "em_3d_reconstruction", "refine"])
    names = {row.get("id"): row.get("pdbx_description", "") for row in data["entity"]}
    sets, found = {"large": [], "small": [], "other": []}, {"large": set(), "small": set(), "other": set()}
    for row in data["atom_site"]:
        if row.get("group_PDB") != "ATOM" or row.get("pdbx_PDB_model_num", "1") != "1" or row.get("label_entity_id") in exclude:
            continue
        description = names.get(row.get("label_entity_id"), "")
        side = "large" if LARGE.search(description) else "small" if SMALL.search(description) else "other"
        try:
            sets[side].append((float(row["Cartn_x"]), float(row["Cartn_y"]), float(row["Cartn_z"])))
        except (KeyError, ValueError):
            continue
        found[side].add(description)
    if not sets["large"] or not sets["small"]:
        raise SystemExit(f"{Path(path).name}: no atoms of {'a large' if not sets['large'] else 'a small'} subunit were found; nothing is measured")
    whole, large, small = spread(sets["large"] + sets["small"]), spread(sets["large"]), spread(sets["small"])
    # The particle's own frame: y from the large subunit's centre to the small one's, x its longest axis made square to y.
    y = unit([small["centre"][i] - large["centre"][i] for i in range(3)])
    # The longest of the particle's own axes that is not along y (within about 6 degrees of it), made square to y.
    for x in whole["axes"]:
        x = [x[i] - dot(x, y) * y[i] for i in range(3)]
        if dot(x, x) > 0.01:
            break
    x = unit(x)
    big = max(range(3), key=lambda i: abs(x[i]))
    if x[big] < 0:
        x = [-v for v in x]
    z = cross(x, y)
    frame = [x, y, z]
    inside = lambda vector: [dot(vector, axis) for axis in frame]  # noqa: E731
    def subunit(part):
        return {
            "atoms": part["atoms"],
            "centre_nm": [nm(v) for v in inside([part["centre"][i] - whole["centre"][i] for i in range(3)])],
            "axes": [[round(v, 4) + 0.0 for v in axis] for axis in settled([inside(axis) for axis in part["axes"]])],
            "across_nm": [nm(2 * h, 1) for h in part["half"]],
            "farthest_nm": [nm(v, 1) for v in part["farthest"]],
            "radius_of_gyration_nm": nm(part["gyration"]),
        }
    return {
        **described(data, path),
        "left_out": sorted(found["other"]),
        "whole": {
            "atoms": whole["atoms"],
            "across_nm": [nm(2 * h, 1) for h in whole["half"]],
            "farthest_nm": [nm(v, 1) for v in whole["farthest"]],
            "middle_98_percent_nm": [nm(v, 1) for v in whole["middle"]],
            "radius_of_gyration_nm": nm(whole["gyration"]),
        },
        "large": subunit(large),
        "small": subunit(small),
        "between_centres_nm": nm(math.dist(large["centre"], small["centre"]), 1),
    }


def framed(whole, y=None):
    """A right-handed frame for the whole: y as given and x its longest axis made square to y (the next one if the longest runs along
    y), z = x × y; or, with no y, its own axes, longest first. Each sign is settled as `settled` settles it."""
    if y is None:
        return settled(whole["axes"])
    for x in whole["axes"]:
        x = [x[i] - dot(x, y) * y[i] for i in range(3)]
        if dot(x, x) > 0.01:
            break
    x = unit(x)
    big = max(range(3), key=lambda i: abs(x[i]))
    if x[big] < 0:
        x = [-v for v in x]
    return [x, y, cross(x, y)]


def body(points, origin, inside):
    """One body's measure: its atoms, its centre and own axes in the frame, the ellipsoid of the same spread, its farthest atoms."""
    part = spread(points)
    return {
        "atoms": part["atoms"],
        "centre_nm": [nm(v) for v in inside([part["centre"][i] - origin[i] for i in range(3)])],
        "axes": [[round(v, 4) + 0.0 for v in axis] for axis in settled([inside(axis) for axis in part["axes"]])],
        "across_nm": [nm(2 * h, 1) for h in part["half"]],
        "farthest_nm": [nm(v, 1) for v in part["farthest"]],
        "radius_of_gyration_nm": nm(part["gyration"]),
    }


def measure_machine(path, parts, exclude=(), frame=None):
    """One entry's measure as a machine: the whole, the parts the caller names, each chain, and how whole each entity is."""
    data = categories(opened(path), ["entity", "entity_poly_seq", "atom_site", "struct", "exptl", "em_3d_reconstruction", "refine"])
    file = Path(path).name
    names = {row.get("id"): row.get("pdbx_description", "") for row in data["entity"]}
    atoms = []  # (x, y, z), entity id, author chain id, residue number in the sequence
    for row in data["atom_site"]:
        if row.get("group_PDB") != "ATOM" or row.get("pdbx_PDB_model_num", "1") != "1" or row.get("label_entity_id") in exclude:
            continue
        if row.get("label_alt_id") not in (None, "", ".", "?", "A"):
            continue  # one place for an atom given in alternatives: the first
        try:
            xyz = (float(row["Cartn_x"]), float(row["Cartn_y"]), float(row["Cartn_z"]))
        except (KeyError, ValueError):
            continue
        atoms.append((xyz, row.get("label_entity_id"), row.get("auth_asym_id") or row.get("label_asym_id"), row.get("label_seq_id")))
    if not atoms:
        raise SystemExit(f"{file}: no polymer atoms in model 1; nothing is measured")
    chosen = {}
    for name, (by, ids) in parts.items():
        points = [atom[0] for atom in atoms if (atom[1] if by == "entities" else atom[2]) in ids]
        if not points:
            raise SystemExit(f"{file}: the part {name} ({by} {','.join(ids)}) names no atom; nothing is measured")
        chosen[name] = points
    whole = spread([atom[0] for atom in atoms])
    between = None
    if frame:
        start, end = spread(chosen[frame[0]])["centre"], spread(chosen[frame[1]])["centre"]
        axes = framed(whole, unit([end[i] - start[i] for i in range(3)]))
        between = nm(math.dist(start, end), 1)
    else:
        axes = framed(whole)
    inside = lambda vector: [dot(vector, axis) for axis in axes]  # noqa: E731
    origin = whole["centre"]
    # Each chain, in the order the file gives them.
    chains = {}
    for xyz, entity, chain, _ in atoms:
        chains.setdefault(chain, (entity, []))[1].append(xyz)
    # How whole each entity is: its copies, the residues modelled against its sequence, the atoms to a modelled residue.
    length = {}
    for row in data["entity_poly_seq"]:
        length.setdefault(row.get("entity_id"), set()).add(row.get("num"))
    counted = {}
    for _, entity, chain, residue in atoms:
        item = counted.setdefault(entity, {"chains": set(), "residues": set(), "atoms": 0})
        item["chains"].add(chain)
        item["atoms"] += 1
        if residue not in (None, ".", "?"):
            item["residues"].add((chain, residue))
    entities = []
    for entity, item in counted.items():
        copies, residues, sequence = len(item["chains"]), len(item["residues"]), len(length.get(entity, ()))
        entities.append({
            "entity": entity, "description": names.get(entity, ""), "copies": copies,
            "sequence_length": sequence or None,
            "residues_modelled_per_copy": round(residues / copies, 1) if copies else 0,
            "modelled_share": round(residues / copies / sequence, 3) if sequence and copies else None,
            "atoms_per_modelled_residue": round(item["atoms"] / residues, 2) if residues else None,
        })
    return {
        **described(data, path),
        "left_out": [{"entity": entity, "description": names.get(entity, "")} for entity in exclude if entity in names],
        "whole": {
            "atoms": whole["atoms"],
            "axes": [[round(v, 4) + 0.0 for v in axis] for axis in settled([inside(axis) for axis in whole["axes"]])],
            "across_nm": [nm(2 * h, 1) for h in whole["half"]],
            "farthest_nm": [nm(v, 1) for v in whole["farthest"]],
            "middle_98_percent_nm": [nm(v, 1) for v in whole["middle"]],
            "radius_of_gyration_nm": nm(whole["gyration"]),
        },
        **({"frame": {"from": frame[0], "to": frame[1], "between_centres_nm": between}} if frame else {}),
        "parts": {name: {"by": parts[name][0], "ids": list(parts[name][1]), **body(points, origin, inside)} for name, points in chosen.items()},
        "chains": [{"chain": chain, "entity": entity, "description": names.get(entity, ""), **body(points, origin, inside)} for chain, (entity, points) in chains.items()],
        "entities": entities,
    }


def part_of(text):
    """`NAME=ENTITY,ENTITY` (entity ids) or `NAME=chains:A,B` (author chain ids), as (name, (by, ids))."""
    name, _, said = text.partition("=")
    by, ids = ("chains", said[len("chains:"):]) if said.startswith("chains:") else ("entities", said)
    ids = [one.strip() for one in ids.split(",") if one.strip()]
    if not name.strip() or not ids:
        raise SystemExit(f"--part {text}: give NAME=ENTITY,ENTITY or NAME=chains:A,B")
    return name.strip(), (by, ids)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("entries", nargs="+", help="mmCIF files of PDB entries, gzipped or not; a biological assembly's file as <id>-assembly1.cif.gz")
    parser.add_argument("--out", help="write the measures here, as JSON (else they are printed)")
    parser.add_argument("--exclude", action="append", default=[], help="entity ids to leave out of the whole (comma-separated; may be given again)")
    parser.add_argument("--machine", action="store_true", help="measure any machine: the whole, named parts, each chain and how whole each entity is")
    parser.add_argument("--part", action="append", default=[], help="machine mode: NAME=ENTITY,ENTITY or NAME=chains:A,B (may be given again)")
    parser.add_argument("--frame-from", help="machine mode: the part whose centre the frame's y runs from")
    parser.add_argument("--frame-to", help="machine mode: the part whose centre the frame's y runs to")
    arguments = parser.parse_args()
    exclude = tuple(one.strip() for given in arguments.exclude for one in given.split(",") if one.strip())
    if not arguments.machine:
        if arguments.part or arguments.frame_from or arguments.frame_to:
            raise SystemExit("--part, --frame-from and --frame-to are for the machine mode: add --machine")
        record = {
            "format": "cells.visualizer.particle@1",
            "tool": "tools/measure_particle.py",
            "definition": DEFINITION,
            "frame": "origin at the centre of both subunits' atoms; y from the large subunit's centre to the small one's; x the whole particle's longest axis made square to y (the next one if the longest runs along y); z = x × y",
            "measured": {entry["entry"]: entry for entry in (measure(path, exclude) for path in arguments.entries)},
        }
    else:
        parts = {}
        for text in arguments.part:
            name, said = part_of(text)
            if name in parts:
                raise SystemExit(f"--part {name} is given twice")
            parts[name] = said
        frame = None
        if arguments.frame_from or arguments.frame_to:
            frame = (arguments.frame_from, arguments.frame_to)
            for name in frame:
                if not name or name not in parts:
                    raise SystemExit(f"the frame's part {name or '(none)'} is not given with --part; nothing is measured")
        record = {
            "format": "cells.visualizer.machine-measure@1",
            "tool": "tools/measure_particle.py",
            "definition": MACHINE_DEFINITION,
            "frame": (
                f"origin at the centre of the whole's atoms; y from the part {frame[0]}'s centre to the part {frame[1]}'s; x the whole's longest axis made square to y (the next one if the longest runs along y); z = x × y"
                if frame else "origin at the centre of the whole's atoms; its own axes, longest first, each sign set so that its largest part is positive; z = x × y"
            ),
            "measured": {},
        }
        for path in arguments.entries:
            measured = measure_machine(path, parts, exclude, frame)
            record["measured"][measured["entry"] + (f"-assembly{measured['assembly']}" if measured.get("assembly") else "")] = measured
    text = json.dumps(record, indent=1, ensure_ascii=False) + "\n"
    if arguments.out:
        Path(arguments.out).write_text(text, encoding="utf-8")
        print(f"wrote {arguments.out}")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
