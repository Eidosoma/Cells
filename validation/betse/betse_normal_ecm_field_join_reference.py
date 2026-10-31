"""Fresh independent Decimal material/network/complete field conditional checks.

Inputs are actual pre-stage copies. No trajectory is independently carried.
Geometry, cache, inverse and field gross majorants derive from declarations.
Scientific modules may only be evaluated by the Chief's qualification runner.
"""

from decimal import Decimal, localcontext

from validation.betse import betse_ecm_grn_reference as network
from validation.betse import betse_ecm_transport_reference as material
from validation.betse import betse_environment_field_reference as environment


def d(value):
    return value if isinstance(value, Decimal) else Decimal.from_float(float(value))


def tree(value, fn):
    if isinstance(value, dict):
        return {key: tree(item, fn) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [tree(item, fn) for item in value]
    return fn(value)


def current_equations(raw, state, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require the two declared independent precision levels")
    with localcontext() as ctx:
        ctx.prec = 100 if refinement == 1 else 160
        g, ions, p = (raw["geometry"], raw["ions"], raw["parameters"])
        owner = g["owner"]
        rows = [[j for j, a in enumerate(owner) if a == i] for i in range(len(g["cell_ids"]))]
        F, sharp = (d(p["F_C_mol"]), d(p["sharpness_cell"]))
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
            sum((z[i] * F * c[i][cell] for i in range(len(z)))) + er[cell]
            for cell in range(len(rows))
        ]
        jmem = [
            -sum((z[i] * F * fm[i][j] for i in range(len(z)))) + ej[j] for j in range(len(owner))
        ]
        jgj = [sum((z[i] * F * fg[i][j] for i in range(len(z)))) for j in range(len(owner))]
        rawj = [a + b for a, b in zip(jmem, jgj, strict=True)]
        ave = [
            sum((rawj[j] * area[j] for j in row)) / surface[cell] for cell, row in enumerate(rows)
        ]
        normal = [wm[j] * rawj[j] + weights[j] * ave[owner[j]] for j in range(len(owner))]
        inward = [-normal[j] * area[j] for j in range(len(owner))]
        vector = [
            [
                sum((normal[j] * norm[j][axis] * area[j] for j in row)) / surface[cell]
                for axis in (0, 1)
            ]
            for cell, row in enumerate(rows)
        ]
        projected = [
            sum((vector[owner[j]][axis] * norm[j][axis] for axis in (0, 1)))
            for j in range(len(owner))
        ]
        grho = [
            sum((abs(z[i] * F * c[i][cell]) for i in range(len(z)))) + abs(er[cell])
            for cell in range(len(rows))
        ]
        gm = [
            sum((abs(z[i] * F * fm[i][j]) for i in range(len(z)))) + abs(ej[j])
            for j in range(len(owner))
        ]
        gg = [sum((abs(z[i] * F * fg[i][j]) for i in range(len(z)))) for j in range(len(owner))]
        gr = [a + b for a, b in zip(gm, gg, strict=True)]
        ga = [sum((gr[j] * area[j] for j in row)) / surface[cell] for cell, row in enumerate(rows)]
        gn = [abs(wm[j]) * gr[j] + abs(weights[j]) * ga[owner[j]] for j in range(len(owner))]
        gi = [gn[j] * area[j] for j in range(len(owner))]
        gv = [
            [
                sum((gn[j] * abs(norm[j][axis]) * area[j] for j in row)) / surface[cell]
                for axis in (0, 1)
            ]
            for cell, row in enumerate(rows)
        ]
        gp = [
            sum((gv[owner[j]][axis] * abs(norm[j][axis]) for axis in (0, 1)))
            for j in range(len(owner))
        ]
        before = [sum((rawj[j] * area[j] for j in row)) for row in rows]
        after = [sum((normal[j] * area[j] for j in row)) for row in rows]
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
        return dict(
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
                sum((area[j] for j in row)) / surface[cell] for cell, row in enumerate(rows)
            ],
            surface_current_before_A=before,
            surface_current_after_A=after,
            smoothing_current_difference_A=[b - a for a, b in zip(before, after, strict=True)],
            refinement=refinement,
            decimal_precision=ctx.prec,
            independent_owner_equations=True,
        )


