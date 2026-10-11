"""NUM-008 preflight uses shorter synthetic preparations, never full-panel solves."""

import ast
import copy
import json
from dataclasses import replace
from time import monotonic

import numpy as np
import pytest

from scripts import audit_physical_ionic_graph_reference as audit
from scripts import qualify_physical_ionic_graph_reference as qualify
from tests import physical_ionic_graph_numerical_checks as check
from tests import physical_ionic_graph_numerical_data as data
from tests import reference_physical_ionic_graph_dynamics as ref


@pytest.fixture(scope="module")
def panel():
    return data.load_panel()


@pytest.fixture(scope="module")
def small(panel):
    base = panel[1][6]
    bindings = list(base.graph.channels)
    bindings[0] = replace(
        bindings[0],
        channel=replace(bindings[0].channel, initial_gate=data.spec.channel.Gate(0.3, 0.7)),
    )
    graph = replace(base.graph, channels=tuple(bindings))
    enabled = data.spec.enabled(graph)
    off = replace(
        enabled,
        leak=tuple((0.0,) * base.layout.s for _ in graph.cells),
        pump=(0.0,) * base.layout.n,
        channel=(0.0,) * base.layout.k,
        junction=(0.0,) * base.layout.e,
    )
    return data.Case(
        "short_synthetic_preflight",
        graph,
        0.012,
        (
            data.Control(0, enabled),
            data.Control(0.0023, replace(enabled, junction=(0.0, 1.0))),
            data.Control(0.0024, replace(enabled, channel=(1.0, 0.0), pump=(0.0, 1.0, 1.0))),
            data.Control(0.0051, off),
            data.Control(0.0089, enabled),
            data.Control(0.012, off),
        ),
    )


@pytest.fixture(scope="module")
def small_records(panel, small):
    plan = panel[0]
    samples = ref.comparison_grid(small, plan["candidate"])
    records, stats = {}, {}
    for setting in plan["references"]:
        name = setting["id"]
        arrays, stats[name] = ref.integrate_reference(small, setting)
        records[name] = arrays | {
            "sample_times_s": samples,
            "sample_state": ref.sample_record(small, arrays, setting["method"], samples),
        }
    for dt in plan["candidate"]["steps_s"]:
        name = f"rk4_{dt:g}"
        arrays, stats[name] = ref.integrate_candidate(small, dt)
        assert stats[name]["status"] == "complete"
        records[name] = arrays | {
            "sample_times_s": samples,
            "sample_state": ref.sample_record(small, arrays, "RK4", samples),
        }
    return records, stats


def test_frozen_inputs_and_boundaries(panel):
    plan, cases = panel
    assert data.sha(data.PANEL) == data.PANEL_SHA256
    assert len(cases) == 12
    assert plan["candidate"]["steps_s"] == [0.002, 0.001, 0.0005, 0.00025]
    assert max(c.horizon_s for c in cases) == 0.3
    assert sum(len(c.graph.cells) for c in cases if c.independent_cell_reduction) == 5
    assert plan["resources"]["max_graph_attempts"] == 84
    assert plan["resources"]["workers"] == 1


@pytest.mark.parametrize("index", range(12))
def test_complete_layout_and_independent_rhs(panel, index):
    case = panel[1][index]
    state = data.initial_state(case, absolute=True)
    assert data.spec.initial_state(case.graph) == case.layout.state(state)
    delta = data.canonical(case, state, absolute=True)
    actual = ref.hyperbolic_rhs(case, case.controls[0], delta)
    expected = ref.bernoulli_rhs(case, case.controls[0], state)
    np.testing.assert_allclose(actual, expected, rtol=2e-12, atol=1e-10)
    assert actual.shape == (case.size,)
    assert not np.shares_memory(state, actual)


