"""Replay saved bath energy identities without changing a qualification result.

Exact rational sums isolate the last seven-term reduction only. The independent
reference is evaluated at the same saved state to retain upstream closure and
field evidence; neither calculation establishes high-precision model dynamics.
"""

import argparse
import math
import sys
from fractions import Fraction
from pathlib import Path


def reduction_record(terms, observed):
    """Separate final binary64 reduction error from already-rounded inputs.

    The standard gamma_(n-1) bound applies to normal finite additions without
    overflow/underflow. Its scale is the actual sum of absolute input terms, not
    an adjusted trajectory tolerance. It bounds reduction error, not physical error.
    """
    values = tuple(float(value) for value in terms)
    observed = float(observed)
    if len(values) < 2 or not all(math.isfinite(v) for v in (*values, observed)):
        raise ValueError("Require finite scalar terms and the saved finite reduction")
    total = values[0]
    intermediates = [total]
    for value in values[1:]:
        total += value
        intermediates.append(total)
    if total != observed:
        raise ValueError("The declared summation order does not reproduce the saved residual")
    if any(
        not math.isfinite(v) or 0 < abs(v) < sys.float_info.min for v in (*values, *intermediates)
    ):
        raise ValueError("This normal-arithmetic error bound excludes overflow and subnormals")
    exact = sum((Fraction.from_float(v) for v in values), Fraction())
    scale = sum((abs(Fraction.from_float(v)) for v in values), Fraction())
    operations = len(values) - 1
    unit_roundoff = Fraction(1, 2**53)
    gamma = operations * unit_roundoff / (1 - operations * unit_roundoff)
    error = Fraction.from_float(observed) - exact
    bound = gamma * scale
    if abs(error) > bound:
        raise ValueError("Observed summation error exceeds its normal-arithmetic bound")
    return dict(
        terms_pJ_s=list(values),
        terms_float_hex=[v.hex() for v in values],
        observed_pJ_s=observed,
        observed_float_hex=observed.hex(),
        exact_sum_of_rounded_terms=dict(
            numerator=str(exact.numerator), denominator=str(exact.denominator)
        ),
        exact_sum_rounded_to_binary64_pJ_s=float(exact),
        fsum_pJ_s=math.fsum(values),
        final_reduction_error_pJ_s=float(error),
        sum_absolute_terms_pJ_s=float(scale),
        final_reduction_error_bound_pJ_s=float(bound),
        reduction_error_within_bound=True,
        upstream_rounding_or_equation_error_bounded=False,
    )


def closure_terms(value, *, finite_fuel):
    """The exact seven signed inputs of open_calcium_reservoirs.close.

    Use the maintenance parent's field. The outer bath adds physical program
    powers but deliberately inherits the parent's residual, so its terms would
    represent a different arithmetic expression.
    """
    import numpy as np

    from cells.processes import finite_energy as energy

    parent, field = value.parent, value.parent.field
    raw = parent.parent
    internal = (
        np.sum(energy.chemical_power_pJ_s(raw.exchange.amount_fmol_s, raw.energy, xp=np))
        if finite_fuel
        else 0.0
    )
    external = (
        np.sum(raw.derivative.regeneration_supplied_work_pJ)
        if finite_fuel
        else sum(
            np.sum(getattr(raw.derivative, key))
            for key in ("metabolic_work_pJ", "plasma_metabolic_work_pJ", "er_metabolic_work_pJ")
        )
    )
    return dict(
        ionic_chemical=field.chemical_energy_rate_pJ_s,
        capacitor_and_ER=field.capacitor_energy_rate_pJ_s,
        internal_fuel_chemical=internal,
        dissipation=field.dissipation_pJ_s,
        negative_external_chemical=-external,
        negative_reservoir=-field.reservoir_power_pJ_s,
        negative_electrode=-field.electrode_power_pJ_s,
    )


