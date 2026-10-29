"""All-channel temporal observer projection, separate from independent oracles.

The qualified production observer is evaluated at independent trajectory states.
Voltage, actual material/fuel, program/source/work and conservation receive
additional independent checks. This is not a new derivation of every observer.
"""

import argparse
from pathlib import Path

from validation.tissue import open_calcium_bath_trajectory_common as artifact


def full_state(model, zero, context, vector):
    import numpy as np

    from validation.tissue import open_calcium_bath_reference as reference

    compact = reference.unpack(context, vector)
    values = []
    for name in zero._fields:
        value = np.zeros_like(getattr(zero, name))
        shape = context["shapes"][name]
        value[tuple(slice(0, size) for size in shape)] = compact[name]
        values.append(value)
    result = model.STATE_TYPE(*values)
    reference.owner.validate_padded_state(context["parent"], model.parent_state(result)._asdict())
    if not np.array_equal(reference.flatten(context, result._asdict()), vector):
        raise ValueError("Oracle projection changed a complete physical field")
    return result


def independent_observer_checks(context, vector, time, observed, protocol):
    import numpy as np

    from validation.tissue import open_calcium_bath_reference as reference

    _, phi, proof = reference.evaluate(context, vector, held_time=float(time))
    invariant = artifact.check_proof(reference.conservation(context, vector), protocol)
    fields = reference.unpack(context, vector)
    parent = context["parent"]
    base = parent["calcium"] if parent["finite_fuel"] else parent
    m = context["raw"]["model"]
    ionic = m["ionic"]
    ids = [row["id"] for row in ionic["species"]]
    inside = np.stack(
        [
            (store.n0 + fields["chemical_amount_increment"][i])[
                [store.ids.index(name) for name in ids], store.cy
            ]
            for i, store in enumerate(base["stores"])
        ],
        axis=1,
    )
    signal = proof["program"]
    physical = reference.physical_fields(context, vector)
    targets = dict(
        amount=inside,
        extracellular_amount=base["ao"]
        + fields["extracellular_amount_increment"]
        + signal["dose_fmol"],
        cell_potential_V=phi[: inside.shape[1]],
        extracellular_potential_V=phi[inside.shape[1] :],
        reservoir_supply_fmol_s=proof["physical_reservoir_supply_fmol_s"],
        electrode_current_A=proof["physical_electrode_current_A"],
        reservoir_power_pJ_s=np.atleast_1d(proof["physical_reservoir_power_pJ_s"]),
        electrode_power_pJ_s=np.atleast_1d(proof["physical_electrode_power_pJ_s"]),
        maintenance_reservoir_supply_fmol_s=proof["reservoir_supply_fmol_s"],
        maintenance_electrode_current_A=proof["electrode_current_A"],
        maintenance_reservoir_power_pJ_s=np.atleast_1d(proof["reservoir_power_pJ_s"]),
        maintenance_electrode_power_pJ_s=np.atleast_1d(proof["electrode_power_pJ_s"]),
        ionic_moiety_fmol=proof["ionic_moiety_fmol"],
        bath_pulse=signal["pulse"],
        bath_dose_fmol=signal["dose_fmol"],
        bath_dose_rate_fmol_s=signal["dose_rate_fmol_s"],
        bath_charge_C=signal["charge_C"],
        bath_chemical_work_pJ=signal["chemical_work_pJ"],
        bath_electrochemical_work_pJ=signal["electrochemical_work_pJ"],
        bath_electrode_work_pJ=signal["electrode_work_pJ"],
    )
    for name in (
        "extracellular_amount_increment",
        "reservoir_supplied",
        "electrode_charge_transferred_C",
        "reservoir_work_pJ",
        "electrode_work_pJ",
        "reservoir_chemical_work_pJ",
    ):
        targets["physical_" + name] = physical[name]
    if parent["finite_fuel"]:
        chemistry = reference.owner.chemistry
        amount = parent["energy_initial"] + fields["energy_amount_increment_fmol"]
        thermo = [
            chemistry.thermodynamics(
                amount[:, i],
                parent["energy_volumes"][i],
                parent["temperature"],
                parent["energy_delta_g0"][i],
            )
            for i in range(amount.shape[1])
        ]
        targets.update(
            energy_amount_fmol=amount,
            energy_concentration_mM=amount / parent["energy_volumes"],
            energy_chemical_potential_J_mol=np.asarray(
                [row["chemical_potential_J_mol"] for row in thermo]
            ).T,
            energy_hydrolysis_free_energy_J_mol=np.asarray(
                [row["hydrolysis_free_energy_J_mol"] for row in thermo]
            ),
            energy_free_energy_change_pJ=np.asarray(
                [
                    chemistry.free_energy_change(
                        parent["energy_initial"][:, i],
                        amount[:, i],
                        parent["energy_volumes"][i],
                        parent["energy_volumes"][i],
                        parent["temperature"],
                        parent["energy_delta_g0"][i],
                    )
                    for i in range(amount.shape[1])
                ]
            ),
            adenylate_fmol=amount[0] + amount[1],
            phosphorus_fmol=3 * amount[0] + 2 * amount[1] + amount[2],
        )
    metrics = {}
    for name, expected in targets.items():
        expected = np.asarray(expected)
        actual = np.asarray(observed[name])
        if actual.ndim != expected.ndim or any(
            a < b for a, b in zip(actual.shape, expected.shape, strict=True)
        ):
            raise ValueError("Independent observer shape disagreement: " + name)
        active = actual[tuple(slice(0, size) for size in expected.shape)]
        error = np.abs(active - expected) / artifact.observer_budget(name, expected, protocol)
        maximum = float(np.max(error, initial=0))
        metrics[name] = maximum
        if not np.isfinite(error).all() or maximum > 1.0:
            raise ValueError("Independent physical observer disagrees: " + name)
    return metrics, invariant


