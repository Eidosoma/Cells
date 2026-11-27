#!/usr/bin/env python3
"""A machine's shape: a smooth, low-resolution surface the viewer works out from a Protein Data Bank entry's coordinates.

The sibling of tools/measure_particle.py, whose reader and frame it uses unchanged, so that a shape sits
exactly where the measure's ellipsoid sits (schema/MACHINE_SHAPES.md). A PDB entry states no surface:
every surface here is the viewer's own, an illustration, and is named so wherever it is written.

The definition, the same for every machine (one sentence, its numbers in the file):
    each chain is the closed surface that holds its own volume (0.135 nm³ for each amino acid, 0.32 nm³ for
    each nucleotide) in a cloud where each residue is spread as a Gaussian 1 nm wide, on a grid 1 nm apart;
    where a machine is drawn by its parts (a ribosome, whose fifty chains are too many to tell apart at this
    resolution), the whole is one solid of all its residues at 1.6 nm, divided between its parts, so that each
    part is one solid and the parts meet at a shared face; a part of protein and nucleic acid is divided again
    into two tones, each inside the part or on it. Of a surface in pieces, its largest and every piece of at
    least 5% of its volume are kept; smaller slivers are dropped, and the file lists what they held.
The widths were weighed on 17 November 2026 (0.8, 1.0 and 1.4 nm for a chain; 1.2, 1.6 and 2.0 nm for a part),
and the user chose these the same day: they hold the budget (schema/MACHINE_SHAPES.md) without a pass that
simplifies the surfaces. A part's solid replaced its separate protein and nucleic-acid surfaces on 17 November
2026: those stood apart, so that a ribosome's subunits did not meet. On 18 November 2026 the budget became what one
chosen machine draws, 12,000 triangles (its solids, or its tones), and 250,000 bytes a file; a machine too large for
it at the setting (the human proteasome, complex I, the IP3 receptor, the 80S and mitochondrial ribosomes) is made at
the finest width, in steps of 0.1 nm, that holds it, given with --width and stated in its file.

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
one surface for each chain; with --by parts one solid for each named part (or subunit), and its two tones.
A part's solid and tones are drawn on the same tetrahedra as the whole, each face clipped by the fields that
bound it, and every vertex where several fields meet is worked out once from the corners and fields that
make it, so that the parts share their faces exactly and the tones fill their part.

Standard library only. It reads the file it is given (untrusted data, by the measuring tool's reader)
and writes only --out. It refuses, and writes nothing, where a part, a frame's part or a subunit has no
atom, or the shapes would break the budget (--most-triangles, --most-bytes).

    python3 -I tools/shape_particle.py ENTRY.cif.gz --measure MEASURE.json [--by chains|parts] [--width NM] [--out FILE]
    python3 -I tools/shape_particle.py ENTRY.cif.gz [--exclude IDS] [--part NAME=IDS ...]
        [--frame-from PART --frame-to PART] [--ribosome] [--by chains|parts] [--width NM] [--out FILE]
With --measure the parts, the frame and what was left out are read from the measure's record, as its
call gave them (since 18 November 2026 every shape file in the tree is made so).
"""

from __future__ import annotations

import argparse
import json
import math
import re
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
SHARE = 0.05  # a surface's piece is kept if it is its largest or holds at least this share of its volume; smaller slivers are dropped
# The six tetrahedra of a cube, all along the diagonal from corner 0 to corner 6, so that neighbouring cubes meet.
CORNERS = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
TETRAHEDRA = [(0, 5, 1, 6), (0, 1, 2, 6), (0, 2, 3, 6), (0, 3, 7, 6), (0, 7, 4, 6), (0, 4, 5, 6)]


