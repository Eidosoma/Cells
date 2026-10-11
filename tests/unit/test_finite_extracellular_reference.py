"""Finite outside specification/reference tests, not production or trajectories."""

import ast
import copy
import math
import subprocess
import sys
from dataclasses import FrozenInstanceError, asdict, fields, replace
from decimal import localcontext

import pytest

from scripts import check_finite_extracellular as check
from tests import reference_finite_extracellular as ref
from tests import reference_multispecies as ion
from tests import reference_physical_ionic_graph as graph


@pytest.fixture
def panel():
    return ion.load_json(check.PROTOCOL)


@pytest.fixture
def definition(panel):
    return check.definition(next(c for c in panel["cases"] if c["id"] == "star_divalent"))


@pytest.fixture
def world(definition):
    return ref.resolve(definition)


def test_frozen_panel_and_bounded_scope():
    result = check.verify()
    assert result["status"] == "pass", result["failures"]
    assert result["checks_failed"] == 0
    assert result["groups"]["blocked_gates_keep_relaxing"]["checks"] == 60
    assert result["groups"]["blocked_outside_exact_zero"]["checks"] == 69
    assert len(result["assemblies"]) == 9
    assert len(result["production_source_sha256"]) == 46
    assert result["production_version"] == "0.13.0"
    assert result["production_change"] is result["independent_ode_solver_run"] is False
    assert (
        result["coupled_trajectory_qualification"] == result["method_selection"] == "not_performed"
    )
    assert result["biological_acceptance"] == "not_assessable"


@pytest.mark.parametrize("case", range(9))
def test_immutable_resolution_and_evaluation_without_input_mutation(panel, case):
    raw = check.definition(panel["cases"][case])
    saved = copy.deepcopy(raw)
    w = ref.resolve(raw)
    state = ref.initial_state(w)
    before = asdict(state)
    ref.evaluate(w, state)
    assert raw == saved and asdict(state) == before
    with pytest.raises(FrozenInstanceError):
        w.extracellular = w.cells[0]


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema",), graph.SCHEMA),
        (("bath",), {}),
        (("species",), []),
        (("species", 0, "valence"), True),
        (("temperature_K",), 310.0),
        (("extracellular", "id"), "cell_0"),
        (("extracellular", "volume_pL"), 0),
        (("extracellular", "volume_pL"), -1),
        (("extracellular", "volume_pL"), math.inf),
        (("extracellular", "volume_pL"), True),
        (("extracellular", "volume_pL"), 1e-320),
        (("extracellular", "initial_amount_fmol", "Na"), 0),
        (("extracellular", "initial_amount_fmol", "Ca"), -1),
        (("extracellular", "initial_amount_fmol", "Ca"), "2"),
        (("extracellular", "initial_amount_fmol", "Ca"), math.nan),
        (("extracellular", "initial_amount_fmol", "unused"), 2),
        (("extracellular", "fixed_charge_equivalent_fmol"), 0),
        (("extracellular", "fixed_charge_equivalent_fmol"), -2),
        (("extracellular", "initial_voltage_V"), 0),
        (("cells",), []),
        (("cells", 0, "cell", "initial_voltage_V"), 0),
        (("cells", 0, "cell", "fixed_charge_equivalent_fmol"), 0),
        (("cells", 0, "membrane", "outside"), "unknown"),
        (("cells", 0, "membrane", "inside"), "cell_1"),
        (("cells", 0, "membrane", "area_m2"), 1e308),
        (("cells", 0, "membrane", "passive", "law"), "unknown@1"),
        (("cells", 0, "membrane", "pump", "roles", "sodium"), "Cl"),
        (("cells", 0, "membrane", "pump", "stoichiometry", "Na"), -2),
        (("cells", 0, "membrane", "pump", "stoichiometry", "Na"), -3.0),
        (("cells", 0, "channel", "species_id"), "Ca"),
        (("cells", 0, "channel", "membrane_id"), "membrane_1"),
        (("cells", 0, "channel", "initial_gate", "m"), 1.01),
        (("junctions",), None),
        (("junctions", 0, "from_cell"), "bath_shared"),
        (("junctions", 0, "from_cell"), "cell_2"),
        (("junctions", 0, "id"), "pump_0"),
        (("junctions", 0, "gate", "tau_s"), 0),
    ],
)
def test_strict_bindings_domains_and_no_charge_repair(definition, path, value):
    node = definition
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ValueError):
        ref.resolve(definition)


@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_junction_refusal(definition, reverse):
    edge = copy.deepcopy(definition["junctions"][0])
    edge["id"] = "duplicate"
    if reverse:
        edge["from_cell"], edge["to_cell"] = edge["to_cell"], edge["from_cell"]
    definition["junctions"].append(edge)
    with pytest.raises(ValueError, match="Duplicate physical edge"):
        ref.resolve(definition)


@pytest.mark.parametrize("field", [f.name for f in fields(ref.State)])
def test_every_state_field_has_independent_shape_and_full_state_requirement(world, field):
    with pytest.raises(ValueError):
        ref.evaluate(world, replace(ref.initial_state(world), **{field: ()}))


