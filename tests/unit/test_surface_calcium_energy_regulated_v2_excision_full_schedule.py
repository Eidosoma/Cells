"""Focused host cut/archive checks for the exact regulated @2 parent.

Independent cut/trajectory reference evidence is owned by the Chief's reference
agent. These tests qualify source validation, physical owner preservation,
ordered rule filtering and complete public archive restoration/refusal.
"""

import hashlib
import json
import os
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core import calcium_energy_regulated_v2_tissue_excision as cut
from cells.core import surface_calcium_energy_regulated_v2_excision_spec as schema
from cells.core import surface_calcium_energy_regulated_v2_spec as parent_schema
from cells.core.errors import NumericalError
from cells.core.excision import excise
from cells.core.grid import EventGrid
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import Checkpoint, initialise
from cells.excision_io import CALCIUM_ENERGY_REGULATED_V2_KIND, load_excision, write_excision
from cells.models import surface_calcium_energy_regulated_v2 as parent
from cells.models import surface_calcium_energy_regulated_v2_excision as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from validation.tissue import calcium_energy_excision_fixtures as inherited_fixtures

ROOT = Path(__file__).resolve().parents[2]


def evidence(name, data):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        (path / ("regulated-v2-excision-" + name + ".json")).write_text(
            json.dumps(
                dict(data, status="passed"),
                indent=2,
                allow_nan=False,
                default=lambda value: value.tolist(),
            )
            + "\n"
        )


def exact(actual, expected):
    assert type(actual) is type(expected)
    for a, b in zip(actual, expected, strict=True):
        np.testing.assert_array_equal(a, b)


def definition(arm="open", *, padded=True):
    """Local boundary fixture; the independent agent owns its separate files."""
    raw = inherited_fixtures.definition(arm, padded=padded)
    m, ion = raw["model"], raw["model"]["ionic"]
    patches = {p["id"]: p for p in ion["membranes"]}
    rules = []
    for patch in ion["membranes"]:
        if patch["pump"] is None:
            continue
        name = "reg_" + patch["pump"]["id"]
        conf = dict(
            name=name,
            target="Na/K-ATPase",
            **{
                "max effect": 0.8,
                "target ion": None,
                "activators": ["ATP"],
                "activator Km": [0.6],
                "activator n": [2.0],
                "inhibitors": ["Ca"],
                "inhibitor Km": [0.003],
                "inhibitor n": [1.0],
            },
        )
        rules.append(
            dict(
                id=name,
                kind="nak",
                target_id=patch["pump"]["id"],
                sample_cell_id=patch["inside"],
                sample_exterior_id=patch["outside"],
                fuel_pool_id="fuel_" + patch["inside"],
                configuration=conf,
            )
        )
    for channel in ion["channels"]:
        if "kv1p5" not in channel["kinetic_law"]:
            continue
        patch = patches[channel["membrane_id"]]
        name = "reg_" + channel["id"]
        conf = dict(
            name=name,
            **{
                "channel class": "K",
                "channel type": "Kv1p5",
                "max Dm": 0.0,
                "max conductivity": None,
                "apply to": "all",
                "init active": True,
                "channel activators": ["ATP"],
                "activator Km": [0.6],
                "activator n": [1.0],
                "channel inhibitors": ["Ca"],
                "inhibitor Km": [0.003],
                "inhibitor n": [1.0],
                "inhibitor max": [0.1],
            },
        )
        rules.append(
            dict(
                id=name,
                kind="channel",
                target_id=channel["id"],
                sample_cell_id=patch["inside"],
                sample_exterior_id=patch["outside"],
                fuel_pool_id="fuel_" + patch["inside"],
                configuration=conf,
            )
        )
    for edge in ion["junctions"]:
        for endpoint in (edge["sender"], edge["receiver"]):
            name = "reg_" + edge["id"] + "_" + endpoint
            conf = dict(
                name=name,
                target="GJ",
                **{
                    "max effect": 0.7,
                    "target ion": None,
                    "activators": ["Pi"],
                    "activator Km": [0.1],
                    "activator n": [1.0],
                    "inhibitors": ["Ca"],
                    "inhibitor Km": [0.003],
                    "inhibitor n": [1.0],
                },
            )
            rules.append(
                dict(
                    id=name,
                    kind="junction",
                    target_id=edge["id"],
                    sample_cell_id=endpoint,
                    sample_exterior_id=None,
                    fuel_pool_id="fuel_" + endpoint,
                    configuration=conf,
                )
            )
    # Surviving shadowed rules remain archived and bounded even if they do not
    # supply the last write at a physical target.
    for target in ("pump_membrane_0_bath", "pump_membrane_1_bath"):
        original = next(r for r in rules if r["target_id"] == target)
        row = deepcopy(original)
        row["id"] = "last_" + target
        row["configuration"] = dict(
            name=row["id"], target="Na/K-ATPase", **{"max effect": 0.23, "target ion": None}
        )
        rules.append(row)
    if arm == "reordered":
        rules.reverse()
    m.update(
        id=parent_schema.MODEL_ID,
        network_regulation=dict(
            law="betse_network_modulation_source_v1_5_0@1",
            timing=parent_schema.TIMING,
            control_composition=parent_schema.COMPOSITION,
            channel_scope=parent_schema.CHANNEL_SCOPE,
            junction_scope=parent_schema.JUNCTION_SCOPE,
            rules=rules,
        ),
    )
    raw["execution"]["regulation_capacity"] = len(rules) + int(padded)
    return raw


