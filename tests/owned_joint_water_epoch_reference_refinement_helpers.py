"""Tighter independent references against immutable completed epoch artifacts.

No production solver is called. Existing RK4 histories remain read-only; each
tighter SIM reference starts from its newly computed independent INIT endpoint.
"""

import argparse
import hashlib
import json
import traceback
from pathlib import Path

import numpy as np

from validation.topology import joint_water_epoch_transient_fixtures as fixtures
from validation.topology import joint_water_epoch_transient_reference as reference

REFERENCE_BUDGET_FRACTION = 0.1
RESOLVED_FINE_ERROR_FRACTION = 0.1


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False, default=lambda x: x.tolist()) + "\n"
    )


def parts(dataset):
    if dataset not in fixtures.DATASETS:
        raise ValueError(dataset)
    phase, family, *_ = dataset.split("-")
    return phase, family


def baseline(bundle, dataset, role):
    manifest = read(bundle / "manifest.json")
    root = Path(manifest["baseline_result"]["path"]).parent
    stem = Path("evidence") / dataset / role
    for suffix in (".json", ".npz"):
        path = stem.with_suffix(suffix)
        if sha(root / path) != manifest["baseline_file_sha256"][str(path)]:
            raise ValueError("The accepted baseline artifact changed: " + str(path))
    return completed(root, dataset, role)


def completed(output, dataset, role="reference-2"):
    stem = output / "evidence" / dataset / role
    meta = read(stem.with_suffix(".json"))
    if meta["status"] != "completed" or sha(stem.with_suffix(".npz")) != meta["arrays_sha256"]:
        raise ValueError("Reference dependency is incomplete or changed")
    with np.load(stem.with_suffix(".npz"), allow_pickle=False) as data:
        return meta, {k: data[k].copy() for k in data.files}


def save(output, dataset, role, meta, arrays):
    stem = output / "evidence" / dataset / role
    stem.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(stem.with_suffix(".npz"), **arrays)
    write(
        stem.with_suffix(".json"),
        dict(meta, arrays_sha256=sha(stem.with_suffix(".npz"))),
    )


def run_reference(bundle, output, dataset):
    phase, family = parts(dataset)
    raw = read(bundle / "inputs" / (dataset + ".json"))
    old, _ = baseline(bundle, dataset, "reference")
    assert raw == old["inputs"]
    initial, dependency = None, None
    if phase == "SIM":
        dependency, data = completed(output, "INIT-" + family)
        assert dependency["refinement"] == 2
        initial = data["state_flat"][-1].copy()
        initial[-1] = 0.0
    times, states, proof = reference.integrate(raw, initial, refinement=2)
    context = reference.scheduled.bind(raw)
    save(
        output,
        dataset,
        "reference-2",
        dict(
            status="completed",
            dataset=dataset,
            refinement=2,
            inputs=raw,
            input_sha256=sha(bundle / "inputs" / (dataset + ".json")),
            proof=proof,
            initial_dependency=dependency,
            baseline_reference_sha256=old["arrays_sha256"],
        ),
        dict(
            times_s=times,
            state_flat=states,
            initial_flat=reference.scheduled.initial(context) if initial is None else initial,
            reference_shapes_json=np.asarray(json.dumps(context["parent"]["shapes"])),
        ),
    )


def numerical_comparison(phase, shapes, old, tight, productions):
    """Saved-array arithmetic; fixed budgets predeclared before reference-2 runs."""
    floors, mask = [], []
    for name, shape in shapes.items():
        length = int(np.prod(shape))
        floors.extend([3e-25 if name.endswith("_C") else 2e-11] * length)
        mask.extend([name == "membrane_transferred"] * length)
    floors, mask = np.r_[floors, 2e-11], np.r_[mask, False].astype(bool)
    reference_delta = tight["state_flat"] - old["state_flat"]
    old_budget = floors + 3e-9 * np.abs(old["state_flat"])
    reference_ratio = float(np.max(np.abs(reference_delta) / old_budget, initial=0))
    assert reference_ratio <= REFERENCE_BUDGET_FRACTION, (
        "reference stability exceeds the predeclared fraction of the state budget",
        reference_ratio,
    )
    tight_budget = floors + 3e-9 * np.abs(tight["state_flat"])
    ref_increment_change = (tight["state_flat"] - tight["initial_flat"]) - (
        old["state_flat"] - old["initial_flat"]
    )
    increment_change = float(np.max(np.abs(ref_increment_change[:, mask]), initial=0))
    records = []
    for data in productions:
        difference = data["state_flat"] - tight["state_flat"]
        ratio = float(np.max(np.abs(difference) / tight_budget, initial=0))
        assert ratio <= 1, ("original production state budget", ratio)
        increment = (data["state_flat"] - data["initial_flat"]) - (
            tight["state_flat"] - tight["initial_flat"]
        )
        records.append(
            dict(
                error_over_budget=ratio,
                max_absolute_state_error=float(np.max(np.abs(difference), initial=0)),
                background_increment_error_fmol=float(
                    np.max(np.abs(increment[:, mask]), initial=0)
                ),
            )
        )
    old_fine = (productions[1]["state_flat"] - productions[1]["initial_flat"]) - (
        old["state_flat"] - old["initial_flat"]
    )
    old_fine_error = float(np.max(np.abs(old_fine[:, mask]), initial=0))
    if phase == "SIM":
        assert old_fine_error > 0
        assert increment_change <= RESOLVED_FINE_ERROR_FRACTION * old_fine_error, (
            "reference uncertainty exceeds ten percent of the resolved fine-RK4 increment error",
            increment_change,
            old_fine_error,
        )
        coarse, fine = (row["background_increment_error_fmol"] for row in records)
        assert coarse > 1e-20 and fine <= 0.35 * coarse + 1e-22, (coarse, fine)
        label = "resolved_SIM_increment_reduction_with_stable_reference"
    elif phase == "INIT":
        high, low = (row["max_absolute_state_error"] for row in records)
        assert low <= max(0.35 * high, 3e-13), (high, low)
        label = "precision_limited" if max(high, low) <= 3e-13 else "resolved_reduction"
    else:
        raise ValueError(phase)
    return dict(
        reference_change_over_original_state_budget=reference_ratio,
        reference_background_increment_change_fmol=increment_change,
        retained_fine_background_increment_error_fmol=old_fine_error,
        reference_increment_change_over_fine_error=(
            increment_change / old_fine_error if phase == "SIM" else None
        ),
        production_against_tighter_reference=records,
        refinement_mode=label,
        convergence_order_claim=False,
    )