def voltage_equations(inputs, state, readout, forcing, refinement, material_gross):
    with localcontext() as ctx:
        ctx.prec = 100 if refinement == 1 else 160
        cdef, raw = (inputs["current_definition"], inputs["voltage_definition"])
        g, grid, p = (cdef["geometry"], raw["grid"], raw["parameters"])
        owner = g["owner"]
        n, m = (len(g["cell_ids"]), len(owner))
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
        phi = [-sum((a * b for a, b in zip(row, rhs, strict=True))) for row in inverse]
        gphi = [sum((abs(a * b) for a, b in zip(row, rhs, strict=True))) for row in inverse]
        F, R, T, cm = (
            d(cdef["parameters"]["F_C_mol"]),
            d(p["R_J_mol_K"]),
            d(p["configured_temperature_K"]),
            d(p["capacitance_F_m2"]),
        )
        z, diffusion = (
            tree(cdef["ions"]["valence"], d),
            tree(raw["ions"]["free_diffusion_m2_s"], d),
        )
        c = tree(state["cell_mol_m3"], d)
        sigma = [
            sum((z[i] ** 2 * F**2 * c[i][j] * diffusion[i] / (10 * R * T) for i in range(len(z))))
            / len(z)
            for j in range(n)
        ]
        gc = tree(material_gross["cell_mol_m3"], d)
        gsigma = [
            sum((z[i] ** 2 * F**2 * gc[i][j] * diffusion[i] / (10 * R * T) for i in range(len(z))))
            / len(z)
            for j in range(n)
        ]
        values, gross = (tree(readout["values"], d), tree(readout["gross"], d))
        diviterm = tree(raw["geometry"]["diviterm_m"], d)
        surface = [a * b for a, b in zip(values["charge_density_C_m3"], diviterm, strict=True)]
        gs = [a * b for a, b in zip(gross["charge_density_C_m3"], diviterm, strict=True)]
        old, dt = (tree(state["voltage_V"], d), d(forcing["material"]["dt_s"]))
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
            gv = [
                value * (1 + gsigma[owner[j]] / sigma[owner[j]]) if sigma[owner[j]] else value
                for j, value in enumerate(gv)
            ]
        mean = [sum((voltage[j] for j in row)) / len(row) for row in rows]
        gm = [sum((gv[j] for j in row)) / len(row) for row in rows]
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
                    -sum((gradient[j] * normal[j][axis] * area[j] for j in row)) / sa[i]
                    for axis in (0, 1)
                ]
                for i, row in enumerate(rows)
            ]
            gf = [
                [
                    sum((gg[j] * abs(normal[j][axis]) * area[j] for j in row)) / sa[i]
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
                sum((field[owner[j]][a] * normal[j][a] for a in (0, 1))) for j in range(m)
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
                sum((gf[owner[j]][a] * abs(normal[j][a]) for a in (0, 1))) for j in range(m)
            ],
            derivative_V_s=[(gv[j] + abs(old[j])) / dt for j in range(m)],
        )
        return dict(values=out, gross=bound)


def absolute(value):
    return tree(value, lambda v: abs(d(v)))


def hodge_gross(x, y, g, bounds):
    """Propagate absolute sums through each source FD and Dirichlet solve."""
    shape, delta = g["shape"], g["delta_m"]
    ny, nx = shape
    inverse = absolute(g["dirichlet_inverse_m2"])
    dx, _ = network.derivative_gross(y, delta)
    _, dy = network.derivative_gross(x, delta)
    dr = environment._combine(dx, dy)
    for i in range(ny):
        for j in range(nx):
            if i in (0, ny - 1) or j in (0, nx - 1):
                dr[i][j] = Decimal(0)
    aa = environment._mv(inverse, environment._flatten(dr))
    ax, ay = network.derivative_gross(environment._reshape(aa, shape), delta)
    dx, _ = network.derivative_gross(x, delta)
    _, dy = network.derivative_gross(y, delta)
    divergence = environment._combine(dx, dy)
    for i in range(ny):
        divergence[i][0], divergence[i][-1] = (
            abs(d(bounds["L"])) / delta**2,
            abs(d(bounds["R"])) / delta**2,
        )
    for j in range(nx):
        divergence[0][j], divergence[-1][j] = (
            abs(d(bounds["B"])) / delta**2,
            abs(d(bounds["T"])) / delta**2,
        )
    bb = environment._mv(inverse, environment._flatten(divergence))
    gx, gy = network.derivative_gross(environment._reshape(bb, shape), delta)
    return dict(
        input_x=x,
        input_y=y,
        rotated_x=y,
        rotated_y=x,
        rotated_divergence=dr,
        AA=aa,
        solenoidal_x=ay,
        solenoidal_y=ax,
        divergence=divergence,
        BB=bb,
        gradient_x=gx,
        gradient_y=gy,
    )


