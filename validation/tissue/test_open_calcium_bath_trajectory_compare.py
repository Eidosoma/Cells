"""Synthetic evidence checks for full-grid comparison and exact INIT lineage.

No physical model or integrator runs. Tiny synthetic arrays exercise the
comparison machinery; independent physical equations retain their own tests.
"""

from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from validation.tissue import open_calcium_bath_trajectory_common as artifact
from validation.tissue import open_calcium_bath_trajectory_compare as compare


def chunks(directory, rows):
    directory.mkdir(parents=True, exist_ok=True)
    boundary = len(rows["times"]) // 2
    entries = []
    for number, selection in enumerate((slice(None, boundary + 1), slice(boundary, None))):
        name = "chunk-" + str(number) + ".npz"
        artifact.save_arrays(
            directory / name, **{key: value[selection] for key, value in rows.items()}
        )
        entries.append(dict(file=name, sha256=artifact.sha(directory / name)))
    artifact.write_json(
        directory / "trajectory-index.json", dict(chunks=entries, samples=len(rows["times"]))
    )


def rewrite_chunk(directory, number, transform):
    index = artifact.read_json(directory / "trajectory-index.json")
    entry = index["chunks"][number]
    path = directory / entry["file"]
    with np.load(path, allow_pickle=False) as archive:
        values = {key: archive[key].copy() for key in archive.files}
    transform(values)
    artifact.save_arrays(path, **values)
    entry["sha256"] = artifact.sha(path)
    artifact.write_json(directory / "trajectory-index.json", index)


def test_chunks_preserve_every_array_and_exact_overlap(tmp_path):
    rows = dict(
        times=np.arange(5.0), state=np.arange(10.0).reshape(5, 2), flag=np.arange(5) % 2 == 0
    )
    chunks(tmp_path, rows)
    restored = artifact.read_chunks(tmp_path)
    assert set(restored) == set(rows)
    for key in rows:
        np.testing.assert_array_equal(restored[key], rows[key], strict=True)


@pytest.mark.parametrize("defect", ["precision", "overlap", "inventory", "length", "sample_count"])
def test_chunks_refuse_rehashed_inconsistent_evidence(tmp_path, defect):
    chunks(tmp_path, dict(times=np.arange(5.0), state=np.arange(10.0).reshape(5, 2)))

    def alter(values):
        if defect == "precision":
            values["state"] = values["state"].astype(np.float32)
        elif defect == "overlap":
            values["state"][0, 0] = np.nextafter(values["state"][0, 0], np.inf)
        elif defect == "inventory":
            values["extra"] = values["state"].copy()
        elif defect == "length":
            values["state"] = values["state"][:-1]

    rewrite_chunk(tmp_path, 1, alter)
    if defect == "sample_count":
        record = artifact.read_json(tmp_path / "trajectory-index.json")
        record["samples"] += 1
        artifact.write_json(tmp_path / "trajectory-index.json", record)
    with pytest.raises(ValueError):
        artifact.read_chunks(tmp_path)


