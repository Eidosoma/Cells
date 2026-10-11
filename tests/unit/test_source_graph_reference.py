"""NUM-005a graph composition/source probes; no accepted integration steps."""

import ast
import copy
import json
from itertools import permutations

import numpy as np
import pytest

from scripts import check_source_graph_reference as check
from tests import reference_emt
from tests import reference_source_graph as ref
from tests import reference_source_pair_numerics as pair
from tests import source_graph_fixtures as fixtures

CASES = fixtures.cases()


def case(name="G02"):
    return copy.deepcopy(next(c for c in CASES if c["id"] == name))


def test_frozen_complete_native_and_pair_acceptance():
    receipt = check.verify()
    assert receipt["status"] == "pass"
    assert receipt["checks_passed"] == 18499
    assert receipt["native_cases"] == 45
    assert receipt["pair_control_settings"] == 17
    assert receipt["cell_counts"] == [1, 2, 3, 4, 5]
    assert receipt["preparation_packets"] == "not_generated"
    assert receipt["trajectory_qualification"] == "not_run"


@pytest.mark.parametrize("data", CASES, ids=lambda c: c["id"])
def test_complete_explicit_state_and_passive_history_roles(data):
    model = ref.Model(data)
    primary, context = model.anchor.copy(), model.context.copy()
    r = model.evaluate(primary)
    assert model.coordinates.size == 13 * model.n + 4 * model.e
    assert r["primary_rate"].shape == (6, model.n)
    assert r["junction_flux"].shape == (4, model.e)
    assert r["gate_scales"].shape == (4, model.e)
    assert r["packet"].shape == (17, model.n)
    np.testing.assert_array_equal(primary, model.anchor)
    np.testing.assert_array_equal(context, model.context)
    np.testing.assert_array_equal(r["packet"][ref.eq.PRIMARY_INDEX], primary)
    np.testing.assert_array_equal(r["packet"][ref.eq.CONTEXT_INDEX], context)
    np.testing.assert_array_equal(r["packet"][8], primary[3])
    state = model.initial()
    slope = model.derivative(state)
    state[6 * model.n :] = np.arange(len(state) - 6 * model.n) - 23
    np.testing.assert_array_equal(model.derivative(state), slope)
    np.testing.assert_array_equal(model.derivative(np.zeros_like(state), increments=True), slope)
    residual = model.accounting(np.array([model.initial(), model.initial() + 1e-5 * slope]))
    assert max(residual.values()) < 2e-12  # tangent identity, not a trajectory qualification


@pytest.mark.parametrize("name", ["G01", "G06", "G07"])
def test_local_processes_once_per_cell_and_sum_only_edge_contributions(name):
    m = ref.Model(case(name))
    r = m.evaluate(m.anchor)
    expected = np.zeros_like(r["primary_rate"])
    for cell in range(m.n):
        single = fixtures.make_case(
            "single",
            [m.cell_ids[cell]],
            [],
            m.anchor[:, cell : cell + 1],
            m.context[:, cell : cell + 1],
            origin="isolated_component_check",
            panel=m.panel,
        )
        single["membrane_diffusion"] = m.membrane_diffusion[:, cell : cell + 1].tolist()
        single["controls"]["leak"] = m.controls["leak"][:, cell : cell + 1].tolist()
        single["controls"]["pump"] = m.controls["pump"][cell : cell + 1].tolist()
        isolated = ref.Model(single)
        expected[:, cell] = isolated.evaluate(isolated.anchor)["primary_rate"][:, 0]
    np.testing.assert_array_equal(expected, r["membrane_rate"] + r["local_rate"])
    for i, (a, b) in enumerate(m.edges):
        transfer = r["junction_flux"][:, i] * m.area / m.volume
        expected[:4, a] -= transfer
        expected[:4, b] += transfer
    np.testing.assert_allclose(r["primary_rate"], expected, atol=5e-15, rtol=2e-14)


@pytest.mark.parametrize("cell_order", list(permutations(range(3))))
@pytest.mark.parametrize("edge_order", [[0, 1], [1, 0]])
def test_cell_and_edge_permutations_preserve_named_physics(cell_order, edge_order):
    base = ref.Model(case())
    changed = ref.Model(fixtures.permute(case(), cells=list(cell_order), edges=edge_order))
    a, b = base.evaluate(base.anchor), changed.evaluate(changed.anchor)
    for name in (
        "primary_rate",
        "local_rate",
        "membrane_rate",
        "contact_rate",
        "packet",
        "leak_flux",
        "pump_flux",
    ):
        np.testing.assert_allclose(b[name], a[name][:, cell_order], atol=5e-15, rtol=2e-14)
    for name in ("gate_scales", "junction_flux"):
        np.testing.assert_array_equal(b[name], a[name][:, edge_order])
    np.testing.assert_array_equal(b["voltage"], a["voltage"][list(cell_order)])


