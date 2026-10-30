"""Independent Decimal owner/current equations and explicit gross scales."""

from decimal import Decimal, localcontext


def d(value):
    return Decimal.from_float(float(value))


def serial(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: serial(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [serial(item) for item in value]
    return value


def evaluate(raw, state, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require the two declared independent precision levels")
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        g, ions, p = raw["geometry"], raw["ions"], raw["parameters"]
        owner = g["owner"]
        rows = [[j for j, a in enumerate(owner) if a == i] for i in range(len(g["cell_ids"]))]
        F, sharp = d(p["F_C_mol"]), d(p["sharpness_cell"])
        z = [d(value) for value in ions["valence"]]
        area = [d(value) for value in g["membrane_area_m2"]]
        surface = [d(value) for value in g["cell_area_m2"]]
        norm = [[d(value) for value in row] for row in g["normal_xy"]]
        c, fm, fg = (
            [[d(value) for value in row] for row in state[key]]
            for key in ("cell_mol_m3", "membrane_flux_mol_m2_s", "junction_flux_mol_m2_s")
        )
        er = [d(value) for value in state["extra_charge_C_m3"]]
        ej = [d(value) for value in state["extra_current_A_m2"]]
        weights = [sharp / len(rows[owner[j]]) for j in range(len(owner))]
        wm = [1 - value for value in weights]
        rho = [
            sum(z[i] * F * c[i][cell] for i in range(len(z))) + er[cell]
            for cell in range(len(rows))
        ]
        jmem = [-sum(z[i] * F * fm[i][j] for i in range(len(z))) + ej[j] for j in range(len(owner))]
        jgj = [sum(z[i] * F * fg[i][j] for i in range(len(z))) for j in range(len(owner))]
        rawj = [a + b for a, b in zip(jmem, jgj, strict=True)]
        ave = [sum(rawj[j] * area[j] for j in row) / surface[cell] for cell, row in enumerate(rows)]
        normal = [wm[j] * rawj[j] + weights[j] * ave[owner[j]] for j in range(len(owner))]
        inward = [-normal[j] * area[j] for j in range(len(owner))]
        vector = [
            [
                sum(normal[j] * norm[j][axis] * area[j] for j in row) / surface[cell]
                for axis in (0, 1)
            ]
            for cell, row in enumerate(rows)
        ]
        projected = [
            sum(vector[owner[j]][axis] * norm[j][axis] for axis in (0, 1))
            for j in range(len(owner))
        ]
        grho = [
            sum(abs(z[i] * F * c[i][cell]) for i in range(len(z))) + abs(er[cell])
            for cell in range(len(rows))
        ]
        gm = [
            sum(abs(z[i] * F * fm[i][j]) for i in range(len(z))) + abs(ej[j])
            for j in range(len(owner))
        ]
        gg = [sum(abs(z[i] * F * fg[i][j]) for i in range(len(z))) for j in range(len(owner))]
        gr = [a + b for a, b in zip(gm, gg, strict=True)]
        ga = [sum(gr[j] * area[j] for j in row) / surface[cell] for cell, row in enumerate(rows)]
        gn = [abs(wm[j]) * gr[j] + abs(weights[j]) * ga[owner[j]] for j in range(len(owner))]
        gi = [gn[j] * area[j] for j in range(len(owner))]
        gv = [
            [
                sum(gn[j] * abs(norm[j][axis]) * area[j] for j in row) / surface[cell]
                for axis in (0, 1)
            ]
            for cell, row in enumerate(rows)
        ]
        gp = [
            sum(gv[owner[j]][axis] * abs(norm[j][axis]) for axis in (0, 1))
            for j in range(len(owner))
        ]
        before = [sum(rawj[j] * area[j] for j in row) for row in rows]
        after = [sum(normal[j] * area[j] for j in row) for row in rows]
        names = (
            "charge_density_C_m3",
            "membrane_current_A_m2",
            "junction_current_A_m2",
            "raw_normal_current_A_m2",
            "average_normal_current_A_m2",
            "normal_current_A_m2",
            "inward_membrane_current_A",
            "cell_current_xy_A_m2",
            "projected_cell_current_A_m2",
        )
        return serial(
            dict(
                values=dict(
                    zip(
                        names,
                        (rho, jmem, jgj, rawj, ave, normal, inward, vector, projected),
                        strict=True,
                    )
                ),
                gross=dict(zip(names, (grho, gm, gg, gr, ga, gn, gi, gv, gp), strict=True)),
                membrane_weight=wm,
                other_weight=weights,
                source_smooth_cells=1 / sharp,
                source_area_ratio=[
                    sum(area[j] for j in row) / surface[cell] for cell, row in enumerate(rows)
                ],
                surface_current_before_A=before,
                surface_current_after_A=after,
                smoothing_current_difference_A=[b - a for a, b in zip(before, after, strict=True)],
                refinement=refinement,
                decimal_precision=ctx.prec,
                independent_owner_equations=True,
            )
        )


def main():
    import argparse
    import builtins
    import importlib.abc
    import json
    import os
    import platform
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refinement", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "numpy", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *values, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Independent current reference import denied: " + name)
        return original(name, *values, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Reference import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    inputs = json.loads(args.inputs.read_text())
    answer = [
        evaluate(inputs["definition"], state, refinement=args.refinement)
        for state in inputs["snapshots"]
    ]
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    if loaded:
        raise ValueError("Reference loaded production/numerical packages")
    result = dict(
        snapshots=answer,
        production_imports_denied=True,
        loaded_production_modules=loaded,
        runtime=dict(
            python=platform.python_version(), measured_cpu_affinity=sorted(os.sched_getaffinity(0))
        ),
    )
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(
        json.dumps(
            dict(
                independent_snapshots=len(answer), decimal_precision=answer[0]["decimal_precision"]
            )
        )
    )


if __name__ == "__main__":
    main()