@lru_cache
def prepared(arm="open", padded=True):
    spec = parse_spec(definition(arm, padded=padded))
    state, p = parent.initial_values(spec)
    times = [0.0, spec.execution.dt, 2 * spec.execution.dt]
    for left, right in zip(times[:-1], times[1:], strict=True):
        table = control_values(spec, [left])
        u = type(table)(*(v[0] for v in table))

        def rhs(y, u, p, a):
            assert parent.control_domain_valid(y, u, p, a, xp=np)
            return parent.rhs(y, u, p, a, xp=np)

        state = rk4_step(rhs, state, right - left, u, p, p.active)
    parent.check_values(state, spec)
    time = times[-1]
    return spec, Checkpoint(
        state, p, time, EventGrid(spec).exact_index(time), event_index(spec, time)
    )


@lru_cache
def normal_cut():
    spec, point = prepared()
    return excise(spec, point, ["cell_1"])


def test_roundtrip_complete_source_and_regulated_physical_readouts():
    spec, point = prepared()
    source = cut.capture_source(spec, point)
    restored, cp = cut.decode_source(source)
    assert restored == spec
    exact(cp.state, point.state)
    exact(cp.layout, point.layout)
    assert len(cp.state) == 38 and set(source["checkpoint"]["state"]) == set(parent.STATE_AXES)
    table = control_values(spec, [point.time])
    u = type(table)(*(v[0] for v in table))
    actual = parent.readouts(point.state, u, point.layout, xp=np)
    values = cut.physical(spec, point)
    np.testing.assert_array_equal(
        values["voltage"], actual.field.rates.membrane_voltage_V[: len(spec.model.membranes)]
    )
    np.testing.assert_array_equal(
        values["regulation_factors"],
        actual.regulation.rule_factors[: len(spec.model.network_regulators)],
    )
    assert np.any(actual.effective_control.pump != u.pump)
    assert np.any(actual.effective_control.channel != u.channel)
    assert np.any(actual.effective_control.junction != u.junction)
    evidence(
        "complete-source",
        dict(state_fields=list(point.state._fields), source=source, actual_regulated_field=True),
    )


