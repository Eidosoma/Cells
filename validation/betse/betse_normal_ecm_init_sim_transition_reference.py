"""Fresh stdlib phase-boundary equations and unchanged existing SIM conditionals.

Voltage-dependent sodium gates retain their inherited [-0.120,+0.060] V oracle
domain. Out-of-domain inputs remain refusals; the constant NaLeak exception is
not applied to voltage-dependent classes and no fixture is calibrated here.
"""

import copy
from decimal import Decimal, localcontext

from validation.betse import betse_normal_ecm_catalog_join_reference as catalog
from validation.betse import betse_normal_ecm_event_join_reference as sim
from validation.betse import betse_normal_ecm_init_phase_reference as ordinary

d, numbers, serial = catalog.d, catalog.numbers, catalog.serial


def phase_rules(inputs):
    old = inputs["incoming"]
    cfg = inputs["setup"]
    names = inputs["ion_ids"]
    before = numbers(old["membrane_diffusion_m2_s"])
    profile = copy.deepcopy(before)
    for row in cfg["tissue_profiles"]:
        if not row["cell_indices"]:
            continue
        for role in ("Na", "K", "Cl", "Ca", "M", "P"):
            if role in names:
                for j in row["membrane_indices"]:
                    profile[names.index(role)][j] = d(row["diffusion_m2_s"]["Dm_" + role])
    current = copy.deepcopy(profile)
    level = d(cfg["static_noise_level"])
    current[names.index("K")] = [
        (1 + level * d(u)) * v
        for u, v in zip(inputs["actual_static_uniforms"], profile[names.index("K")], strict=True)
    ]
    denv = []
    environment = cfg["environment_diffusion"]
    for i, free in enumerate(old["D_free"]):
        values = [d(free)] * inputs["environment_sites"]
        for j in environment["environment_in_cluster_indices"]:
            values[j] = d(free) * d(environment["adherens_multiplier"])
        for key in ("all_bound_mem_inds", "interior_bound_mem_inds", "ecm_inds_bound_cell"):
            for j in inputs["grid_index_groups"][key]:
                values[j] = (
                    d(free)
                    * d(environment["tight_junction_multiplier"])
                    * d(environment["tight_junction_relative"][i])
                )
        denv.append(values)
    mechanical = numbers(old["mechanics"])
    mechanical["div_u_osmo"] = [Decimal(0)] * inputs["cells"]
    if inputs["mechanics_policy"]["deformation"]:
        mechanical["d_cells_x"] = [Decimal(0)] * inputs["cells"]
        mechanical["d_cells_y"] = [Decimal(0)] * inputs["cells"]
    sweep = cfg["frequency_sweep"]
    slope = (
        d(sweep["f slope"])
        if sweep["f slope"] is not None
        else (d(sweep["f stop"]) - d(sweep["f start"])) / d(inputs["SIM_total_s"])
        if inputs["source_f_sweep_configured"]
        else None
    )
    clock, sample_indices = ordinary.phase_clock(
        dict(
            init_total_s=inputs["time_profile"]["sim_total_s"],
            init_dt_s=inputs["time_profile"]["sim_dt_s"],
            init_sampling_s=inputs["time_profile"]["sim_sampling_s"],
        )
    )
    return dict(
        clock=clock,
        sample_indices=sample_indices,
        Dm_base=profile,
        Dm_scheduled=[[Decimal(0) for _ in row] for row in profile],
        Dm_cells=current,
        D_env=denv,
        P_base=numbers(old["P_cells"]),
        P_mod=numbers(old["P_cells"]),
        mechanics=mechanical,
        rate_CaATP=copy.deepcopy(old["rate_CaATP"]),
        rate_NaKATP=copy.deepcopy(old["rate_NaKATP"]),
        rho_pump=1,
        rho_channel=1,
        source_phase="SIM",
        legacy_run_sim=True,
        new_call_index=0,
        new_material_dt_sum_s=0.0,
        retained_INIT_call_count=inputs["INIT_call_count"],
        f_sweep_slope=slope,
        grn_owner_reused=True,
        grn_core_reused=True,
        molecular_current_concentrations_retained=True,
        source_cold_recapture=False,
        native_pickle_or_load_attested=False,
    )


