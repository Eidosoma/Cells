"""Explicit seed provenance and small native geometry/operator cases."""

from copy import deepcopy
from math import sqrt

UNIT = 2.0**-17


def cloud(n=3):
    return [
        [UNIT * (i + 0.5 * (j % 2)), UNIT * sqrt(3) * j / 2] for j in range(n) for i in range(n)
    ]


def base():
    points = cloud()
    return dict(
        name="centroid-core",
        seed=17,
        seed_points_m=points,
        seed_ids=[f"seed-r{j}-c{i}" for j in range(3) for i in range(3)],
        seed_policy="Explicit staggered triangular points; no production random generator",
        mesh=dict(
            cell_radius=UNIT / 2,
            mesh_type="tri",
            use_centroids=True,
            use_alpha_shape=False,
            alpha_shape=0.4,
            single_cell_sides=6,
            single_cell_noise=0.1,
            make_all_operators=False,
            allow_merging=False,
            merge_thresh=0.2,
            close_thresh=0.1,
        ),
        cell=dict(
            cell_radius=UNIT / 2,
            scale_cell=0.98,
            cell_space=UNIT * 0.02,
            cell_height=UNIT,
            tm=5e-9,
            grid_size=4,
        ),
        bounds_m=[-2 * UNIT, 6 * UNIT, -2 * UNIT, 6 * UNIT],
        environment_boundaries=dict(N="flux", S="flux", E="flux", W="flux"),
    )


def cases():
    result = [base()]
    item = base()
    item["name"] = "centroid-aux"
    item["mesh"]["make_all_operators"] = True
    result.append(item)
    item = deepcopy(item)
    item["name"] = "circumcenter-aux"
    item["mesh"]["use_centroids"] = False
    result.append(item)
    item = base()
    item["name"] = "irregular-centroid-aux"
    item["mesh"]["make_all_operators"] = True
    item["seed_points_m"][4][0] += 0.13 * UNIT
    item["seed_points_m"][4][1] -= 0.07 * UNIT
    result.append(item)
    item = deepcopy(item)
    item["name"] = "irregular-circumcenter-aux"
    item["mesh"]["use_centroids"] = False
    result.append(item)
    item = deepcopy(item)
    item["name"] = "translated-scaled-circumcenter"
    item["seed_points_m"] = [[2 * x + UNIT, 2 * y - UNIT] for x, y in item["seed_points_m"]]
    item["bounds_m"] = [-4 * UNIT, 12 * UNIT, -4 * UNIT, 12 * UNIT]
    item["mesh"]["cell_radius"] *= 2
    item["cell"]["cell_radius"] *= 2
    item["cell"]["cell_space"] *= 2
    result.append(item)
    for seed in (17, 23):
        item = base()
        item["name"] = f"native-single-preset-seed{seed}"
        item["seed"] = seed
        item["seed_points_m"] = None
        item["seed_ids"] = None
        item["seed_policy"] = "Actual DECMesh.make_single_cell_points; captured seed and RNG states"
        result.append(item)
    item = base()
    item["name"] = "merged-square-aux"
    item["seed_points_m"] = [[UNIT * i, UNIT * j] for j in range(3) for i in range(3)]
    item["mesh"].update(allow_merging=True, make_all_operators=True, mesh_type="quad")
    result.append(item)
    for n in (5, 9):
        item = base()
        item["name"] = f"directional-refinement-{n}"
        item["seed_points_m"] = [[2 * x / (n - 1), 2 * y / (n - 1)] for x, y in cloud(n)]
        item["seed_ids"] = [f"refine{n}-r{j}-c{i}" for j in range(n) for i in range(n)]
        item["mesh"]["cell_radius"] = UNIT / (n - 1)
        item["cell"]["cell_radius"] = UNIT / (n - 1)
        item["cell"]["cell_space"] = UNIT * 0.04 / (n - 1)
        result.append(item)
    item = base()
    item["name"] = "mixed-environment-corners"
    item["environment_boundaries"] = dict(N="value", S="flux", E="value", W="flux")
    result.append(item)
    return result


def limitations():
    result = []

    def add(name, **values):
        item = base()
        item["name"] = name
        item.update(values)
        result.append(item)
        return item

    add("too-few-seeds", seed_points_m=[[0, 0], [UNIT, 0]], seed_ids=["A", "B"])
    add("collinear-seeds", seed_points_m=[[i * UNIT, 0] for i in range(4)], seed_ids=list("ABCD"))
    item = add("duplicate-seed-removal")
    item["seed_points_m"].append(item["seed_points_m"][4][:])
    item["seed_ids"].append("duplicate-explicit-owner")
    item = add("close-seed-removal")
    item["seed_points_m"].append([UNIT * 1.50001, UNIT * sqrt(3) / 2])
    item["seed_ids"].append("close-explicit-owner")
    item = add("unmerged-cocircular-dual")
    item["mesh"]["use_centroids"] = False
    item["seed_points_m"] = [[UNIT * i, UNIT * j] for j in range(3) for i in range(3)]
    item = add("alpha-removes-all")
    item["mesh"].update(use_alpha_shape=True, alpha_shape=100.0)
    item = add("zero-cell-scale")
    item["cell"]["scale_cell"] = 0.0
    item = add("zero-height")
    item["cell"]["cell_height"] = 0.0
    item = add("nonintegral-grid-aspect")
    item["bounds_m"][-1] = 5 * UNIT
    item = add("core-missing-aux")
    item["probe_failure"] = "aux"
    item = add("unsupported-gradient-domain")
    item["probe_failure"] = "gtype"
    item = add("membrane-normal-y-source-bug")
    item["probe_failure"] = "normal-y"
    return result


def grid_cases():
    result = []
    for n in (4, 8, 16):
        result.append(
            dict(
                name=f"environment-refinement-{n}",
                n=n,
                bounds_m=[0, UNIT, 0, UNIT],
                boundaries=dict(N="flux", S="flux", E="flux", W="flux"),
            )
        )
    result.append(
        dict(
            name="environment-value-boundary",
            n=4,
            bounds_m=[0, UNIT, 0, UNIT],
            boundaries=dict(N="value", S="value", E="value", W="value"),
        )
    )
    return result