def comparison(bundle, output, dataset):
    phase, family = parts(dataset)
    old_meta, old = baseline(bundle, dataset, "reference")
    meta, tight = completed(output, dataset)
    assert meta["refinement"] == 2 and meta["inputs"] == old_meta["inputs"]
    for key in (
        "rtol",
        "amount_volume_energy_atol",
        "background_transfer_atol_fmol",
        "charge_atol_C",
        "clock_atol_s",
        "max_step_s",
    ):
        assert meta["proof"][key] == old_meta["proof"][key] / 2
    np.testing.assert_array_equal(tight["times_s"], old["times_s"])
    assert (
        meta["proof"]["held_control_boundaries_s"] == old_meta["proof"]["held_control_boundaries_s"]
    )
    assert str(tight["reference_shapes_json"]) == str(old["reference_shapes_json"])
    if phase == "SIM":
        init_meta, init = completed(output, "INIT-" + family)
        assert meta["initial_dependency"] == init_meta
        np.testing.assert_array_equal(tight["initial_flat"][:-1], init["state_flat"][-1, :-1])
        assert tight["initial_flat"][-1] == 0
    pairs = [baseline(bundle, dataset, "production-" + str(i)) for i in (1, 2)]
    production = [data for _, data in pairs]
    shapes = json.loads(str(tight["reference_shapes_json"]))
    fields = [*shapes, "phase_clock_s"]
    assert len(fields) == (44 if family == "water" else 49)
    arrays = dict(
        times_s=tight["times_s"],
        reference_1_flat=old["state_flat"],
        reference_2_flat=tight["state_flat"],
        reference_1_initial=old["initial_flat"],
        reference_2_initial=tight["initial_flat"],
        reference_shapes_json=tight["reference_shapes_json"],
    )
    for factor, data in enumerate(production, 1):
        np.testing.assert_array_equal(data["times_s"], tight["times_s"])
        assert data["state_fields"].tolist() == fields
        arrays["production_" + str(factor) + "_flat"] = data["state_flat"]
    offset = 0
    for name, shape in dict(shapes, phase_clock_s=[1]).items():
        length = int(np.prod(shape))
        arrays["reference_2__" + name] = tight["state_flat"][:, offset : offset + length].reshape(
            (len(tight["times_s"]), *shape)
        )
        offset += length
    # Preserve complete comparison inputs before any numerical acceptance assertion.
    stem = output / "evidence" / dataset / "comparison-inputs.npz"
    np.savez_compressed(stem, **arrays)
    try:
        report = numerical_comparison(phase, shapes, old, tight, production)
        context = reference.scheduled.bind(meta["inputs"])
        energy = [reference.energy_residual(context, vector) for vector in tight["state_flat"]]
        ledgers = [reference.conservation(context, vector) for vector in tight["state_flat"]]
        conservation = {k: max(row[k] for row in ledgers) for k in ledgers[0]}
        assert max(map(abs, energy)) <= 1e-9
        for key, value in conservation.items():
            assert value <= (4096 * np.finfo(float).eps if key == "damage_ledger" else 2e-12)
        write(
            stem.with_name("comparison.json"),
            dict(
                report,
                status="passed",
                dataset=dataset,
                complete_state_fields=len(fields),
                arrays_sha256=sha(stem),
                independent_energy_residual_pJ=energy,
                independent_conservation=conservation,
                all_observations_compared=True,
                independently_rechained_INIT_SIM=True,
                unchanged_original_accounting_anchors=True,
                production_reused_not_rerun=True,
                biological_case_count=0,
            ),
        )
    except Exception as error:
        write(
            stem.with_name("comparison-failure.json"),
            dict(
                status="failed",
                error=str(error),
                traceback=traceback.format_exc(),
                arrays_sha256=sha(stem),
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", choices=fixtures.DATASETS, required=True)
    args = parser.parse_args()
    try:
        run_reference(args.bundle, args.output, args.dataset)
    except Exception as error:
        path = args.output / "evidence" / args.dataset / "reference-2-failure"
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(error, reference.IntegrationFailure):
            np.savez_compressed(path.with_suffix(".npz"), **error.arrays)
        write(
            path.with_suffix(".json"),
            dict(status="failed", error=str(error), traceback=traceback.format_exc()),
        )
        raise


if __name__ == "__main__":
    main()
