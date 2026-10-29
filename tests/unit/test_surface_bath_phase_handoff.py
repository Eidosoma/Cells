"""Complete bath history carry, explicit initial operation and refusal boundaries."""

from copy import deepcopy
from functools import lru_cache

import numpy as np
import pytest

from cells.core import surface_bath_phase_handoff as bridge
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError, digest
from validation.topology import surface_bath_phase_fixtures as fixtures
from validation.topology import surface_bath_phase_handoff_reference as reference


@lru_cache
def setup(family, case="changed"):
    ordinary, schema, model, count = fixtures.OWNERS[family]
    prepared = fixtures.prepared(family, case)
    spec = schema.parse(prepared.definition)
    state, layout = model.initial_values(spec)
    return ordinary, schema, model, count, prepared, spec, state, layout


def seal_source(source):
    source["identity"] = digest({key: value for key, value in source.items() if key != "identity"})


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", fixtures.CASES)
def test_exact_complete_history_carry_then_separate_sim_controller_operation(family, case):
    ordinary, _, model, count, prepared, spec, state, p = setup(family, case)
    source, checkpoint = fixtures.source_checkpoint(family)
    assert len(state) == count
    assert type(state) is model.STATE_TYPE
    assert type(p) is model.LAYOUT_TYPE
    assert checkpoint.time > 0
    assert np.any(checkpoint.state.reservoir_chemical_work_pJ != 0)
    for key in state._fields:
        expected = np.zeros(1) if key == "phase_clock_s" else getattr(checkpoint.state, key)
        np.testing.assert_array_equal(getattr(state, key), expected, err_msg=key)
    for a, b in zip(model.parent_layout(checkpoint.layout), model.parent_layout(p), strict=True):
        np.testing.assert_array_equal(a, b)
    before = model.scheduled.physical_state(checkpoint.state, checkpoint.layout, xp=np)
    after = model.physical_state(state, p, xp=np)
    operation = model.handoff_record(spec)["controller_operation"]
    np.testing.assert_array_equal(
        after.extracellular_amount_increment,
        before.extracellular_amount_increment + operation["dose_fmol"],
    )
    np.testing.assert_array_equal(
        after.reservoir_supplied, before.reservoir_supplied + operation["dose_fmol"]
    )
    np.testing.assert_array_equal(
        after.electrode_charge_transferred_C,
        before.electrode_charge_transferred_C + operation["electrode_charge_C"],
    )
    for name in ("reservoir_work_pJ", "electrode_work_pJ"):
        expected = operation["electrochemical_work_pJ" if name == "reservoir_work_pJ" else name]
        np.testing.assert_array_equal(getattr(after, name), getattr(before, name) + expected)
    if case == "empty":
        np.testing.assert_array_equal(operation["dose_fmol"], 0)
    else:
        assert np.any(np.asarray(operation["dose_fmol"]) != 0)
    if case == "retarget":
        shared = next(i for i, row in enumerate(spec.model.extracellular) if row.id == "shared")
        np.testing.assert_array_equal(np.asarray(operation["dose_fmol"])[:, shared], 0)
    model.check_values(state, spec)
    preservation = prepared.provenance["preservation"]
    assert "reservoir_chemical_work_pJ" in preservation["carried_fields"]
    assert preservation["controller_operation_identity"] == operation["identity"]
    assert (
        ordinary.owner_spec(source).model
        == ordinary.owner_spec(model.schema.scheduled_spec(spec)).model
    )
    if family == "active":
        assert len({v.kinetic_law for v in spec.model.channels}) == 56
        assert np.any(
            state.channel_gate
            != fixtures.OWNERS[family][2].scheduled.initial_values(source)[0].channel_gate
        )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("changed", "empty"))
