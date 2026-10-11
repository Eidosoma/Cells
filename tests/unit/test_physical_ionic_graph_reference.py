"""SPEC-007 graph contract tests; reference arithmetic only, no production change."""

import ast
import copy
import json
import math
import subprocess
import sys
from dataclasses import FrozenInstanceError, asdict, fields, replace
from decimal import localcontext

import pytest

from scripts import check_physical_ionic_graph as check
from tests import reference_multispecies as ionic
from tests import reference_physical_ionic_graph as ref


@pytest.fixture
def panel():
    return ionic.load_json(check.PROTOCOL)


@pytest.fixture
def definition(panel):
    return copy.deepcopy(
        next(c["definition"] for c in panel["cases"] if c["id"] == "star_divalent")
    )


@pytest.fixture
def graph(definition):
    return ref.resolve(definition)


def test_frozen_instantaneous_panel_and_scope():
    result = check.verify()
    assert result["status"] == "pass", result["failures"]
    assert result["checks_failed"] == 0
    assert result["groups"]["decimal_edge_flux"]["checks"] == 1890
    assert len(result["assemblies"]) == 8
    assert len(result["production_source_sha256"]) == 44
    assert result["production_version"] == "0.12.0"
    assert not result["production_change"] and not result["independent_ode_solver_run"]
    assert (
        result["method_selection"] == result["coupled_trajectory_qualification"] == "not_performed"
    )
    assert result["biological_acceptance"] == "not_assessable"


@pytest.mark.parametrize("z", [-3, -2, -1, 1, 2, 3])
@pytest.mark.parametrize("dv", [-0.1, -1e-12, 0, 1e-12, 0.1])
def test_oriented_constant_field_arithmetic_and_dissipation(z, dv):
    args = (z, 12.0, 18.0, dv, 298.15, 1e-11, 1e-8, 0.25, 0.1, 0.3)
    actual = ref.transfer(*args)
    with localcontext() as context:
        context.prec = 70
        expected = float(check.decimal_transfer(*args))
    assert actual == pytest.approx(expected, rel=2e-12, abs=1e-13)
    reverse = ref.transfer(z, 18.0, 12.0, -dv, *args[4:])
    assert reverse == pytest.approx(-actual, rel=2e-12, abs=1e-13)
    delta_mu = ionic.R * 298.15 * math.log(18 / 12) - z * ionic.F * dv
    assert -1e-15 * actual * delta_mu >= -1e-24


@pytest.mark.parametrize("case", range(8))
def test_reference_is_immutable_and_does_not_edit_inputs(panel, case):
    raw = panel["cases"][case]["definition"]
    original = copy.deepcopy(raw)
    graph = ref.resolve(raw)
    state = ref.initial_state(graph)
    before = asdict(state)
    ref.evaluate(graph, state)
    assert raw == original and asdict(state) == before
    with pytest.raises(FrozenInstanceError):
        graph.cells = ()


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema",), "wrong@1"),
        (("unknown",), 1),
        (("cells",), []),
        (("cells",), {}),
        (("junctions",), None),
        (("bath", "background_charge_mM"), 0),
        (("cells", 0, "cell", "initial_voltage_V"), -0.04),
        (("cells", 0, "cell", "fixed_charge_equivalent_fmol"), 0),
        (("cells", 0, "membrane", "inside"), "cell_1"),
        (("cells", 0, "channel", "membrane_id"), "membrane_1"),
        (("cells", 0, "channel", "species_id"), "Ca"),
        (("cells", 0, "channel", "initial_gate", "m"), True),
        (("cells", 0, "channel", "max_permeability_m_per_s"), math.inf),
        (("junctions", 0, "from_cell"), "missing"),
        (("junctions", 0, "from_cell"), "cell_2"),
        (("junctions", 0, "id"), "cell_0"),
        (("junctions", 0, "id"), "channel_0"),
        (("junctions", 0, "area_m2"), 0),
        (("junctions", 0, "area_m2"), 1e308),
        (("junctions", 0, "permeability_m_per_s", "Ca"), -1),
        (("junctions", 0, "permeability_m_per_s", "Ca"), "0"),
        (("junctions", 0, "residual_fraction", "Ca"), True),
        (("junctions", 0, "residual_fraction", "Ca"), 1.01),
        (("junctions", 0, "gate", "law"), "algebraic@1"),
        (("junctions", 0, "gate", "tau_s"), 0),
        (("junctions", 0, "gate", "sensitivity_per_V"), math.nan),
        (("junctions", 0, "gate", "half_voltage_V"), -0.01),
        (("junctions", 0, "gate", "initial_gate"), 1.01),
    ],
)
def test_strict_host_bindings_and_no_repairs(definition, path, value):
    target = definition
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        ref.resolve(definition)


