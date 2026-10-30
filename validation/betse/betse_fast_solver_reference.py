"""Independent Decimal circuit equations and carried original-clock histories.

No Cells, BETSE, NumPy or JAX imports. This reference derives operators from
named raw owner inputs and never consumes production/native coefficients.
"""

from decimal import Decimal, localcontext
from fractions import Fraction


def d(value):
    return Decimal.from_float(float(value))


def serial(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: serial(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(item) for item in value]
    return value


def coefficients(raw):
    g, ions, source = (raw[key] for key in ("geometry", "ions", "parameters"))
    p = {key: d(value) for key, value in source.items() if key != "is_ecm"}
    owner, neighbor = g["owner"], g["neighbor"]
    rows = [[j for j, value in enumerate(owner) if value == i] for i in range(len(g["cell_ids"]))]
    counts = [len(row) for row in rows]
    z = [d(value) for value in ions["valence"]]
    ci = [[d(value) for value in row] for row in ions["cell_mol_m3"]]
    co = [[d(value) for value in row] for row in ions["environment_mol_m3"]]
    dm = [[d(value) for value in row] for row in ions["membrane_diffusion_m2_s"]]
    df = [d(value) for value in ions["free_diffusion_m2_s"]]
    sm, sg, reversals, cbar = [], [], {}, {}
    for i, name in enumerate(ions["ids"]):
        inside = sum(ci[i]) / len(ci[i])
        outside = sum(co[i]) / len(co[i]) if source["is_ecm"] else co[i]
        cbar[name] = (
            (inside + outside) / 2
            if source["is_ecm"]
            else [(inside + value) / 2 for value in outside]
        )
        factor = p["R_J_mol_K"] * p["temperature_K"] / (z[i] * p["F_C_mol"])
        reversals[name] = (
            factor * (outside / inside).ln()
            if source["is_ecm"]
            else [factor * (value / inside).ln() for value in outside]
        )
        sg.append(
            df[i]
            * p["q_C"]
            * p["junction_surface_fraction"]
            * p["F_C_mol"]
            * inside
            * z[i] ** 2
            / (p["gap_length_m"] * p["kb_J_K"] * p["configured_temperature_K"])
        )
        sm.append(
            [
                dm[i][j]
                * p["q_C"]
                * p["F_C_mol"]
                * (cbar[name] if source["is_ecm"] else cbar[name][j])
                * z[i] ** 2
                / (p["membrane_thickness_m"] * p["kb_J_K"] * p["configured_temperature_K"])
                for j in range(len(owner))
            ]
        )
    leak, gleak, sigma_init, sigma = [], [], [], []
    for cell, row in enumerate(rows):
        numerator = denominator = Decimal(0)
        for i in range(len(z)):
            avg_d = sum(dm[i][j] for j in row) / counts[cell]
            exterior = (
                sum(co[i][g["environment_index"][j]] if source["is_ecm"] else co[i][j] for j in row)
                / counts[cell]
            )
            factor = avg_d / p["membrane_thickness_m"]
            numerator += factor * (exterior if z[i] > 0 else ci[i][cell])
            denominator += factor * (ci[i][cell] if z[i] > 0 else exterior)
        leak.append(
            p["R_J_mol_K"] * p["temperature_K"] / p["F_C_mol"] * (numerator / denominator).ln()
        )
        gleak.append(
            sum(sum(sm[i][j] for i in range(len(z))) * d(g["membrane_area_m2"][j]) for j in row)
            / d(g["cell_area_m2"][cell])
        )
        sigma_init.append(
            sum(
                z[i] ** 2
                * p["q_C"]
                * p["F_C_mol"]
                * ci[i][cell]
                * df[i]
                * d(0.1)
                / (p["kb_J_K"] * p["configured_temperature_K"])
                for i in range(len(z))
            )
        )
        sigma.append(
            sum(
                z[i] ** 2
                * p["F_C_mol"] ** 2
                * ci[i][cell]
                * df[i]
                * d(0.1)
                / (p["R_J_mol_K"] * p["configured_temperature_K"])
                for i in range(len(z))
            )
            / len(z)
        )
    means = [value if source["is_ecm"] else sum(value) / len(value) for value in cbar.values()]
    result = dict(
        leak_reversal_V=leak,
        leak_conductance_S_m2=gleak,
        junction_conductance_S_m2=[sum(sg) / count for count in counts],
        init_dynamics_sigma_S_m=sigma_init,
        sigma_cell_S_m=sigma,
        membrane_conductivity_S_m2=sm,
        ion_reversal_V=reversals,
        ion_mean_mol_m3=cbar,
        cbar_all_mol_m3=sum(means) / len(means),
        cbar_sum_mol_m3=sum(means),
    )
    return result, dict(rows=rows, counts=counts, owner=owner, neighbor=neighbor, parameters=p)


def integrate(raw, calendar, initial_voltage_V, initial_drive, drives, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require the two declared independent precision settings")
    count = len(drives)
    if not 0 < count <= calendar["step_count"] or calendar["phase"] not in ("INIT", "SIM"):
        raise ValueError("Require a bounded complete original phase prefix")
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        c, context = coefficients(raw)
        rows, nmem, owner, neighbor, p = (
            context[key] for key in ("rows", "counts", "owner", "neighbor", "parameters")
        )
        g = raw["geometry"]
        area, surface, volume = (
            [d(value) for value in g[key]]
            for key in ("membrane_area_m2", "cell_area_m2", "cell_volume_m3")
        )
        normals = [[d(value) for value in row] for row in g["normal_xy"]]
        weights = [d(value) for value in g["junction_weights"]]
        voltage, packet = [d(value) for value in initial_voltage_V], initial_drive
        cm, dt = p["capacitance_F_m2"], d(calendar["dt_s"])
        endpoints = []
        for index, proposed in enumerate(drives):
            if calendar["phase"] == "SIM":
                packet = proposed
            extra = [d(value) for value in packet["extra_current_A_m2"]]
            block = packet["junction_block"]
            block = (
                [d(value) for value in block]
                if isinstance(block, list)
                else [d(block)] * len(owner)
            )
            vgj = [voltage[b] - voltage[a] for a, b in zip(owner, neighbor, strict=True)]
            current = [
                -vgj[j] * c["junction_conductance_S_m2"][owner[j]] + extra[j]
                for j in range(len(owner))
            ]
            before = voltage
            voltage = [
                before[cell]
                + dt
                / cm
                * (
                    c["junction_conductance_S_m2"][cell] * sum(vgj[j] for j in row)
                    - sum(extra[j] * area[j] for j in row) / surface[cell]
                    - c["leak_conductance_S_m2"][cell] * (before[cell] - c["leak_reversal_V"][cell])
                )
                for cell, row in enumerate(rows)
            ]
            sigma_mean = sum(c["sigma_cell_S_m"]) / len(rows)
            unprojected = [
                [current[j] * normals[j][axis] / (d(0.1) * sigma_mean) for axis in range(2)]
                for j in range(len(owner))
            ]
            divergence = [
                sum(
                    sum(unprojected[j][axis] * normals[j][axis] for axis in range(2)) * area[j]
                    for j in row
                )
                / volume[cell]
                for cell, row in enumerate(rows)
            ]
            pressure = [
                divergence[owner[j]] * volume[owner[j]] / (nmem[owner[j]] * area[j])
                for j in range(len(owner))
            ]
            field_mem = [
                [unprojected[j][axis] - pressure[j] * normals[j][axis] for axis in range(2)]
                for j in range(len(owner))
            ]
            corrected_div = [
                sum(
                    sum(field_mem[j][axis] * normals[j][axis] for axis in range(2)) * area[j]
                    for j in row
                )
                / volume[cell]
                for cell, row in enumerate(rows)
            ]
            cell_current = [
                [
                    sum(current[j] * normals[j][axis] * area[j] for j in row) / surface[cell]
                    for axis in range(2)
                ]
                for cell, row in enumerate(rows)
            ]
            field = [
                [
                    cell_current[cell][axis] / (d(0.1) * c["sigma_cell_S_m"][cell])
                    for axis in range(2)
                ]
                for cell in range(len(rows))
            ]
            bound = [
                cm
                / (
                    c["leak_conductance_S_m2"][cell]
                    + c["junction_conductance_S_m2"][cell]
                    * sum(neighbor[j] != owner[j] for j in row)
                )
                for cell, row in enumerate(rows)
            ]
            label = (
                0.0
                if calendar["step_count"] == 1
                else float(
                    Fraction(index, calendar["step_count"] - 1)
                    * calendar["step_count"]
                    * Fraction(calendar["dt_s"])
                )
            )
            endpoints.append(
                dict(
                    cell_voltage_V=voltage,
                    membrane_voltage_V=[voltage[i] for i in owner],
                    old_gap_voltage_V=vgj,
                    junction_open=[block[j] * weights[j] for j in range(len(owner))],
                    normal_current_A_m2=current,
                    cell_current_xy_A_m2=cell_current,
                    cell_field_xy_V_m=field,
                    membrane_field_xy_V_m=field_mem,
                    corrected_divergence_V_m2=corrected_div,
                    monotone_dt_limit_s=bound,
                    monotone_step=[dt <= value for value in bound],
                    native_voltage_nan_gate=True,
                    finite=True,
                    event_label_s=label,
                    start_s=index * calendar["dt_s"],
                    end_s=(index + 1) * calendar["dt_s"],
                )
            )
        return serial(
            dict(
                coefficients=c,
                endpoints=endpoints,
                refinement=refinement,
                decimal_precision=ctx.prec,
                independent_carried_equations=True,
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
    blocked = {"cells", "jax", "jaxlib", "betse", "numpy"}
    original = builtins.__import__

    def guarded(name, *values, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Reference import denied: " + name)
        return original(name, *values, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Independent reference import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    inputs = json.loads(args.inputs.read_text())
    answer = integrate(
        inputs["definition"],
        inputs["calendar"],
        inputs["initial_voltage_V"],
        inputs["initial_drive"],
        inputs["drives"],
        refinement=args.refinement,
    )
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    if loaded:
        raise ValueError("Reference loaded production/numerical packages")
    record = dict(
        answer=answer,
        production_imports_denied=True,
        loaded_production_modules=loaded,
        runtime=dict(
            python=platform.python_version(), measured_cpu_affinity=sorted(os.sched_getaffinity(0))
        ),
    )
    with args.output.open("x") as handle:
        json.dump(record, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(
        json.dumps(
            dict(
                independent_decimal_precision=answer["decimal_precision"],
                complete_calls=len(answer["endpoints"]),
            )
        )
    )


if __name__ == "__main__":
    main()
