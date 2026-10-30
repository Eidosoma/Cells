"""Inspect the first recovery interval from a preserved, conditional prefix.

This is a diagnostic, not an accepted recovery checkpoint or trajectory. The
source is the completed supply-off history; equality with the lost recovery
prefix follows from identical inputs/left-held controls, not a saved comparison.
Production stages and a fresh production-denied reference process stay separate.
"""

import argparse
import hashlib
import importlib.abc
import json
import math
import os
import sys
from copy import deepcopy
from pathlib import Path


def write(path, value):
    def convert(item):
        return item.tolist() if hasattr(item, "tolist") else str(item)

    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False, default=convert)
        stream.write("\n")


def load(root):
    inputs = json.loads((root / "inputs.json").read_text())
    for name, checksum in inputs["evidence_sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != checksum:
            raise ValueError("Changed original evidence: " + name)
    off = json.loads((root / "inputs/supply-off.json").read_text())["inputs"]
    recovery = json.loads((root / "inputs/recovery.json").read_text())["inputs"]
    old = deepcopy(recovery)
    schedules = old["experiment"]["regeneration_controls"]
    assert len(schedules) == 1
    assert schedules[0]["schedule"].pop() == dict(time=0.25, availability=0.1)
    assert old == off, "Only the declared recovery event may differ"
    return inputs, off, recovery


def production(root):
    import numpy as np

    from cells.core.errors import NumericalError
    from cells.core.schedule import control_values
    from cells.core.specs import parse_spec
    from cells.models import surface_cotransport_water as model
    from cells.numerics.fixed_step import rk4_step
    from cells.processes import finite_energy as fuel

    inputs, off, raw = load(root)
    spec, off_spec = parse_spec(raw), parse_spec(off)
    _, layout = model.initial_values(spec)
    _, off_layout = model.initial_values(off_spec)
    for first, second in zip(layout, off_layout, strict=True):
        np.testing.assert_array_equal(first, second)
    before = [0.0, np.nextafter(0.25, 0.0)]
    for first, second in zip(
        control_values(spec, before), control_values(off_spec, before), strict=True
    ):
        np.testing.assert_array_equal(first, second)
    with np.load(root / "inputs/supply-off-history.npz", allow_pickle=False) as saved:
        index = inputs["source_row"]
        assert saved["accepted_times"][index] == 0.25
        start, end = map(float, saved["accepted_times"][index : index + 2])
        state = model.STATE_TYPE(*(saved[name][index].copy() for name in model.STATE_TYPE._fields))
    parent_diagnostics = model.check_values(state, spec)
    table = control_values(spec, [start])
    held = type(table)(*(v[0] for v in table))
    np.savez_compressed(
        root / "source.npz",
        **state._asdict(),
        **{"layout__" + k: v for k, v in layout._asdict().items()},
        **{"control__" + k: v for k, v in held._asdict().items()},
    )

    def terms(value):
        water = model.water_state(value)
        physical = model.water_layout(layout)
        balances = model.balances(value, layout)
        free = model.prior.pool_free_energy_change_pJ(water, physical)
        parts = dict(
            pool_free_energy_change_pJ=float(np.sum(free)),
            metabolic_transfer_pJ=float(np.sum(value.metabolic_work_pJ)),
            regeneration_heat_pJ=float(np.sum(value.regeneration_dissipated_energy_pJ)),
            negative_supplied_work_pJ=-float(np.sum(value.regeneration_supplied_work_pJ)),
            negative_pool_volume_work_pJ=-float(np.sum(value.pool_volume_work_pJ)),
        )
        return dict(
            energy_residual_pJ=float(balances["energy"]),
            pool_energy_residual_pJ=float(np.max(np.abs(balances["pool_energy"]))),
            signed_pool_terms=parts,
            compensated_pool_sum_pJ=math.fsum(parts.values()),
            pool_amount_fmol=layout.energy_initial_amount_fmol + value.energy_amount_increment_fmol,
        )

    source_terms = terms(state)
    write(
        root / "source.json",
        dict(
            start_s=start,
            end_s=end,
            interval_s=end - start,
            parent_diagnostics=parent_diagnostics,
            source_terms=source_terms,
            inputs_identical_except_recovery_event=True,
            observed_recovery_prefix_equality=False,
            original_anchors_carried=True,
            qualification_pass=False,
        ),
    )
    results = []
    for subdivisions in inputs["subdivisions"]:
        current = model.STATE_TYPE(*(v.copy() for v in state))
        times = np.linspace(start, end, subdivisions + 1)
        arrays, stages, endpoints = {}, [], []
        failure = None
        for step, dt in enumerate(np.diff(times)):
            stage_index = 0

            def evaluate(
                trial,
                control,
                parameters,
                active,
                *,
                stages=stages,
                arrays=arrays,
                step=step,
                dt=dt,
                times=times,
            ):
                nonlocal stage_index
                key = f"s{len(stages):04d}"
                arrays.update({key + "__" + k: v.copy() for k, v in trial._asdict().items()})
                entry = dict(
                    key=key,
                    step=step,
                    stage=stage_index,
                    dt_s=float(dt),
                    physical_time_s=float(times[step] + (0.0, 0.5, 0.5, 1.0)[stage_index] * dt),
                    held_control_time_s=start,
                )
                stages.append(entry)
                stage_index += 1
                valid = model.control_domain_valid(trial, control, parameters, active, xp=np)
                entry["valid"] = bool(valid)
                if not valid:
                    raise NumericalError("Diagnostic RK4 trial outside the original domain")
                value = model.readouts(trial, control, parameters, xp=np)
                slope = model.rhs(trial, control, parameters, active, xp=np)
                arrays.update({key + "__rhs__" + k: v for k, v in slope._asdict().items()})
                thermo = fuel.thermodynamics(
                    parameters.energy_initial_amount_fmol + trial.energy_amount_increment_fmol,
                    parameters.volume + trial.volume_increment_pL,
                    model.prior.prior.pool_parameters(
                        model.prior.energy_layout(model.water_layout(parameters))
                    ),
                    xp=np,
                )
                entry.update(
                    terms=terms(trial),
                    chemical_potential_J_mol=thermo.chemical_potential_J_mol,
                    physical_energy_rate_residual_pJ_s=float(value.field.energy_balance_pJ_s),
                    regeneration_rate_fmol_s=slope.regeneration_cycles_fmol,
                    regeneration_heat_pJ_s=slope.regeneration_dissipated_energy_pJ,
                    supplied_work_pJ_s=slope.regeneration_supplied_work_pJ,
                )
                return slope

            try:
                proposed = rk4_step(evaluate, current, float(dt), held, layout, layout.active)
                key = f"e{step:04d}"
                arrays.update({key + "__" + k: v for k, v in proposed._asdict().items()})
                if not model.control_domain_valid(proposed, held, layout, layout.active, xp=np):
                    raise NumericalError("Diagnostic endpoint outside the original domain")
                row = dict(key=key, time_s=float(times[step + 1]), terms=terms(proposed))
                try:
                    row["diagnostics"] = model.check_values(proposed, spec)
                    row["original_accounting_pass"] = True
                except NumericalError as error:
                    row.update(original_accounting_pass=False, accounting_failure=str(error))
                endpoints.append(row)
                # Cumulative accounting is evaluated after rollout by the original
                # runner. Carry these domain-valid proposals only as diagnostics.
                current = proposed
            except Exception as error:
                failure = dict(type=type(error).__name__, message=str(error), step=step)
                break
        np.savez_compressed(root / f"stages-r{subdivisions}.npz", **arrays)
        result = dict(
            subdivisions=subdivisions,
            completed_intervals=len(endpoints),
            stages=stages,
            endpoints=endpoints,
            failure=failure,
            original_energy_limit_pJ=2e-8,
            qualification_pass=False,
        )
        write(root / f"stages-r{subdivisions}.json", result)
        results.append(result)
    write(root / "production.json", dict(status="diagnostic_captured", variants=results))


def independent(root):
    denied = {"cells", "jax", "jaxlib", "betse"}

    class Deny(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in denied:
                raise ImportError("Denied production import: " + fullname)

    sys.meta_path.insert(0, Deny())
    import numpy as np
    from scipy.integrate import solve_ivp

    from validation.tissue import surface_cotransport_water_reference as reference

    inputs, _, raw = load(root)
    context = reference.bind(raw)
    with np.load(root / "source.npz", allow_pickle=False) as saved:
        fields = {k: saved[k].copy() for k in context["shapes"]}
    source = reference.flatten(context, fields)
    metadata = json.loads((root / "source.json").read_text())
    start, duration = metadata["start_s"], metadata["interval_s"]
    comparisons, finals = [], []

    def pool_terms(vector, original):
        fields = reference.unpack(context, vector)
        water = context["water_energy"]
        amounts = water["energy_initial"] + fields["energy_amount_increment_fmol"]
        free = sum(
            reference.water_energy.chemistry.free_energy_change(
                water["energy_initial"][:, owner].tolist(),
                amounts[:, owner].tolist(),
                float(context["vi"][owner]),
                float(context["vi"][owner] + fields["volume_increment_pL"][owner]),
                raw["model"]["temperature_K"],
                float(water["energy_delta_g0"][owner]),
            )
            for owner in range(len(context["vi"]))
        )
        parts = original["signed_pool_terms"]
        revised = dict(parts, pool_free_energy_change_pJ=free)
        return dict(
            original_pool_free_energy_change_pJ=parts["pool_free_energy_change_pJ"],
            independent_80_digit_pool_free_energy_change_pJ=free,
            free_energy_difference_pJ=free - parts["pool_free_energy_change_pJ"],
            compensated_pool_terms_pJ=math.fsum(parts.values()),
            compensated_pool_terms_with_independent_free_energy_pJ=math.fsum(revised.values()),
            ledger_rounding_not_bounded=True,
        )

    pool_comparisons = [dict(role="source", **pool_terms(source, metadata["source_terms"]))]
    base_atol = reference.flatten(
        context,
        {k: np.full(v, 3e-25 if k.endswith("_C") else 2e-11) for k, v in context["shapes"].items()},
    )
    # Reuse the component's full-rate comparison limits. Endpoint state limits
    # have different units and must not be described as an RHS error budget.
    rate_atol = reference.flatten(
        context,
        {k: np.full(v, 3e-23 if k.endswith("_C") else 3e-12) for k, v in context["shapes"].items()},
    )
    for count in inputs["subdivisions"]:
        row = json.loads((root / f"stages-r{count}.json").read_text())
        with np.load(root / f"stages-r{count}.npz", allow_pickle=False) as saved:
            for stage in row["stages"]:
                if not stage["valid"]:
                    continue
                vector = reference.flatten(
                    context, {k: saved[stage["key"] + "__" + k] for k in context["shapes"]}
                )
                actual = reference.flatten(
                    context, {k: saved[stage["key"] + "__rhs__" + k] for k in context["shapes"]}
                )
                expected, _, proof = reference.evaluate(context, vector, start)
                comparisons.append(
                    dict(
                        subdivisions=count,
                        stage=stage["key"],
                        proof=proof,
                        max_rhs_error_fraction=float(
                            np.max(abs(actual - expected) / (rate_atol + 3e-10 * abs(expected)))
                        ),
                    )
                )
            if row["completed_intervals"] == count:
                last = row["endpoints"][-1]
                finals.append(
                    (
                        count,
                        reference.flatten(
                            context, {k: saved[last["key"] + "__" + k] for k in context["shapes"]}
                        ),
                    )
                )
                pool_comparisons.append(
                    dict(role=f"endpoint-r{count}", **pool_terms(finals[-1][1], last["terms"]))
                )
    write(
        root / "same-state-reference.json",
        dict(
            records=comparisons,
            pool_energy_reconstruction=pool_comparisons,
            production_imports_denied=True,
            rate_tolerances=dict(atol_per_s=3e-12, charge_atol_C_s=3e-23, rtol=3e-10),
        ),
    )
    slope = reference.evaluate(context, source, start)[0]
    pool_rate = reference.unpack(context, slope)["energy_amount_increment_fmol"][0, 0]
    first_step = min(
        duration / 1000, metadata["source_terms"]["pool_amount_fmol"][0][0] / abs(pool_rate) / 8
    )
    answers = []
    for refinement in (1, 2):
        trials = []

        def evaluate(time, delta, *, trials=trials):
            actual = source + delta
            trials.append((time, actual.copy()))
            return reference.evaluate(context, actual, start)[0]

        atol = reference.flatten(
            context,
            {
                k: np.full(v, (1e-29 if k.endswith("_C") else 2e-14) / refinement)
                for k, v in context["shapes"].items()
            },
        )
        try:
            value = solve_ivp(
                evaluate,
                (0.0, duration),
                np.zeros_like(source),
                method="DOP853",
                rtol=2e-11 / refinement,
                atol=atol,
                first_step=first_step / refinement,
                max_step=duration / (8 * refinement),
            )
            if not value.success:
                raise ValueError(value.message)
            answers.append(source + value.y[:, -1])
            write(
                root / f"reference-r{refinement}.json",
                dict(
                    status="completed",
                    nfev=value.nfev,
                    first_step_s=first_step / refinement,
                    local_clock=True,
                    original_anchors_carried=True,
                ),
            )
        except Exception as error:
            write(
                root / f"reference-r{refinement}-failure.json",
                dict(type=type(error).__name__, message=str(error), automatic_retry=False),
            )
            raise
        finally:
            np.savez_compressed(
                root / f"reference-r{refinement}-trials.npz",
                local_times=[t for t, _ in trials],
                states=[v for _, v in trials],
            )
    tight = answers[1]
    budget = base_atol + 3e-9 * abs(tight)
    report = dict(
        status="diagnostic_completed",
        qualification_pass=False,
        production_imports_denied=True,
        max_same_state_rhs_error_fraction=max(r["max_rhs_error_fraction"] for r in comparisons),
        reference_uncertainty_fraction=float(np.max(abs(answers[0] - tight) / budget)),
        endpoint_error_fractions={
            str(n): float(np.max(abs(v - tight) / budget)) for n, v in finals
        },
        original_full_recovery_qualified=False,
    )
    np.savez_compressed(
        root / "reference-endpoints.npz",
        normal=answers[0],
        tight=tight,
        **{f"production_r{n}": v for n, v in finals},
    )
    assert not any(name.split(".")[0] in denied for name in sys.modules)
    write(root / "independent.json", report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("production", "independent"))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        (production if args.phase == "production" else independent)(args.directory)
    finally:
        import importlib.metadata
        import platform

        files = {}
        for module in tuple(sys.modules.values()):
            name = getattr(module, "__file__", None)
            if name and Path(name).is_file():
                path = Path(name).resolve()
                files[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        executable = Path(sys.executable).resolve()
        files[str(executable)] = hashlib.sha256(executable.read_bytes()).hexdigest()
        write(
            args.directory / ("runtime-" + args.phase + ".json"),
            dict(
                files=files,
                python=platform.python_version(),
                affinity=sorted(os.sched_getaffinity(0)),
                versions={
                    name: importlib.metadata.version(name)
                    for name in ("numpy", "scipy", "jax", "jaxlib")
                },
                environment={
                    name: os.environ.get(name)
                    for name in (
                        "OMP_NUM_THREADS",
                        "OPENBLAS_NUM_THREADS",
                        "MKL_NUM_THREADS",
                        "JAX_PLATFORMS",
                        "JAX_ENABLE_X64",
                        "CUDA_VISIBLE_DEVICES",
                    )
                },
            ),
        )


if __name__ == "__main__":
    main()