@pytest.mark.parametrize("arm,padded", [("open", True), ("reordered", False)])
def test_evolved_cut_preserves_order_owners_factors_and_all_gates(arm, padded):
    spec, point = prepared(arm, padded)
    original = cut.capture_source(spec, point)
    result = normal_cut() if (arm, padded) == ("open", True) else excise(spec, point, ["cell_1"])
    assert get_model(result.spec.model) is model
    assert result.spec.to_dict()["model"]["id"] == schema.MODEL_ID
    assert result.spec == parse_spec(result.spec.to_dict())
    assert type(result.checkpoint.layout) is parent.LAYOUT_TYPE
    exact(initialise(result.spec).state, result.checkpoint.state)
    assert result.checkpoint.time == point.time == model.initial_time(result.spec)
    before, after = cut.physical(spec, point), cut.physical(result.spec, result.checkpoint)
    kept = [i for i, c in enumerate(spec.model.cells) if c.id != "cell_1"]
    np.testing.assert_array_equal(after["chemical_amount"], before["chemical_amount"][kept])
    np.testing.assert_array_equal(after["fuel_amount"], before["fuel_amount"][:, kept])
    np.testing.assert_array_equal(after["charge"], before["charge"][kept])
    assert {r.id for r in result.spec.model.network_regulators} == set(
        result.report["retained_regulator_ids"]
    )
    assert "last_pump_membrane_0_bath" in result.report["retained_regulator_ids"]
    assert "reg_pump_membrane_0_bath" in result.report["retained_regulator_ids"]
    assert "last_pump_membrane_1_bath" in result.report["removed_regulator_ids"]
    assert any(
        r.target_id == "junction_0_2" and r.sample_cell_id == "cell_2"
        for r in result.spec.model.network_regulators
    )
    assert not any(r.sample_cell_id == "cell_1" for r in result.spec.model.network_regulators)
    assert all(
        not np.any(getattr(result.checkpoint.state, k))
        for k in model.STATE_AXES
        if k not in cut.GATES
    )
    assert set(result.report["archived_retained_state"]) == set(parent.STATE_AXES)
    assert set(result.report["archived_removed_state"]) == set(parent.STATE_AXES)
    assert {c.time for c in spec.experiment.changes} <= {
        c.time for c in result.spec.experiment.changes
    }
    assert result.report["extra_regulation_ATP_cost_fmol"] == 0.0
    assert cut.capture_source(spec, point) == original
    evidence(
        "cut-" + arm, dict(source=spec.to_dict(), after=result.spec.to_dict(), report=result.report)
    )


def test_postcut_rates_use_retained_native_factors_and_existing_fuel_only():
    result = normal_cut()
    spec, point = result.spec, result.checkpoint
    table = control_values(spec, [point.time])
    u = type(table)(*(v[0] for v in table))
    actual = model.rhs(point.state, u, point.layout, point.layout.active, xp=np)
    expected = parent.rhs(point.state, u, point.layout, point.layout.active, xp=np)
    exact(actual, expected)
    assert not any("regulat" in k for k in model.STATE_AXES)
    original = cut.capture_source(spec, point)
    advanced = rk4_step(
        lambda y, u, p, a: model.rhs(y, u, p, a, xp=np),
        point.state,
        spec.execution.dt,
        u,
        point.layout,
        point.layout.active,
    )
    model.check_values(advanced, spec)
    assert cut.capture_source(spec, point) == original
    evidence(
        "postcut-rates", dict(state_fields=38, inherited_rhs_exact=True, source_immutable=True)
    )


@pytest.mark.parametrize("field", ["step_index", "event_index", "time"])
def test_invalid_absolute_source_clock_refuses(field):
    spec, point = prepared()
    value = getattr(point, field) + (1 if field != "time" else 0.13 * spec.execution.dt)
    invalid = replace(point, **{field: value})
    with pytest.raises(ConfigError):
        excise(spec, invalid, ["cell_1"])
    evidence("source-clock-" + field, dict(refused=True))


