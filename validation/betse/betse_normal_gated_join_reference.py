"""Independent Decimal active-gate recurrence and coupled source equations."""

import copy
from decimal import Decimal, localcontext

from validation.betse.betse_normal_current_reference import evaluate as current_equations
from validation.betse.betse_normal_ion_join_reference import convert, d
from validation.betse.betse_normal_voltage_reference import tree, voltage_equations


def rates(voltage, threshold):
    shift = d(1000) * abs(voltage) - d(threshold)
    alpha = d(0.0013) * (-d(0.077) * shift).exp()
    raw_beta = d(0.0013) * (d(0.14) * shift).exp()
    return alpha, raw_beta, raw_beta / (1 + 50 * raw_beta)


def gate_step(
    opening, opening_gross, voltages, voltage_gross, dt, block, parameters, ion_id, update_index
):
    minimum = d(parameters["minimum"])
    dt_ms = dt * 1000
    values, gross = {}, {}
    for key in (
        "voltage_before_nonce_V",
        "opening_before",
        "alpha_per_ms",
        "raw_beta_per_ms",
        "beta_per_ms",
        "opening_unblocked",
        "opening_stored",
    ):
        values[key], gross[key] = [], []
    for old, old_gross, voltage, gv, b in zip(
        opening, opening_gross, voltages, voltage_gross, block, strict=True
    ):
        voltage = d(float(voltage))
        alpha, raw_beta, beta = rates(voltage, parameters["threshold_mV"])
        denominator = 1 + dt_ms * (alpha + beta)
        unblocked = (old + dt_ms * (alpha + beta * minimum)) / denominator
        ga, gb = 77 * alpha, 140 * beta
        sensitivity = dt_ms * (
            (ga + gb * minimum) / denominator
            + (old_gross + dt_ms * (alpha + beta * minimum)) * (ga + gb) / denominator**2
        )
        unblocked_gross = (
            old_gross + dt_ms * (alpha + beta * minimum)
        ) / denominator + sensitivity * gv
        actual = (voltage, old, alpha, raw_beta, beta, unblocked, b * unblocked)
        bounds = (
            gv,
            old_gross,
            alpha * (1 + 77 * gv),
            raw_beta * (1 + 140 * gv),
            beta * (1 + 140 * gv),
            unblocked_gross,
            abs(b) * unblocked_gross,
        )
        for key, value, bound in zip(values, actual, bounds, strict=True):
            values[key].append(value)
            gross[key].append(bound)
    return (
        values["opening_stored"],
        gross["opening_stored"],
        dict(
            ion_id=ion_id,
            update_index=update_index,
            values=values,
            gross=gross,
            dt_s=dt,
            dt_ms=dt_ms,
        ),
    )


def initialize(inputs, refinement):
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        alpha, raw, beta, opening = [], [], [], []
        params = inputs["gate_definition"]
        for voltage, block in zip(
            inputs["initial"]["junction_voltage_V"], inputs["initial_gate_block"], strict=True
        ):
            a, r, b = rates(d(voltage), params["threshold_mV"])
            alpha.append(a)
            raw.append(r)
            beta.append(b)
            opening.append(d(block) * (a / (a + b) + d(params["minimum"])))
        return tree(
            dict(
                alpha_per_ms=alpha,
                raw_beta_per_ms=raw,
                beta_per_ms=beta,
                class_open=opening,
                updates=0,
            ),
            lambda x: float(x) if isinstance(x, Decimal) else x,
        )


