"""Tier-1 smoke test of scheduled_membrane_insertion@1 (docs/PUMP_COMPOSITE_V2_DESIGN.md §3).

In NumPy on bound worlds (no compile):
* the composite's capacitor energy is the physical 1/2 sum C V^2 - 1/2 sum C0 V0^2 over a
  spread of declared (C0, V0) and current (C, V), on one patch and on two clamps, with the
  clamps' plate charges (the energy rule: @3's term on the declared layout plus the view
  correction);
* one patch: |Vm| falls by C/(C + dC) at fixed charge, H = q^2 dC / (2 C (C + dC)), no image
  charge, and every ledger closes;
* two clamps: the image charge each clamp supplies, W = sum phi_b dq_b, dU = W - H, and the
  host checks of the composition;
* a zero rate selects the start state bitwise;
* the onset: the furrow patch, its cleft node and access face are masked until the event
  flips them, and the view is then the declared layout bitwise;
* definition refusals and the step checks on the largest area (R5).
The compiled guards are test_membrane_insertion_runs.py.
"""

import copy
import math
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.specs import ConfigError, parse_spec
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_tissue as tissue
from cells.models.operators import membrane_insertion as insertion
from cells.models.registry import get_model
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests import membrane_insertion_fixtures as fx

IDLE = {"membrane_0": ({}, None, [(0.0, 0.0)])}


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def bind(raw):
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return spec, model, state, p


def half_step(model, state, p, rates, *, opened=None):
    control = SimpleNamespace(
        insertion_rate_m2_s=np.asarray(rates, dtype=float),
        insertion_open=np.ones(len(rates)) if opened is None else np.asarray(opened, float),
    )
    return model.operators[1].half_step(state, fx.DT / 2, control, p, xp=np)


def capacitor_energy(state, p):
    """1/2 sum C V^2 (pJ) at the current view, from the view's own field solve."""
    q, _ = insertion.capacitor_view(state, p, xp=np)
    v = adapter.patch_voltages(adapter.node_potentials(state, q, xp=np), q, xp=np)
    return 0.5e12 * np.sum(np.where(q.membrane_active, q.membrane_capacitance, 0.0) * v**2), v


def declared(base, c0, v0):
    """base with its patches' capacitances c0 (tuple) and the cell charge giving V0 = v0
    against bath_0 at 0 V on one patch (the heredity fixture's charge rule)."""
    m = base["model"]
    for patch, c in zip(m["membranes"], c0, strict=True):
        patch["capacitance_F"] = c
    cell = m["cells"][0]
    z = {s["id"]: s["valence"] for s in m["species"]}
    charge = v0 * sum(c0)  # With every bath at 0 V, V0 = Q0 / sum C0 on each patch.
    cell["initial_charge_C"] = charge
    cell["fixed_charge_equivalent_fmol"] = charge / CHARGE_PER_FMOL - math.fsum(
        z[s] * a for s, a in cell["initial_amount_fmol"].items()
    )
    return base


@pytest.mark.parametrize("v0", [-0.09, 0.0, 0.03])
@pytest.mark.parametrize("c0", [1.6e-11, 1e-8])
def test_the_capacitor_energy_is_the_physical_total_on_one_patch(c0, v0):
    """The energy rule: @3's term on the declared layout, 1/2 sum C0 (Vb^2 - V0^2), plus the
    view correction is 1/2 C V^2 - 1/2 C0 V0^2 for every (C, V) of the spread."""
    _, _, state, p = bind(fx.with_operators(declared(fx.one_patch(), (c0,), v0), IDLE))
    bound = adapter.inner_layout(p)
    assert bound.initial_membrane_voltage_V[0] == pytest.approx(v0, abs=1e-15)
    k = list(bound.valence[:, 0]).index(1.0)  # A univalent cation carries the charge.
    for ratio in (1.0, 1.0 + 1e-7, 1.5, 4.0):
        for v in (-0.08, 0.0, 0.05):
            c = c0 * ratio
            amounts = np.zeros_like(state.amount_increment)
            amounts[k, 0] = (c * v - c0 * v0) / CHARGE_PER_FMOL
            row = state._replace(
                amount_increment=amounts,
                membrane_capacitance_increment_F=np.array([c - c0]),
            )
            view, _ = insertion.capacitor_view(row, p, xp=np)
            _, _, dv = tissue.capacitor_change(row, bound, xp=np)
            inner = adapter.capacitor_free_energy_pJ(dv, bound, xp=np)  # @3's own term.
            correction = adapter.view_capacitor_terms(row, view, bound, xp=np)[0]
            target = 0.5e12 * (c * v**2 - c0 * v0**2)
            bulk = 0.5e12 * (c * v**2 + c0 * v0**2)
            assert abs(inner + correction - target) <= 1e-12 * bulk + 1e-30, (ratio, v)
            if ratio == 1.0:
                assert correction == 0.0  # No field input changed: an exact zero, selected.


