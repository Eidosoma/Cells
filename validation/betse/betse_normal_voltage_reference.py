"""Independent Decimal boundary/voltage equations and carried qualified references."""

import copy
from decimal import Decimal, localcontext

from validation.betse.betse_normal_current_reference import evaluate as current_equations
from validation.betse.betse_normal_ion_join_reference import evaluate as material_equations


def d(value):
    return Decimal.from_float(float(value))


def tree(value, fn):
    if isinstance(value, dict):
        return {key: tree(item, fn) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [tree(item, fn) for item in value]
    return fn(value)


def voltage_equations(inputs, state, readout, forcing, refinement, material_gross):
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        cdef, raw = inputs["current_definition"], inputs["voltage_definition"]
        g, grid, p = cdef["geometry"], raw["grid"], raw["parameters"]
        owner = g["owner"]
        n, m = len(g["cell_ids"]), len(owner)
        rows = [[j for j, a in enumerate(owner) if a == cell] for cell in range(n)]
        shape = grid["shape"]
        rhs = [Decimal(0)] * (shape[0] * shape[1])
        delta = d(grid["delta_m"])
        bounds = {key: d(value) for key, value in forcing["boundary_V"].items()}
        for row in range(shape[0]):
            rhs[row * shape[1] + shape[1] - 1] = -bounds["R"] / delta**2
            rhs[row * shape[1]] = -bounds["L"] / delta**2
        for col in range(shape[1]):
            rhs[(shape[0] - 1) * shape[1] + col] = -bounds["T"] / delta**2
            rhs[col] = -bounds["B"] / delta**2
        inverse = tree(grid["inverse_m2"], d)
        phi = [-sum(a * b for a, b in zip(row, rhs, strict=True)) for row in inverse]
        gphi = [sum(abs(a * b) for a, b in zip(row, rhs, strict=True)) for row in inverse]
        F, R, T, cm = (
            d(cdef["parameters"]["F_C_mol"]),
            d(p["R_J_mol_K"]),
            d(p["configured_temperature_K"]),
            d(p["capacitance_F_m2"]),
        )
        z, diffusion = tree(cdef["ions"]["valence"], d), tree(raw["ions"]["free_diffusion_m2_s"], d)
        c = tree(state["cell_mol_m3"], d)
        sigma = [
            sum(z[i] ** 2 * F**2 * c[i][j] * diffusion[i] / (10 * R * T) for i in range(len(z)))
            / len(z)
            for j in range(n)
        ]
        gc = tree(material_gross["cell_mol_m3"], d)
        gsigma = [
            sum(z[i] ** 2 * F**2 * gc[i][j] * diffusion[i] / (10 * R * T) for i in range(len(z)))
            / len(z)
            for j in range(n)
        ]
        values, gross = tree(readout["values"], d), tree(readout["gross"], d)
        diviterm = tree(raw["geometry"]["diviterm_m"], d)
        surface = [a * b for a, b in zip(values["charge_density_C_m3"], diviterm, strict=True)]
        gs = [a * b for a, b in zip(gross["charge_density_C_m3"], diviterm, strict=True)]
        old, dt = tree(state["voltage_V"], d), d(forcing["material"]["dt_s"])
        radius, normal, area, sa = (
            tree(raw["geometry"]["radius_m"], d),
            tree(g["normal_xy"], d),
            tree(g["membrane_area_m2"], d),
            tree(g["cell_area_m2"], d),
        )
        if p["polarizability"] == 0:
            voltage = [surface[owner[j]] / cm - phi[grid["membrane_to_grid"][j]] for j in range(m)]
            gv = [gs[owner[j]] / cm + gphi[grid["membrane_to_grid"][j]] for j in range(m)]
        else:
            alpha = [dt * sigma[owner[j]] / (cm * radius[j]) for j in range(m)]
            voltage = [
                (
                    old[j]
                    - dt * values["normal_current_A_m2"][j] / cm
                    + alpha[j] * surface[owner[j]] / cm
                )
                / (1 + alpha[j])
                for j in range(m)
            ]
            gv = [
                (
                    abs(old[j])
                    + dt * gross["normal_current_A_m2"][j] / cm
                    + alpha[j] * gs[owner[j]] / cm
                )
                / (1 + alpha[j])
                for j in range(m)
            ]
            # Include conductivity perturbations in both numerator and denominator.
            gv = [
                value * (1 + gsigma[owner[j]] / sigma[owner[j]]) if sigma[owner[j]] else value
                for j, value in enumerate(gv)
            ]
        mean = [sum(voltage[j] for j in row) / len(row) for row in rows]
        gm = [sum(gv[j] for j in row) / len(row) for row in rows]
        if p["polarizability"] == 0:
            field = [
                [values["cell_current_xy_A_m2"][i][axis] / sigma[i] for axis in (0, 1)]
                for i in range(n)
            ]
            gf = [
                [gross["cell_current_xy_A_m2"][i][axis] / abs(sigma[i]) for axis in (0, 1)]
                for i in range(n)
            ]
            gf = [
                [value * (1 + gsigma[i] / abs(sigma[i])) for value in row]
                for i, row in enumerate(gf)
            ]
        else:
            ratio = d(p["true_cell_size_m"]) / d(p["cell_radius_m"])
            gradient = [(voltage[j] - mean[owner[j]]) / (radius[j] * ratio) for j in range(m)]
            gg = [(gv[j] + gm[owner[j]]) / (radius[j] * ratio) for j in range(m)]
            field = [
                [
                    -sum(gradient[j] * normal[j][axis] * area[j] for j in row) / sa[i]
                    for axis in (0, 1)
                ]
                for i, row in enumerate(rows)
            ]
            gf = [
                [
                    sum(gg[j] * abs(normal[j][axis]) * area[j] for j in row) / sa[i]
                    for axis in (0, 1)
                ]
                for i, row in enumerate(rows)
            ]
        out = dict(
            boundary_rhs_V_m2=[rhs[j * shape[1] : (j + 1) * shape[1]] for j in range(shape[0])],
            boundary_potential_V=phi,
            conductivity_S_m=sigma,
            surface_charge_C_m2=surface,
            voltage_V=voltage,
            mean_voltage_V=mean,
            cell_field_xy_V_m=field,
            normal_cell_field_V_m=[
                sum(field[owner[j]][a] * normal[j][a] for a in (0, 1)) for j in range(m)
            ],
            derivative_V_s=[(voltage[j] - old[j]) / dt for j in range(m)],
        )
        bound = dict(
            boundary_rhs_V_m2=tree(out["boundary_rhs_V_m2"], abs),
            boundary_potential_V=gphi,
            conductivity_S_m=gsigma,
            surface_charge_C_m2=gs,
            voltage_V=gv,
            mean_voltage_V=gm,
            cell_field_xy_V_m=gf,
            normal_cell_field_V_m=[
                sum(gf[owner[j]][a] * abs(normal[j][a]) for a in (0, 1)) for j in range(m)
            ],
            derivative_V_s=[(gv[j] + abs(old[j])) / dt for j in range(m)],
        )
        return tree(
            dict(values=out, gross=bound), lambda v: float(v) if isinstance(v, Decimal) else v
        )


def transport_gross(inputs, old, forcing, carried):
    """Propagate gross scales through feedback using |Bernoulli'(x)| <= 1.

    The GHK flux is D/d*(ca*B(alpha)-cb*B(-alpha)). For real alpha,
    |B(alpha)| <= 1+|alpha| and |B'(alpha)| <= 1. These scalar bounds carry
    prior voltage cancellation scales into fluxes and subsequent amounts.
    """
    raw = inputs["ion_definition"]
    g, species, p = raw["geometry"], raw["ions"], raw["parameters"]
    owner, partner = g["owner"], g["partner"]
    count, m = len(species["ids"]), len(owner)
    out = copy.deepcopy(carried)
    gm = [[0.0] * m for _ in range(count)]
    gg = [[0.0] * m for _ in range(count)]
    dt = forcing["material"]["dt_s"]
    gv = [x + len(species["moving_ids"]) * 1e-25 for x in carried["voltage_V"]]
    ggap = [gv[j] + gv[partner[j]] + 1e-25 for j in range(m)]
    for name in species["moving_ids"]:
        i = species["ids"].index(name)
        z = abs(float(species["valence"][i]) + 1e-25)
        km = z * p["F_C_mol"] / (p["R_J_mol_K"] * forcing["material"]["runtime_temperature_K"])
        kg = z * p["F_C_mol"] / (p["R_J_mol_K"] * p["configured_temperature_K"])
        for j in range(m):
            cg = carried["bath_mol_m3"][i] + carried["membrane_mol_m3"][i][j]
            gm[i][j] = (
                species["membrane_diffusion_m2_s"][i][j]
                / p["membrane_thickness_m"]
                * cg
                * (1 + km * (abs(old["voltage_V"][j]) + gv[j]))
            )
            cg = carried["membrane_mol_m3"][i][j] + carried["membrane_mol_m3"][i][partner[j]]
            gg[i][j] = (
                species["gap_diffusion_m2_s"][i][j]
                * p["junction_surface_fraction"]
                * forcing["material"]["junction_block"][j]
                * g["gap_weights"][j]
                / g["gap_length_m"][j]
                * cg
                * (1 + kg * (abs(old["voltage_V"][partner[j]] - old["voltage_V"][j]) + ggap[j]))
            )
            if g["boundary"][j]:
                gg[i][j] = 0.0
                if not p["cluster_open"]:
                    gm[i][j] = 0.0
        for cell in range(len(g["cell_ids"])):
            row = [j for j, a in enumerate(owner) if a == cell]
            membrane_add = (
                dt
                * sum(gm[i][j] * g["membrane_area_m2"][j] for j in row)
                / g["cell_volume_m3"][cell]
            )
            gap_add = (
                dt
                * sum(gg[i][j] * g["membrane_area_m2"][j] for j in row)
                / g["cell_volume_m3"][cell]
            )
            out["cell_mol_m3"][i][cell] = carried["cell_mol_m3"][i][cell] + membrane_add + gap_add
            for j in row:
                out["membrane_mol_m3"][i][j] = carried["cell_mol_m3"][i][cell] + membrane_add
        out["bath_mol_m3"][i] = carried["bath_mol_m3"][i] + dt * sum(
            gm[i][j] * g["membrane_area_m2"][j] for j in range(m)
        ) / (m * p["bath_volume_m3"])
    out.update(
        membrane_flux_mol_m2_s=gm,
        junction_flux_mol_m2_s=gg,
        voltage_V=gv,
        junction_voltage_V=ggap,
        junction_field_V_m=[ggap[j] / g["gap_length_m"][j] for j in range(m)],
        junction_field_xy_V_m=[
            [ggap[j] / g["gap_length_m"][j] * abs(g["normal_xy"][j][a]) for a in (0, 1)]
            for j in range(m)
        ],
        gap_open=[forcing["material"]["junction_block"][j] * g["gap_weights"][j] for j in range(m)],
    )
    return out


def evaluate(inputs, *, refinement=1):
    state = copy.deepcopy(inputs["initial"])
    carried = tree(state, abs)
    history = []
    for forcing in inputs["drives"]:
        material_gross = transport_gross(inputs, state, forcing, carried)
        material = material_equations(
            dict(definition=inputs["ion_definition"], initial=state, steps=[forcing["material"]]),
            refinement=refinement,
        )["history"][0]
        state = material["final_state"]
        readout = current_equations(
            inputs["current_definition"],
            dict(
                cell_mol_m3=state["cell_mol_m3"],
                membrane_flux_mol_m2_s=state["membrane_flux_mol_m2_s"],
                junction_flux_mol_m2_s=state["junction_flux_mol_m2_s"],
                extra_charge_C_m3=forcing["extra_charge_C_m3"],
                extra_current_A_m2=forcing["extra_current_A_m2"],
            ),
            refinement=refinement,
        )
        conditioned = current_equations(
            inputs["current_definition"],
            dict(
                cell_mol_m3=material_gross["cell_mol_m3"],
                membrane_flux_mol_m2_s=material_gross["membrane_flux_mol_m2_s"],
                junction_flux_mol_m2_s=material_gross["junction_flux_mol_m2_s"],
                extra_charge_C_m3=tree(forcing["extra_charge_C_m3"], abs),
                extra_current_A_m2=tree(forcing["extra_current_A_m2"], abs),
            ),
            refinement=refinement,
        )
        readout["gross"] = conditioned["gross"]
        voltage = voltage_equations(inputs, state, readout, forcing, refinement, material_gross)
        before = copy.deepcopy(state)
        state = copy.deepcopy(state)
        state["voltage_V"] = voltage["values"]["voltage_V"]
        carried = copy.deepcopy(material_gross)
        carried["voltage_V"] = voltage["gross"]["voltage_V"]
        history.append(
            dict(
                material_state=before,
                material_gross=material_gross,
                current=readout,
                voltage=voltage,
                final_state=state,
            )
        )
    return dict(
        history=history, refinement=refinement, decimal_precision=90 if refinement == 1 else 140
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
            raise ImportError("Voltage reference import denied: " + name)
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
        raise ValueError("Reference loaded production/numerical modules")
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