def test_hyperbolic_does_not_call_candidate_evaluator(small, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Independent RHS called candidate equations")

    for module, field in (
        (ref.spec, "evaluate"),
        (ref.spec, "transfer"),
        (ref.spec.channel, "evaluate"),
        (ref.spec.ionic, "evaluate"),
    ):
        monkeypatch.setattr(module, field, forbidden)
    assert np.isfinite(
        ref.hyperbolic_rhs(small, small.controls[0], data.initial_state(small))
    ).all()


@pytest.mark.parametrize("index", range(12))
def test_meshes_resolve_events_and_observation_requests(panel, index):
    plan, cases = panel
    case = cases[index]
    samples = ref.comparison_grid(case, plan["candidate"])
    np.testing.assert_array_equal(
        samples, check.expected_grid(case.definition(), plan["candidate"])
    )
    assert len(samples) <= plan["resources"]["max_samples_per_case"]
    for dt in plan["candidate"]["steps_s"]:
        mesh = ref.candidate_grid(case, dt)
        np.testing.assert_array_equal(mesh, check.native_mesh(case.definition(), dt))
        assert all(c.time_s in mesh and c.time_s in samples for c in case.controls)


@pytest.mark.parametrize("field", ["membrane_gate", "junction_gate"])
@pytest.mark.parametrize("bad", [-1e-15, 1.000000000000001, np.nan, np.inf])
def test_real_gates_checked_even_with_all_controls_off(small, field, bad):
    state = data.initial_state(small)
    state[small.layout.slices[field].start] = bad
    with pytest.raises(ref.DomainViolation):
        ref.hyperbolic_rhs(small, small.controls[-1], state)


@pytest.mark.parametrize("bad", [0, -1, True, np.inf, np.nan, 0.301])
def test_invalid_horizon_refused(small, bad):
    with pytest.raises(ValueError):
        replace(small, horizon_s=bad)


@pytest.mark.parametrize("bad", [0, -1, True, np.inf, np.nan, 1e-100])
def test_bad_or_unbounded_step_refused(small, bad):
    with pytest.raises(ValueError):
        ref.candidate_grid(small, bad)


@pytest.mark.parametrize("group", ["leak", "pump", "channel", "junction"])
def test_unknown_control_binding_refused(panel, small, group):
    row = copy.deepcopy(panel[0]["profiles"]["baseline"]["controls"][0])
    row["overrides"][group]["unknown"] = {} if group == "leak" else 0
    with pytest.raises(ValueError, match="Unknown control owner"):
        data.resolve_control(small.graph, row)


@pytest.mark.parametrize("bad", [-1, 1.01, True, "0", np.nan])
def test_bad_control_fraction_refused(panel, small, bad):
    row = copy.deepcopy(panel[0]["profiles"]["baseline"]["controls"][0])
    row["overrides"]["junction"]["junction_0"] = bad
    with pytest.raises(ValueError):
        data.resolve_control(small.graph, row)


def test_unknown_species_and_partial_snapshot_refused(panel, small):
    row = copy.deepcopy(panel[0]["profiles"]["baseline"]["controls"][0])
    row["overrides"]["leak"]["cell_0"] = {"not_an_ion": 0}
    with pytest.raises(ValueError, match="species"):
        data.resolve_control(small.graph, row)
    del row["pump"]
    with pytest.raises(ValueError, match="exactly"):
        data.resolve_control(small.graph, row)


def test_controls_are_strict_and_right_continuous(small):
    assert small.control_at(0.0023) == small.controls[1]
    assert small.control_at(np.nextafter(0.0023, 0).item()) == small.controls[0]
    assert small.control_at(0.012) == small.controls[-1]
    for controls in (
        list(small.controls),
        (),
        (small.controls[1],),
        small.controls + (small.controls[-1],),
    ):
        with pytest.raises(ValueError):
            replace(small, controls=controls)
    for query in (-1.0, 0.013, True, np.nan):
        with pytest.raises(ValueError):
            small.control_at(query)


@pytest.mark.parametrize(
    "name", ["radau", "bdf", "refined", "rk4_0.002", "rk4_0.001", "rk4_0.0005", "rk4_0.00025"]
)
def test_data_only_replay_native_identity_and_accounting(small, small_records, panel, name):
    records, _ = small_records
    arrays = records[name]
    kind = "RK4" if name.startswith("rk4_") else "BDF" if name == "bdf" else "Radau"
    definition = small.definition()
    check.validate_record(definition, arrays, kind)
    np.testing.assert_array_equal(audit.replay(definition, arrays, kind), arrays["sample_state"])
    np.testing.assert_array_equal(
        ref.sample_record(small, arrays, kind, arrays["native_times_s"]),
        data.canonical(small, arrays["native_state"], absolute=kind == "RK4"),
    )
    assert check.inspect_samples(
        definition, arrays["sample_times_s"], arrays["sample_state"], panel[0]["accounting_limits"]
    )["pass"]
    assert check.control_checks(
        definition, arrays["sample_times_s"], arrays["sample_state"], panel[0]["trajectory_limits"]
    )["pass"]


@pytest.mark.parametrize("method", ["Radau", "BDF"])
def test_dense_basis_matches_pinned_scipy(small, panel, monkeypatch, method):
    original, captured = ref.solve_ivp, []

    def solve(*args, **kwargs):
        value = original(*args, **kwargs)
        captured.append(value)
        return value

    monkeypatch.setattr(ref, "solve_ivp", solve)
    setting = next(s for s in panel[0]["references"] if s["method"] == method)
    arrays, _ = ref.integrate_reference(small, setting)
    for result in captured:
        queries = result.t[:-1] + 0.37 * np.diff(result.t)
        np.testing.assert_allclose(
            ref.sample_record(small, arrays, method, queries),
            result.sol(queries).T,
            rtol=0,
            atol=1e-13,
        )


def test_held_endpoint_slope_and_final_event_do_not_retroact(small, small_records):
    arrays = small_records[0]["rk4_0.0005"]
    for slot, right in enumerate(arrays["native_times_s"][1:]):
        if right not in [c.time_s for c in small.controls[1:]]:
            continue
        left = arrays["native_times_s"][slot]
        coefficient = arrays["coefficients"][slot]
        actual = (coefficient[:, 1] + 2 * coefficient[:, 2] + 3 * coefficient[:, 3]) / (
            right - left
        )
        expected = ref.bernoulli_rhs(
            small, small.control_at(float(left)), arrays["native_state"][slot + 1]
        )
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-10)
    without = replace(small, controls=small.controls[:-1])
    other, _ = ref.integrate_candidate(without, 0.0005)
    np.testing.assert_array_equal(arrays["native_state"], other["native_state"])
    final = arrays["native_state"][-1]
    new_rate = small.layout.split(
        ref.bernoulli_rhs(small, small.control_at(small.horizon_s), final)
    )
    assert np.all(new_rate["amount"] == 0) and np.all(new_rate["junction_transferred"] == 0)
    assert np.any(new_rate["junction_gate"] != 0) and np.any(new_rate["membrane_gate"] != 0)


