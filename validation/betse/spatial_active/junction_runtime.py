"""Initial/static export and evidence binding for ordinary dynamic junctions."""

import json
from pathlib import Path

import numpy as np

from cells.core.betse_junction_spec import MODEL_ID, SOLVER_ID
from cells.core.betse_spatial_spec import INITIAL_FIELDS
from cells.numerics import betse_active as active
from validation.betse.spatial_active import junction_refinement as long
from validation.betse.spatial_active import junctions, refinement
from validation.betse.spatial_trajectory.reference import material_roundoff

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_PATH = Path(__file__).with_name("junction_runtime_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def baseline():
    rule = protocol()
    reports = {}
    for name in ("prior_binding", "prefix_binding", "runtime_prefix_binding", "source_binding"):
        binding = rule[name]
        root = Path(binding["root"])
        assert refinement.digest(root / "completion.json") == binding["completion_sha256"]
        reports[name] = refinement.completed_prior(binding, current_root=root / "source")
    root = Path(rule["source_binding"]["root"])
    registration = json.loads((root / "registration.json").read_text())
    changed = []
    for name, sha in registration["sources_sha256"].items():
        if refinement.digest(ROOT / name) != sha:
            assert name in rule["allowed_prior_source_changes"], name
            changed.append(name)
    assert set(changed) == set(rule["allowed_prior_source_changes"])
    production = {str(p.relative_to(ROOT)) for p in (ROOT / "src").rglob("*.py")}
    old = {n for n in registration["sources_sha256"] if n.startswith("src/")}
    assert production - old == set(rule["new_production_files"])
    assert old <= production
    # Permit exactly the declared parser-bound edits in production. In particular,
    # the update law, clocks, controls, accounting and shared runners stay frozen.
    replacements = rule["production_source_replacements"]
    assert set(replacements) == {n for n in changed if n.startswith("src/")}
    for name in (n for n in changed if n.startswith("src/")):
        expected = (root / "source" / name).read_text()
        for before, after in replacements[name]:
            assert expected.count(before) == 1, (name, before)
            expected = expected.replace(before, after)
        assert (ROOT / name).read_text() == expected, name
    for name, sha in rule["additional_source_sha256"].items():
        assert refinement.digest(ROOT / name) == sha, name
    reference = json.loads(
        (Path(rule["prior_binding"]["root"]) / "component-protocol.json").read_text()
    )
    assert rule["tolerances"] == reference["tolerances"]
    return dict(
        status="passed",
        prerequisites=reports,
        changed_prior_files=changed,
        unchanged_prior_files=len(registration["sources_sha256"]) - len(changed),
        unchanged_production_files=len(old) - sum(n.startswith("src/") for n in changed),
        new_production_files=rule["new_production_files"],
        unchanged_additional_sources=len(rule["additional_source_sha256"]),
        production_comparison_scope=(
            "Dynamic horizon and scope extend from 256 to 512 us; shared parsing "
            "accepts a model-specific bound with the static default still 256 us"
        ),
    )


def capture_folder(case, index):
    return Path(protocol()["prior_binding"]["root"]) / (
        f"evidence/cpu/long-junction-native/{case}/step-{index}/observed"
    )


def native_protocol():
    """Keep the completed native fixture's physical inputs and checks unchanged."""
    rule = protocol()
    old = json.loads((Path(rule["prior_binding"]["root"]) / "component-protocol.json").read_text())
    names = (
        "species",
        "base_concentration_mM",
        "concentration_gradient_mM",
        "outside_mM",
        "gj_surface_fraction",
        "initial_voltage_extent_V",
        "native_update_tolerances",
        "tolerances",
        "temperature_K",
        "initial_gate",
        "pump_parameters",
        "cases",
        "junction",
    )
    return {name: old[name] for name in names} | dict(
        kind="betse_spatial_dynamic_junction_runtime_native@1",
        duration_s=rule["duration_s"],
        native_steps_s=rule["native_steps_s"],
        resources=rule["resources"],
        scope="Fresh native targets for ordinary runtime correspondence through 512 us",
        automatic_followup=False,
    )


def authenticate_capture(path, rule):
    """Verify the standard native receipt without retaining all trace arrays."""
    path = Path(path)
    assert not (path / "failure.json").exists()
    receipt = json.loads((path / "completion.json").read_text())
    assert receipt["status"] == "native_spatial_contact_recorded"
    assert receipt["panel_sha256"] == refinement.digest(path / "panel.json")
    panel = json.loads((path / "panel.json").read_text())
    assert panel["protocol"] == rule
    expected = {
        f"{case['id']}/step-{i}/{mode}"
        for case in rule["cases"]
        for i in range(len(rule["native_steps_s"]))
        for mode in ("observed", "bare")
    }
    assert {r["path"] for r in panel["rows"]} == expected
    assert len(panel["rows"]) == len(expected)
    rows = {}
    for item in panel["rows"]:
        directory = path / item["path"]
        assert refinement.digest(directory / "result.json") == item["sha256"]
        row = json.loads((directory / "result.json").read_text())
        assert row["mode"] == item["path"].rsplit("/", 1)[1]
        assert refinement.digest(directory / "preparation.json") == row["preparation_sha256"]
        assert row["hook_restored"] and row["native_pickle_present"]
        assert row["steps"] == round(rule["duration_s"] / row["dt_s"])
        if row["mode"] == "observed":
            assert refinement.digest(directory / "trace.npz") == row["trace_sha256"]
        rows[item["path"]] = row
    for case in rule["cases"]:
        for i, dt in enumerate(rule["native_steps_s"]):
            observed, bare = (
                rows[f"{case['id']}/step-{i}/{mode}"] for mode in ("observed", "bare")
            )
            assert observed["case"] == case and observed["dt_s"] == dt
            for name in (
                "case",
                "dt_s",
                "steps",
                "fixture",
                "geometry",
                "parameters",
                "arrays",
                "species",
                "final",
            ):
                assert observed[name] == bare[name], (case["id"], i, name)
    return rows


def definition(case="block_release", index=0, *, backend="cpu", steps=None):
    rule = protocol()
    if case not in rule["cases"] or index not in rule["step_indices"]:
        raise ValueError("Unknown qualified junction case")
    root = Path(rule["prior_binding"]["root"])
    old = json.loads((root / "component-protocol.json").read_text())
    folder = capture_folder(case, index)
    row = json.loads((folder / "result.json").read_text())
    with np.load(folder / "trace.npz", allow_pickle=False) as trace:
        state, p = junctions.prepare(row, trace, old)
    a = p.active
    # Keep the public example and all existing short experiments unchanged.
    count = round(rule["default_duration_s"] / row["dt_s"]) if steps is None else steps
    if not 0 < count <= round(rule["duration_s"] / row["dt_s"]):
        raise ValueError("Runtime export must stay within the registered horizon")
    dt = row["dt_s"]
    values = state.active.tissue._asdict() | state.active._asdict()
    patches = a.tissue.membrane_area.size
    changes = [
        dict(
            time=round(c["time_s"] / dt) * dt,
            pump=[1.0] * patches,
            channel=[1.0] * patches,
            junction=[c["fraction"]] * patches,
        )
        for c in row["case"]["junction_changes"]
        if round(c["time_s"] / dt) <= count
    ]
    species = rule["native_species_inventory"]
    assert all(species[i] == name for name, i in row["species"].items())
    return dict(
        schema_version=1,
        model=dict(
            id=MODEL_ID,
            species=species,
            tissue={k: v.tolist() for k, v in a.tissue._asdict().items()},
            pump={k: v.tolist() for k, v in a.pump._asdict().items()},
            **{k: getattr(a, k).tolist() for k in active.Layout._fields[2:]},
            junction={k: v.tolist() for k, v in p.junction._asdict().items()},
            junction_block=p.junction_block.tolist(),
            moving_order=p.moving_order.tolist(),
            initial={k: values[k].tolist() for k in INITIAL_FIELDS}
            | dict(junction_open=state.junction_open.tolist()),
        ),
        experiment=dict(
            end_time=count * dt,
            observation_times=[i * dt for i in range(count + 1)],
            changes=changes,
        ),
        execution=dict(
            dt=dt,
            capacity=a.tissue.cell_volume.size,
            membrane_capacity=patches,
            edge_capacity=patches,
            extracellular_capacity=a.tissue.boundary_values.size,
            jit=True,
            backend=backend,
            precision="float64",
            solver=SOLVER_ID,
            max_steps=4096,
            max_trace_bytes=(
                rule["resources"]["long_trace_max_bytes"] if count > row["steps"] else 1024**3
            ),
            material_balance_atol_fmol={k: 2e-11 for k in species},
        ),
    )


def compare_native(actual, row, trace):
    """Compare ordinary state/fields directly with frozen native captures.

    The existing independent ledger reconstruction and inventory-scaled
    roundoff allowance are unchanged. Native evolving values are targets only.
    Rates and per-ion intermediates remain covered by the completed component.
    """
    # The ledger oracle revisits fields per native step. Materialize an NPZ
    # once instead of decompressing the same field on every access.
    trace = dict(trace)
    series, tol = long.native_series(row, trace), protocol()["tolerances"]
    concentration = dict(
        cell_concentration="cc_cells",
        membrane_concentration="cc_at_mem",
        outside_concentration="cc_env",
    )
    states = {
        k.removeprefix("state__"): np.asarray(v)
        for k, v in actual.items()
        if k.startswith("state__")
    }
    rounding = material_roundoff(row, trace, states, tol["material_roundoff_ops_per_step"])
    count, fields = 0, {}
    for key, values in actual.items():
        section, name = key.split("__", 1)
        if name == "step_count":
            expected = np.arange(1, row["steps"] + 1)
            np.testing.assert_array_equal(values, expected)
            fields[key] = dict(max_absolute_error=0, max_error_over_budget=0)
            count += values.size
            continue
        if name == "elapsed_s":
            expected = np.arange(1, row["steps"] + 1) * row["dt_s"]
            atol, rtol = tol["clock_atol_s"], 0
        elif name in concentration:
            expected = series["observed"][concentration[name]]
            atol, rtol = tol["concentration_atol_mM"], tol["concentration_rtol"]
        elif key == "junction__open":
            expected = series["junction_open"]
            atol, rtol = tol["gate_atol"], tol["gate_rtol"]
        else:
            expected = series[
                {"state": "states", "active": "active", "observed": "observed"}[section]
            ][name]
            atol, rtol = refinement.tolerance(name, tol)
        assert values.shape == expected.shape, key
        assert np.isfinite(values).all() and np.isfinite(expected).all(), key
        budget = atol + rtol * abs(expected) + (rounding.get(name, 0) if section == "state" else 0)
        difference = abs(values - expected)
        np.testing.assert_allclose(difference / budget, 0, atol=1, rtol=0, err_msg=key)
        fields[key] = dict(
            max_absolute_error=float(np.max(difference)),
            max_error_over_budget=float(np.max(difference / budget)),
        )
        count += values.size
    return dict(
        status="passed",
        compared_scalars=count,
        fields=fields,
        max_error_over_budget=max(v["max_error_over_budget"] for v in fields.values()),
        scope="All 14 ordinary state arrays and 7 derived fields; native targets only",
    )