@pytest.mark.parametrize("value", [0, -1, True, math.inf, math.nan])
def test_blocking_does_not_hide_invalid_outside_amount(world, value):
    state = ref.initial_state(world)
    outside = list(state.extracellular_amount)
    outside[0] = value
    off = graph.Control(
        ((0.0,) * len(world.species_ids),) * len(world.cells),
        (0.0,) * len(world.cells),
        (0.0,) * len(world.channels),
        (0.0,) * len(world.junctions),
    )
    with pytest.raises(ValueError):
        ref.evaluate(world, replace(state, extracellular_amount=tuple(outside)), off)


@pytest.mark.parametrize("field", ["pump_cycles", "channel_transferred", "junction_gate"])
def test_nonfinite_complete_hidden_state_is_not_ignored(world, field):
    state = ref.initial_state(world)
    values = list(getattr(state, field))
    values[0] = math.nan
    with pytest.raises(ValueError):
        ref.evaluate(world, replace(state, **{field: tuple(values)}))


@pytest.mark.parametrize("group", ["leak", "pump", "channel", "junction"])
def test_controls_remain_independent_and_strict(world, group):
    control = graph.enabled(world)
    with pytest.raises(ValueError):
        ref.evaluate(world, control=replace(control, **{group: ()}))


def test_countercharge_is_not_a_second_voltage_degree_of_freedom(world):
    state = ref.initial_state(world)
    outside = list(state.extracellular_amount)
    outside[0] += 0.001
    with pytest.raises(ValueError, match="countercharge"):
        ref.evaluate(world, replace(state, extracellular_amount=tuple(outside)))
    assert abs(world.initial_countercharge_C) < ref.CHARGE_TOLERANCE_C
    assert world.extracellular.charge(world.valence, state.extracellular_amount) != 0


def test_charge_balance_does_not_replace_material_history_checks(world):
    state = ref.initial_state(world)
    outside = list(state.extracellular_amount)
    outside[0] += 0.001
    outside[2] += 0.001  # Neutral NaCl corruption passes charge, not material.
    state = replace(state, extracellular_amount=tuple(outside))
    residual = ref.ledger_residuals(world, state)
    assert abs(residual["countercharge_increment_C"]) < ref.CHARGE_TOLERANCE_C
    assert max(abs(x) for x in residual["global_material_fmol"]) > 0.0009


def test_a_shared_finite_outside_couples_cells_without_junctions(world):
    w = replace(world, junctions=())
    state = ref.initial_state(w)
    original = ref.evaluate(w, state)
    inside = [list(row) for row in state.amount]
    outside = list(state.extracellular_amount)
    for s in (0, 2):  # Transfer neutral NaCl from cell 1 to the common outside.
        inside[1][s] -= 0.01
        outside[s] += 0.01
    changed = replace(
        state, amount=tuple(tuple(row) for row in inside), extracellular_amount=tuple(outside)
    )
    result = ref.evaluate(w, changed)
    assert changed.amount[0] == state.amount[0]
    assert result.voltage_V[0] == original.voltage_V[0]
    assert result.membrane_rate_fmol_per_s[0] != original.membrane_rate_fmol_per_s[0]


def test_internal_only_transport_never_changes_outside(world):
    on = graph.enabled(world)
    internal = replace(
        on,
        leak=((0.0,) * len(world.species_ids),) * len(world.cells),
        pump=(0.0,) * len(world.cells),
        channel=(0.0,) * len(world.channels),
    )
    r = ref.evaluate(world, control=internal)
    assert r.rate.extracellular_amount == (0.0,) * len(world.species_ids)
    assert any(x != 0 for row in r.rate.junction_transferred for x in row)
    assert r.stored_energy_rate_W <= 0


def test_no_external_pump_drive_has_nonincreasing_resolved_free_energy(world):
    membranes = tuple(
        replace(m, pump=None if m.pump is None else replace(m.pump, drive_J_per_mol=0.0))
        for m in world.membranes
    )
    r = ref.evaluate(replace(world, membranes=membranes))
    assert r.supplied_power_W == 0
    assert r.stored_energy_rate_W < 0
    assert r.stored_energy_rate_W == pytest.approx(
        -math.fsum((*r.membrane_dissipation_W, *r.junction_dissipation_W)), abs=1e-23
    )


def test_absent_routes_leave_empty_channel_edge_state_and_no_pump_history(definition):
    definition["junctions"] = []
    for cell in definition["cells"]:
        cell["channel"] = None
        cell["membrane"]["pump"] = None
    w = ref.resolve(definition)
    state = ref.initial_state(w)
    result = ref.evaluate(w, state)
    assert result.rate.membrane_gate == result.rate.junction_gate == ()
    assert result.rate.pump_cycles == (0.0, 0.0, 0.0)
    with pytest.raises(ValueError, match="Absent pump"):
        ref.evaluate(w, replace(state, pump_cycles=(1e-5, 0.0, 0.0)))