def material_equations_active(inputs, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require the two independent precision levels")
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        raw = inputs["definition"]
        g, ions, p = (raw["geometry"], raw["ions"], raw["parameters"])
        owner, partner = (g["owner"], g["partner"])
        n, m = (len(g["cell_ids"]), len(owner))
        rows = [[j for j, a in enumerate(owner) if a == cell] for cell in range(n)]
        moving = [ions["ids"].index(name) for name in ions["moving_ids"]]
        v = convert(inputs["initial"], d)
        gross = convert(v, abs)
        A, V, length = (
            convert(g[key], d) for key in ("membrane_area_m2", "cell_volume_m3", "gap_length_m")
        )
        norms = convert(g["normal_xy"], d)
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
        zero, nonce = (Decimal(0), d(1e-25))
        history = []
        gate_frames = []
        gross["gap_open"] = convert(inputs["gate_input_gross"], d)
        gross["voltage_V"] = convert(inputs["gate_voltage_gross"], d)

        def flux(ca, cb, gca, gcb, diffusion, distance, z, voltage, temperature):
            alpha = z * voltage * F / (R * temperature)
            exponential = (-alpha).exp()
            denominator = 1 - exponential
            factor = -diffusion * alpha / (distance * denominator)
            return (factor * (cb - ca * exponential), abs(factor) * (gcb + gca * abs(exponential)))

        for step_index, forcing in enumerate(inputs["steps"]):
            dt, temperature = (d(forcing["dt_s"]), d(forcing["runtime_temperature_K"]))
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
                answer = gate_step(
                    v["gap_open"],
                    gross["gap_open"],
                    pre_voltage,
                    [gross["voltage_V"][j] + gross["voltage_V"][partner[j]] for j in range(m)],
                    dt,
                    block,
                    inputs["gate_definition"],
                    ions["ids"][i],
                    inputs["gate_update_base"] + len(gate_frames) + 1,
                )
                v["gap_open"], gross["gap_open"] = (answer[0], answer[1])
                gate_frames.append(answer[2])
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
                fm, fg = (v["membrane_flux_mol_m2_s"][i], v["junction_flux_mol_m2_s"][i])
                gm, gg = (gross["membrane_flux_mol_m2_s"][i], gross["junction_flux_mol_m2_s"][i])
                for cell, row in enumerate(rows):
                    v["cell_mol_m3"][i][cell] += dt * sum((fm[j] * A[j] for j in row)) / V[cell]
                    gross["cell_mol_m3"][i][cell] += dt * sum((gm[j] * A[j] for j in row)) / V[cell]
                v["membrane_mol_m3"][i] = [v["cell_mol_m3"][i][a] for a in owner]
                gross["membrane_mol_m3"][i] = [gross["cell_mol_m3"][i][a] for a in owner]
                v["bath_mol_m3"][i] -= dt * sum((fm[j] * A[j] for j in range(m))) / (m * volume_env)
                gross["bath_mol_m3"][i] += (
                    dt * sum((gm[j] * A[j] for j in range(m))) / (m * volume_env)
                )
                observe("membrane_commit", i)
                for cell, row in enumerate(rows):
                    v["cell_mol_m3"][i][cell] -= dt * sum((fg[j] * A[j] for j in row)) / V[cell]
                    gross["cell_mol_m3"][i][cell] += dt * sum((gg[j] * A[j] for j in row)) / V[cell]
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
                            (
                                (v["cell_mol_m3"][i][j] - old["cell_mol_m3"][i][j]) * V[j]
                                for j in range(n)
                            )
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
            dict(
                history=history,
                decimal_precision=ctx.prec,
                refinement=refinement,
                gate_updates=gate_frames,
            ),
            lambda value: float(value) if isinstance(value, Decimal) else value,
        )