def test_empty_rule_set_remains_empty_after_cut():
    raw = definition()
    raw["model"]["network_regulation"]["rules"] = []
    spec = parse_spec(raw)
    result = excise(spec, initialise(spec), ["cell_1"])
    assert not result.spec.model.network_regulators
    assert result.report["removed_regulator_ids"] == []
    assert result.report["retained_regulation_factors"] == []
    evidence("no-rules", dict(no_implicit_regulators=True, complete_fields=38))


@pytest.mark.parametrize("selection", [[], ["cell_0", "cell_1", "cell_2"]])
def test_noop_and_terminal_preserve_complete_source(selection):
    spec, point = prepared()
    source = cut.capture_source(spec, point)
    result = excise(spec, point, selection)
    if selection:
        assert result.spec is None and result.checkpoint is None
        assert result.report["removed_regulator_ids"] == [
            r.id for r in spec.model.network_regulators
        ]
    else:
        assert result.spec == spec and result.checkpoint is point
        assert not result.report["removed_regulator_ids"]
    assert cut.capture_source(spec, point) == source
    evidence("terminal" if selection else "noop", dict(report=result.report, source_unchanged=True))


def test_complete_public_archive_roundtrip_and_nonoverwrite(tmp_path):
    result = normal_cut()
    path = write_excision(tmp_path / "cut", result)
    loaded = load_excision(path)
    assert loaded.spec == result.spec and loaded.report == result.report
    exact(loaded.source_checkpoint.state, result.source_checkpoint.state)
    exact(loaded.source_checkpoint.layout, result.source_checkpoint.layout)
    exact(loaded.checkpoint.state, result.checkpoint.state)
    exact(loaded.checkpoint.layout, result.checkpoint.layout)
    assert (
        json.loads((path / "manifest.json").read_text())["kind"] == CALCIUM_ENERGY_REGULATED_V2_KIND
    )
    with pytest.raises(FileExistsError):
        write_excision(path, result)
    evidence(
        "archive",
        dict(family=CALCIUM_ENERGY_REGULATED_V2_KIND, complete_fields=38, exact_restore=True),
    )


@pytest.mark.parametrize(
    "fault",
    [
        "rule-order",
        "drop-shadowed",
        "rule-parameter",
        "endpoint-owner",
        "fuel-owner",
        "source-factor-layout",
        "missing-history",
        "past-control",
        "fuel-amount",
        "gate",
        "dt",
        "wrong-parent",
    ],
)
def test_definition_tampering_refuses_without_repair(fault):
    raw = deepcopy(normal_cut().spec.to_dict())
    m, record = raw["model"]["tissue"], raw["model"]["excision"]
    rules = m["network_regulation"]["rules"]
    if fault == "rule-order":
        rules.reverse()
    if fault == "drop-shadowed":
        rules[:] = [r for r in rules if r["id"] != "reg_pump_membrane_0_bath"]
    if fault == "rule-parameter":
        rules[0]["configuration"]["max effect"] = 0.5
    if fault == "endpoint-owner":
        row = next(r for r in rules if r["kind"] == "junction")
        row["sample_cell_id"] = "cell_2" if row["sample_cell_id"] == "cell_0" else "cell_0"
        row["fuel_pool_id"] = "fuel_" + row["sample_cell_id"]
    if fault == "fuel-owner":
        rules[0]["fuel_pool_id"] = "fuel_cell_2"
    if fault == "source-factor-layout":
        record["source"]["checkpoint"]["layout"]["regulation_max_effect"][0][0] += 0.1
    if fault == "missing-history":
        del record["source"]["checkpoint"]["state"]["regeneration_supplied_work_pJ"]
    if fault == "past-control":
        raw["experiment"]["channel_controls"][0]["schedule"][0]["availability"] = 0.0
    if fault == "fuel-amount":
        m["energy_pools"][0]["initial_amount_fmol"]["ATP"] += 1e-6
    if fault == "gate":
        m["ionic"]["channels"][0]["initial_gate"][0] = 0.0
    if fault == "dt":
        raw["execution"]["dt"] /= 2
    if fault == "wrong-parent":
        record["source"]["definition"]["model"]["id"] = "resolved_calcium_energy_regulated@1"
    with pytest.raises((ConfigError, NumericalError)):
        parse_spec(raw)
    evidence("refused-" + fault, dict(fault=fault, input_sha256=digest(raw), refused=True))


