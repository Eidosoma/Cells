"""Independent stdlib polygons, ordered ownership and oriented graph arithmetic.

Native-generated topology is an explicit input, not an independent Delaunay or
mesh-generation implementation. No production, NumPy, SciPy or JAX imports.
"""

from math import fsum, hypot


def polygon(points):
    terms = [
        a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1], strict=True)
    ]
    area = fsum(terms) / 2
    if area <= 0:
        raise ValueError("Require strictly positive CCW polygon area")
    centre = [
        fsum(
            (a[k] + b[k]) * v
            for a, b, v in zip(points, points[1:] + points[:1], terms, strict=True)
        )
        / (6 * area)
        for k in (0, 1)
    ]
    return area, centre


def incidence(edges, count):
    result = [[0.0] * count for _ in edges]
    for row, (a, b) in zip(result, edges, strict=True):
        row[a] = -1.0
        row[b] = 1.0
    return result


def face_incidence(faces, edges, reverse=False):
    result = [[0.0] * len(edges) for _ in faces]
    missing = []
    lookup = {tuple(edge): (i, 1.0) for i, edge in enumerate(edges)}
    lookup.update({(b, a): (i, -1.0) for i, (a, b) in enumerate(edges)})
    for k, face in enumerate(faces):
        other = face[-1:] + face[:-1] if reverse else face[1:] + face[:1]
        for a, b in zip(face, other, strict=True):
            if (a, b) in lookup:
                i, sign = lookup[(a, b)]
                result[k][i] = sign
            else:
                missing.append([k, a, b])
    return result, missing


def matvec(matrix, value):
    return [fsum(a * b for a, b in zip(row, value, strict=True)) for row in matrix]


def graph_laplacian(edges, dual_lengths, primal_lengths, areas):
    result = [[0.0] * len(areas) for _ in areas]
    for (a, b), dual, primal in zip(edges, dual_lengths, primal_lengths, strict=True):
        w = dual / primal
        result[a][a] -= w / areas[a]
        result[a][b] += w / areas[a]
        result[b][b] -= w / areas[b]
        result[b][a] += w / areas[b]
    return result


def grid_laplacian(shape, delta, bound):
    ny, nx = shape
    result = [[0.0] * (nx * ny) for _ in range(nx * ny)]
    for i in range(ny):
        for j in range(nx):
            k = i * nx + j
            side = None
            if i == 0 and j == 0:
                side = "S"
            elif i == ny - 1 and j == 0:
                side = "N"
            elif j == nx - 1 and i in (0, ny - 1):
                side = "E"
            elif i == 0:
                side = "S"
            elif i == ny - 1:
                side = "N"
            elif j == 0:
                side = "W"
            elif j == nx - 1:
                side = "E"
            if side is not None and bound[side] == "value":
                result[k][k] = 1 / delta**2
            else:
                for ii, jj in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
                    if 0 <= ii < ny and 0 <= jj < nx:
                        result[k][ii * nx + jj] = 1 / delta**2
                        result[k][k] -= 1 / delta**2
    return result


def cell_geometry(record):
    raw = record["input"]
    height = raw["cell"]["cell_height"]
    scale = raw["cell"]["scale_cell"]
    polygons = record["mesh"]["vcell_verts"]
    areas, centres = zip(*(polygon(points) for points in polygons), strict=True)
    result = dict(
        cell_centres=list(centres),
        cell_verts=[],
        mem_edges_flat=[],
        mem_mids_flat=[],
        mem_sa=[],
        mem_vol=[],
        mem_vects_flat=[],
        mem_to_cells=[],
        cell_to_mems=[],
        cell_vol=[],
        cell_sa=[],
        polygon_volume_m3=[],
    )
    for cell, (points, centre) in enumerate(zip(polygons, centres, strict=True)):
        shrunk = [[centre[k] + scale * (v[k] - centre[k]) for k in (0, 1)] for v in points]
        result["cell_verts"].append(shrunk)
        start = len(result["mem_sa"])
        for a, b in zip(shrunk[-1:] + shrunk[:-1], shrunk, strict=True):
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = hypot(dx, dy)
            tx, ty = dx / length, dy / length
            mid = [(a[k] + b[k]) / 2 for k in (0, 1)]
            sa = length * height
            radius = hypot(mid[0] - centre[0], mid[1] - centre[1])
            result["mem_edges_flat"].append([a, b])
            result["mem_mids_flat"].append(mid)
            result["mem_sa"].append(sa)
            result["mem_vol"].append(radius * sa / 2)
            result["mem_vects_flat"].append([*mid, ty, -tx, tx, ty])
            result["mem_to_cells"].append(cell)
        group = list(range(start, len(result["mem_sa"])))
        result["cell_to_mems"].append(group)
        result["cell_vol"].append(fsum(result["mem_vol"][i] for i in group))
        result["cell_sa"].append(fsum(result["mem_sa"][i] for i in group))
        result["polygon_volume_m3"].append(polygon(shrunk)[0] * height)
    result["voronoi_volume_before_patch_m3"] = [v * height for v in areas]
    return result