def evaluate(inputs, *, refinement, retain):
    if refinement not in (1, 2):
        raise ValueError("Require the predeclared independent precision forms")
    precision = 100 if refinement == 1 else 160
    mode = inputs.get("mode")
    with localcontext() as context:
        context.prec = precision
        if mode == "phase_rules":
            answer = phase_rules(inputs)
            ordinary.retain_raw(retain, mode, answer, precision)
            result = serial(answer)
        elif mode == "nak":
            answer = ordinary.nak_equations(inputs, refinement)
            ordinary.retain_raw(retain, mode, answer, precision)
            result = serial(answer)
        elif mode == "material":
            adapted = copy.deepcopy(inputs)
            predicted = ordinary.nak_equations(inputs["nak_before"], refinement)
            ordinary.retain_raw(retain, "independent-NaK-before-material", predicted, precision)
            adapted["steps"][0]["supplied_pump_membrane_flux_mol_m2_s"] = predicted["applied_flux"]
            adapted["calcium"]["Ca_index"] = inputs["definition"][
                "environment_geometry_definition"
            ]["current_definition"]["ions"]["ids"].index("Ca")
            result = sim.material_model(
                adapted,
                refinement=refinement,
                retain_decimal=lambda value: ordinary.retain_raw(retain, mode, value, precision),
            )
        elif mode == "mechanics":
            result = ordinary.mechanics.evaluate(
                {key: inputs[key] for key in ("definition", "initial", "steps")},
                refinement=refinement,
                retain=retain,
            )
        else:
            # These bodies include the unchanged sodium domain guard. A source
            # native return outside the oracle domain receives no accuracy pass.
            result = sim.evaluate(inputs, refinement=refinement)
    result.update(
        mode=mode,
        decimal_precision=precision,
        carried_reference_forms=0,
        source_phase="SIM",
        legacy_run_sim=True,
        source_cold_recapture=False,
        independent_trajectory=False,
        fresh_conditional_reference=True,
        physical_global_conservation_credit=False,
        inherited_voltage_dependent_sodium_domain_V=[-0.120, 0.060],
    )
    return result


def main():
    import argparse
    import builtins
    import hashlib
    import importlib.abc
    import json
    import sys
    from pathlib import Path

    from validation.betse.betse_normal_channel_join_runtime import inventory
    from validation.betse.betse_normal_ecm_init_phase_capture import record_failure

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refinement", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "numpy", "scipy", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *values, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Independent phase-transition import denied: " + name)
        return original(name, *values, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError(
                    "Independent phase-transition import denied: " + fullname
                )

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    retained = args.output.parent / ("raw-reference-" + str(args.refinement))
    completed_retained = []

    def retain(name, value):
        retained.mkdir(parents=True, exist_ok=True)
        with (retained / (name + ".json")).open("x") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
        completed_retained.append(name)

    def file_record(path):
        if not path.exists():
            return dict(path=str(path), present=False)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Failure evidence must be a regular file: " + str(path))
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        return dict(path=str(path), present=True, bytes=path.stat().st_size, sha256=digest)

    def raw_records():
        return dict(
            completed_names=list(completed_retained),
            files=[file_record(path) for path in sorted(retained.iterdir())]
            if retained.exists()
            else [],
            incomplete_files_are_not_completed_forms=True,
        )

    def retain_failure(payload):
        payload.update(worker_kind="independent_INIT_SIM_transition_reference", scientific_credit=0)
        failure_path = args.output.with_name(args.output.name + ".failure.json")
        with failure_path.open("x") as stream:
            json.dump(payload, stream, indent=2, allow_nan=False)
            stream.write("\n")

    stage = "input"
    try:
        incoming = json.loads(args.inputs.read_text())
        stage = "evaluate"
        result = evaluate(incoming, refinement=args.refinement, retain=retain)
        stage = "runtime"
        loaded = [n for n in sys.modules if n.split(".")[0] in blocked]
        if loaded:
            raise ImportError("Forbidden transition reference modules were loaded")
        result.update(
            production_imports_denied=True, loaded_production_modules=loaded, runtime=inventory()
        )
        stage = "result_write"
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except Exception as error:
        record_failure(
            error,
            stage=stage,
            readers=dict(
                inputs=lambda: file_record(args.inputs),
                output=lambda: file_record(args.output),
                refinement=lambda: args.refinement,
                raw_reference_records=raw_records,
                runtime=inventory,
                loaded_production_modules=lambda: sorted(
                    n for n in sys.modules if n.split(".")[0] in blocked
                ),
            ),
            retain=retain_failure,
        )
        raise


if __name__ == "__main__":
    main()
