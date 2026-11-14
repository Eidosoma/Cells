"""Lay out a hexagonal sheet of cells from who is joined to whom.

Saved runs name each junction's two cells but give no coordinates. For a sheet whose
cells sit on a hexagonal lattice the junction graph fixes the layout exactly, up to where
it is put, which way it is turned and its handedness:

  * three cells joined to one another are a triangle of the lattice;
  * for two joined cells x and y with a common neighbour z, their other common neighbour
    lies at x + y - z (the two triangles on an edge form a parallelogram).

So one triangle is placed by hand and every other cell follows. The result is checked:
every cell placed, no two in one place, every junction between lattice neighbours.

Coordinates are axial lattice coordinates (q, r). Standard library only.
"""

from __future__ import annotations

import math
from collections import deque

# The six neighbours of a lattice site, in order round the site.
DIRECTIONS = ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1))


class LayoutError(ValueError):
    """The junction graph is not a sheet on a hexagonal lattice."""


def embed(count, edges):
    """Axial coordinates [(q, r)] for cells 0..count-1, from the junctions' (a, b) pairs.

    The first triangle found from the best-connected, lowest-numbered cell is placed at
    (0, 0), (1, 0), (0, 1). That choice fixes the turn and the handedness; both are
    arbitrary, and the same input always gives the same layout.
    """
    neighbours = [set() for _ in range(count)]
    for a, b in edges:
        if not (0 <= a < count and 0 <= b < count) or a == b:
            raise LayoutError(f"junction between cells {a} and {b}: not two cells of the sheet")
        neighbours[a].add(b)
        neighbours[b].add(a)
    crowded = [index for index, near in enumerate(neighbours) if len(near) > 6]
    if crowded:
        raise LayoutError(f"cell {crowded[0]} has {len(neighbours[crowded[0]])} neighbours; a hexagonal sheet allows six")

    start = min(range(count), key=lambda index: (-len(neighbours[index]), index))
    seed = None
    for second in sorted(neighbours[start]):
        common = sorted(neighbours[start] & neighbours[second])
        if common:
            seed = (start, second, common[0])
            break
    if seed is None:
        raise LayoutError("no three cells are joined to one another, so the sheet cannot be laid out")

    place = {seed[0]: (0, 0), seed[1]: (1, 0), seed[2]: (0, 1)}
    seen = {frozenset(seed)}
    queue = deque([seed])
    while queue:
        a, b, c = queue.popleft()
        for x, y, z in ((a, b, c), (b, c, a), (c, a, b)):
            across = (neighbours[x] & neighbours[y]) - {z}
            if len(across) > 1:
                raise LayoutError(f"cells {x} and {y} share {len(across) + 1} neighbours; a hexagonal sheet allows two")
            for w in across:
                site = (place[x][0] + place[y][0] - place[z][0], place[x][1] + place[y][1] - place[z][1])
                if place.setdefault(w, site) != site:
                    raise LayoutError(f"cell {w} would lie in two places; the junctions do not form a hexagonal sheet")
                triangle = frozenset((x, y, w))
                if triangle not in seen:
                    seen.add(triangle)
                    queue.append((x, y, w))

    missing = [index for index in range(count) if index not in place]
    if missing:
        raise LayoutError(f"{len(missing)} of {count} cells could not be placed (first: cell {missing[0]})")
    sites = {}
    for index in range(count):
        other = sites.setdefault(place[index], index)
        if other != index:
            raise LayoutError(f"cells {other} and {index} would lie in the same place")
    for a, b in edges:
        step = (place[b][0] - place[a][0], place[b][1] - place[a][1])
        if step not in DIRECTIONS:
            raise LayoutError(f"the junction between cells {a} and {b} does not join lattice neighbours")
    return [place[index] for index in range(count)]


def cartesian(q, r, pitch):
    """Where a lattice point lies, for neighbours `pitch` apart (the q axis along x)."""
    return pitch * (q + r / 2), pitch * (math.sqrt(3) / 2) * r


def hexagons(coordinates, pitch, digits=4):
    """Regular hexagons for the cells, sharing corners, centred on the sheet's middle.

    Returns (vertices, faces, centres): vertices as [x, y], one face of six vertex
    indices per cell (in the order of `coordinates`, going round the cell), and each
    cell's centre. A hexagon's corner is the middle of the triangle the cell forms with
    two neighbouring sites, so corners are keyed exactly, in thirds of a lattice step.
    """
    points = [cartesian(q, r, pitch) for q, r in coordinates]
    middle = (sum(x for x, _ in points) / len(points), sum(y for _, y in points) / len(points))
    tidy = lambda value: round(value, digits) + 0.0  # noqa: E731  (adding 0.0 turns -0.0 into 0.0)
    index_of, vertices, faces = {}, [], []
    for q, r in coordinates:
        face = []
        for k in range(6):
            first, second = DIRECTIONS[k], DIRECTIONS[(k + 1) % 6]
            key = (3 * q + first[0] + second[0], 3 * r + first[1] + second[1])
            if key not in index_of:
                x, y = cartesian(key[0] / 3, key[1] / 3, pitch)
                index_of[key] = len(vertices)
                vertices.append([tidy(x - middle[0]), tidy(y - middle[1])])
            face.append(index_of[key])
        faces.append(face)
    centres = [[tidy(x - middle[0]), tidy(y - middle[1])] for x, y in points]
    return vertices, faces, centres