def test_archive_checksum_refusal_even_with_resealed_outer_inventory(tmp_path):
    result = normal_cut()
    path = write_excision(tmp_path / "cut", result)
    manifest = json.loads((path / "manifest.json").read_text())
    report_path = path / "transition.json"
    report = json.loads(report_path.read_text())
    report["retained_regulator_ids"].reverse()
    report_path.write_text(json.dumps(report) + "\n")
    with pytest.raises(ConfigError, match="checksum"):
        load_excision(path)
    manifest["files"]["transition.json"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
    (path / "manifest.json").write_text(json.dumps(manifest) + "\n")
    with pytest.raises(ConfigError, match="manifest/transition"):
        load_excision(path)
    evidence("archive-refusals", dict(checksum_and_recomputed_physical_source_refuse=True))


def test_sequential_cut_keeps_nested_regulation_history_and_absolute_time():
    first = normal_cut()
    # Removing the remaining owners yields a terminal event and still retains
    # the exact first epoch source, its regulators and all pre-cut ledgers.
    terminal = excise(first.spec, first.checkpoint, ["cell_0", "cell_2"])
    assert terminal.spec is None and terminal.report["terminal"]
    source = cut.capture_source(first.spec, first.checkpoint)
    restored, point = cut.decode_source(source)
    assert restored == first.spec
    exact(point.state, first.checkpoint.state)
    assert point.time == first.source_checkpoint.time
    assert (
        source["definition"]["model"]["excision"]["source"]["definition"]["model"]["id"]
        == parent_schema.MODEL_ID
    )
    evidence(
        "sequential",
        dict(terminal=terminal.report, nested_source_restores=True, absolute_time=point.time),
    )


# The original 150-us schedule/archive family above is preserved from host03.
# These additional panels consume frozen independent accepted checkpoints,
# rather than recomputing its already-qualified 50/150-us trajectories.
REFERENCE = Path("/mnt/workspaces/Cells/calcium-energy-regulated-v2-excision-reference-20261029-01")
REFERENCE_SHA = "b81a4882743abf33e9ba1d91bdb3cf7a1eb9030169ba9de8f9b62e3457ddfb28"


def reference_record():
    handoff = REFERENCE / "HANDOFF.json"
    assert hashlib.sha256(handoff.read_bytes()).hexdigest() == REFERENCE_SHA
    receipt = json.loads(handoff.read_text())
    relative = "trajectory-01/evidence/complete-regulated-cut-continuation.json"
    path = REFERENCE / relative
    assert hashlib.sha256(path.read_bytes()).hexdigest() == receipt["artifact_sha256"][relative]
    return json.loads(path.read_text()), receipt


def checkpoint_from_reference(spec, values, time):
    implementation = get_model(spec.model)
    state, layout = implementation.initial_values(spec)
    assert set(values) == set(state._fields)
    for key, value in values.items():
        array = np.asarray(value, dtype=np.float64)
        getattr(state, key)[tuple(slice(0, n) for n in array.shape)] = array
    implementation.check_values(state, spec)
    point = Checkpoint(
        state, layout, time, EventGrid(spec).exact_index(time), event_index(spec, time)
    )
    cut._point_check(spec, point)
    return point


@lru_cache
def late_cut():
    record, _ = reference_record()
    source = record["archive"]
    spec = parse_spec(source["definition"])
    point = checkpoint_from_reference(spec, source["checkpoint"]["state"], record["cut_time_s"])
    result = excise(spec, point, ["cell_1"])
    return result


def test_full_schedule_50us_cut_matches_independent_transition_and_complete_archive(tmp_path):
    from validation.tissue import calcium_energy_regulated_v2_excision_reference as reference

    result = late_cut()
    source = result.source_checkpoint
    original = reference.bind(result.source_spec.to_dict())
    expected = reference.excise(
        result.source_spec.to_dict(),
        reference.flatten(original, source.state._asdict()),
        ["cell_1"],
        source.time,
    )
    context = reference.bind(result.spec.to_dict())
    actual = reference.flatten(context, result.checkpoint.state._asdict())
    np.testing.assert_array_equal(actual, expected["state"])
    assert result.report["retained_regulator_ids"] == expected["audit"]["retained_regulator_ids"]
    assert result.report["removed_regulator_ids"] == expected["audit"]["removed_regulator_ids"]
    assert result.source_spec.experiment.end_time > 149e-6
    assert source.time == 50e-6
    assert {c.time for c in result.source_spec.experiment.changes} <= {
        c.time for c in result.spec.experiment.changes
    }
    path = write_excision(tmp_path / "late-50us", result)
    restored = load_excision(path)
    exact(restored.source_checkpoint.state, source.state)
    exact(restored.checkpoint.state, result.checkpoint.state)
    evidence(
        "full-schedule-50us",
        dict(
            reference_receipt=str(REFERENCE / "HANDOFF.json"),
            sha256=REFERENCE_SHA,
            checkpoint_source="Frozen independent accepted prefix; no prefix recomputation",
            source_clock=result.report["source_clock"],
            report=result.report,
            complete_archive=True,
        ),
    )


def test_full_schedule_150us_checkpoint_and_past_history_archive(tmp_path):
    from validation.tissue import calcium_energy_regulated_v2_excision_reference as reference

    record, receipt = reference_record()
    result = late_cut()
    context = reference.bind(record["after_definition"])
    relative = "trajectory-01/evidence/suffix-refinement-1.npz"
    path = REFERENCE / relative
    assert hashlib.sha256(path.read_bytes()).hexdigest() == receipt["artifact_sha256"][relative]
    with np.load(path, allow_pickle=False) as data:
        flat = data["state"][-1]
    relative_time = "trajectory-01/evidence/suffix-refinement-1.json"
    timing_file = REFERENCE / relative_time
    assert (
        hashlib.sha256(timing_file.read_bytes()).hexdigest()
        == receipt["artifact_sha256"][relative_time]
    )
    time = float(json.loads(timing_file.read_text())["times"][-1])
    point = checkpoint_from_reference(result.spec, reference.unpack(context, flat), time)
    assert time > 149e-6 and point.time == result.spec.experiment.end_time
    table = control_values(result.spec, [time])
    u = type(table)(*(v[0] for v in table))
    actual = model.rhs(point.state, u, point.layout, point.layout.active, xp=np)
    production_context = reference.bind(result.spec.to_dict())
    current = reference.flatten(production_context, point.state._asdict())
    expected, _, _ = reference.evaluate(production_context, current, time)
    budget = reference.flatten(
        production_context,
        {
            k: np.full(s, 3e-23 if k.endswith("_C") else 3e-12)
            for k, s in production_context["shapes"].items()
        },
    ) + 3e-10 * np.abs(expected)
    ratio = float(
        np.max(
            np.abs(reference.flatten(production_context, actual._asdict()) - expected) / budget,
            initial=0,
        )
    )
    assert ratio <= 1
    noop = excise(result.spec, point, [])
    archive = write_excision(tmp_path / "end-150us", noop)
    restored = load_excision(archive)
    exact(restored.source_checkpoint.state, point.state)
    assert restored.source_checkpoint.time == point.time
    assert not restored.report["changed"]
    evidence(
        "full-schedule-150us",
        dict(
            reference_receipt=str(REFERENCE / "HANDOFF.json"),
            sha256=REFERENCE_SHA,
            checkpoint_source="Frozen independent accepted suffix; no suffix recomputation",
            absolute_time_s=time,
            stage_max_error_over_budget=ratio,
            all_38_fields=True,
            complete_nested_archive=True,
        ),
    )