def test_heterotypic_reversal_requires_hemichannel_swap():
    a, no_swap, swapped = [ref.Model(case(name)) for name in ("G02", "G03", "G04")]
    x, y, z = [m.evaluate(m.anchor) for m in (a, no_swap, swapped)]
    np.testing.assert_allclose(x["primary_rate"], z["primary_rate"], atol=5e-15, rtol=2e-14)
    np.testing.assert_allclose(x["junction_flux"], -z["junction_flux"], atol=1e-21, rtol=2e-14)
    assert np.max(abs(x["gate_scales"] - y["gate_scales"])) > 0.001


def test_disconnected_components_cannot_read_each_other():
    m = ref.Model(case("G07"))
    changed = m.anchor.copy()
    changed[3:, :2] += 17
    original, perturbed = m.evaluate(m.anchor), m.evaluate(changed)
    np.testing.assert_array_equal(original["primary_rate"][:, 2:], perturbed["primary_rate"][:, 2:])
    np.testing.assert_array_equal(original["junction_flux"][:, 1], perturbed["junction_flux"][:, 1])


def test_base_membrane_and_leak_controls_do_not_share_pump_eligibility():
    no_base, no_leak = [ref.Model(case(name)) for name in ("G08", "G09")]
    a, b = [m.evaluate(m.anchor) for m in (no_base, no_leak)]
    np.testing.assert_array_equal(a["pump_flux"][:, 1], np.zeros(3))
    assert b["pump_flux"][0, 1] != 0
    np.testing.assert_array_equal(a["leak_flux"][:, 1], np.zeros(3))
    np.testing.assert_array_equal(b["leak_flux"][:, 1], np.zeros(3))


def test_rna_transport_is_voltage_dependent_but_not_charge_inventory():
    m = ref.Model(case("G01"))
    r = m.evaluate(m.anchor)
    changed = m.anchor.copy()
    changed[3:] += 10
    q = m.evaluate(changed)
    np.testing.assert_array_equal(r["voltage"], q["voltage"])
    np.testing.assert_array_equal(r["primary_rate"][:3], q["primary_rate"][:3])
    new_case = case("G01")
    new_case["context"][0][0] += 0.001
    other = ref.Model(new_case)
    assert not np.array_equal(
        r["junction_flux"][3], other.evaluate(other.anchor)["junction_flux"][3]
    )


def test_context_is_retained_without_inventing_st_memory():
    original = ref.Model(case())
    changed = case()
    changed["context"][2] = [0.73, 0.09, 0.81]
    other = ref.Model(changed)
    np.testing.assert_array_equal(
        original.evaluate(original.anchor)["primary_rate"],
        other.evaluate(other.anchor)["primary_rate"],
    )
    np.testing.assert_array_equal(other.evaluate(other.anchor)["packet"][16], changed["context"][2])


def test_blocked_edges_retain_distinct_ledgers_without_evolving_them():
    blocked, absent = [ref.Model(case(name)) for name in ("G10", "G11")]
    a, b = [m.evaluate(m.anchor) for m in (blocked, absent)]
    np.testing.assert_array_equal(a["primary_rate"], b["primary_rate"])
    assert blocked.coordinates.size == 47 and absent.coordinates.size == 39
    slope = blocked.derivative(blocked.initial())
    np.testing.assert_array_equal(slope[blocked.coordinates.ionic], np.zeros(6))
    np.testing.assert_array_equal(slope[blocked.coordinates.mirna], np.zeros(2))


def test_per_edge_controls_do_not_block_unrelated_routes():
    m = ref.Model(case("G01"))
    controls = copy.deepcopy(m.case["controls"])
    controls["mirna_contact"][0] = 0
    changed = m.evaluate(m.anchor, controls=controls)
    original = m.evaluate(m.anchor)
    assert changed["junction_flux"][3, 0] == 0
    np.testing.assert_array_equal(changed["junction_flux"][:3], original["junction_flux"][:3])
    np.testing.assert_array_equal(changed["junction_flux"][:, 1], original["junction_flux"][:, 1])
    np.testing.assert_array_equal(changed["local_rate"], original["local_rate"])


def test_two_donors_sum_into_one_recipient_without_degree_normalization():
    data = case("seed/E_to_M/active")
    m = ref.Model(data)
    r = m.evaluate(m.anchor)
    np.testing.assert_array_equal(r["junction_flux"][:, 0], r["junction_flux"][:, 1])
    np.testing.assert_allclose(
        r["contact_rate"][:4, 0],
        -2 * r["junction_flux"][:, 0] * m.area / m.volume,
        atol=1e-15,
        rtol=2e-14,
    )
    assert m.mirna_diffusion.tolist() == [2e-15, 2e-15]