def test_the_capacitor_energy_and_plate_charges_on_two_clamps():
    raw = fx.with_operators(fx.two_clamps(potential_V=0.02), IDLE)
    _, _, state, p = bind(raw)
    bound = adapter.inner_layout(p)
    c0 = np.asarray(bound.membrane_capacitance)
    phi = np.asarray(bound.boundary_V)  # Both clamps: 0 and 20 mV.
    q0 = bound.initial_cell_charge_C[0]
    k = list(bound.valence[:, 0]).index(1.0)

    def analytic(c, q):
        cell = (q + np.sum(c * phi)) / np.sum(c)
        v = cell - phi
        return 0.5e12 * np.sum(c * v**2), c * (phi - cell)  # Energy (pJ), plate charges (C).

    u0, plates0 = analytic(c0, q0)
    for scale in ((1.0, 1.0), (1.3, 1.0), (1.0, 2.5), (3.0, 0.7)):
        for dq in (0.0, 2e-13, -5e-13):
            c = c0 * np.asarray(scale)
            amounts = np.zeros_like(state.amount_increment)
            amounts[k, 0] = dq / CHARGE_PER_FMOL
            row = state._replace(amount_increment=amounts, membrane_capacitance_increment_F=c - c0)
            view, _ = insertion.capacitor_view(row, p, xp=np)
            _, cap, dv = tissue.capacitor_change(row, bound, xp=np)
            inner = adapter.capacitor_free_energy_pJ(dv, bound, xp=np)
            energy, electrode, _, _ = adapter.view_capacitor_terms(row, view, bound, xp=np)
            u, plates = analytic(c, q0 + dq)
            assert inner + energy == pytest.approx(u - u0, rel=1e-11, abs=1e-18), (scale, dq)
            # @3's electrode term (declared plates) plus the correction: the view's plates.
            np.testing.assert_allclose(
                cap[1:] + electrode, plates - plates0, rtol=1e-11, atol=1e-28
            )


def test_one_patch_analytic():
    _, model, state, p = bind(fx.with_operators(fx.one_patch(), IDLE))
    c = float(p.membrane_capacitance[0])
    u0, v0 = capacitor_energy(state, p)
    for factor in (1e-6, 0.5, 1.0):  # dC / C in one half-step.
        rate = factor * c / fx.SPECIFIC_CAPACITANCE / (fx.DT / 2)
        new, ok = half_step(model, state, p, [rate])
        assert ok
        dc = float(new.membrane_capacitance_increment_F[0])
        assert dc == pytest.approx(factor * c, rel=1e-13)
        u1, v1 = capacitor_energy(new, p)
        assert v1[0] == pytest.approx(v0[0] * c / (c + dc), rel=1e-12)
        charge = c * v0[0]
        heat = float(new.insertion_dissipated_energy_pJ[0])
        assert heat == pytest.approx(0.5e12 * charge**2 * dc / (c * (c + dc)), rel=1e-9)
        assert not np.any(new.electrode_charge_transferred_C) and not np.any(new.electrode_work_pJ)
        assert u1 - u0 == pytest.approx(-heat, rel=1e-9)  # dU = W - H with W = 0.
        for name, residual in model.balances(new, p).items():
            assert np.max(np.abs(residual), initial=0.0) < 1e-15, (factor, name)