def test_analytic_all_off_relaxation_and_no_gate_reset(small, small_records, panel):
    arrays = small_records[0]["refined"]
    result = check.control_checks(
        small.definition(),
        arrays["sample_times_s"],
        arrays["sample_state"],
        panel[0]["trajectory_limits"],
        factor=0.1,
    )
    interval = next(r for r in result["intervals"] if r["start_s"] == 0.0051)
    assert interval["disabled_ledgers_exact"] and interval["constant_voltage_cells"] == [True] * 3
    assert interval["analytic_membrane_gate_error"] < 1e-5
    assert interval["analytic_junction_gate_error"] < 1e-5
    t, y = arrays["sample_times_s"], arrays["sample_state"]
    a, b = (y[np.searchsorted(t, q)] for q in (0.0051, 0.0089))
    for field in ("membrane_gate", "junction_gate"):
        assert not np.array_equal(a[small.layout.slices[field]], b[small.layout.slices[field]])


@pytest.mark.parametrize(
    "field",
    [
        "amount",
        "junction_transferred",
        "leak_transferred",
        "channel_transferred",
        "membrane_dissipated_energy_pJ",
        "junction_dissipated_energy_pJ",
    ],
)
def test_history_or_energy_corruption_fails(small, small_records, panel, field):
    arrays = small_records[0]["refined"]
    values = arrays["sample_state"].copy()
    values[-1, small.layout.slices[field].start] += 1e-4
    assert not check.inspect_samples(
        small.definition(), arrays["sample_times_s"], values, panel[0]["accounting_limits"]
    )["pass"]