def contacts(geometry, raw):
    mids = geometry["mem_mids_flat"]
    normals = [v[2:4] for v in geometry["mem_vects_flat"]]
    radius = 3 * (1 - raw["cell"]["scale_cell"]) * raw["cell"]["cell_radius"]
    pairs = []
    boundary = []
    candidates = []
    for i, point in enumerate(mids):
        found = [j for j, p in enumerate(mids) if hypot(p[0] - point[0], p[1] - point[1]) <= radius]
        candidates.append(found)
        if len(found) == 1:
            pairs.append([i, i])
            boundary.append(i)
        elif len(found) == 2:
            pairs.append(found)
        else:
            pair = []
            for j in found:
                pair = (
                    [i, j]
                    if round(fsum(a * b for a, b in zip(normals[i], normals[j], strict=True)), 1)
                    == -1.0
                    else [i, i]
                )
            pairs.append(pair)
    partner = [b if a == i else a for i, (a, b) in enumerate(pairs)]
    return dict(mem_nn=pairs, nn_i=partner, bflags_mems=boundary, candidates=candidates)


def cell_probes(geometry, record):
    probe = record["cell_probes"]["probe"]
    fx = record["cell_probes"]["fx"]
    fy = record["cell_probes"]["fy"]
    partner = record["cells"]["nn_i"]
    owner = geometry["mem_to_cells"]
    centres = geometry["cell_centres"]
    grad = []
    mean = []
    for i, j in enumerate(partner):
        a, b = owner[i], owner[j]
        distance = (
            hypot(centres[a][0] - centres[b][0], centres[a][1] - centres[b][1]) if a != b else -1
        )
        grad.append((probe[b] - probe[a]) / distance)
        mean.append((probe[a] + probe[b]) / 2)
    vector = geometry["mem_vects_flat"]
    sa = geometry["mem_sa"]
    volumes = geometry["cell_vol"]
    normals = [fx[i] * v[2] + fy[i] * v[3] for i, v in enumerate(vector)]
    boundary = set(record["cells"]["bflags_mems"])
    div = [
        fsum(normals[i] * sa[i] for i in group) / volume
        for group, volume in zip(geometry["cell_to_mems"], volumes, strict=True)
    ]
    closed = [
        fsum(normals[i] * sa[i] for i in group if i not in boundary) / volume
        for group, volume in zip(geometry["cell_to_mems"], volumes, strict=True)
    ]
    return dict(
        gradient=[
            grad,
            [g * v[2] for g, v in zip(grad, vector, strict=True)],
            [g * v[3] for g, v in zip(grad, vector, strict=True)],
        ],
        mean=mean,
        divergence=div,
        divergence_closed=closed,
    )


def solve_dense(matrix, values):
    """Small independent pivoted elimination, for explicit gauge test inputs."""
    rows = [list(row) + [v] for row, v in zip(matrix, values, strict=True)]
    n = len(rows)
    for k in range(n):
        pivot = max(range(k, n), key=lambda i: abs(rows[i][k]))
        if not rows[pivot][k]:
            raise ValueError("Singular reference system")
        rows[k], rows[pivot] = rows[pivot], rows[k]
        scale = rows[k][k]
        rows[k] = [v / scale for v in rows[k]]
        for i in range(n):
            if i != k:
                a = rows[i][k]
                rows[i] = [x - a * y for x, y in zip(rows[i], rows[k], strict=True)]
    return [row[-1] for row in rows]