def test_two_clamps_image_charge_and_energy():
    spec, model, state, p = bind(fx.with_operators(fx.two_clamps(potential_V=0.02), IDLE))
    c = np.asarray(p.membrane_capacitance)
    rate = 0.3 * c[0] / fx.SPECIFIC_CAPACITANCE / (fx.DT / 2)
    new, ok = half_step(model, state, p, [rate, 0.0])
    assert ok
    q, phi = p.initial_cell_charge_C[0], np.asarray(p.boundary_V)
    c1 = c + np.asarray(new.membrane_capacitance_increment_F)
    before = (q + np.sum(c * phi)) / np.sum(c)
    after = (q + np.sum(c1 * phi)) / np.sum(c1)
    image = c1 * (phi - after) - c * (phi - before)
    np.testing.assert_allclose(new.electrode_charge_transferred_C, image, rtol=1e-12)
    assert image[0] == pytest.approx(-image[1], rel=1e-12) and image[0] != 0
    work = float(np.sum(new.electrode_work_pJ))
    assert work == pytest.approx(1e12 * np.sum(phi * image), rel=1e-12)
    heat = float(np.sum(new.insertion_dissipated_energy_pJ))
    u0, _ = capacitor_energy(state, p)
    u1, _ = capacitor_energy(new, p)
    assert heat > 0 and u1 - u0 == pytest.approx(work - heat, rel=1e-12)  # dU = W - H.
    history = type(state)(*(np.stack([a, b]) for a, b in zip(state, new, strict=True)))
    diagnostics = model.check_values(history, spec, steps=[0, 1])
    assert diagnostics["max_electrode_charge_error_C"] < 1e-26
    assert diagnostics["max_energy_balance_error_pJ"] < 1e-15


def test_a_zero_rate_selects_the_start_state_bitwise():
    _, model, state, p = bind(fx.with_operators(fx.two_clamps(), IDLE))
    idle, ok = half_step(model, state, p, [0.0, 0.0])
    assert ok
    for a, b in zip(idle, state, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()


def test_the_onset_opens_the_patch_its_node_and_face():
    spec, model, state, p = bind(fx.with_operators(fx.cleft_cell(), fx.furrow_insertion()))
    op = model.operators[1]
    furrow, cleft = 1, 1  # Patch and outside slots of the furrow and the cleft.
    closed = model.view(p, state, xp=np)
    assert not closed.membrane_active[furrow] and not closed.outside_active[cleft]
    assert not closed.face_active[0] and not np.any(closed.extracellular_amount_reference[:, cleft])
    assert closed.membrane_active[0] and closed.outside_active[0]
    open_now = SimpleNamespace(insertion_rate_m2_s=np.zeros(2), insertion_open=np.ones(2))
    opened, ok = op.event(state, open_now, p, xp=np)
    assert ok and opened.insertion_opened.tolist() == [0, 1]
    view, declared = model.view(p, opened, xp=np), adapter.inner_layout(p)
    for name in declared._fields:  # Open, and nothing inserted yet: the declared layout.
        a, b = np.asarray(getattr(view, name)), np.asarray(getattr(declared, name))
        assert a.tobytes() == b.tobytes(), name
    stale = SimpleNamespace(insertion_rate_m2_s=np.zeros(2), insertion_open=np.zeros(2))
    assert not op.event(opened, stale, p, xp=np)[1]  # A restart against the wrong schedule.
    _, ok = half_step(model, state, p, [0.0, 1e-11], opened=[1.0, 0.0])
    assert not ok  # A rate on a patch before its onset.
    for name, residual in model.balances(opened, p).items():
        assert np.max(np.abs(residual), initial=0.0) < 1e-15, name


def furrow(change):
    raw = fx.with_operators(fx.cleft_cell(), fx.furrow_insertion())
    change(raw)
    return raw


def onset_on_main(raw):
    raw["experiment"]["insertion_controls"][0].update(membrane_id="membrane_0")
    raw["model"]["operators"][1]["patches"][0]["membrane_id"] = "membrane_0"


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (
            fx.with_operators(fx.one_patch(), {"membrane_0": ({}, None, [(0.0, -1e-12)])}),
            "retrieval",
        ),
        (
            furrow(
                lambda r: r["experiment"]["insertion_controls"][0]["schedule"].insert(
                    1, dict(time=0.001, rate_m2_per_s=1e-12)
                )
            ),
            "outside its schedule",
        ),  # fmt: skip
        (furrow(onset_on_main), "Channel populations on an onset patch"),
        (
            furrow(
                lambda r: r["model"]["extracellular"][1].update(
                    initial_charge_C=1e-15,
                    fixed_charge_equivalent_fmol=r["model"]["extracellular"][1][
                        "fixed_charge_equivalent_fmol"
                    ]
                    + 1e-15 / CHARGE_PER_FMOL,
                )
            ),
            "charge anchor must be 0",
        ),  # fmt: skip
        (
            furrow(lambda r: r["model"]["operators"].pop(0)),
            "requires membrane_entity_state@1",
        ),
    ],
)
def test_definition_refusals(raw, message):
    with pytest.raises(ConfigError, match=message):
        parse_spec(raw)