@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_edges_are_not_parallel_transport(definition, reverse):
    edge = copy.deepcopy(definition["junctions"][0])
    edge["id"] = "duplicate"
    if reverse:
        edge["from_cell"], edge["to_cell"] = edge["to_cell"], edge["from_cell"]
    definition["junctions"].append(edge)
    with pytest.raises(ValueError, match="Duplicate physical edge"):
        ref.resolve(definition)


@pytest.mark.parametrize("group", ["permeability_m_per_s", "residual_fraction"])
@pytest.mark.parametrize("action", ["missing", "extra"])
def test_every_species_has_an_explicit_edge_binding(definition, group, action):
    values = definition["junctions"][0][group]
    if action == "missing":
        del values["Ca"]
    else:
        values["unused"] = 0
    with pytest.raises(ValueError):
        ref.resolve(definition)


def test_duplicate_json_keys_and_nonfinite_literals_are_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"schema":1,"schema":2}')
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        ionic.load_json(path)
    path.write_text('{"value":NaN}')
    with pytest.raises(ValueError):
        ionic.load_json(path)


@pytest.mark.parametrize("field", [f.name for f in fields(ref.State)])
def test_all_complete_state_fields_are_shape_checked(graph, field):
    bad = replace(ref.initial_state(graph), **{field: ()})
    with pytest.raises(ValueError):
        ref.evaluate(graph, bad)


@pytest.mark.parametrize(
    "field", ["amount", "leak_transferred", "membrane_gate", "junction_transferred"]
)
def test_state_matrices_reject_nonfinite_values_and_mutability(graph, field):
    state = ref.initial_state(graph)
    values = getattr(state, field)
    bad = ((math.nan, *values[0][1:]), *values[1:])
    with pytest.raises(ValueError):
        ref.evaluate(graph, replace(state, **{field: bad}))
    with pytest.raises(ValueError):
        ref.evaluate(graph, replace(state, **{field: list(values)}))


@pytest.mark.parametrize(
    "field",
    [
        "pump_cycles",
        "membrane_dissipated_energy_pJ",
        "channel_transferred",
        "junction_gate",
        "junction_dissipated_energy_pJ",
    ],
)
def test_state_vectors_reject_nonfinite_values(graph, field):
    state = ref.initial_state(graph)
    values = getattr(state, field)
    with pytest.raises(ValueError):
        ref.evaluate(graph, replace(state, **{field: (math.inf, *values[1:])}))


@pytest.mark.parametrize("field", ["leak", "pump", "channel", "junction"])
def test_all_controls_are_complete_independent_and_bounded(graph, field):
    control = ref.enabled(graph)
    values = getattr(control, field)
    for bad in ((), list(values)):
        with pytest.raises(ValueError):
            ref.evaluate(graph, control=replace(control, **{field: bad}))
    invalid = ((1.01, *values[0][1:]), *values[1:]) if field == "leak" else (1.01, *values[1:])
    with pytest.raises(ValueError):
        ref.evaluate(graph, control=replace(control, **{field: invalid}))


@pytest.mark.parametrize("gate", [-1e-15, 1.0000001, math.nan, True])
def test_disabled_edges_still_validate_gates(graph, gate):
    state = replace(ref.initial_state(graph), junction_gate=(gate, 0.5))
    control = replace(ref.enabled(graph), junction=(0.0, 0.0))
    with pytest.raises(ValueError):
        ref.evaluate(graph, state, control)