@pytest.fixture
def phase(tmp_path, monkeypatch):
    # Only physical binding is replaced. Real grid, array, observer, tolerance,
    # tightening, refinement and durable-comparison code execute unchanged.
    from validation.tissue import open_calcium_bath_reference as reference

    shapes = dict(marker=(1,), reservoir_chemical_work_pJ=(1,), phase_clock_s=(1,))
    context = dict(shapes=shapes, parent=dict(shapes=shapes))
    monkeypatch.setattr(reference, "bind", lambda raw: context)
    monkeypatch.setattr(reference, "initial", lambda value: np.zeros(3))
    monkeypatch.setattr(
        reference, "flatten", lambda context, values: np.concatenate([values[k] for k in shapes])
    )
    monkeypatch.setattr(reference.owner, "validate_padded_state", lambda context, values: None)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    artifact.write_json(bundle / "manifest.json", dict(synthetic=True))
    raw = dict(
        experiment=dict(end_time=8e-6, observation_times=[0.0, 4e-6, 8e-6]),
        execution=dict(dt=4e-6, max_steps=8, extracellular_capacity=1),
        model=dict(ionic=dict(cells=[{}], extracellular=[{}])),
    )
    protocol = dict(
        base_dt_s=4e-6,
        dt_divisors=[1, 2, 4],
        epoch_init_duration_s=8e-6,
        refinement=dict(roundoff_resolution_fraction=0.01),
        tolerances=dict(
            trajectory_charge_atol=1e-6,
            trajectory_state_atol=1e-6,
            trajectory_rtol=0.0,
            clock_atol_s=1e-19,
            field_potential_atol_V=1e-6,
            field_potential_rtol=0.0,
            oracle_tightening_max_fraction_of_budget=0.1,
        ),
    )
    jobs, sources, arrays = {}, {}, {}
    production = {str(divisor): "production" + str(divisor) for divisor in (1, 2, 4)}
    oracles = {variant: "oracle-" + variant for variant in ("standard", "tight")}
    ids = dict(
        integrations=[*oracles.values(), *production.values()],
        oracles=oracles,
        production=production,
        projection="projection",
        definition="dt1.json",
    )
    plan = dict(jobs=jobs, datasets=dict(synthetic=ids))
    for divisor in (1, 2, 4):
        definition = deepcopy(raw)
        definition["execution"]["dt"] /= divisor
        artifact.write_json(bundle / ("dt" + str(divisor) + ".json"), definition)
    for name in ids["integrations"]:
        is_production = name.startswith("production")
        divisor = int(name[-1]) if is_production else 4
        job = dict(
            role="production" if is_production else "oracle",
            family="calcium",
            dataset="synthetic",
            phase="SIM",
            is_epoch=False,
            definition="dt" + str(divisor if is_production else 1) + ".json",
            observer_fields=["times", "marker", "gate"],
        )
        if is_production:
            job["dt_divisor"] = divisor
        else:
            job["oracle_variant"] = name.removeprefix("oracle-")
        definition = artifact.read_json(bundle / job["definition"])
        grid = artifact.accepted_times(raw, protocol["base_dt_s"] / divisor)
        job["expected_samples"] = len(grid)
        jobs[name] = job
        marker = (grid / 8e-6)[:, None]
        rows = dict(
            times=grid,
            state=np.column_stack((marker[:, 0], np.zeros(len(grid)), grid)),
            potential_V=np.zeros((len(grid), 2)),
        )
        if is_production:
            rows.update(
                full__marker=marker.copy(),
                full__reservoir_chemical_work_pJ=np.zeros((len(grid), 1)),
                full__phase_clock_s=grid[:, None],
                observer__times=grid.copy(),
                observer__marker=marker.copy(),
                observer__gate=np.zeros((len(grid), 1), dtype=bool),
            )
        directory = tmp_path / name
        chunks(directory, rows)
        record = artifact.identity(bundle, protocol, job, definition, name) | dict(
            state_shapes={key: list(shape) for key, shape in shapes.items()},
            complete_fields=3,
            control_times_s=artifact.control_times(raw),
            samples=len(grid),
            rk_stages=4 * (len(grid) - 1),
            observer_fields=job["observer_fields"],
            variant=job.get("oracle_variant"),
            imported_production_or_jax=False,
            synthetic=True,
        )
        artifact.success(directory, record)
        sources[name] = dict(
            data=str(directory),
            record=record,
            child_result_sha256=artifact.sha(directory / "result.json"),
        )
        arrays[name] = rows
    pjob = dict(
        role="projection",
        family="calcium",
        dataset="synthetic",
        phase="SIM",
        observer_fields=["times", "marker", "gate"],
    )
    jobs["projection"] = pjob
    record = artifact.identity(bundle, protocol, pjob, raw, "projection") | dict(
        observer_fields=pjob["observer_fields"], variants={}
    )
    for variant, name in oracles.items():
        grid = arrays[name]["times"]
        rows = dict(
            times=grid,
            observer__times=grid.copy(),
            observer__marker=(grid / 8e-6)[:, None],
            observer__gate=np.zeros((len(grid), 1), dtype=bool),
        )
        chunks(tmp_path / "projection" / variant, rows)
        record["variants"][variant] = dict(
            source_result_sha256=sources[name]["child_result_sha256"]
        )
    sources["projection"] = dict(data=str(tmp_path / "projection"), record=record)
    output = tmp_path / "comparison"
    output.mkdir()
    return dict(
        bundle=bundle,
        dataset="synthetic",
        protocol=protocol,
        plan=plan,
        sources=sources,
        output=output,
    )


