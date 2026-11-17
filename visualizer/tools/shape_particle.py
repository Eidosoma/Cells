#!/usr/bin/env python3
"""A machine's shape: a smooth, low-resolution surface the viewer works out from a Protein Data Bank entry's coordinates.

The sibling of tools/measure_particle.py, whose reader and frame it uses unchanged, so that a shape sits
exactly where the measure's ellipsoid sits (schema/MACHINE_SHAPES.md). A PDB entry states no surface:
every surface here is the viewer's own, an illustration, and is named so wherever it is written.

The definition, the same for every machine (one sentence, its numbers in the file):
    each chain is the closed surface that holds its own volume (0.135 nm³ for each amino acid, 0.32 nm³ for
    each nucleotide) in a cloud where each residue is spread as a Gaussian 1 nm wide, on a grid 1 nm apart;
    where a machine is drawn by its parts (a ribosome, whose fifty chains are too many to tell apart at this
    resolution), each part's protein and nucleic acid, at 1.6 nm.
The widths were weighed on 17 November 2026 (0.8, 1.0 and 1.4 nm for a chain; 1.2, 1.6 and 2.0 nm for a part):
these hold the budget (schema/MACHINE_SHAPES.md) without a pass that simplifies the surfaces.

How: one atom stands for each residue (an amino acid's alpha carbon, a nucleotide's phosphorus or else
its C4'), of model 1's polymer atoms, one place for an atom given in alternatives, but for the entities
left out with --exclude. Each is spread as a Gaussian of standard deviation `width` on a grid `grid` apart (the same, by
default); the level is the one at which the surface holds the chain's own volume, found by halving; the
surface is where the cloud crosses that level, by marching tetrahedra (each grid cell cut into six
tetrahedra along one diagonal, so that neighbouring cells meet): closed, every edge shared by two
triangles, each triangle facing out. Its vertices are given in the measuring tool's frame, in nanometres,
as integers on a grid of `unit` nm; no normals are stored.

The machine mode takes what the measuring tool's machine mode takes; --ribosome takes its two-subunit
mode (the large and the small subunit by their entities' names, and its frame). With --by chains there is
one surface for each chain; with --by parts one for each named part (or subunit), split into what is
protein and what is nucleic acid.

Standard library only. It reads the file it is given (untrusted data, by the measuring tool's reader)
and writes only --out. It refuses, and writes nothing, where a part, a frame's part or a subunit has no
atom, or the shapes would break the budget (--most-triangles, --most-bytes).

    python3 -I tools/shape_particle.py ENTRY.cif.gz [--exclude IDS] [--part NAME=IDS ...]
        [--frame-from PART --frame-to PART] [--ribosome] [--by chains|parts] [--width NM] [--out FILE]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # it writes only --out: no cache beside the measuring tool
sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure_particle as M  # noqa: E402  the reader, the spread and the frame, used as they are

FORMAT = "cells.visualizer.machine-shape@1"
VOLUME = {"protein": 0.135, "nucleic": 0.32}  # nm³ a residue: 110 Da at 1.35 g/cm³; 330 Da at 1.7 g/cm³
STANDS_FOR = {"protein": ("CA",), "nucleic": ("P", "C4'")}  # the atom that stands for a residue, in order of choice
NUCLEOTIDES = {"A", "C", "G", "U", "T", "I", "DA", "DC", "DG", "DT", "DU", "DI", "PSU", "5MU", "5MC", "1MA", "2MG", "7MG", "M2G", "OMC", "OMG", "H2U", "4SU"}
UNIT = 0.01  # nm: the vertices' grid
WIDTH = {"chains": 1.0, "parts": 1.6}  # nm: the Gaussian's width and the grid, for a chain's surface and for a part's
REACH = 3.0  # a Gaussian is spread this many widths out
# The six tetrahedra of a cube, all along the diagonal from corner 0 to corner 6, so that neighbouring cubes meet.
CORNERS = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
TETRAHEDRA = [(0, 5, 1, 6), (0, 1, 2, 6), (0, 2, 3, 6), (0, 3, 7, 6), (0, 7, 4, 6), (0, 4, 5, 6)]


def definition(width, grid, by="chains"):
    return (
        f"{'each chain' if by == 'chains' else 'each part' + chr(39) + 's protein and nucleic acid'} as the closed surface that holds its own volume "
        f"({VOLUME['protein']} nm³ for each amino acid, {VOLUME['nucleic']} nm³ for each nucleotide) in a cloud where each residue "
        f"is spread as a Gaussian {width:g} nm wide, on a grid {grid:g} nm apart"
    )


def residues(data, exclude):
    """The atoms that stand for residues: (x, y, z) in ångström, entity, author chain, kind, residue key; and every polymer atom, for the frame."""
    picked, every = {}, []
    for row in data["atom_site"]:
        if row.get("group_PDB") != "ATOM" or row.get("pdbx_PDB_model_num", "1") != "1" or row.get("label_entity_id") in exclude:
            continue
        if row.get("label_alt_id") not in (None, "", ".", "?", "A"):
            continue
        try:
            xyz = (float(row["Cartn_x"]), float(row["Cartn_y"]), float(row["Cartn_z"]))
        except (KeyError, ValueError):
            continue
        every.append((xyz, row.get("label_entity_id"), row.get("auth_asym_id") or row.get("label_asym_id")))
        atom, comp = row.get("label_atom_id"), (row.get("label_comp_id") or "").upper()
        kind = "nucleic" if comp in NUCLEOTIDES or len(comp) <= 2 else "protein"  # amino acids have three letters; nucleotides one or two, or a listed modified one
        if atom not in STANDS_FOR[kind]:
            continue
        chain = row.get("auth_asym_id") or row.get("label_asym_id")
        key = (chain, row.get("label_seq_id"), row.get("pdbx_PDB_ins_code"))
        rank = STANDS_FOR[kind].index(atom)
        if key not in picked or rank < picked[key][5]:
            picked[key] = (xyz, row.get("label_entity_id"), chain, kind, key, rank)
    return [item[:5] for item in picked.values()], every


def held(vertices, triangles):
    """The volume a closed surface holds, from its triangles' signed volumes (ångström³)."""
    total = 0.0
    for a, b, c in triangles:
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = vertices[a], vertices[b], vertices[c]
        total += x1 * (y2 * z3 - y3 * z2) - y1 * (x2 * z3 - x3 * z2) + z1 * (x2 * y3 - x3 * y2)
    return total / 6