def test_unavailable_channels_are_not_inactive_capacity(graph):
    state = replace(ref.initial_state(graph), membrane_gate=((1.01, 0.5), (0.2, 0.8)))
    control = replace(ref.enabled(graph), channel=(0.0, 0.0))
    with pytest.raises(ValueError):
        ref.evaluate(graph, state, control)


def test_blocking_preserves_complete_gate_evolution_and_histories(graph):
    state = check.manufactured_history(graph, 1e-5)
    nominal = ref.evaluate(graph, state)
    blocked = ref.evaluate(
        graph, state, replace(ref.enabled(graph), junction=(0.0, 0.0), channel=(0.0, 0.0))
    )
    assert blocked.rate.junction_gate == nominal.rate.junction_gate
    assert blocked.rate.membrane_gate == nominal.rate.membrane_gate
    assert all(v == 0 for row in blocked.rate.junction_transferred for v in row)
    assert blocked.rate.channel_transferred == (0.0, 0.0)
    assert any(v != 0 for row in state.junction_transferred for v in row)
    assert any(v != 0 for v in state.channel_transferred)


def test_absent_channels_and_pumps_are_explicit(definition):
    for c in definition["cells"]:
        c["channel"] = None
        c["membrane"]["pump"] = None
    graph = ref.resolve(definition)
    state = ref.initial_state(graph)
    result = ref.evaluate(graph)
    assert graph.channels == state.membrane_gate == result.rate.channel_transferred == ()
    assert result.rate.pump_cycles == (0.0, 0.0, 0.0)
    with pytest.raises(ValueError, match="Absent pump"):
        ref.evaluate(graph, replace(state, pump_cycles=(1e-5, 0.0, 0.0)))


def test_disconnected_cells_are_exact_local_reductions(graph):
    disconnected = replace(graph, junctions=())
    state, control = ref.initial_state(disconnected), ref.enabled(disconnected)
    actual = ref.evaluate(disconnected, state, control)
    local, _ = check.local_reference(disconnected, state, control)
    assert actual.rate.amount == local
    assert actual.rate.junction_gate == actual.rate.junction_transferred == ()
    assert len(disconnected.channels) == 2 and len(disconnected.cells) == 3


def test_membrane_is_evaluated_once_per_cell_not_per_neighbor(graph, monkeypatch):
    calls = []
    original = ionic.evaluate

    def record(p, *args, **kwargs):
        calls.append(p.cell_id)
        return original(p, *args, **kwargs)

    monkeypatch.setattr(ionic, "evaluate", record)
    ref.evaluate(graph)
    assert calls == list(graph.cell_ids)