def test_amounts_cannot_reconstruct_distinct_internal_cycle_history(definition):
    edge = copy.deepcopy(definition["junctions"][0])
    edge.update(id="third_edge", from_cell="cell_0", to_cell="cell_1")
    definition["junctions"].append(edge)
    w = ref.resolve(definition)
    state = ref.initial_state(w)
    # Stored edges 0->2, 1->2, 0->1: circulation coefficients -1,+1,+1.
    history = tuple(tuple(sign * 1e-5 for _ in w.species_ids) for sign in (-1, 1, 1))
    changed = replace(state, junction_transferred=history)
    residual = ref.ledger_residuals(w, changed)
    assert all(x == 0 for row in residual["inside_material_fmol"] for x in row)
    assert residual["outside_material_fmol"] == (0.0,) * len(w.species_ids)
    assert ref.evaluate(w, state) == ref.evaluate(w, changed)


def test_stable_finite_energy_is_zero_at_anchor_and_matches_decimal(world):
    state = ref.initial_state(world)
    assert ref.energy_change_J(world, state) == 0.0
    nonzero = check.manufactured_history(world, 1e-6)
    with localcontext() as context:
        context.prec = 70
        expected = float(check.decimal_energy(world, nonzero) - check.decimal_energy(world, state))
    assert ref.energy_change_J(world, nonzero) == pytest.approx(expected, abs=1e-20, rel=2e-12)


@pytest.mark.parametrize("corruption", ["outside_rate", "stored_energy"])
def test_independent_checks_detect_incorrect_exchange_or_energy(panel, monkeypatch, corruption):
    original = ref.evaluate

    def wrong(*args, **kwargs):
        result = original(*args, **kwargs)
        if corruption == "outside_rate":
            return replace(
                result,
                rate=replace(
                    result.rate, extracellular_amount=(0.0,) * len(result.rate.extracellular_amount)
                ),
            )
        return replace(result, stored_energy_rate_W=result.stored_energy_rate_W + 1e-12)

    monkeypatch.setattr(ref, "evaluate", wrong)
    checks = check.Checks(panel["tolerances"])
    with localcontext() as context:
        context.prec = 70
        check.composition_checks(panel | {"cases": panel["cases"][:1]}, checks)
    assert checks.failures
    group = "closed_species_rate" if corruption == "outside_rate" else "closed_energy_power"
    assert checks.groups[group]["failed"] > 0


def test_strict_json_and_refusal_to_overwrite_prior_evidence(tmp_path):
    path = tmp_path / "receipt.json"
    path.write_text('{"value":1,"value":2}')
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        ion.load_json(path)
    before = path.read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            str(check.ROOT / "scripts/check_finite_extracellular.py"),
            "--output",
            str(path),
        ],
        capture_output=True,
    )
    assert result.returncode != 0 and path.read_bytes() == before


def test_reference_does_not_import_production_arrays_or_time_integrators():
    for name in (
        "tests/reference_finite_extracellular.py",
        "scripts/check_finite_extracellular.py",
    ):
        tree = ast.parse((check.ROOT / name).read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(x.name.split(".")[0] for x in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not imported & {"cells", "jax", "numpy", "scipy"}


@pytest.mark.parametrize("value", [None, {}, "world"])
def test_public_evaluation_requires_resolved_world(value):
    with pytest.raises(ValueError, match="resolved finite world"):
        ref.evaluate(value)
    with pytest.raises(ValueError, match="resolved finite world"):
        ref.initial_state(value)


def test_species_names_are_bindings_not_kinetic_dispatch(definition):
    original = ref.evaluate(ref.resolve(definition))
    names = {s["id"]: f"ion_{i}" for i, s in enumerate(definition["species"])}
    for s in definition["species"]:
        s["id"] = names[s["id"]]

    def rename(mapping):
        return {names[k]: v for k, v in mapping.items()}

    outside = definition["extracellular"]
    outside["initial_amount_fmol"] = rename(outside["initial_amount_fmol"])
    for entry in definition["cells"]:
        cell, membrane = entry["cell"], entry["membrane"]
        cell["initial_amount_fmol"] = rename(cell["initial_amount_fmol"])
        passive = membrane["passive"]
        passive["permeability_m_per_s"] = rename(passive["permeability_m_per_s"])
        if membrane["pump"] is not None:
            pump = membrane["pump"]
            pump["roles"] = {k: names[v] for k, v in pump["roles"].items()}
            pump["stoichiometry"] = rename(pump["stoichiometry"])
        if entry["channel"] is not None:
            entry["channel"]["species_id"] = names[entry["channel"]["species_id"]]
    for edge in definition["junctions"]:
        for key in ("permeability_m_per_s", "residual_fraction"):
            edge[key] = rename(edge[key])
    assert ref.evaluate(ref.resolve(definition)) == original


def test_nonfinite_derived_pump_scale_rejected_without_channels(world):
    with pytest.raises(ValueError, match="pump thermal scale"):
        replace(world, channels=(), temperature_K=1.5e307)