def transport_gross(inputs, old, forcing, carried, gate_bounds):
    """Propagate gross scales through feedback using |Bernoulli'(x)| <= 1.

    The GHK flux is D/d*(ca*B(alpha)-cb*B(-alpha)). For real alpha,
    |B(alpha)| <= 1+|alpha| and |B'(alpha)| <= 1. These scalar bounds carry
    prior voltage cancellation scales into fluxes and subsequent amounts.
    """
    raw = inputs["ion_definition"]
    g, species, p = (raw["geometry"], raw["ions"], raw["parameters"])
    owner, partner = (g["owner"], g["partner"])
    count, m = (len(species["ids"]), len(owner))
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
                * gate_bounds[i][j]
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
                * sum((gm[i][j] * g["membrane_area_m2"][j] for j in row))
                / g["cell_volume_m3"][cell]
            )
            gap_add = (
                dt
                * sum((gg[i][j] * g["membrane_area_m2"][j] for j in row))
                / g["cell_volume_m3"][cell]
            )
            out["cell_mol_m3"][i][cell] = carried["cell_mol_m3"][i][cell] + membrane_add + gap_add
            for j in row:
                out["membrane_mol_m3"][i][j] = carried["cell_mol_m3"][i][cell] + membrane_add
        out["bath_mol_m3"][i] = carried["bath_mol_m3"][i] + dt * sum(
            (gm[i][j] * g["membrane_area_m2"][j] for j in range(m))
        ) / (m * p["bath_volume_m3"])
    if not species["moving_ids"]:
        out.update(membrane_flux_mol_m2_s=gm, junction_flux_mol_m2_s=gg)
        return out
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
        gap_open=[gate_bounds[i][j] for j in range(m)],
    )
    return out


def evaluate(inputs, *, refinement=1):
    state = copy.deepcopy(inputs["initial"])
    carried = tree(state, abs)
    gate_cache = initialize(inputs, refinement)
    initial_gate_cache = copy.deepcopy(gate_cache)
    gate_cache_gross = tree(gate_cache, abs)
    history = []
    names = inputs["ion_definition"]["ions"]["ids"]
    for forcing in inputs["drives"]:
        old = state
        active = material_equations_active(
            dict(
                definition=inputs["ion_definition"],
                initial=state,
                steps=[forcing["material"]],
                gate_definition=inputs["gate_definition"],
                gate_input_gross=carried["gap_open"],
                gate_voltage_gross=carried["voltage_V"],
                gate_update_base=gate_cache["updates"],
            ),
            refinement=refinement,
        )
        material = active["history"][0]
        state = material["final_state"]
        gate_bounds = [[0.0] * len(inputs["initial"]["voltage_V"]) for _ in names]
        for gate in active["gate_updates"]:
            gate_bounds[names.index(gate["ion_id"])] = gate["gross"]["opening_stored"]
            for key in ("alpha_per_ms", "raw_beta_per_ms", "beta_per_ms"):
                gate_cache[key] = gate["values"][key]
                gate_cache_gross[key] = gate["gross"][key]
            gate_cache["updates"] = gate["update_index"]
            gate_cache_gross["updates"] = gate["update_index"]
        material_gross = transport_gross(inputs, old, forcing, carried, gate_bounds)
        current_source = dict(
            cell_mol_m3=state["cell_mol_m3"],
            membrane_flux_mol_m2_s=state["membrane_flux_mol_m2_s"],
            junction_flux_mol_m2_s=state["junction_flux_mol_m2_s"],
            extra_charge_C_m3=forcing["extra_charge_C_m3"],
            extra_current_A_m2=forcing["extra_current_A_m2"],
        )
        readout = current_equations(
            inputs["current_definition"], current_source, refinement=refinement
        )
        gross_source = dict(
            cell_mol_m3=material_gross["cell_mol_m3"],
            membrane_flux_mol_m2_s=material_gross["membrane_flux_mol_m2_s"],
            junction_flux_mol_m2_s=material_gross["junction_flux_mol_m2_s"],
            extra_charge_C_m3=tree(forcing["extra_charge_C_m3"], abs),
            extra_current_A_m2=tree(forcing["extra_current_A_m2"], abs),
        )
        readout["gross"] = current_equations(
            inputs["current_definition"], gross_source, refinement=refinement
        )["gross"]
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
                gate_updates=active["gate_updates"],
                gate_cache=copy.deepcopy(gate_cache),
                gate_cache_gross=copy.deepcopy(gate_cache_gross),
            )
        )
    return dict(
        history=history,
        initialization=initial_gate_cache,
        refinement=refinement,
        decimal_precision=90 if refinement == 1 else 140,
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
            raise ImportError("Gated join reference import denied: " + name)
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