def definition(width, grid, by="chains"):
    volumes = f"{VOLUME['protein']} nm³ for each amino acid, {VOLUME['nucleic']} nm³ for each nucleotide"
    pieces = f"; of a surface in pieces, its largest and every piece of at least {SHARE:.0%} of its volume are kept, smaller ones dropped (listed under dropped)"
    setting = WIDTH[by]
    if width > setting:
        width_note = f" (coarser than the setting's {setting:g} nm, to hold the budget)"
    elif width < setting:
        width_note = f" (finer than the standard {setting:g} nm setting)"
    else:
        width_note = ""
    if by == "chains":
        return f"each chain as the closed surface that holds its own volume ({volumes}) in a cloud where each residue is spread as a Gaussian {width:g} nm wide, on a grid {grid:g} nm apart{width_note}{pieces}"
    return (
        f"each part as one solid: the closed surface that holds its residues' own volume ({volumes}), protein and nucleic acid together, in a cloud "
        f"where each residue is spread as a Gaussian {width:g} nm wide weighted by its volume, on a grid {grid:g} nm apart{width_note}{pieces}; for two tones, "
        "that solid divided where the nucleic acid's share of the cloud is the greater and where the protein's is (under tones, each inside the solid or on it)"
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


class Cloud:
    """Residues spread as Gaussians on one grid (in ångström), and the closed surfaces where a field on that grid crosses
    a level, by marching tetrahedra: each grid cell cut into six tetrahedra along one diagonal, so that neighbouring cells
    meet; closed, every edge shared by two triangles, each triangle facing out."""

    # The steps that join two grid points along an edge of the tetrahedra: every sum of distinct unit steps, both ways.
    STEPS = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1), (0, 1, 1), (1, 1, 1)]
    STEPS = STEPS + [(-a, -b, -c) for a, b, c in STEPS]

    def __init__(self, points, width, grid):
        self.sigma, self.h = width * 10, grid * 10  # ångström: the Gaussian's width, and the grid's spacing
        pad = REACH * self.sigma + 2 * self.h
        self.low = [min(p[i] for p in points) - pad for i in range(3)]
        self.nx, self.ny, self.nz = [int(math.ceil((max(p[i] for p in points) + pad - self.low[i]) / self.h)) + 1 for i in range(3)]
        self.busy = []

    def point(self, a):
        k = a % self.nz
        j = (a // self.nz) % self.ny
        i = a // (self.nz * self.ny)
        return (self.low[0] + i * self.h, self.low[1] + j * self.h, self.low[2] + k * self.h)

    def spread(self, points, weights=None):
        """The cloud: each point a Gaussian of its weight (1 unless given), summed at the grid's points."""
        nx, ny, nz, low, h, sigma = self.nx, self.ny, self.nz, self.low, self.h, self.sigma
        field = [0.0] * (nx * ny * nz)
        reach = int(math.ceil(REACH * sigma / h))
        two = 2 * sigma * sigma
        for n, (x, y, z) in enumerate(points):
            w = 1.0 if weights is None else weights[n]
            ci, cj, ck = int(round((x - low[0]) / h)), int(round((y - low[1]) / h)), int(round((z - low[2]) / h))
            for i in range(ci - reach, ci + reach + 1):
                dx = (low[0] + i * h - x) ** 2
                for j in range(cj - reach, cj + reach + 1):
                    dxy = dx + (low[1] + j * h - y) ** 2
                    row = (i * ny + j) * nz
                    for k in range(ck - reach, ck + reach + 1):
                        d = dxy + (low[2] + k * h - z) ** 2
                        if d < 9 * sigma * sigma:
                            field[row + k] += w * math.exp(-d / two)
        return field

    def cells(self, field):
        """The cells a surface of this field may cross at any level above the lowest, found once."""
        at = lambda i, j, k: (i * self.ny + j) * self.nz + k  # noqa: E731
        self.busy = []
        for i in range(self.nx - 1):
            for j in range(self.ny - 1):
                for k in range(self.nz - 1):
                    corners = [at(i + a, j + b, k + c) for a, b, c in CORNERS]
                    if max(field[n] for n in corners) > 0:
                        self.busy.append(corners)

    def contour(self, values, level):
        """The surface where `values` cross `level`: vertices (ångström), triangles, and the volume it holds (nm³)."""
        vertices, index, triangles = [], {}, []
        point = self.point

        def cut(a, b):
            """The vertex where the surface crosses the edge from grid point a to grid point b (shared by every tetrahedron on that edge)."""
            key = (a, b) if a < b else (b, a)
            if key not in index:
                fa, fb = values[a] - level, values[b] - level
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

        for corners in self.busy:
            above = [values[n] > level for n in corners]
            if all(above) or not any(above):
                continue
            for tetra in TETRAHEDRA:
                ids = [corners[n] for n in tetra]
                inside = [n for n in ids if values[n] > level]
                outside = [n for n in ids if values[n] <= level]
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
        return vertices, triangles, held(vertices, triangles) / 1000

    def region(self, functions):
        """The closed surface round the space where each of several fields is on its own side of zero, as the tetrahedra
        interpolate them. `functions`: (name, values, side), side 1 keeping the values above zero and -1 those at or below
        it, so that a field shared by two neighbouring regions with opposite sides divides them along one face. In each
        tetrahedron each field's zero is cut out and clipped by the others; a vertex where several zeros meet is worked
        out once from the corners and the fields that make it (whichever tetrahedron finds it), so that every surface
        drawn on these fields shares it exactly. Returns vertices (ångström), triangles, each vertex's key (its corners
        and the fields zero there), the fields' values at each vertex, and how many triangles come first that lie on
        the first field's zero (the outside, where the first field is the whole's); the rest lie on another's."""
        values = {name: v for name, v, _ in functions}
        side = {name: s for name, _, s in functions}
        names = [name for name, _, _ in functions]
        index, vertices, keys, weights, triangles, on_first = {}, [], [], [], [], []
        point = self.point

        def within(name, value):
            return value > 0 if side[name] > 0 else not value > 0

        def vertex(corners, zeros):
            key = (corners, zeros)
            if key not in index:
                rows = [[1.0] * len(corners) + [1.0]] + [[values[z][c] for c in corners] + [0.0] for z in zeros]
                w = solve(rows)
                index[key] = len(vertices)
                vertices.append(tuple(sum(w[i] * point(c)[n] for i, c in enumerate(corners)) for n in range(3)))
                keys.append(key)
                weights.append(w)
            return index[key]

        def at(n, name):
            """A field's value at vertex n: zero where it is one of the fields that make it."""
            corners, zeros = keys[n]
            return 0.0 if name in zeros else sum(w * values[name][c] for w, c in zip(weights[n], corners))

        for corners in self.busy:
            for tetra in TETRAHEDRA:
                ids = [corners[n] for n in tetra]
                inside = {name: [within(name, values[name][c]) for c in ids] for name in names}
                if any(not any(flags) for flags in inside.values()) or all(all(flags) for flags in inside.values()):
                    continue
                for g in names:
                    flags = inside[g]
                    if all(flags) or not any(flags):
                        continue
                    ins = [c for c, f in zip(ids, flags) if f]
                    outs = [c for c, f in zip(ids, flags) if not f]
                    cut = lambda a, b: vertex(tuple(sorted((a, b))), (g,))  # noqa: E731
                    if len(ins) == 1 or len(outs) == 1:
                        one, rest = (ins[0], outs) if len(ins) == 1 else (outs[0], ins)
                        polygon = [cut(one, other) for other in rest]
                    else:
                        polygon = [cut(ins[0], outs[0]), cut(ins[0], outs[1]), cut(ins[1], outs[1]), cut(ins[1], outs[0])]
                    for h in names:
                        if h == g or not polygon:
                            continue
                        kept_, count = [], len(polygon)
                        on = [h in keys[n][1] or within(h, at(n, h)) for n in polygon]
                        for i in range(count):
                            a, b = polygon[i], polygon[(i + 1) % count]
                            if on[i]:
                                kept_.append(a)
                            if on[i] != on[(i + 1) % count] and h not in keys[a][1] and h not in keys[b][1]:
                                corners_ = tuple(sorted(set(keys[a][0]) | set(keys[b][0])))
                                zeros = tuple(sorted((set(keys[a][1]) & set(keys[b][1])) | {h}))
                                kept_.append(vertex(corners_, zeros))
                        polygon = [n for i, n in enumerate(kept_) if n != kept_[i - 1]] if len(kept_) > 1 else kept_
                    if len(polygon) < 3:
                        continue
                    # Facing out: away from the corners where this field keeps the region.
                    cin = [sum(point(c)[n] for c in ins) / len(ins) for n in range(3)]
                    cout = [sum(point(c)[n] for c in outs) / len(outs) for n in range(3)]
                    out = [cout[n] - cin[n] for n in range(3)]
                    p = [vertices[n] for n in polygon]
                    normal = [0.0, 0.0, 0.0]
                    for i in range(len(p)):
                        u, v = p[i], p[(i + 1) % len(p)]
                        normal[0] += (u[1] - v[1]) * (u[2] + v[2])
                        normal[1] += (u[2] - v[2]) * (u[0] + v[0])
                        normal[2] += (u[0] - v[0]) * (u[1] + v[1])
                    if M.dot(normal, out) < 0:
                        polygon = polygon[::-1]
                    triangles += [(polygon[0], polygon[i], polygon[i + 1]) for i in range(1, len(polygon) - 1)]
                    on_first += [g == names[0]] * (len(polygon) - 2)
        # The triangles on the first field's zero first, each set in the order found.
        triangles = [tri for tri, first in zip(triangles, on_first) if first] + [tri for tri, first in zip(triangles, on_first) if not first]
        # Only the vertices the triangles use (a cut that a later field clipped away is not one), in their order.
        used = sorted({n for tri in triangles for n in tri})
        renumber = {old: new for new, old in enumerate(used)}
        vertices, keys[:], weights[:] = [vertices[n] for n in used], [keys[n] for n in used], [weights[n] for n in used]
        return vertices, [tuple(renumber[n] for n in tri) for tri in triangles], keys, at, sum(on_first)

    def level(self, field, wanted):
        """The level at which the surface of `field` holds `wanted` nm³ (to within 1%), found by halving on a logarithmic
        scale, and that surface."""
        top = max(field)
        lo, hi = top * 1e-4, top
        for _ in range(40):
            middle = math.sqrt(lo * hi)
            made = self.contour(field, middle)
            if abs(made[2] - wanted) <= 0.01 * wanted:
                break
            if made[2] > wanted:
                lo = middle
            else:
                hi = middle
        return middle, made


def solve(rows):
    """A small linear system (each row its coefficients and then its value), by elimination with the largest pivot."""
    rows = [list(row) for row in rows]
    size = len(rows)
    for col in range(size):
        pivot = max(range(col, size), key=lambda r: abs(rows[r][col]))
        rows[col], rows[pivot] = rows[pivot], rows[col]
        for r in range(size):
            if r != col and rows[col][col] != 0:
                factor = rows[r][col] / rows[col][col]
                rows[r] = [x - factor * y for x, y in zip(rows[r], rows[col])]
    return [rows[r][size] / rows[r][r] if rows[r][r] != 0 else 0.0 for r in range(size)]


def split(triangles, count):
    """A surface's pieces: its triangles joined where they share a vertex, each piece a list of triangle numbers."""
    parent = list(range(count))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b, c in triangles:
        parent[find(b)] = find(a)
        parent[find(c)] = find(a)
    pieces = {}
    for n, tri in enumerate(triangles):
        pieces.setdefault(find(tri[0]), []).append(n)
    return list(pieces.values())


def enclosed(point, vertices, triangles):
    """Whether a point lies inside a closed surface: the parity of a ray's crossings, in a direction no grid follows."""
    d = (1.0, 0.3713, 0.1781)
    crossings = 0
    for a, b, c in triangles:
        p0, p1, p2 = vertices[a], vertices[b], vertices[c]
        e1, e2 = [p1[n] - p0[n] for n in range(3)], [p2[n] - p0[n] for n in range(3)]
        h = M.cross(d, e2)
        det = M.dot(e1, h)
        if abs(det) < 1e-12:
            continue
        s_ = [point[n] - p0[n] for n in range(3)]
        u = M.dot(s_, h) / det
        if u < 0 or u > 1:
            continue
        q = M.cross(s_, e1)
        v = M.dot(d, q) / det
        if v < 0 or u + v > 1:
            continue
        if M.dot(e2, q) / det > 0:
            crossings += 1
    return crossings % 2 == 1


def kept(vertices, triangles):
    """A surface's pieces: the largest, and every one that holds at least SHARE of the whole's volume; the rest dropped.
    Returns the kept surface (its vertices renumbered, in their order) and the pieces dropped (their vertices and
    triangles, and the volume they held, nm³)."""
    pieces = split(triangles, len(vertices))
    volume = [held(vertices, [triangles[n] for n in piece]) / 1000 for piece in pieces]
    whole = sum(volume)
    largest = max(range(len(pieces)), key=lambda n: volume[n]) if pieces else None
    keep = [n == largest or volume[n] >= SHARE * whole for n in range(len(pieces))]
    if all(keep):
        return vertices, triangles, [], keep, pieces, list(range(len(triangles)))
    lost = [([triangles[n] for n in pieces[i]], volume[i]) for i in range(len(pieces)) if not keep[i]]
    order = sorted(n for i, piece in enumerate(pieces) if keep[i] for n in piece)
    chosen = [triangles[n] for n in order]
    used = sorted({n for tri in chosen for n in tri})
    renumber = {old: new for new, old in enumerate(used)}
    return [vertices[n] for n in used], [tuple(renumber[n] for n in tri) for tri in chosen], lost, keep, pieces, order


def losses(lost, vertices, points, chains):
    """What the dropped pieces held: their count, volume, and the residues whose standing atom lies inside one, by chain."""
    within = [chain for point, chain in zip(points, chains) if any(enclosed(point, vertices, tris) for tris, _ in lost)]
    return {"pieces": len(lost), "volume_nm3": sum(volume for _, volume in lost), "within": within}


def surface(points, kind, width, grid, chains):
    """A chain's surface: the closed surface that holds its residues' own volume in their Gaussian cloud, with its
    slivers dropped. Returns vertices (ångström), triangles, and what was dropped (or None)."""
    cloud = Cloud(points, width, grid)
    field = cloud.spread(points)
    cloud.cells(field)
    _, (vertices, triangles, _) = cloud.level(field, len(points) * VOLUME[kind])
    all_vertices = vertices
    vertices, triangles, lost, _, _, _ = kept(vertices, triangles)
    return vertices, triangles, losses(lost, all_vertices, points, chains) if lost else None


def solids(points, kinds, parts, chains, width, grid):
    """A machine drawn by its parts: the whole as one solid, the closed surface that holds all its residues' own volume
    (protein and nucleic acid together) in their cloud, each residue's Gaussian weighted by its volume; divided between
    the parts where each part's share of the cloud is the greater (each pair of parts by the difference of their clouds),
    so that each part is one solid and neighbouring parts meet at one shared face. Where a part holds both kinds, its two
    tones divide it again where its nucleic acid's cloud is the greater and where its protein's is: closed, inside the
    part or on it, and filling it. Slivers of a part are dropped, and its tones' pieces inside them.
    Returns, for each part: its surface (vertices in ångström, triangles), what was dropped (or None), and its tones by kind."""
    cloud = Cloud(points, width, grid)
    names = list(dict.fromkeys(parts))
    present = sorted(set(kinds))
    own = {}
    for name in names:
        for kind in present:
            mine = [point for point, k, part in zip(points, kinds, parts) if k == kind and part == name]
            if mine:
                own[(name, kind)] = cloud.spread(mine, [VOLUME[kind]] * len(mine))
    by_part = {name: [sum(values) for values in zip(*(own[(name, kind)] for kind in present if (name, kind) in own))] for name in names}
    field = [sum(values) for values in zip(*by_part.values())] if len(names) > 1 else by_part[names[0]]
    cloud.cells(field)
    level, _ = cloud.level(field, sum(VOLUME[kind] for kind in kinds))
    whole = ("whole", [value - level for value in field], 1)
    pairs = {(p, q): [x - y for x, y in zip(by_part[p], by_part[q])] for i, p in enumerate(names) for q in names[i + 1:]}
    made = {}
    for name in names:
        fields = [whole] + [(f"pair {p} {q}", values, 1 if p == name else -1) for (p, q), values in pairs.items() if name in (p, q)]
        vertices, triangles, keys, at, outside = cloud.region(fields)
        all_vertices, all_triangles = vertices, triangles
        vertices, triangles, lost, keep, pieces, order = kept(vertices, triangles)
        outer = sum(1 for n in order if n < outside)
        mine = [(point, chain) for point, part, chain in zip(points, parts, chains) if part == name]
        dropped = losses(lost, all_vertices, [p for p, _ in mine], [c for _, c in mine]) if lost else None
        tones = {}
        held_kinds = [kind for kind in present if (name, kind) in own]
        if len(held_kinds) == 2:
            nucleic_less_protein = [x - y for x, y in zip(own[(name, "nucleic")], own[(name, "protein")])]
            # The part's dropped pieces, by the keys of their vertices: a tone's piece that shares a key with one is dropped too.
            lost_keys = {keys[v] for i, piece in enumerate(pieces) if not keep[i] for t in piece for v in all_triangles[t]}
            for kind in held_kinds:
                tv, tt, tk, tat, toutside = cloud.region(fields + [(f"kinds {name}", nucleic_less_protein, 1 if kind == "nucleic" else -1)])
                torder = list(range(len(tt)))
                # Inside the part or on it: at every vertex each of the part's fields is on its side, or zero.
                lowest = min((side * tat(n, field_name) for n in range(len(tv)) for field_name, _, side in fields), default=0.0) / level
                if lost_keys:
                    tpieces = split(tt, len(tv))
                    torder = sorted(n for piece in tpieces if not any(tk[v] in lost_keys for t in piece for v in tt[t]) for n in piece)
                    tt = [tt[n] for n in torder]
                used = sorted({n for tri in tt for n in tri})
                renumber = {old: new for new, old in enumerate(used)}
                tones[kind] = {"vertices": [tv[n] for n in used], "triangles": [tuple(renumber[n] for n in tri) for tri in tt], "lowest": lowest,
                               "outer": sum(1 for n in torder if n < toutside)}
        if not all(tone["triangles"] for tone in tones.values()):
            tones = {}  # one kind is the greater nowhere: the part is all one tone, and its solid is drawn as it is
        made[name] = (vertices, triangles, dropped, tones, outer)
    return made


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
    # What each surface is drawn from: a chain's residues, or a part's (its protein and nucleic acid together).
    groups = {}
    for xyz, entity, chain, kind, _ in stand:
        if args.by == "chains":
            key = ("chain", chain)
        else:
            name = owner.get(("entities", entity)) or owner.get(("chains", chain))
            if not name:
                continue
            key = ("part", name)
        group = groups.setdefault(key, {"points": [], "kinds": [], "chains": [], "entity": entity, "chain": chain, "kind": kind})
        group["points"].append(xyz)
        group["kinds"].append(kind)
        group["chains"].append(chain)
    placed = lambda vertices: [int(round(value / 10 / UNIT)) for vertex in vertices for value in inside([vertex[n] - origin[n] for n in range(3)])]  # noqa: E731
    flat = lambda triangles: [n for tri in triangles for n in tri]  # noqa: E731
    meshes, tones, dropped, unsure = [], [], [], []
    if args.by == "parts" and groups:
        every_point = [point for group in groups.values() for point in group["points"]]
        every_kind = [kind for group in groups.values() for kind in group["kinds"]]
        every_part = [key[1] for key, group in groups.items() for _ in group["points"]]
        every_chain = [chain for group in groups.values() for chain in group["chains"]]
        divided = solids(every_point, every_kind, every_part, every_chain, args.width, args.grid)
    for key, group in groups.items():
        two = {}
        if key[0] == "chain":
            vertices, triangles, lost = surface(group["points"], group["kind"], args.width, args.grid, group["chains"])
            mesh = {"id": f"chain-{group['chain']}", "chain": group["chain"], "entity": group["entity"], "description": names.get(group["entity"], ""),
                    "part": owner.get(("entities", group["entity"])) or owner.get(("chains", group["chain"])), "kind": group["kind"]}
            each = VOLUME[group["kind"]]
        else:
            vertices, triangles, lost, two, outer = divided[key[1]]
            present = sorted(set(group["kinds"]))
            mesh = {"id": f"part-{key[1]}", "part": key[1], "kind": present[0] if len(present) == 1 else "nucleoprotein", "outer": outer}
            each = sum(VOLUME[kind] for kind in group["kinds"]) / len(group["kinds"])
        if not triangles:
            continue
        mesh.update({"residues": len(group["points"]), "vertices": placed(vertices), "triangles": flat(triangles)})
        meshes.append(mesh)
        if lost:
            # What was dropped: its pieces, the volume they held (and as how many residues' volume), the residues whose
            # standing atom lies inside them, and their chains.
            dropped.append({"surface": mesh["id"], "pieces": lost["pieces"], "volume_nm3": round(lost["volume_nm3"], 2), "residues_volume": round(lost["volume_nm3"] / each, 1),
                            "residues_within": len(lost["within"]), "chains": [group["chain"]] if key[0] == "chain" else sorted(set(lost["within"]))})
        # The two tones are kept only where they lie inside the solid or on it (as they are made to); else left out, and said.
        if two and all(tone["lowest"] >= -1e-9 for tone in two.values()):
            for kind, tone in sorted(two.items()):
                tones.append({"id": f"part-{key[1]}-{kind}", "within": mesh["id"], "part": key[1], "kind": kind, "residues": group["kinds"].count(kind),
                              "outer": tone["outer"], "vertices": placed(tone["vertices"]), "triangles": flat(tone["triangles"])})
        elif two:
            unsure.append(mesh["id"])
    # The budget is what one chosen machine draws: its meshes, or its meshes with each part's tones in its solid's place.
    toned = {tone["within"] for tone in tones}
    total = max(sum(len(mesh["triangles"]) // 3 for mesh in meshes), sum(len(mesh["triangles"]) // 3 for mesh in [m for m in meshes if m["id"] not in toned] + tones))
    if total > args.most_triangles:
        raise SystemExit(f"{file}: {total} triangles drawn, above the budget of {args.most_triangles}; nothing is made")
    counted = lambda items: {"meshes": len(items), "vertices": sum(len(item["vertices"]) // 3 for item in items), "triangles": sum(len(item["triangles"]) // 3 for item in items)}  # noqa: E731
    described = M.described(data, path)
    return {
        "format": FORMAT,
        "tool": "tools/shape_particle.py",
        "definition": definition(args.width, args.grid, args.by),
        "illustration": "The viewer's own surface of the entry's coordinates, an illustration: not the structure, and nothing of the entry is copied but the numbers worked out here. The Protein Data Bank states no surface.",
        "parameters": {"width_nm": args.width, "grid_nm": args.grid, "reach_widths": REACH, "volume_nm3": VOLUME, "stands_for": {kind: list(atoms) for kind, atoms in STANDS_FOR.items()}, "by": args.by, "piece_share": SHARE,
                       **({"setting_width_nm": WIDTH[args.by]} if args.width != WIDTH[args.by] else {})},
        **described,
        "left_out": [{"entity": entity, "description": names.get(entity, "")} for entity in exclude if entity in names],
        "frame": frame_words,
        "unit_nm": UNIT,
        "counts": {**counted(meshes), **({"tones": counted(tones)} if tones else {})},
        "dropped": dropped,
        **({"tones_left_out": {"surfaces": unsure, "why": "a tone did not lie inside its solid or on it"}} if unsure else {}),
        "meshes": meshes,
        **({"tones": tones} if tones else {}),
    }


def from_measure(args):
    """The options a measure was made with, read from its record (tools/measure_particle.py), so that the shape is made in
    its frame: its two-subunit mode (and any entity the caller placed), or its parts in their order, the parts its frame
    runs between (from its words) and the entities it left out."""
    record = json.loads(Path(args.measure).read_text(encoding="utf-8"))
    stem = Path(args.entry).name.split(".")[0]
    measured = record.get("measured") or {}
    found = measured.get(stem) or next((one for one in measured.values() if one.get("entry") == stem), None)
    if not found:
        raise SystemExit(f"{Path(args.measure).name} holds no measure of {stem}; nothing is made")
    frame = record.get("frame") or ""
    if frame.startswith("origin at the centre of both subunits' atoms"):
        args.ribosome = True
        for entity, said in (found.get("placed_by_the_caller") or {}).items():
            getattr(args, said["subunit"]).append(entity)
        return
    left = [item["entity"] if isinstance(item, dict) else item for item in found.get("left_out") or []]
    args.exclude = [",".join(left)] if left else []
    args.part = [f"{name}={'chains:' if body['by'] == 'chains' else ''}{','.join(body['ids'])}" for name, body in (found.get("parts") or {}).items()]
    said = re.search(r"y from the part (\S+)'s centre to the part (\S+)'s", frame)
    if said:
        args.frame_from, args.frame_to = said.groups()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("entry", help="an mmCIF file of a PDB entry, gzipped or not; a biological assembly's file as <id>-assembly1.cif.gz")
    parser.add_argument("--out", help="write the shapes here, as JSON (else they are printed)")
    parser.add_argument("--exclude", action="append", default=[], help="entity ids to leave out (comma-separated; may be given again)")
    parser.add_argument("--part", action="append", default=[], help="NAME=ENTITY,ENTITY or NAME=chains:A,B (may be given again), as the measuring tool takes it")
    parser.add_argument("--frame-from", help="the part whose centre the frame's y runs from")
    parser.add_argument("--frame-to", help="the part whose centre the frame's y runs to")
    parser.add_argument("--measure", help="take the parts, the frame and what was left out from this measure's record (tools/measure_particle.py), so that the shape is in its frame")
    parser.add_argument("--ribosome", action="store_true", help="the measuring tool's two-subunit mode: the parts large and small by their entities' names, and its frame")
    parser.add_argument("--large", action="append", default=[], help="with --ribosome: entity ids to place in the large subunit whatever their description says")
    parser.add_argument("--small", action="append", default=[], help="with --ribosome: entity ids to place in the small subunit whatever their description says")
    parser.add_argument("--by", choices=["chains", "parts"], default=None, help="one surface for each chain, or one solid for each part with its two tones (default: chains; parts with --ribosome)")
    parser.add_argument("--width", type=float, default=None, help=f"the Gaussian's width, in nm (default {WIDTH['chains']} for chains, {WIDTH['parts']} for parts)")
    parser.add_argument("--grid", type=float, default=None, help="the grid's spacing, in nm (default: the width)")
    parser.add_argument("--most-triangles", type=int, default=12000, help="the budget: refuse where one chosen machine would draw more triangles, as its solids or its tones (default 12,000)")
    parser.add_argument("--most-bytes", type=int, default=250000, help="the budget: refuse a file above this many bytes (default 250,000)")
    args = parser.parse_args()
    if args.measure:
        if args.part or args.exclude or args.frame_from or args.frame_to or args.ribosome or args.large or args.small:
            raise SystemExit("--measure gives the parts, the frame and what is left out: give none of them besides")
        from_measure(args)
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