def field_gross(raw, packet, g, cache, values):
    p = raw["parameters"]
    z = list(map(d, raw["current_definition"]["ions"]["valence"]))
    f = d(raw["current_definition"]["parameters"]["F_C_mol"])
    shape, delta, mapping = g["shape"], g["delta_m"], g["membrane_to_grid"]
    size = shape[0] * shape[1]
    currents = []
    for axis, key in enumerate(("environment_flux_x", "environment_flux_y")):
        currents.append(
            environment._reshape(
                [
                    sum(abs(zz * f * d(packet[key][i][k])) for i, zz in enumerate(z))
                    + abs(d(packet["extra_environment_current_xy"][k][axis]))
                    for k in range(size)
                ],
                shape,
            )
        )
    hh = hodge_gross(*currents, g, packet["boundary_V"])
    charge = [
        sum(abs(zz * f * d(packet["environment_mol_m3"][i][k])) for i, zz in enumerate(z))
        + abs(d(packet["extra_environment_charge_C_m3"][k]))
        for k in range(size)
    ]
    surface = [Decimal(0)] * size
    mean_area = sum(g["membrane_area_per_site_m2"][k] for k in mapping) / len(mapping)
    for k in mapping:
        surface[k] = charge[k] * d(p["cell_height_m"]) * delta**2 / mean_area
    surface_voltage = [
        v
        / (
            cache["ko_environment_per_m"]
            * d(p["vacuum_permittivity_F_m"])
            * d(p["relative_permittivity"])
        )
        for v in surface
    ]
    rhs = absolute(values["boundary_rhs"])
    phi = environment._mv(absolute(g["dirichlet_inverse_m2"]), environment._flatten(rhs))
    voltage = [
        a + b
        for a, b in zip(
            environment._flatten(
                environment._gaussian(environment._reshape(surface_voltage, shape), constant=True)
            ),
            phi,
            strict=True,
        )
    ]
    screen = abs(values["screen"])
    screened = environment._reshape([screen * v for v in voltage], shape)
    gx, gy = network.derivative_gross(screened, delta)
    fx, fy = environment._flatten(gx), environment._flatten(gy)
    normals = raw["current_definition"]["geometry"]["normal_xy"]
    normal = [
        fx[k] * abs(d(normals[j][0])) + fy[k] * abs(d(normals[j][1])) for j, k in enumerate(mapping)
    ]
    gross = dict(
        raw_environment_current_x=currents[0],
        raw_environment_current_y=currents[1],
        local_voltage_assignment=None,
        local_voltage_smoothed=None,
        surface_charge_C_m2=surface,
        surface_voltage_V=surface_voltage,
        environment_charge_C_m3=charge,
        screened_voltage_source=screened,
        screen=screen,
        boundary_rhs=rhs,
        boundary_potential_V=phi,
        environment_voltage_V=voltage,
        electric_x_source=gx,
        electric_y_source=gy,
        normal_electric_source=normal,
        environment_current_x=hh["solenoidal_x"],
        environment_current_y=hh["solenoidal_y"],
        total_current_x_source=environment._combine(hh["solenoidal_x"], hh["gradient_x"]),
        total_current_y_source=environment._combine(hh["solenoidal_y"], hh["gradient_y"]),
        magnetic_field_source=[v * abs(d(p["magnetic_permeability_H_m"])) for v in hh["AA"]],
    )
    return gross, hh