@pytest.mark.parametrize("field", sorted(ref.CASE_KEYS))
def test_missing_complete_reference_field_refused(field):
    data = case()
    del data[field]
    with pytest.raises(ValueError, match="fields"):
        ref.Model(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("cell_ids", [100, 100, 300]),
        ("cell_ids", [True, 200, 300]),
        ("edge_ids", [10, 10]),
        ("edge_ids", [-1, 20]),
        ("edges", [[100, 100], [100, 300]]),
        ("edges", [[100, 200], [200, 100]]),
        ("edges", [[100, 999], [100, 300]]),
        ("edges", [[100, 200]]),
        ("primary", [[1.0]]),
        ("context", [[80], [72], [0]]),
        ("membrane_diffusion", [[1e-18]]),
        ("ionic_diffusion", [[1e-18]]),
        ("mirna_diffusion", [-1, 1e-18]),
        ("mirna_diffusion", [float("nan"), 1e-18]),
        ("gates", ["unknown", None]),
        ("gates", [None]),
        ("swap_hemichannels", [False, 1]),
        ("controls", {"ion_contact": [0, 0]}),
    ],
)
def test_invalid_reference_layout_and_parameters_refused(field, value):
    data = case()
    data[field] = value
    with pytest.raises(ValueError):
        ref.Model(data)


@pytest.mark.parametrize(
    "row,value",
    [(0, 0.0), (1, -1.0), (2, 1001.0), (3, -1e-12), (4, float("nan")), (5, float("inf"))],
)
def test_invalid_state_is_refused_not_clipped(row, value):
    m = ref.Model(case())
    y = m.anchor.copy()
    y[row, 0] = value
    with pytest.raises(ValueError):
        m.evaluate(y)
    assert not m.anchor.flags.writeable


def test_voltage_guard_includes_transjunction_difference():
    data = case("G01")
    panel = ref.eq.load_panel()
    area, volume = ref.eq.geometry(panel)
    factor = panel["parameters"]["F"] * volume / (area * panel["parameters"]["cm"])
    y = np.asarray(data["primary"])
    data["context"][0] = (y[0] + y[1] - y[2] - np.array([0.15, -0.15, 0]) / factor).tolist()
    with pytest.raises(ValueError, match="voltage"):
        ref.Model(data)


def test_caller_arrays_are_copied_and_controls_checked():
    data = case()
    m = ref.Model(data)
    original = m.evaluate(m.anchor)["primary_rate"]
    data["primary"][3][0] = 0
    data["controls"]["pump"][0] = 0
    data["edges"][0].reverse()
    np.testing.assert_array_equal(m.evaluate(m.anchor)["primary_rate"], original)
    bad = copy.deepcopy(m.case["controls"])
    bad["ion_contact"][0] = 1.1
    with pytest.raises(ValueError):
        m.evaluate(m.anchor, controls=bad)


@pytest.mark.parametrize(
    "mutation", ["slope", "cache", "missing", "reorder", "audit", "context", "origin", "profile"]
)
def test_native_audit_rejects_corrupt_or_incomplete_evidence(mutation):
    native = json.loads(check.FIXTURE.read_text())
    record = native["probes"]["records"][0]
    if mutation == "slope":
        record["primary_rate"][3][0] += 1
    elif mutation == "cache":
        record["packet"][8][0] += 1
    elif mutation == "missing":
        native["probes"]["records"].pop()
    elif mutation == "reorder":
        native["probes"]["records"].reverse()
    elif mutation == "audit":
        record["audits"]["primary_unchanged"] = False
    elif mutation == "context":
        record["input_packet"][4][0] += 1
    elif mutation == "origin":
        record["origin"] = "qualified_equilibrium"
    else:
        native["probes"]["profile"]["iterate_binding"] = True
    with pytest.raises(ValueError):
        check.compare_native(native)


def test_graph_acceptance_does_not_call_an_integrator(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Instantaneous gate called an integrator")

    monkeypatch.setattr(reference_emt, "solve_ivp", forbidden)
    monkeypatch.setattr(pair, "solve_ivp", forbidden)
    assert check.verify()["trajectory_qualification"] == "not_run"


def test_reference_has_no_production_or_upstream_imports():
    for name in (
        "tests/reference_source_graph.py",
        "tests/reference_source_pair.py",
        "tests/reference_source_pair_numerics.py",
        "tests/reference_emt.py",
    ):
        for node in ast.walk(ast.parse((ref.eq.ROOT / name).read_text())):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            assert all(
                module.split(".")[0] not in {"cells", "sim", "GRN_miRNA", "GJ_lib", "zombie"}
                for module in modules
            )