def run(bundle, job_id, output, dependency_runs):
    import numpy as np

    from cells.core.resources import trace_bytes
    from validation.tissue import open_calcium_bath_reference as reference

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    last, trial = {}, {}
    try:
        bundle = Path(bundle).resolve()
        protocol, job, raw = artifact.load_job(bundle, job_id, "projection")
        sources = artifact.dependencies(bundle, job, dependency_runs)
        if job["family"] == "calcium":
            from cells.core import surface_open_calcium_bath_events_spec as schema
            from cells.models import surface_open_calcium_bath_events as model
        else:
            from cells.core import surface_open_calcium_energy_bath_events_spec as schema
            from cells.models import surface_open_calcium_energy_bath_events as model
        spec = schema.parse(raw)
        zero, layout = model.initial_values(spec)
        context = reference.bind(raw)
        width = protocol["production"]["storage_window_steps"]
        while width > 1 and trace_bytes(spec, width, width + 1) > spec.execution.max_trace_bytes:
            width //= 2
        if trace_bytes(spec, width, width + 1) > spec.execution.max_trace_bytes:
            raise ValueError("Observer window exceeds original trace cap")
        outputs, largest = {}, {}
        with (output / "progress.jsonl").open("x") as progress:
            for variant in ("standard", "tight"):
                parent_id = job["oracles"][variant]
                source = sources[parent_id]
                record = source["record"]
                if (
                    record["role"] != "oracle"
                    or record["variant"] != variant
                    or record["dataset"] != job["dataset"]
                    or record["duration_s"] != protocol["duration_s"]
                ):
                    raise ValueError("Projection oracle identity or full duration changed")
                data = artifact.read_chunks(source["data"])
                times, vectors = data["times"], data["state"]
                chunks, total = [], 0
                for start in range(0, len(times) - 1, width):
                    stop = min(start + width + 1, len(times))
                    states = [
                        full_state(model, zero, context, value) for value in vectors[start:stop]
                    ]
                    history = model.STATE_TYPE(
                        *(np.stack([getattr(row, key) for row in states]) for key in zero._fields)
                    )
                    observed = model.observe_history(
                        times[start:stop], history, layout, times[start:stop], spec
                    )
                    fields = {key: np.asarray(value) for key, value in vars(observed).items()}
                    if job["is_epoch"]:
                        # This is a read-only observer projection, not a forged
                        # production checkpoint or epoch preparation.
                        fields["init_phase_clock_s"] = np.full_like(
                            fields["phase_clock_s"], record["source_phase_clock_s"]
                        )
                        fields["elapsed_time_s"] = (
                            protocol["epoch_init_duration_s"] + fields["phase_clock_s"]
                        )
                    if set(fields) != set(job["observer_fields"]):
                        raise ValueError("Projection omitted or added a qualified observer channel")
                    for local, i in enumerate(range(start, stop)):
                        last = dict(
                            variant=variant, sample_index=i, physical_time_s=float(times[i])
                        )
                        trial = dict(
                            state=vectors[i], **{key: value[local] for key, value in fields.items()}
                        )
                        metric, invariant = independent_observer_checks(
                            context,
                            vectors[i],
                            times[i],
                            {key: value[local] for key, value in fields.items()},
                            protocol,
                        )
                        for name, value in metric.items():
                            largest[name] = max(largest.get(name, 0.0), value)
                        artifact.write_progress(
                            progress,
                            last
                            | dict(
                                independent_observer_errors=metric, independent_invariants=invariant
                            ),
                        )
                    name = variant + "-observers-" + str(len(chunks)).zfill(4) + ".npz"
                    artifact.save_arrays(
                        output / name,
                        times=times[start:stop],
                        **{"observer__" + key: value for key, value in fields.items()},
                    )
                    total += stop - start - bool(chunks)
                    chunks.append(
                        dict(file=name, sha256=artifact.sha(output / name), rows=stop - start)
                    )
                folder = output / variant
                folder.mkdir()
                # An index lives with its chunks; relative links avoid copies.
                artifact.write_json(
                    folder / "trajectory-index.json",
                    dict(
                        samples=total,
                        chunks=[row | dict(file="../" + row["file"]) for row in chunks],
                    ),
                )
                outputs[variant] = dict(
                    index=str(folder / "trajectory-index.json"),
                    samples=total,
                    source_result_sha256=source["child_result_sha256"],
                )
        artifact.success(
            output,
            artifact.identity(bundle, protocol, job, raw, job_id)
            | dict(
                observer_fields=job["observer_fields"],
                variants=outputs,
                independent_physical_observer_max_errors=largest,
                storage_window_steps=width,
                projection_policy=(
                    "qualified complete observer map on independent states; "
                    "no observer formula independence claim"
                ),
                source_dependencies=sources,
            ),
        )
    except BaseException as error:
        artifact.failure(output, error, context=last, arrays=trial)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--job", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dependency-runs", required=True, type=Path)
    args = parser.parse_args()
    run(args.bundle, args.job, args.output, args.dependency_runs)


if __name__ == "__main__":
    main()