def voltage_declaration(inputs, g):
    raw = inputs["definition"]["environment_geometry_definition"]
    cg = raw["current_definition"]["geometry"]
    geometry = raw["geometry"]
    radius = [
        sum(
            (d(point[a]) - d(geometry["cell_centres_m"][cg["owner"][j]][a])) ** 2 for a in (0, 1)
        ).sqrt()
        for j, point in enumerate(geometry["membrane_midpoints_m"])
    ]
    diviterm = [
        d(v) / d(a) for v, a in zip(geometry["cell_volume_m3"], cg["cell_area_m2"], strict=True)
    ]
    p = raw["parameters"]
    return dict(
        grid=dict(
            shape=g["shape"],
            delta_m=g["delta_m"],
            membrane_to_grid=g["membrane_to_grid"],
            inverse_m2=g["dirichlet_inverse_m2"],
        ),
        geometry=dict(diviterm_m=diviterm, radius_m=radius),
        ions=dict(free_diffusion_m2_s=raw["cache_initial_state"]["free_diffusion_m2_s"]),
        parameters=dict(
            inputs["field_parameters"],
            R_J_mol_K=inputs["definition"]["parameters"]["R_J_mol_K"],
            configured_temperature_K=p["configured_temperature_K"],
            true_cell_size_m=p["true_cell_size_m"],
            cell_radius_m=p["cell_radius_m"],
        ),
    )


def fields(inputs, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require two declared independent precision levels")
    with localcontext() as context:
        context.prec = 100 if refinement == 1 else 160
        raw = inputs["definition"]["environment_geometry_definition"]
        g = environment.geometry(raw, precision=context.prec)
        cache = environment._cache(raw)
        readout = current_equations(
            raw["current_definition"], inputs["current"], refinement=refinement
        )
        values, smoothing, hodge = environment._fields(raw, inputs["environment"], g, cache)
        if smoothing is not None or values.get("refused_zero_screening"):
            raise ValueError("Independent ordinary fields require positive screening ECM branch")
        gross, hh = field_gross(raw, inputs["environment"], g, cache, values)
        state = dict(
            cell_mol_m3=inputs["current"]["cell_mol_m3"],
            voltage_V=inputs["environment"]["old_voltage_V"],
        )
        vm = voltage_equations(
            dict(
                current_definition=raw["current_definition"],
                voltage_definition=voltage_declaration(inputs, g),
            ),
            state,
            readout,
            dict(
                boundary_V=inputs["environment"]["boundary_V"], material=dict(dt_s=inputs["dt_s"])
            ),
            refinement,
            dict(cell_mol_m3=absolute(state["cell_mol_m3"])),
        )
        return environment.serial(
            dict(
                mode="field",
                phase=inputs["phase"],
                decimal_precision=context.prec,
                current=readout,
                environment=dict(values=values, gross=gross, current_hodge=hodge, hodge_gross=hh),
                voltage=vm,
                geometry=g,
                cache=cache,
                carried_reference_forms=0,
                fresh_conditional_reference=True,
                physical_global_conservation_credit=False,
                independent_trajectory=False,
                inverse_supplied=False,
                cache_supplied=False,
                old_fields_supplied=False,
            )
        )


def evaluate(inputs, *, refinement=1):
    if inputs.get("mode") == "field":
        return fields(inputs, refinement=refinement)
    if inputs.get("mode") == "material":
        result = material.evaluate(inputs, refinement=refinement)
        result.update(
            mode="material",
            decimal_precision=result["precision"],
            carried_reference_forms=0,
            fresh_conditional_reference=True,
            physical_global_conservation_credit=False,
        )
        return result
    return network.evaluate(inputs, refinement=refinement)


def main():
    import argparse
    import builtins
    import importlib.abc
    import json
    import sys
    from pathlib import Path

    from validation.betse.betse_normal_channel_join_runtime import inventory

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refinement", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "numpy", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *rest, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Independent molecule reference import denied: " + name)
        return original(name, *rest, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Independent molecule reference import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    result = evaluate(json.loads(args.inputs.read_text()), refinement=args.refinement)
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    assert not loaded
    result.update(
        production_imports_denied=True, loaded_production_modules=loaded, runtime=inventory()
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