def surface(points, kind, width, grid):
    """The closed surface that holds the points' own volume in their Gaussian cloud: (vertices in ångström, triangles)."""
    sigma, h = width * 10, grid * 10  # ångström: the Gaussian's width, and the grid's spacing
    pad = REACH * sigma + 2 * h
    low = [min(p[i] for p in points) - pad for i in range(3)]
    size = [int(math.ceil((max(p[i] for p in points) + pad - low[i]) / h)) + 1 for i in range(3)]
    nx, ny, nz = size
    field = [0.0] * (nx * ny * nz)
    reach = int(math.ceil(REACH * sigma / h))
    two = 2 * sigma * sigma
    for x, y, z in points:
        ci, cj, ck = int(round((x - low[0]) / h)), int(round((y - low[1]) / h)), int(round((z - low[2]) / h))
        for i in range(ci - reach, ci + reach + 1):
            dx = (low[0] + i * h - x) ** 2
            for j in range(cj - reach, cj + reach + 1):
                dxy = dx + (low[1] + j * h - y) ** 2
                row = (i * ny + j) * nz
                for k in range(ck - reach, ck + reach + 1):
                    d = dxy + (low[2] + k * h - z) ** 2
                    if d < 9 * sigma * sigma:
                        field[row + k] += math.exp(-d / two)
    at = lambda i, j, k: (i * ny + j) * nz + k  # noqa: E731

    def point(a):
        k = a % nz
        j = (a // nz) % ny
        i = a // (nz * ny)
        return (low[0] + i * h, low[1] + j * h, low[2] + k * h)

    # The cells the surface may cross at any level above the lowest, found once.
    busy = []
    for i in range(nx - 1):
        for j in range(ny - 1):
            for k in range(nz - 1):
                corners = [at(i + a, j + b, k + c) for a, b, c in CORNERS]
                if max(field[n] for n in corners) > 0:
                    busy.append(corners)

    def contour(level):
        """The surface where the cloud crosses `level`, by marching tetrahedra: vertices, triangles, and the volume it holds."""
        vertices, index, triangles = [], {}, []

        def cut(a, b):
            """The vertex where the surface crosses the edge from grid point a to grid point b (shared by every tetrahedron on that edge)."""
            key = (a, b) if a < b else (b, a)
            if key not in index:
                fa, fb = field[a] - level, field[b] - level
                t = fa / (fa - fb)
                pa, pb = point(a), point(b)
                index[key] = len(vertices)
                vertices.append(tuple(pa[n] + t * (pb[n] - pa[n]) for n in range(3)))
            return index[key]

        def facing(tri, inside, outside):
            """The triangle turned so that it faces from the inside points to the outside ones."""
            p0, p1, p2 = (vertices[n] for n in tri)
            normal = M.cross([p1[n] - p0[n] for n in range(3)], [p2[n] - p0[n] for n in range(3)])
            cin = [sum(point(a)[n] for a in inside) / len(inside) for n in range(3)]
            cout = [sum(point(a)[n] for a in outside) / len(outside) for n in range(3)]
            return tri if M.dot(normal, [cout[n] - cin[n] for n in range(3)]) >= 0 else (tri[0], tri[2], tri[1])

        for corners in busy:
            values = [field[n] > level for n in corners]
            if all(values) or not any(values):
                continue
            for tetra in TETRAHEDRA:
                ids = [corners[n] for n in tetra]
                inside = [n for n in ids if field[n] > level]
                outside = [n for n in ids if field[n] <= level]
                if not inside or not outside:
                    continue
                if len(inside) == 1 or len(outside) == 1:
                    one, rest = (inside[0], outside) if len(inside) == 1 else (outside[0], inside)
                    triangles.append(facing(tuple(cut(one, other) for other in rest), inside, outside))
                else:
                    a, b = inside
                    c, d = outside
                    ac, ad, bd, bc = cut(a, c), cut(a, d), cut(b, d), cut(b, c)
                    triangles.append(facing((ac, ad, bd), inside, outside))
                    triangles.append(facing((ac, bd, bc), inside, outside))
        return vertices, triangles, held(vertices, triangles) / 1000  # nm³

    # The level: the one at which the surface holds the residues' own volume, found by halving (on a logarithmic scale),
    # starting from the grid's points.
    wanted = len(points) * VOLUME[kind]
    top = max(field)
    lo, hi = top * 1e-4, top
    for _ in range(40):
        middle = math.sqrt(lo * hi)
        made = contour(middle)
        if abs(made[2] - wanted) <= 0.01 * wanted:
            break
        if made[2] > wanted:
            lo = middle
        else:
            hi = middle
    vertices, triangles, _ = made
    return vertices, triangles


def frame_of(data, every, args, chosen):
    """The measuring tool's frame: its origin, its three axes, and its words (the same as the measure's, so that a shape sits on its ellipsoid)."""
    if args.ribosome:
        large, small = chosen["large"], chosen["small"]
        whole = M.spread(large + small)
        y = M.unit([M.spread(small)["centre"][i] - M.spread(large)["centre"][i] for i in range(3)])
        return whole["centre"], M.framed(whole, y), "the measuring tool's two-subunit frame: origin at the centre of both subunits' atoms; y from the large subunit's centre to the small one's; x the whole particle's longest axis made square to y; z = x × y"
    whole = M.spread([item[0] for item in every])
    if args.frame_from:
        start, end = M.spread(chosen[args.frame_from])["centre"], M.spread(chosen[args.frame_to])["centre"]
        return whole["centre"], M.framed(whole, M.unit([end[i] - start[i] for i in range(3)])), f"the measuring tool's frame: origin at the centre of the whole's atoms; y from the part {args.frame_from}'s centre to the part {args.frame_to}'s; x the whole's longest axis made square to y; z = x × y"
    return whole["centre"], M.framed(whole), "the measuring tool's frame: origin at the centre of the whole's atoms; its own axes, longest first, each sign set so that its largest part is positive; z = x × y"


def shape(path, args):
    data = M.categories(M.opened(path), ["entity", "atom_site", "struct", "exptl", "em_3d_reconstruction", "refine"])
    file = Path(path).name
    names = {row.get("id"): row.get("pdbx_description", "") for row in data["entity"]}
    exclude = tuple(one.strip() for given in args.exclude for one in given.split(",") if one.strip())
    stand, every = residues(data, exclude)
    if not every:
        raise SystemExit(f"{file}: no polymer atoms in model 1; nothing is made")
    # The parts, as the measuring tool takes them: every polymer atom of each, for the frame; the residues of each, for its surfaces.
    parts, chosen, owner = {}, {}, {}
    if args.ribosome:
        named = {}
        for side in ("large", "small"):
            for entity in (one.strip() for given in getattr(args, side) for one in given.split(",") if one.strip()):
                if named.get(entity, side) != side:
                    raise SystemExit(f"the entity {entity} is named for both subunits")
                if entity not in names:
                    raise SystemExit(f"{file}: the entity {entity} named for a subunit is not in the entry; nothing is made")
                named[entity] = side
        # As the measuring tool's two-subunit mode places them: by the caller's word, else by the description.
        for entity, side in M.sides(names, exclude, named).items():
            if side:
                parts.setdefault(side, ("entities", []))[1].append(entity)
        for side in ("large", "small"):
            if side not in parts:
                raise SystemExit(f"{file}: no atoms of a {side} subunit were found; nothing is made")
        # The measuring tool's two-subunit frame reads every ATOM of model 1, alternatives and all.
        frame_atoms = {side: [] for side in parts}
        for row in data["atom_site"]:
            if row.get("group_PDB") != "ATOM" or row.get("pdbx_PDB_model_num", "1") != "1" or row.get("label_entity_id") in exclude:
                continue
            for side, (_, ids) in parts.items():
                if row.get("label_entity_id") in ids:
                    try:
                        frame_atoms[side].append((float(row["Cartn_x"]), float(row["Cartn_y"]), float(row["Cartn_z"])))
                    except (KeyError, ValueError):
                        pass
        chosen = frame_atoms
    else:
        for text in args.part:
            name, said = M.part_of(text)
            if name in parts:
                raise SystemExit(f"--part {name} is given twice")
            parts[name] = said
        for name, (by, ids) in parts.items():
            points = [item[0] for item in every if (item[1] if by == "entities" else item[2]) in ids]
            if not points:
                raise SystemExit(f"{file}: the part {name} ({by} {','.join(ids)}) names no atom; nothing is made")
            chosen[name] = points
        for name in (args.frame_from, args.frame_to):
            if (args.frame_from or args.frame_to) and (not name or name not in parts):
                raise SystemExit(f"the frame's part {name or '(none)'} is not given with --part; nothing is made")
    for name, (by, ids) in parts.items():
        for one in ids:
            owner[(by, one)] = name
    origin, axes, frame_words = frame_of(data, every, args, chosen)
    inside = lambda vector: [M.dot(vector, axis) for axis in axes]  # noqa: E731
    # What each surface is drawn from.
    groups = {}
    for xyz, entity, chain, kind, _ in stand:
        if args.by == "chains":
            key = ("chain", chain)
        else:
            name = owner.get(("entities", entity)) or owner.get(("chains", chain))
            if not name:
                continue
            key = ("part", name, kind)
        groups.setdefault(key, {"points": [], "entity": entity, "chain": chain, "kind": kind})["points"].append(xyz)
    meshes, total = [], 0
    for key, group in groups.items():
        vertices, triangles = surface(group["points"], group["kind"], args.width, args.grid)
        if not triangles:
            continue
        total += len(triangles)
        made = [int(round(value / 10 / UNIT)) for vertex in vertices for value in inside([vertex[n] - origin[n] for n in range(3)])]
        if key[0] == "chain":
            mesh = {"id": f"chain-{group['chain']}", "chain": group["chain"], "entity": group["entity"], "description": names.get(group["entity"], ""),
                    "part": owner.get(("entities", group["entity"])) or owner.get(("chains", group["chain"])), "kind": group["kind"]}
        else:
            mesh = {"id": f"part-{key[1]}-{key[2]}", "part": key[1], "kind": key[2]}
        mesh.update({"residues": len(group["points"]), "vertices": made, "triangles": [n for tri in triangles for n in tri]})
        meshes.append(mesh)
    if total > args.most_triangles:
        raise SystemExit(f"{file}: {total} triangles, above the budget of {args.most_triangles}; nothing is made")
    described = M.described(data, path)
    return {
        "format": FORMAT,
        "tool": "tools/shape_particle.py",
        "definition": definition(args.width, args.grid, args.by),
        "illustration": "The viewer's own surface of the entry's coordinates, an illustration: not the structure, and nothing of the entry is copied but the numbers worked out here. The Protein Data Bank states no surface.",
        "parameters": {"width_nm": args.width, "grid_nm": args.grid, "reach_widths": REACH, "volume_nm3": VOLUME, "stands_for": {kind: list(atoms) for kind, atoms in STANDS_FOR.items()}, "by": args.by},
        **described,
        "left_out": [{"entity": entity, "description": names.get(entity, "")} for entity in exclude if entity in names],
        "frame": frame_words,
        "unit_nm": UNIT,
        "counts": {"meshes": len(meshes), "vertices": sum(len(mesh["vertices"]) // 3 for mesh in meshes), "triangles": total},
        "meshes": meshes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("entry", help="an mmCIF file of a PDB entry, gzipped or not; a biological assembly's file as <id>-assembly1.cif.gz")
    parser.add_argument("--out", help="write the shapes here, as JSON (else they are printed)")
    parser.add_argument("--exclude", action="append", default=[], help="entity ids to leave out (comma-separated; may be given again)")
    parser.add_argument("--part", action="append", default=[], help="NAME=ENTITY,ENTITY or NAME=chains:A,B (may be given again), as the measuring tool takes it")
    parser.add_argument("--frame-from", help="the part whose centre the frame's y runs from")
    parser.add_argument("--frame-to", help="the part whose centre the frame's y runs to")
    parser.add_argument("--ribosome", action="store_true", help="the measuring tool's two-subunit mode: the parts large and small by their entities' names, and its frame")
    parser.add_argument("--large", action="append", default=[], help="with --ribosome: entity ids to place in the large subunit whatever their description says")
    parser.add_argument("--small", action="append", default=[], help="with --ribosome: entity ids to place in the small subunit whatever their description says")
    parser.add_argument("--by", choices=["chains", "parts"], default=None, help="one surface for each chain, or for each part's protein and nucleic acid (default: chains; parts with --ribosome)")
    parser.add_argument("--width", type=float, default=None, help=f"the Gaussian's width, in nm (default {WIDTH['chains']} for chains, {WIDTH['parts']} for parts)")
    parser.add_argument("--grid", type=float, default=None, help="the grid's spacing, in nm (default: the width)")
    parser.add_argument("--most-triangles", type=int, default=20000, help="the budget: refuse above this many triangles (default 20,000)")
    parser.add_argument("--most-bytes", type=int, default=400000, help="the budget: refuse a file above this many bytes (default 400,000)")
    args = parser.parse_args()
    args.by = args.by or ("parts" if args.ribosome else "chains")
    args.width = args.width or WIDTH[args.by]
    args.grid = args.grid or args.width
    if (args.large or args.small) and not args.ribosome:
        raise SystemExit("--large and --small are for --ribosome; name parts with --part")
    if args.ribosome and (args.part or args.frame_from or args.frame_to):
        raise SystemExit("--ribosome takes its parts and frame from the measuring tool's two-subunit mode: give no --part or frame")
    if args.by == "parts" and not args.ribosome and not args.part:
        raise SystemExit("--by parts needs --part, or --ribosome")
    record = shape(args.entry, args)
    text = json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n"
    if len(text.encode("utf-8")) > args.most_bytes:
        raise SystemExit(f"{Path(args.entry).name}: {len(text.encode('utf-8'))} bytes, above the budget of {args.most_bytes}; nothing is made")
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}: {record['counts']['meshes']} surfaces, {record['counts']['triangles']} triangles, {len(text.encode('utf-8')):,} bytes")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