def test_species_and_entity_names_are_not_kernel_dispatch(definition):
    original = ref.resolve(definition)
    expected = ref.evaluate(original)
    species_map = {s["id"]: f"ion_{i}" for i, s in enumerate(definition["species"])}
    owner_map = {definition["bath"]["id"]: "bath_other"}
    for i, item in enumerate(definition["cells"]):
        owner_map[item["cell"]["id"]] = f"node_{i}"
        owner_map[item["membrane"]["id"]] = f"surface_{i}"
        if item["membrane"]["pump"]:
            owner_map[item["membrane"]["pump"]["id"]] = f"transporter_{i}"
        if item["channel"]:
            owner_map[item["channel"]["id"]] = f"protein_{i}"
    for i, e in enumerate(definition["junctions"]):
        owner_map[e["id"]] = f"contact_{i}"
    renaming = species_map | owner_map

    def rename(value):
        if isinstance(value, dict):
            return {renaming.get(k, k): rename(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rename(v) for v in value]
        return renaming.get(value, value) if isinstance(value, str) else value

    renamed = ref.resolve(rename(definition))
    actual = ref.evaluate(renamed)
    assert actual.rate == expected.rate
    assert actual.voltage_V == expected.voltage_V
    assert actual.stored_energy_rate_W == expected.stored_energy_rate_W


def test_real_impermeant_species_still_participates_in_charge(graph):
    state = ref.initial_state(graph)
    s = graph.species_ids.index("Ca")
    impermeant = replace(
        graph,
        junctions=tuple(
            replace(
                e,
                permeability_m_per_s=tuple(
                    0.0 if i == s else p for i, p in enumerate(e.permeability_m_per_s)
                ),
            )
            for e in graph.junctions
        ),
    )
    amount = tuple(
        tuple(v + (1e-5 if i == 0 and j == s else 0) for j, v in enumerate(row))
        for i, row in enumerate(state.amount)
    )
    actual = ref.evaluate(impermeant, replace(state, amount=amount))
    assert all(row[s] == 0 for row in actual.rate.junction_transferred)
    expected_dv = (
        2
        * ionic.CHARGE_PER_FMOL
        / graph.cells[0].capacitance_F
        * (amount[0][s] - state.amount[0][s])
    )
    assert actual.voltage_V[0] - graph.cells[0].initial_voltage_V == pytest.approx(
        expected_dv, abs=1e-15
    )


def test_zero_permeability_does_not_bypass_junction_domain():
    with pytest.raises(ValueError, match="Voltage exceeds"):
        ref.transfer(3, 12, 18, 1.0, 298.15, 1e-11, 0, 0, 0, 0)


def test_resolved_graph_constructor_cannot_bypass_binding_checks(graph):
    with pytest.raises(ValueError):
        replace(graph, cells=list(graph.cells))
    with pytest.raises(ValueError):
        replace(graph, channels=(graph.channels[0], graph.channels[0]))
    incompatible = replace(graph.cells[2], bath_id="other_bath")
    with pytest.raises(ValueError, match="common species table"):
        replace(graph, cells=(*graph.cells[:2], incompatible))


def test_extreme_symmetric_gate_is_stable_and_not_an_algebraic_switch(graph):
    e = graph.junctions[0]
    assert e.target(100) == e.target(-100) == 0.0
    assert e.gate_rate(100, 1) == -1 / e.tau_s
    with pytest.raises(ValueError):
        replace(e, tau_s=0)


def test_arbitrary_nonzero_ledgers_are_not_material_pools(graph):
    state = check.manufactured_history(graph, 1e-5)
    residuals = ref.ledger_residuals(graph, state)
    assert max(abs(x) for row in residuals["material_fmol"] for x in row) < 1e-12
    assert max(abs(x) for x in residuals["charge_V"]) < 1e-10
    bad = replace(
        state, junction_transferred=((0.0,) * len(graph.species_ids),) * len(graph.junctions)
    )
    assert (
        max(abs(x) for row in ref.ledger_residuals(graph, bad)["material_fmol"] for x in row) > 1e-6
    )
    assert ref.evaluate(graph, bad).rate == ref.evaluate(graph, state).rate


def test_static_dependency_boundary_has_no_production_or_integrator_calls():
    for path in (
        check.ROOT / "tests/reference_physical_ionic_graph.py",
        check.ROOT / "scripts/check_physical_ionic_graph.py",
    ):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(not item.name.startswith(("cells", "jax")) for item in node.names)
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("cells", "jax"))
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                assert name not in {"solve_ivp", "rk4", "run", "initialise", "device_put"}


def test_cli_does_not_overwrite_evidence(tmp_path):
    target = tmp_path / "existing.json"
    target.write_text("preserve this")
    result = subprocess.run(
        [
            sys.executable,
            str(check.ROOT / "scripts/check_physical_ionic_graph.py"),
            "--output",
            str(target),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and target.read_text() == "preserve this"
    assert "FileExistsError" in result.stderr


def test_frozen_protocol_tampering_is_refused(tmp_path, monkeypatch, panel):
    path = tmp_path / "changed.json"
    panel["tolerances"]["rtol"] = 1.0
    path.write_text(json.dumps(panel))
    monkeypatch.setattr(check, "PROTOCOL", path)
    with pytest.raises(ValueError, match="Frozen SPEC-007 inputs changed"):
        check.verify()