def test_injection_and_the_node_cap_are_refused():
    raw = fx.with_operators(fx.one_patch(), IDLE)
    cell = raw["model"]["cells"][0]["id"]
    raw["model"]["operators"].append(
        dict(
            law="electrode_current_injection@1",
            electrodes=[dict(cell_id=cell, carriers={"K": 0.4912, "M": 0.5088})],
        )
    )
    raw["experiment"]["injection_controls"] = [
        dict(cell_id=cell, schedule=[dict(time=0.0, current_A=0.0)])
    ]
    with pytest.raises(ConfigError, match="books image charge on the declared layout"):
        parse_spec(raw)
    wide = fx.with_operators(fx.one_patch())
    wide["execution"].update(capacity=40, extracellular_capacity=25)
    with pytest.raises(ConfigError, match="limited to 64 field nodes"):
        parse_spec(wide)


def test_step_checks_take_the_largest_area_and_the_state_before_onset():
    """R5: @3's explicit-rate bound on the inserted patches' largest area (their declared
    capacitance kept, the smallest), and on the definition before any onset."""
    end = 0.004
    area = fx.one_patch()["model"]["membranes"][0]["area_m2"]
    grown = {"membrane_0": ({}, None, [(0.0, 400 * area / end)])}  # 400 x the area.
    for schedule, refused in ((IDLE, False), (grown, True)):
        spec = parse_spec(fx.with_operators(fx.one_patch(end=end), schedule))
        check = get_model(spec.model).bind_step_checks(spec)
        if refused:
            with pytest.raises(ConfigError, match="explicit-rate"):
                check(np.array([fx.DT]))
        else:
            check(np.array([fx.DT]))
    # Before the onset the cell has only its own patch: a large, nearly closed furrow lowers
    # the declared definition's rate, which the inner check alone would read.
    raw = fx.with_operators(fx.cleft_cell(end=1.0, observation_times=[0.0, 1.0]), {
        "furrow": ({}, 0.5, [(0.0, 0.0)])})  # fmt: skip
    patch = raw["model"]["membranes"][1]
    patch["capacitance_F"] = 100 * raw["model"]["membranes"][0]["capacitance_F"]
    patch["permeability_m_per_s"] = {s: 1e-16 for s in patch["permeability_m_per_s"]}
    raw["execution"]["dt"] = 0.5
    raw["execution"]["max_steps"] = 16
    spec = parse_spec(raw)
    model = get_model(spec.model)
    model.inner.bind_step_checks(model.operators[1].inner_check_spec(spec, spec, *(
        cs.entries(spec)[1][1:])))(np.array([0.5]))  # fmt: skip
    with pytest.raises(ConfigError, match="before the insertion onset"):
        model.bind_step_checks(spec)(np.array([0.5]))


def test_declarations_round_trip():
    raw = fx.with_operators(fx.cleft_cell(), fx.furrow_insertion())
    spec = parse_spec(raw)
    assert parse_spec(spec.to_dict()) == spec
    assert copy.deepcopy(cs.to_dict(spec))["experiment"]["insertion_controls"] == raw[
        "experiment"]["insertion_controls"]  # fmt: skip