@pytest.mark.parametrize("field", ["amount", "membrane_gate", "junction_gate"])
def test_cubic_interior_violation_cannot_hide_between_valid_endpoints(small, small_records, field):
    arrays = {k: v.copy() for k, v in small_records[0]["rk4_0.0005"].items()}
    index = small.layout.slices[field].start
    if field == "amount":
        row = [1.0, -8.0, 8.0, 0.0]
    else:
        row = [0.5, 4.0, -4.0, 0.0]
    arrays["coefficients"][0, index, :4] = row
    assert not check.candidate_polynomial_domain(small.definition(), arrays)["pass"]


def test_edge_domain_checked_even_without_channels_or_transport(small):
    graph = replace(small.graph, channels=())
    controls = tuple(
        data.Control(c.time_s, replace(c.value, channel=(), junction=(0.0, 0.0)))
        for c in small.controls
    )
    case = replace(small, graph=graph, controls=controls)
    state = data.initial_state(case)
    amounts = case.layout.split(state)["amount"]
    for i, target in ((0, 0.4), (2, -0.4)):
        p = case.graph.cells[i]
        amounts[i, 0] = (target - p.initial_voltage_V) * p.capacitance_F / data.QF
    with pytest.raises(ref.DomainViolation, match="Junction"):
        ref.domain(case, state)


def test_candidate_rejection_retains_prefix_and_offending_stage(small):
    graph = replace(
        small.graph,
        junctions=tuple(
            replace(e, permeability_m_per_s=tuple(p * 1e5 for p in e.permeability_m_per_s))
            for e in small.graph.junctions
        ),
    )
    case = replace(small, graph=graph)
    arrays, stats = ref.integrate_candidate(case, 0.002)
    assert stats["status"] == "rejected"
    saved = arrays | {"sample_times_s": np.empty(0), "sample_state": np.empty((0, case.size))}
    check.validate_record(case.definition(), saved, "RK4", complete=False)
    assert check.rejection_check(case.definition(), saved, stats)["rejection_domain_confirmed"]
    fake = copy.deepcopy(stats)
    fake["rejected_trial"]["absolute_state"] = data.initial_state(case, absolute=True).tolist()
    with pytest.raises(ValueError, match="does not violate"):
        check.rejection_check(case.definition(), saved, fake)


def test_cubic_edge_difference_has_its_own_domain_check(small):
    graph = replace(small.graph, channels=())
    controls = tuple(data.Control(c.time_s, replace(c.value, channel=())) for c in small.controls)
    case = replace(small, graph=graph, controls=controls)
    coefficient = np.zeros((case.size, 6))
    coefficient[:, 0] = data.initial_state(case, absolute=True)
    for i, target in ((0, 0.4), (2, -0.4)):
        cell = case.graph.cells[i]
        change = (target - cell.initial_voltage_V) * cell.capacitance_F / data.QF
        coefficient[i * case.layout.s, 1:3] = [4 * change, -4 * change]
    result = check.candidate_polynomial_domain(
        case.definition(), {"coefficients": coefficient[None]}
    )
    assert result["max_abs_x"] < 50 < result["max_edge_abs_x"]
    assert not result["pass"]


def test_reversing_all_edges_preserves_cells_and_reverses_only_signed_transfers(small):
    reversed_graph = replace(
        small.graph,
        junctions=tuple(
            replace(e, from_cell=e.to_cell, to_cell=e.from_cell) for e in small.graph.junctions
        ),
    )
    left, _ = ref.integrate_candidate(small, 0.0005)
    right, _ = ref.integrate_candidate(replace(small, graph=reversed_graph), 0.0005)
    expected = left["native_state"].copy()
    expected[:, small.layout.slices["junction_transferred"]] *= -1
    np.testing.assert_allclose(right["native_state"], expected, rtol=0, atol=2e-12)


