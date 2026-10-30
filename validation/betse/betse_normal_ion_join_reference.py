"""Independent Decimal flux/owner equations for the scoped no-ECM join."""

import copy
from decimal import Decimal, localcontext


def d(value):
    return Decimal.from_float(float(value))


def convert(value, function):
    if isinstance(value, dict):
        return {key: convert(item, function) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [convert(item, function) for item in value]
    return function(value)


def evaluate(inputs, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require the two independent precision levels")
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        raw = inputs["definition"]
        g, ions, p = raw["geometry"], raw["ions"], raw["parameters"]
        owner, partner = g["owner"], g["partner"]
        n, m = len(g["cell_ids"]), len(owner)
        rows = [[j for j, a in enumerate(owner) if a == cell] for cell in range(n)]
        moving = [ions["ids"].index(name) for name in ions["moving_ids"]]
        v = convert(inputs["initial"], d)
        gross = convert(v, abs)
        A, V, length = (
            convert(g[key], d) for key in ("membrane_area_m2", "cell_volume_m3", "gap_length_m")
        )
        norms, weights = convert(g["normal_xy"], d), convert(g["gap_weights"], d)
        dm, dg = (
            convert(ions[key], d) for key in ("membrane_diffusion_m2_s", "gap_diffusion_m2_s")
        )
        F, R, thickness, fraction, volume_env, pt = (
            d(p[key])
            for key in (
                "F_C_mol",
                "R_J_mol_K",
                "membrane_thickness_m",
                "junction_surface_fraction",
                "bath_volume_m3",
                "configured_temperature_K",
            )
        )
        zero, nonce = Decimal(0), d(1e-25)
        history = []

        def flux(ca, cb, gca, gcb, diffusion, distance, z, voltage, temperature):
            alpha = z * voltage * F / (R * temperature)
            exponential = (-alpha).exp()
            denominator = 1 - exponential
            factor = -diffusion * alpha / (distance * denominator)
            return factor * (cb - ca * exponential), abs(factor) * (gcb + gca * abs(exponential))

        for step_index, forcing in enumerate(inputs["steps"]):
            dt, temperature = d(forcing["dt_s"]), d(forcing["runtime_temperature_K"])
            block = convert(forcing["junction_block"], d)
            frames = []
            old = copy.deepcopy(v)
            clipped = [zero for _ in ions["ids"]]

            def observe(stage, i=None, actual_frames=frames):
                actual_frames.append(
                    dict(
                        stage=stage,
                        ion_id=None if i is None else ions["ids"][i],
                        values=copy.deepcopy(v),
                        gross=copy.deepcopy(gross),
                    )
                )

            observe("initial")
            for key in ("membrane_flux_mol_m2_s", "junction_flux_mol_m2_s"):
                v[key] = [[zero] * m for _ in ions["ids"]]
                gross[key] = [[zero] * m for _ in ions["ids"]]
            observe("reset_flux")
            for i in moving:
                # These additions are stores into binary64 source arguments;
                # all constitutive/transport equations below use Decimal.
                z = d(float(ions["valence"][i]) + 1e-25)
                v["voltage_V"] = [d(float(value) + 1e-25) for value in v["voltage_V"]]
                gross["voltage_V"] = [value + nonce for value in gross["voltage_V"]]
                for j in range(m):
                    value, bound = flux(
                        v["bath_mol_m3"][i],
                        v["membrane_mol_m3"][i][j],
                        gross["bath_mol_m3"][i],
                        gross["membrane_mol_m3"][i][j],
                        dm[i][j],
                        thickness,
                        z,
                        v["voltage_V"][j],
                        temperature,
                    )
                    if not p["cluster_open"] and g["boundary"][j]:
                        value = bound = zero
                    v["membrane_flux_mol_m2_s"][i][j] = value
                    gross["membrane_flux_mol_m2_s"][i][j] = bound
                observe("membrane_flux", i)
                pre_voltage = [v["voltage_V"][partner[j]] - v["voltage_V"][j] for j in range(m)]
                v["junction_field_V_m"] = [-pre_voltage[j] / length[j] for j in range(m)]
                gross["junction_field_V_m"] = [
                    (gross["voltage_V"][partner[j]] + gross["voltage_V"][j]) / length[j]
                    for j in range(m)
                ]
                v["junction_field_xy_V_m"] = [
                    [v["junction_field_V_m"][j] * norms[j][axis] for axis in (0, 1)]
                    for j in range(m)
                ]
                gross["junction_field_xy_V_m"] = [
                    [gross["junction_field_V_m"][j] * abs(norms[j][axis]) for axis in (0, 1)]
                    for j in range(m)
                ]
                v["gap_open"] = [block[j] * weights[j] for j in range(m)]
                gross["gap_open"] = [abs(value) for value in v["gap_open"]]
                v["junction_voltage_V"] = [d(float(value) + 1e-25) for value in pre_voltage]
                gross["junction_voltage_V"] = [
                    gross["voltage_V"][partner[j]] + gross["voltage_V"][j] + nonce for j in range(m)
                ]
                for j in range(m):
                    value, bound = flux(
                        v["membrane_mol_m3"][i][j],
                        v["membrane_mol_m3"][i][partner[j]],
                        gross["membrane_mol_m3"][i][j],
                        gross["membrane_mol_m3"][i][partner[j]],
                        dg[i][j] * fraction * v["gap_open"][j],
                        length[j],
                        z,
                        v["junction_voltage_V"][j],
                        pt,
                    )
                    if g["boundary"][j]:
                        value = bound = zero
                    v["junction_flux_mol_m2_s"][i][j] = value
                    gross["junction_flux_mol_m2_s"][i][j] = bound
                observe("junction_flux", i)
                v["membrane_mol_m3"][i] = [v["cell_mol_m3"][i][a] for a in owner]
                gross["membrane_mol_m3"][i] = [gross["cell_mol_m3"][i][a] for a in owner]
                observe("refresh_at_mem", i)
            for i in moving:
                fm, fg = v["membrane_flux_mol_m2_s"][i], v["junction_flux_mol_m2_s"][i]
                gm, gg = gross["membrane_flux_mol_m2_s"][i], gross["junction_flux_mol_m2_s"][i]
                for cell, row in enumerate(rows):
                    v["cell_mol_m3"][i][cell] += dt * sum(fm[j] * A[j] for j in row) / V[cell]
                    gross["cell_mol_m3"][i][cell] += dt * sum(gm[j] * A[j] for j in row) / V[cell]
                v["membrane_mol_m3"][i] = [v["cell_mol_m3"][i][a] for a in owner]
                gross["membrane_mol_m3"][i] = [gross["cell_mol_m3"][i][a] for a in owner]
                v["bath_mol_m3"][i] -= dt * sum(fm[j] * A[j] for j in range(m)) / (m * volume_env)
                gross["bath_mol_m3"][i] += (
                    dt * sum(gm[j] * A[j] for j in range(m)) / (m * volume_env)
                )
                observe("membrane_commit", i)
                for cell, row in enumerate(rows):
                    v["cell_mol_m3"][i][cell] -= dt * sum(fg[j] * A[j] for j in row) / V[cell]
                    gross["cell_mol_m3"][i][cell] += dt * sum(gg[j] * A[j] for j in row) / V[cell]
                observe("junction_commit", i)
                for cell in range(n):
                    if v["cell_mol_m3"][i][cell] < 0:
                        clipped[i] -= v["cell_mol_m3"][i][cell] * V[cell]
                        v["cell_mol_m3"][i][cell] = zero
                observe("clip_bulk", i)
            history.append(
                dict(
                    step_index=step_index + 1,
                    frames=frames,
                    final_state=copy.deepcopy(v),
                    final_gross=copy.deepcopy(gross),
                    clipping_added_mol=clipped,
                    cell_change_mol=[
                        sum(
                            (v["cell_mol_m3"][i][j] - old["cell_mol_m3"][i][j]) * V[j]
                            for j in range(n)
                        )
                        for i in range(len(ions["ids"]))
                    ],
                    bath_change_mol=[
                        (v["bath_mol_m3"][i] - old["bath_mol_m3"][i]) * volume_env
                        for i in range(len(ions["ids"]))
                    ],
                )
            )
        return convert(
            dict(history=history, decimal_precision=ctx.prec, refinement=refinement),
            lambda value: float(value) if isinstance(value, Decimal) else value,
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
            raise ImportError("Independent ion join import denied: " + name)
        return original(name, *values, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Reference import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    result = evaluate(json.loads(args.inputs.read_text()), refinement=args.refinement)
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    if loaded:
        raise ValueError("Independent reference loaded production/numerical packages")
    result.update(
        production_imports_denied=True,
        loaded_production_modules=loaded,
        runtime=dict(
            python=platform.python_version(), measured_cpu_affinity=sorted(os.sched_getaffinity(0))
        ),
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                carried_calls=len(result["history"]), decimal_precision=result["decimal_precision"]
            )
        )
    )


if __name__ == "__main__":
    main()