def test_sealed_epoch_replay_and_preparation_storage(tmp_path, family, case):
    _, schema, _, _, prepared, spec, _, _ = setup(family, case)
    assert schema.to_dict(spec) == prepared.definition
    replayed = bridge.replay(prepared.provenance)
    assert replayed == prepared
    output = tmp_path / "bath-epoch"
    bridge.write_preparation(output, prepared)
    assert bridge.read_preparation(output) == prepared
    with pytest.raises(ConfigError, match="exists"):
        bridge.write_preparation(output, prepared)
    context, independent = reference.verify_epoch(prepared.definition)
    assert context["source_time_s"] > 0
    assert independent[-1] == 0


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault",
    (
        "dtype",
        "shape",
        "integer_value",
        "bool_value",
        "padding",
        "missing_chemical_work",
        "chemical_work",
        "layout_anchor",
        "clock",
        "event_index",
        "SIM_source",
    ),
)
def test_rehashed_source_cannot_drop_work_padding_original_anchors_or_clock(family, fault):
    request = fixtures.request(family)
    source = request["source"]
    point = source["checkpoint"]
    if fault == "dtype":
        point["state"]["amount_increment"]["dtype"] = "<f4"
    elif fault == "shape":
        point["state"]["amount_increment"]["shape"][-1] += 1
    elif fault in ("integer_value", "bool_value"):
        point["state"]["amount_increment"]["values"][0][0] = (
            0 if fault == "integer_value" else False
        )
    elif fault == "padding":
        point["state"]["amount_increment"]["values"][0][-1] = 1e-4
    elif fault == "missing_chemical_work":
        point["state"].pop("reservoir_chemical_work_pJ")
    elif fault == "chemical_work":
        point["state"]["reservoir_chemical_work_pJ"]["values"][0] += 1e-4
    elif fault == "layout_anchor":
        point["layout"]["initial_outside_charge_C"]["values"][0] += 1e-13
    elif fault == "clock":
        point["state"]["phase_clock_s"]["values"][0] += 1e-9
    elif fault == "event_index":
        point["event_index"] += 1
    else:
        source["definition"]["model"]["phase"] = "SIM"
    seal_source(source)
    with pytest.raises((ConfigError, NumericalError)):
        bridge.prepare(request)
    with pytest.raises(ValueError):
        reference.initial(request)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault",
    (
        "volume",
        "amount",
        "fixed_background",
        "charge_anchor",
        "boundary_voltage",
        "reservoir_owner",
    ),
)
def test_sim_cannot_rebase_or_replace_a_physical_owner(family, fault):
    request = fixtures.request(family)
    m = request["simulation"]["model"]
    row = m["extracellular"][0]
    if fault == "volume":
        row["volume_pL"] *= 1.1
    elif fault == "amount":
        row["initial_amount_fmol"]["Na"] += 0.01
        row["fixed_charge_equivalent_fmol"] -= 0.01
    elif fault == "fixed_background":
        row["fixed_charge_equivalent_fmol"] += 0.01
    elif fault == "charge_anchor":
        row["initial_charge_C"] += 1e-13
    elif fault == "boundary_voltage":
        row["boundary_potential_V"] += 0.001
    else:
        row["reservoir"] = False
        row["boundary_potential_V"] = 0.0
    with pytest.raises((ConfigError, NumericalError)):
        bridge.prepare(request)
    with pytest.raises(ValueError):
        reference.initial(request)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "capacity",
    ("capacity", "extracellular_capacity", "membrane_capacity", "edge_capacity", "face_capacity"),
)
def test_no_physical_capacity_remap_at_epoch_boundary(family, capacity):
    request = fixtures.request(family)
    request["simulation"]["execution"][capacity] += 1
    with pytest.raises(ConfigError, match="capacit"):
        bridge.prepare(request)
    with pytest.raises(ValueError, match="capacit"):
        reference.initial(request)


def test_complete_ionic_channel_slots_cannot_be_remapped():
    request = fixtures.request("active")
    request["simulation"]["execution"]["channel_capacity"] += 1
    with pytest.raises(ConfigError, match="capacit"):
        bridge.prepare(request)
    with pytest.raises(ValueError, match="capacit"):
        reference.initial(request)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_evolved_histories_cannot_be_relabelled_as_an_initial_checkpoint(family):
    request = fixtures.request(family)
    point = request["source"]["checkpoint"]
    point.update(time=0.0, step_index=0, event_index=0)
    point["state"]["phase_clock_s"]["values"] = [0.0]
    seal_source(request["source"])
    with pytest.raises(ConfigError, match="rewrites"):
        bridge.prepare(request)
    with pytest.raises(ValueError, match="rewrites"):
        reference.initial(request)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault",
    (
        "dose_fmol",
        "charge_C",
        "chemical_work_pJ",
        "electrochemical_work_pJ",
        "electrode_work_pJ",
        "electrode_charge_C",
        "binding",
        "clock",
    ),
)
def test_rehashed_initial_operation_cannot_hide_a_material_charge_or_work_jump(family, fault):
    _, schema, _, _, prepared, _, _, _ = setup(family)
    raw = deepcopy(prepared.definition)
    record = raw["model"]["handoff"]
    op = record["controller_operation"]
    if fault == "dose_fmol":
        op[fault][0][0] += 0.01
    elif fault == "binding":
        op["native_bath_binding_identities"][0] = "0" * 64
    elif fault == "clock":
        record["clocks"]["sim_phase_clock_s"] = 1e-6
    else:
        op[fault][0] += 1e-10 if fault.endswith("_C") else 1e-4
    op["identity"] = digest({k: v for k, v in op.items() if k != "identity"})
    with pytest.raises(ConfigError):
        schema.parse(raw)
    with pytest.raises(ValueError):
        reference.verify_epoch(raw)