def test_cell_order_is_not_transport_ownership(small):
    order = [2, 0, 1]
    graph = replace(small.graph, cells=tuple(small.graph.cells[i] for i in order))
    controls = tuple(
        data.Control(
            c.time_s,
            replace(
                c.value,
                leak=tuple(c.value.leak[i] for i in order),
                pump=tuple(c.value.pump[i] for i in order),
            ),
        )
        for c in small.controls
    )
    other = replace(small, graph=graph, controls=controls)
    left, _ = ref.integrate_candidate(small, 0.0005)
    right, _ = ref.integrate_candidate(other, 0.0005)
    a, b = small.layout.split(left["native_state"]), other.layout.split(right["native_state"])
    for field in data.FIELD_NAMES:
        expected = a[field][:, order] if field in data.FIELD_NAMES[:4] else a[field]
        np.testing.assert_allclose(b[field], expected, rtol=0, atol=2e-12)


def test_complete_histories_are_not_used_to_reanchor_voltage(small):
    initial = data.initial_state(small)
    altered = initial.copy()
    for field in (
        "leak_transferred",
        "pump_cycles",
        "membrane_dissipated_energy_pJ",
        "channel_transferred",
        "junction_transferred",
        "junction_dissipated_energy_pJ",
    ):
        altered[small.layout.slices[field]] = 0.1
    np.testing.assert_array_equal(
        ref.hyperbolic_rhs(small, small.controls[0], initial),
        ref.hyperbolic_rhs(small, small.controls[0], altered),
    )
    a, b = initial.copy(), altered.copy()
    a[: small.layout.amount_count] += small.initial_amount.ravel()
    b[: small.layout.amount_count] += small.initial_amount.ravel()
    np.testing.assert_array_equal(
        ref.bernoulli_rhs(small, small.controls[0], a),
        ref.bernoulli_rhs(small, small.controls[0], b),
    )


def test_call_and_wall_caps_prevent_unbounded_work(small):
    with pytest.raises(ref.ResourceLimit, match="RHS budget"):
        ref.integrate_candidate(small, 0.0005, budget=ref.Budget(max_calls=1))
    with pytest.raises(ref.ResourceLimit, match="wall-time"):
        ref.integrate_candidate(small, 0.0005, budget=ref.Budget(deadline=monotonic() - 1))


def test_local_projection_does_not_double_shared_recipient(small, small_records):
    state = small_records[0]["refined"]["sample_state"][-1]
    for i, local in enumerate(ref.local_cases(small)):
        expected = data.local_definition(small.definition(), i)
        assert json.loads(json.dumps(local.definition())) == expected
        np.testing.assert_array_equal(
            ref.local_state(small, state, i),
            data.project_local(small.definition(), state[None], i)[0],
        )


def test_refinement_selection_requires_finer_success_and_independent_references(
    small, small_records, panel
):
    plan = copy.deepcopy(panel[0])
    plan["cases"] = [{"id": small.id}]
    analysis = check.analyze_case(small.definition(), *small_records, plan)
    assert analysis["references_pass"]
    result = check.select_candidate({small.id: analysis}, plan)
    assert result["status"] == "pass"
    assert result["selected_dt_s"] != plan["candidate"]["steps_s"][-1]
    for entry in analysis["attempts"].values():
        entry["pass"] = False
    analysis["attempts"]["rk4_0.00025"]["pass"] = True
    assert check.select_candidate({small.id: analysis}, plan)["status"] == "not_qualified"


def test_artifacts_refuse_overwrite_and_enforce_quota(tmp_path):
    path = tmp_path / "bounded"
    artifacts = qualify.Artifacts(path, 65540)
    artifacts.write("one", b"1234")
    with pytest.raises(FileExistsError):
        qualify.Artifacts(path, 65540)
    with pytest.raises(ref.ResourceLimit):
        artifacts.write("two", b"5")
    with pytest.raises(FileExistsError):
        artifacts.write("one", b"", closing=True)


def test_auditor_is_solver_free_and_capsule_is_complete():
    for name in (
        "scripts/audit_physical_ionic_graph_reference.py",
        "tests/physical_ionic_graph_numerical_checks.py",
        "tests/physical_ionic_graph_numerical_data.py",
    ):
        tree = ast.parse((data.ROOT / name).read_text())
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(
            "dynamics" in n or "scipy" in n or n.startswith("cells") or "jax" in n for n in imports
        )
    assert len(qualify.SOURCE_FILES) == len(set(qualify.SOURCE_FILES))
    assert all((data.ROOT / n).is_file() for n in qualify.SOURCE_FILES)