def test_full_grid_accuracy_keeps_unresolved_order_and_fixed_clock_budget(phase):
    record, _, _ = compare.phase_comparison(**phase)
    assert record["violations"] == []
    expected_channels = {
        "state__marker",
        "state__reservoir_chemical_work_pJ",
        "state__phase_clock_s",
        "potential_V",
        "observer__times",
        "observer__marker",
        "observer__gate",
    }
    assert set(record["accuracy"]) == {"1", "2", "4"}
    assert all(set(row) == expected_channels for row in record["accuracy"].values())
    assert all(
        row["observed_order"] is None and row["status"] == "below_refinement_resolution"
        for row in record["refinement"].values()
    )
    with np.load(phase["output"] / "synthetic-comparison.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["budget__state__phase_clock_s"], np.full((9, 1), 1e-19))
        assert len(saved["oracle_times"]) == 9
        assert len(saved["common_times"]) == 3


@pytest.mark.parametrize("channel", ["observer__gate", "observer__marker", "potential_V"])
def test_late_only_channel_error_is_not_hidden_by_other_exact_rows(phase, channel):
    path = Path(phase["sources"]["production4"]["data"])

    def change(values):
        values[channel][-1, 0] = True if channel.endswith("gate") else 1.001

    rewrite_chunk(path, 1, change)
    record, _, _ = compare.phase_comparison(**phase)
    assert record["accuracy"]["4"][channel] > 1
    assert (
        "production full state/observer trajectory exceeds fixed accuracy budget"
        in record["violations"]
    )
    assert (phase["output"] / "synthetic-comparison.npz").exists()
    assert artifact.read_json(phase["output"] / "synthetic-comparison.json")["violations"]


def test_oracle_tightening_has_its_own_budget(phase):
    path = Path(phase["sources"]["oracle-standard"]["data"])

    def change(values):
        values["state"][-1, 0] += 2e-7

    rewrite_chunk(path, 1, change)
    record, _, _ = compare.phase_comparison(**phase)
    assert record["oracle_uncertainty_fraction"]["state__marker"] > 0.1
    assert "oracle tightening exceeds its fixed uncertainty share" in record["violations"]
    assert all(error == 0 for row in record["accuracy"].values() for error in row.values())


def test_missing_observer_cannot_be_treated_as_zero_error(phase):
    path = Path(phase["sources"]["production4"]["data"])
    for index in (0, 1):
        rewrite_chunk(path, index, lambda values: values.pop("observer__gate"))
    with pytest.raises(ValueError, match="incomplete"):
        compare.phase_comparison(**phase)


@pytest.mark.parametrize(
    "defect",
    [
        None,
        "material",
        "padding",
        "clock",
        "source_clock",
        "short_init",
        "wrong_parent",
        "unclaimed",
    ],
)
def test_actual_init_lineage_uses_exact_arrays_and_receipts(defect):
    parent, child = "init-production1", "epoch-production1"
    plan = dict(
        jobs={child: dict(parent=parent, role="production")},
        datasets={"epoch": dict(integrations=[child])},
    )
    sources = {parent: dict(result_sha256="parent-supervisor", child_result_sha256="parent-child")}
    before = dict(
        state=np.array([[0.0, 0.0], [1.0, 8e-6]]), full__material=np.array([[0.0, 0.0], [1.0, 0.0]])
    )
    after = dict(
        state=np.array([[1.0, 0.0], [2.0, 8e-6]]), full__material=np.array([[1.0, 0.0], [2.0, 0.0]])
    )
    trajectories = {parent: before, child: after}
    records = {
        parent: dict(phase="INIT", duration_s=8e-6),
        child: dict(
            full_actual_INIT_carry=True,
            source_dependency=deepcopy(sources[parent]),
            source_phase_clock_s=8e-6,
        ),
    }
    if defect == "material":
        after["state"][0, 0] = np.nextafter(1.0, np.inf)
    elif defect == "padding":
        after["full__material"][0, 1] = np.nextafter(0.0, np.inf)
    elif defect == "clock":
        after["state"][0, -1] = 8e-6
    elif defect == "source_clock":
        records[child]["source_phase_clock_s"] = 1e-9
    elif defect == "short_init":
        records[parent]["duration_s"] = 1e-9
    elif defect == "wrong_parent":
        records[child]["source_dependency"]["child_result_sha256"] = "other-resolution"
    elif defect == "unclaimed":
        records[child]["full_actual_INIT_carry"] = False
    if defect:
        with pytest.raises(ValueError, match="carry|array"):
            compare.check_carry(
                plan, "epoch", sources, trajectories, records, dict(epoch_init_duration_s=8e-6)
            )
    else:
        result = compare.check_carry(
            plan, "epoch", sources, trajectories, records, dict(epoch_init_duration_s=8e-6)
        )
        assert result[child]["exact_nonclock_carry"] and result[child]["reset_clock_only"]


@pytest.mark.parametrize(
    "first,second,passed",
    [(0.8, 0.05, True), (0.8, 0.2, False), (0.2, 0.4, False), (0.8, 0.0, True)],
)
def test_resolved_refinement_does_not_accept_accurate_but_nonconverging_results(
    first, second, passed
):
    row = compare.refinement(first, second, 0.01)
    assert row["status"] == "resolved_refinement"
    assert row["passed"] is passed
