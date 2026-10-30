"""Independent Decimal chemistry/mover equations from actual pre-network state.

All forms are fresh conditional local checks. No upstream or independently
carried trajectory accuracy follows from this reference.
"""

import copy
from decimal import Decimal, localcontext

from validation.betse.betse_normal_network_join_reference import _alpha, d


def plain(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


def hill(gad, prefix, state, site):
    if gad is None:
        return d(1)
    alpha = d(1)
    for activating, sign in ((True, "activators"), (False, "inhibitors")):
        names = gad.get(prefix + sign)
        if names is None:
            continue
        for name, km, power in zip(
            names, gad["Km " + prefix + sign], gad["n " + prefix + sign], strict=True
        ):
            load = (state[name][site] / d(km)) ** d(power)
            alpha *= load / (1 + load) if activating else 1 / (1 + load)
    return alpha


def cold(inputs, *, refinement=1):
    if refinement not in (1, 2) or inputs["mode"] != "cold_initialization":
        raise ValueError("Require cold configuration inputs before owner construction")
    with localcontext() as context:
        context.prec = 90 if refinement == 1 else 140
        net = inputs["network"]
        cfg = net["grn_configuration"]
        n, m = inputs["cells"], inputs["membranes"]
        genes = {}
        for row in cfg["biomolecules"]:
            gad = row["growth and decay"]
            fields = dict(
                Dm=d(row["Dm"]),
                Do=d(row["Do"]),
                Dgj=d(row.get("Dgj", 1e-16)),
                z=d(row["z"]),
                ignore_ECM_pump=True,
                ignoreTJ=row["TJ permeable"],
                ignoreGJ=row["GJ impermeable"],
                TJ_factor=d(row["TJ factor"]),
                update_intra_conc=False,
                transmem=False,
                Mu_mem=d(0),
                u_mt=d(0),
                scale_factor=d(row.get("scale factor", 1)),
                modify_time_factor=d(cfg.get("time dilation factor", 1))
                if row.get("use time dilation", False)
                else d(1),
                active_pumping=False,
                ion_channel_gating=False,
                change_bounds=False,
                cell_clamp=False,
                c_cells=[d(row["cell conc"])] * n,
                cc_at_mem=[d(row["cell conc"])] * m,
                c_env=[d(row["env conc"])] * m,
                flux_intra=[d(0)] * m,
                c_bound=d(row["env conc"]),
                simple_growth=gad is not None,
                gad_scale_factor=d(1) if gad is None else d(gad.get("scale factor", 1)),
                r_production=None if gad is None else d(gad["production rate"]),
                r_decay=None if gad is None else d(gad["decay rate"]),
                growth_targets_cell=list(range(n)),
            )
            if gad is not None:
                fields.update(
                    growth_targets_mem=list(range(m)), decay_max=d(gad.get("decay max", 0))
                )
            genes[row["name"]] = fields
        ids = inputs["ion_ids"] + [row["name"] for row in cfg["biomolecules"]]
        matrix = [[d(0)] * 3 for _ in ids]
        matrix[ids.index("X")] = [d(1), d(0), d(-1)]
        matrix[ids.index("Y")] = [d(0), d(1), d(1)]
        simulator = dict(
            extra_rho_cells=list(map(d, inputs["incoming_charge_C_m3"])),
            extra_J_mem=list(map(d, inputs["incoming_current_A_m2"])),
        )
        if net["grn_initialization_publish"]:
            simulator.update(extra_rho_cells=[d(0)] * n, extra_rho_env=[d(0)] * m)
        return plain(
            dict(
                molecule_fields=genes,
                reaction_matrix=matrix,
                simulator_fields=simulator,
                owner_fields=dict(
                    reset_MT=False,
                    recalc_fluid=False,
                    reactions=True,
                    transporters=False,
                    channels=False,
                    modulators=cfg.get("modulators") is not None,
                ),
                charge_has_been_balanced=net["grn_initialization_publish"],
                decimal_precision=context.prec,
                carried_reference_forms=0,
                fresh_conditional_reference=True,
                cold_initialization=True,
                physical_conservation_credit=False,
            )
        )


def warm(inputs, *, refinement=1):
    if refinement not in (1, 2) or not inputs["conditioned_before_model_network"]:
        raise ValueError("Require actual immutable pre-network inputs")
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        definition, before = inputs["definition"], inputs["molecule_states_before"]
        configured = definition["molecules"]
        names, ions = [row["name"] for row in configured], inputs["ion_ids"]
        assert set(names) == {"X", "Y"} and len(names) == 2
        geometry = inputs["molecular_geometry"]
        owner, partner, boundary = geometry["owner"], geometry["partner"], geometry["boundary"]
        n, m = len(geometry["cell_volume_m3"]), len(owner)
        cell_rows = [[j for j, index in enumerate(owner) if index == i] for i in range(n)]
        area, volume, length = (
            [d(v) for v in geometry[key]]
            for key in ("membrane_area_m2", "cell_volume_m3", "gap_length_m")
        )
        dt, F, R = d(inputs["dt_s"]), d(inputs["F"]), d(inputs["R"])
        runtime, configured_T = (
            d(inputs["runtime_temperature_K"]),
            d(inputs["configured_temperature_K"]),
        )
        thickness, env_volume = d(inputs["membrane_thickness_m"]), d(inputs["bath_volume_m3"])
        vm = list(map(float, inputs["values_before"]["voltage_V"]))
        vgj = list(map(float, inputs["values_before"]["junction_voltage_V"]))
        raw = dict(
            sample_mM=[
                left + right
                for left, right in zip(
                    inputs["values_before"]["membrane_mol_m3"],
                    inputs["values_before"]["bath_mol_m3"],
                    strict=True,
                )
            ],
            membrane_to_environment=definition["membrane_to_environment"],
            species_ids=ions,
            species_valence=inputs["valence"],
            voltage_V=vm,
            faraday_C_mol=inputs["F"],
            gas_constant_J_mol_K=inputs["R"],
            temperature_K=inputs["runtime_temperature_K"],
        )
        controls = {key: list(map(d, value)) for key, value in inputs["controls_before"].items()}
        writes = []
        for row in ():  # Standalone never dispatches configured modulators.
            value = [d(row["max effect"]) * _alpha(row, raw, j) for j in range(m)]
            key = "gj_block" if row["target"] == "GJ" else "NaKATP_block"
            controls[key] = value
            writes.append(
                dict(
                    rule_id=row["name"],
                    target=row["target"],
                    value=value[:],
                    gj_block=controls["gj_block"][:],
                    NaKATP_block=controls["NaKATP_block"][:],
                )
            )
        old_cell = {name: list(map(d, before[name]["c_cells"])) for name in names}
        old_env = {name: list(map(d, before[name]["c_env"])) for name in names}
        cell_state = {
            name: list(map(d, values))
            for name, values in zip(ions, inputs["values_before"]["cell_mol_m3"], strict=True)
        }
        cell_state.update(old_cell)
        configs = {row["name"]: row for row in definition["grn_configuration"]["biomolecules"]}
        growth, growth_gross = {}, {}
        for row in configured:
            name, parameters, g = row["name"], row["parameters"], row["growth"]
            if (
                any(
                    parameters[key]
                    for key in (
                        "update_intra_conc",
                        "transmem",
                        "active_pumping",
                        "ion_channel_gating",
                        "change_bounds",
                        "cell_clamp",
                    )
                )
                or parameters["Mu_mem"] != 0
                or parameters["u_mt"] != 0
            ):
                raise ValueError(
                    "Reference requires the declared instant-mixing passive mover seam"
                )
            factor, scale = d(parameters["modify_time_factor"]), d(g["scale_factor"])
            values, gross = [], []
            for site, concentration in enumerate(old_cell[name]):
                production = (
                    d(g["production_rate_mM_s"])
                    * factor
                    * hill(configs[name]["growth and decay"], "", cell_state, site)
                )
                basal = d(g["decay_rate_per_s"]) * factor * concentration / scale
                regulated = (
                    d(g["decay_max_per_s"])
                    * factor
                    * concentration
                    / scale
                    * hill(configs[name]["growth and decay"], "decay ", cell_state, site)
                )
                values.append(production - basal - regulated if g["enabled"] else Decimal(0))
                gross.append(
                    abs(production) + abs(basal) + abs(regulated) if g["enabled"] else Decimal(0)
                )
            growth[name], growth_gross[name] = values, gross
        reaction = []
        if definition["reactions"]:
            row = definition["reactions"][0]
            if (
                row["standard free energy"] != "None"
                or row["reactants"] != ["X"]
                or row["products"] != ["Y"]
            ):
                raise ValueError("Reference only implements the declared irreversible X to Y seam")
            reaction = [
                d(row["max rate"])
                * (value / d(row["Km reactants"][0]))
                / (1 + value / d(row["Km reactants"][0]))
                for value in old_cell["X"]
            ]
        rate = reaction or [Decimal(0)] * n
        delta = {
            name: [growth[name][j] + (-rate[j] if name == "X" else rate[j]) for j in range(n)]
            for name in names
        }
        rate_gross = {
            name: [growth_gross[name][j] + abs(rate[j]) for j in range(n)] for name in names
        }
        delta_rows = [[Decimal(0)] * n for _ in ions] + [delta[name] for name in names]
        gross_rows = [[Decimal(0)] * n for _ in ions] + [rate_gross[name] for name in names]

        def ghk(ca, cb, diffusion, distance, z, voltage, temperature):
            alpha = z * voltage * F / (R * temperature)
            exponential = (-alpha).exp()
            denominator = 1 - exponential
            factor = -diffusion * alpha / (distance * denominator)
            return factor * (cb - ca * exponential), abs(factor) * (abs(cb) + abs(ca * exponential))

        molecules, gross_molecules, balances = {}, {}, {}
        charge, charge_gross = [Decimal(0)] * n, [Decimal(0)] * n
        current = list(map(d, inputs["incoming_channel_current_A_m2"]))
        current_gross = list(map(abs, current))
        publication = inputs["substances_affect_charge"]
        for row in configured:
            name, p = row["name"], row["parameters"]
            # Source update_intra(False) refreshes this membrane cache BEFORE
            # every rate is evaluated. Chemistry later changes bulk only.
            stale_membrane = [old_cell[name][i] for i in owner]
            cell = [old_cell[name][j] + delta[name][j] * dt for j in range(n)]
            cell_gross = [abs(old_cell[name][j]) + rate_gross[name][j] * dt for j in range(n)]
            membrane_flux, membrane_flux_gross = [], []
            if p["Dm"] != 0.0:
                vm = [value + 1e-25 for value in vm]
                z = d(float(p["z"]) + 1e-25)
                for j in range(m):
                    flux, gross = ghk(
                        old_env[name][j],
                        stale_membrane[j],
                        d(p["Dm"]),
                        thickness,
                        z,
                        d(vm[j]),
                        runtime,
                    )
                    if not inputs["cluster_open"] and boundary[j]:
                        flux = gross = Decimal(0)
                    membrane_flux.append(flux)
                    membrane_flux_gross.append(gross)
            else:
                membrane_flux = [Decimal(0)] * m
                membrane_flux_gross = [Decimal(0)] * m
            for i in range(n):
                increment = (
                    sum((membrane_flux[j] * area[j] for j in cell_rows[i]), Decimal(0))
                    / volume[i]
                    * dt
                )
                bound = (
                    sum((membrane_flux_gross[j] * area[j] for j in cell_rows[i]), Decimal(0))
                    / volume[i]
                    * dt
                )
                cell[i] += increment
                cell_gross[i] += bound
            env_scalar = (
                sum(
                    (
                        old_env[name][j] - membrane_flux[j] * (area[j] / env_volume) * dt
                        for j in range(m)
                    ),
                    Decimal(0),
                )
                / m
            )
            env_gross = (
                sum(
                    (
                        abs(old_env[name][j]) + membrane_flux_gross[j] * (area[j] / env_volume) * dt
                        for j in range(m)
                    ),
                    Decimal(0),
                )
                / m
            )
            membrane = [cell[i] for i in owner]
            membrane_gross = [cell_gross[i] for i in owner]
            gap_flux, gap_flux_gross = [], []
            if not p["ignoreGJ"]:
                vgj = [value + 1e-25 for value in vgj]
                z = d(float(p["z"]) + 1e-25)
                for j in range(m):
                    diffusion = d(p["Dgj"]) * controls["gj_block"][j] * d(inputs["gap_open"][j])
                    value, bound = ghk(
                        membrane[j],
                        membrane[partner[j]],
                        diffusion,
                        length[j],
                        z,
                        d(vgj[j]),
                        configured_T,
                    )
                    if boundary[j]:
                        value = bound = Decimal(0)
                    gap_flux.append(value)
                    gap_flux_gross.append(bound)
                time = d(p["modify_time_factor"])
                for i in range(n):
                    increment = (
                        sum((-gap_flux[j] * area[j] for j in cell_rows[i]), Decimal(0))
                        / volume[i]
                        * dt
                        * time
                    )
                    bound = (
                        sum((gap_flux_gross[j] * area[j] for j in cell_rows[i]), Decimal(0))
                        / volume[i]
                        * dt
                        * time
                    )
                    cell[i] += increment
                    cell_gross[i] += bound
                membrane = [cell[i] for i in owner]
                membrane_gross = [cell_gross[i] for i in owner]
            else:
                gap_flux = [Decimal(0)] * m
                gap_flux_gross = [Decimal(0)] * m
            env = [env_scalar] * m
            molecules[name] = dict(
                c_cells=cell,
                cc_at_mem=membrane,
                c_env=env,
                flux_intra=copy.deepcopy(before[name]["flux_intra"]),
                f_mem=membrane_flux,
                f_gj=gap_flux,
                fenvx=0,
                fenvy=0,
                present_fields=[
                    "c_cells",
                    "cc_at_mem",
                    "c_env",
                    "flux_intra",
                    "f_mem",
                    "f_gj",
                    "fenvx",
                    "fenvy",
                ],
            )
            gross_molecules[name] = dict(
                c_cells=cell_gross,
                cc_at_mem=membrane_gross,
                c_env=[env_gross] * m,
                flux_intra=list(map(abs, before[name]["flux_intra"])),
                f_mem=membrane_flux_gross,
                f_gj=gap_flux_gross,
            )
            chemical_amount = sum((delta[name][i] * volume[i] * dt for i in range(n)), Decimal(0))
            directed_gap = (
                -sum((gap_flux[j] * area[j] for j in range(m)), Decimal(0))
                * dt
                * d(p["modify_time_factor"])
            )
            old_amount = (
                sum((old_cell[name][i] * volume[i] for i in range(n)), Decimal(0))
                + sum(old_env[name], Decimal(0)) * env_volume
            )
            new_amount = (
                sum((cell[i] * volume[i] for i in range(n)), Decimal(0))
                + sum(env, Decimal(0)) * env_volume
            )
            declared_old = (
                sum((old_cell[name][i] * volume[i] for i in range(n)), Decimal(0))
                + sum(old_env[name], Decimal(0)) / m * env_volume
            )
            declared_new = (
                sum((cell[i] * volume[i] for i in range(n)), Decimal(0)) + env_scalar * env_volume
            )
            balances[name] = dict(
                initial_amount_mol=old_amount,
                final_amount_mol=new_amount,
                chemical_source_mol=chemical_amount,
                directed_GJ_change_mol=directed_gap,
                source_effective_residual_mol=new_amount
                - old_amount
                - chemical_amount
                - directed_gap,
                global_GJ_zero_assumed=False,
                source_effective_bath_volume_m3=m * env_volume,
                declared_single_bath_volume_m3=env_volume,
                declared_single_bath_residual_mol=declared_new
                - declared_old
                - chemical_amount
                - directed_gap,
                expected_single_bath_defect_mol=dt
                * (1 - Decimal(1) / m)
                * sum((membrane_flux[j] * area[j] for j in range(m)), Decimal(0)),
                physical_global_conservation_credit=False,
            )
            if publication:
                z, scale = d(p["z"]), d(p["scale_factor"])
                for i in range(n):
                    charge[i] += F * cell[i] * z * scale
                    charge_gross[i] += abs(F * z * scale) * cell_gross[i]
                for j in range(m):
                    current[j] += -z * membrane_flux[j] * F * scale + z * gap_flux[j] * F * scale
                    current_gross[j] += abs(z * F * scale) * (
                        membrane_flux_gross[j] + gap_flux_gross[j]
                    )
        return plain(
            dict(
                molecules_after=molecules,
                gross_molecules=gross_molecules,
                controls_after=controls,
                control_writes=writes,
                rhs=dict(
                    growth_rates=[growth[name] for name in names],
                    reaction_rates=[reaction] if reaction else [],
                    all_rates=[growth[name] for name in names] + ([reaction] if reaction else []),
                ),
                delta_conc=delta_rows,
                delta_gross=gross_rows,
                extra_rho_cells=charge,
                extra_rho_gross=charge_gross,
                extra_J_mem=current,
                extra_J_gross=current_gross,
                voltage_after_V=vm,
                junction_voltage_after_V=vgj,
                balances=balances,
                executed_chemistry=bool(definition["reactions"])
                or any(row["growth"]["enabled"] for row in configured),
                decimal_precision=ctx.prec,
                carried_reference_forms=0,
                conditional_actual_pre_network_only=True,
                no_upstream_or_trajectory_accuracy_claim=True,
            )
        )


def clock(inputs, *, refinement=1):
    """Independent binary64 clock specification; no NumPy or source execution.

    Decimal90/140 additionally counts the amount of numerical dt advanced.
    Source linspace has N endpoints over N*dt; timestamps and dt differ.
    """
    call = inputs["call"]
    dt, total, sample = map(float, (call["dt_s"], call["total_s"], call["sample_s"]))
    n = int(float(total / dt))
    if not 1 <= n <= 8 or sample < dt:
        raise ValueError("Require bounded progressing standalone clocks")
    end = float(n * dt)
    if n == 1:
        tt = [0.0]
    else:
        interval = float(end / (n - 1))
        tt = [float(i * interval) for i in range(n)]
        tt[-1] = end
    stride = float(sample / dt)
    i, indices = 0, []
    while i < n - stride:
        i = int(float(i + stride))
        indices.append(i)
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        return plain(
            dict(
                tt=tt,
                sample_indices=indices,
                sample_times=[tt[i] for i in indices],
                steps=n,
                source_dt_s=dt,
                declared_total_s=total,
                source_endpoint_s=end,
                timestamp_interval_s=None if n == 1 else float(end / (n - 1)),
                numerical_dt_advanced_s=d(dt) * n,
                forced_substances_affect_charge=False,
                clear_run_loop_called=False,
                configured_modulators_dispatched=False,
                owner_time_resets=True,
                simulator_time_appends=True,
                concentrations_reset_by_reinitialize=False,
                sample_cache_reset_by_clear_cache=True,
                first_step_t_zero_advances=True,
                decimal_precision=ctx.prec,
                carried_reference_forms=0,
                physical_conservation_credit=False,
                standalone_clock=True,
            )
        )


def evaluate(inputs, *, refinement=1):
    if inputs.get("mode") == "standalone_clock":
        return clock(inputs, refinement=refinement)
    if inputs.get("mode") == "cold_initialization":
        return cold(inputs, refinement=refinement)
    return warm(inputs, refinement=refinement)


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