def run(bundle, completed, output):
    import numpy as np

    from cells.core.schedule import control_values
    from validation.tissue import open_calcium_bath_reference as reference
    from validation.tissue import open_calcium_bath_trajectory_common as artifact
    from validation.tissue.open_calcium_bath_trajectory_observers import full_state

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    last = {}
    try:
        bundle, completed = Path(bundle).resolve(), Path(completed).resolve()
        manifest = artifact.verify_bundle(bundle)
        summary = artifact.read_json(completed / "saved-evidence-summary.json")
        if summary["bundle_manifest_sha256"] != artifact.sha(bundle / "manifest.json"):
            raise ValueError("Saved comparison summary belongs to another source bundle")
        plan = artifact.read_json(bundle / "plan.json")
        records, selections, pins = [], {}, {}
        for dataset in ("ordinary-calcium", "ordinary-energy"):
            finite = dataset.endswith("energy")
            if finite:
                from cells.core import surface_open_calcium_energy_bath_events_spec as schema
                from cells.models import surface_open_calcium_energy_bath_events as model
            else:
                from cells.core import surface_open_calcium_bath_events_spec as schema
                from cells.models import surface_open_calcium_bath_events as model
            ids = plan["datasets"][dataset]
            comparison_pin = summary["comparisons"][dataset + "-compare"]
            comparison = Path(comparison_pin["comparison_path"])
            if artifact.sha(comparison) != comparison_pin["comparison_sha256"]:
                raise ValueError("Failed comparison changed")
            pins[str(comparison)] = artifact.sha(comparison)
            archive = comparison.parent / (dataset + "-comparison.npz")
            pins[str(archive)] = artifact.sha(archive)
            key = "observer__energy_balance_pJ_s"
            with np.load(archive, allow_pickle=False) as saved:
                common, oracle = saved["common_times"], saved["oracle_times"]
                lookup = {float(v): i for i, v in enumerate(oracle)}
                on_common = np.asarray([lookup[float(v)] for v in common])
                budget = saved["budget__" + key]
                chosen = {
                    float(common[0]): ["initial control"],
                    float(common[-1]): ["full-duration endpoint control"],
                }
                for prefix in ("coarse_middle", "middle_fine"):
                    ratios = np.abs(saved[prefix + "_difference__" + key]) / budget[on_common]
                    i = np.unravel_index(np.argmax(ratios), ratios.shape)[0]
                    chosen.setdefault(float(common[i]), []).append(prefix + " maximum")
                ratios = np.abs(saved["oracle_difference__" + key]) / budget
                i = np.unravel_index(np.argmax(ratios), ratios.shape)[0]
                chosen.setdefault(float(oracle[i]), []).append("oracle-tightening maximum")
            selections[dataset] = {str(k): v for k, v in sorted(chosen.items())}
            raw = artifact.read_json(bundle / ids["definition"])
            spec, context = schema.parse(raw), reference.bind(raw)
            zero, layout = model.initial_values(spec)
            physical_nodes = np.r_[
                np.flatnonzero(layout.active),
                layout.active.size + np.flatnonzero(layout.outside_active),
            ]
            artifact.save_arrays(output / (dataset + "-layout.npz"), **layout._asdict())
            projection_path = Path(summary["verified_role_receipts"][ids["projection"]]["path"])
            artifact.verify_result(projection_path.parent)
            artifact.verify_result(projection_path.parent / "data")
            for job in ids["integrations"]:
                pin = summary["verified_role_receipts"][job]
                result = Path(pin["path"])
                if artifact.sha(result) != pin["sha256"]:
                    raise ValueError("Saved trajectory supervisor changed")
                artifact.verify_result(result.parent)
                artifact.verify_result(result.parent / "data")
                pins[str(result)] = artifact.sha(result)
                rows = artifact.read_chunks(result.parent / "data")
                wanted = plan["jobs"][job]
                production = wanted["role"] == "production"
                observers = (
                    rows
                    if production
                    else artifact.read_chunks(
                        projection_path.parent / "data" / wanted["oracle_variant"]
                    )
                )
                if not np.array_equal(rows["times"], observers["times"]):
                    raise ValueError("Saved state and observer clocks differ")
                indices = {float(v): i for i, v in enumerate(rows["times"])}
                for time, reasons in sorted(chosen.items()):
                    if time not in indices:
                        records.append(
                            dict(
                                job=job,
                                time_s=time,
                                selection=reasons,
                                status="not_on_this_accepted_grid_no_interpolation",
                            )
                        )
                        continue
                    i = indices[time]
                    last = dict(job=job, time_s=time, sample_index=i)
                    state = (
                        model.STATE_TYPE(*(rows["full__" + k][i] for k in zero._fields))
                        if production
                        else full_state(model, zero, context, rows["state"][i])
                    )
                    table = control_values(schema.owner_spec(spec), [time])
                    control = type(table)(*(v[0] for v in table))
                    value = model.readouts(state, control, layout, xp=np)
                    observed = float(np.asarray(observers[key][i]).item())
                    if not value.valid or value.field.energy_balance_pJ_s != observed:
                        raise ValueError(
                            "Frozen readout does not exactly replay the saved residual"
                        )
                    terms = closure_terms(value, finite_fuel=finite)
                    reduction = reduction_record(terms.values(), observed)
                    slope, phi, proof = reference.evaluate(
                        context, rows["state"][i], held_time=time
                    )
                    production_slope = reference.flatten(context, value.derivative._asdict())
                    rhs_budget = reference.flatten(
                        context,
                        {
                            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
                            for key, shape in context["shapes"].items()
                        },
                    ) + 3e-10 * np.abs(slope)
                    rhs_error = float(np.max(np.abs(production_slope - slope) / rhs_budget))
                    signal = value.signal
                    program = (
                        signal.chemical_power_pJ_s
                        - signal.electrochemical_power_pJ_s
                        - signal.electrode_power_pJ_s
                    )
                    identifier = job + "-" + str(i).zfill(4)
                    artifact.save_arrays(
                        output / (identifier + ".npz"),
                        complete_saved_state=rows["state"][i],
                        production_rhs=production_slope,
                        reference_rhs=slope,
                        reference_potential_V=phi,
                        charge_residual_C=value.field.charge_residual_C,
                        component_current_residual_A=value.field.component_current_residual_A,
                        bath_program_identity_pJ_s=program,
                        **{"control__" + k: v for k, v in control._asdict().items()},
                    )
                    records.append(
                        last
                        | dict(
                            selection=reasons,
                            status="saved_row_replayed",
                            terms=list(terms),
                            reduction=reduction,
                            original_stage_RHS_error_over_budget=rhs_error,
                            independent_same_state_energy_residual_pJ_s=proof[
                                "physical_energy_balance_pJ_s"
                            ],
                            maximum_program_identity_residual_pJ_s=float(np.max(np.abs(program))),
                            maximum_charge_residual_C=float(
                                np.max(np.abs(value.field.charge_residual_C))
                            ),
                            maximum_current_residual_A=float(
                                np.max(np.abs(value.field.component_current_residual_A))
                            ),
                            charge_normalized=float(value.field.charge_normalized),
                            current_normalized=float(value.field.current_normalized),
                            independent_same_state_potential_error_over_budget=float(
                                np.max(
                                    np.abs(value.field.potential_V[physical_nodes] - phi)
                                    / (3e-13 + 3e-10 * np.abs(phi))
                                )
                            ),
                            arrays=identifier + ".npz",
                        )
                    )
        artifact.verify_bundle(bundle)
        if any(artifact.sha(Path(p)) != h for p, h in pins.items()):
            raise ValueError("Saved input artifact changed during diagnosis")
        accepted = [r for r in records if r["status"] == "saved_row_replayed"]
        artifact.success(
            output,
            dict(
                kind="cells.saved_bath_energy_reduction_diagnosis@1",
                scope=(
                    "Read-only selected-state diagnosis; "
                    "no trajectory, accepted-threshold or order change"
                ),
                bundle_manifest_sha256=artifact.sha(bundle / "manifest.json"),
                frozen_bundle_files_verified=len(manifest["file_sha256"]),
                summary_sha256=artifact.sha(completed / "saved-evidence-summary.json"),
                selections=selections,
                input_pins=pins,
                records=records,
                replayed_rows=len(accepted),
                largest_observed_residual_pJ_s=max(
                    abs(r["reduction"]["observed_pJ_s"]) for r in accepted
                ),
                largest_exact_rounded_input_sum_pJ_s=max(
                    abs(r["reduction"]["exact_sum_rounded_to_binary64_pJ_s"]) for r in accepted
                ),
                largest_final_reduction_error_pJ_s=max(
                    abs(r["reduction"]["final_reduction_error_pJ_s"]) for r in accepted
                ),
                largest_stage_RHS_error_over_budget=max(
                    r["original_stage_RHS_error_over_budget"] for r in accepted
                ),
                original_failures_retained=True,
                automatic_followup=False,
            ),
        )
    except BaseException as error:
        artifact.failure(output, error, context=last)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--completed", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.bundle, args.completed, args.output)
