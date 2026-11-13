"""Tier-1 smoke test of restricted_cleft_lumen@1 (docs/CELL_DIVISION_S3_PLAN.md §1).

In NumPy on the S2 cleft cell (tests/membrane_insertion_fixtures.cleft_cell: a furrow patch of
1e-11 m^2 on a 0.01 pL cleft, so w = 2 um), no compile:
* the fill: after an insertion half-step the lumen holds w dA / 2 more volume, filled at the
  bath's composition and booked as @3 books its own supply (the cleft's amounts, the bath's
  reservoir_supplied and the work mu_b dn), with the fluid's volume work -Pi_b dV; every
  ledger closes, and the second half-step of the step selects its start state bitwise;
* at another lumen composition the fill heat is the exact W - dG of the fill (> 0), from the
  free energy written out here, and every ledger still closes;
* Q5's observer reads the lumen filled to its patch's area, bitwise a NumPy fill of the state;
* zero growth: the half-step selects its start state bitwise and the view is the declared
  layout;
* definition refusals, insertion's onset rule admitting this operator, and the round trip.
The compiled guards are test_restricted_lumen_runs.py.
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
from cells.models.operators import membrane_insertion as insertion
from cells.models.operators import restricted_lumen as lumen
from cells.models.operators.contract import Operator, check_declarations
from cells.models.registry import get_model
from cells.processes.electrochemistry import F, R
from tests import membrane_insertion_fixtures as fx

WIDTH = 2e-6  # m: the cleft cell's 0.01 pL is w A_on / 2 over its 1e-11 m^2 furrow.
RATE = 1e-11  # m^2/s.
H = fx.DT / 2
CLEFT, BATH, FURROW = 1, 0, 1  # Outside and patch slots.


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def block(node="cleft", source="bath_0", width=WIDTH):
    return dict(law=lumen.LAW_ID, lumens=[dict(node_id=node, source_id=source, gap_width_m=width)])


def world(rate=RATE, onset=0.002, *, base=None, lumen_block=None):
    base = fx.cleft_cell() if base is None else base
    raw = fx.with_operators(base, fx.furrow_insertion(rate=rate, onset=onset))
    raw["model"]["operators"].append(block() if lumen_block is None else lumen_block)
    return raw


def bind(raw):
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return spec, model, state, p


def controls(rate):
    return SimpleNamespace(insertion_rate_m2_s=np.array([0.0, rate]), insertion_open=np.ones(2))


def opened_and_grown(model, state, p, rate=RATE):
    """The onset event, then one insertion half-step at rate."""
    ins = model.operators[1]
    state, ok = ins.event(state, controls(rate), p, xp=np)
    assert ok
    state, ok = ins.half_step(state, H, controls(rate), p, xp=np)
    assert ok
    return state


def fill(model, state, p):
    """One lumen half-step at the composite's view, as the step passes it."""
    return model.operators[2].half_step(
        state, H, controls(0.0), p, xp=np, view=model.view(p, state, xp=np)
    )


def assert_ledgers_close(model, state, p, *, energy=1e-15):
    for name, residual in model.balances(state, p).items():
        bound = energy if name == "energy" else 1e-15
        assert np.max(np.abs(residual), initial=0.0) <= bound, name


def bath_composition(p):
    return np.asarray(p.extracellular_amount_reference[:, BATH] / p.extracellular_volume[BATH])


def free_energy(n, v, temperature):
    """RT sum n (ln(n / V) - 1) of one well-mixed compartment, pJ (n fmol, V pL)."""
    return 1e-3 * R * temperature * math.fsum(x * (math.log(x / v) - 1.0) for x in n)


def test_the_fill_books_bath_fluid_as_supply():
    spec, model, state, p = bind(world())
    grown = opened_and_grown(model, state, p)
    new, ok = fill(model, grown, p)
    assert ok
    da = float(grown.membrane_area_increment_m2[FURROW])
    dv = float(new.lumen_volume_increment_pL[CLEFT])
    assert dv == pytest.approx(0.5e15 * WIDTH * da, rel=1e-12) and dv > 0
    c_bath = bath_composition(p)
    dn = c_bath * dv
    np.testing.assert_allclose(new.extracellular_amount_increment[:, CLEFT], dn, rtol=1e-14)
    np.testing.assert_allclose(new.reservoir_supplied[:, BATH], dn, rtol=1e-14)
    np.testing.assert_allclose(new.lumen_supplied_fmol[:, CLEFT], dn, rtol=1e-14)
    assert not np.any(new.reservoir_supplied[:, CLEFT])
    assert not np.any(new.lumen_supplied_fmol[:, BATH])
    t, z = float(p.temperature), np.asarray(p.valence)[:, 0]
    mu = R * t * np.log(c_bath) + z * F * float(p.boundary_V[BATH])
    assert float(new.reservoir_work_pJ[BATH]) == pytest.approx(1e-3 * np.sum(mu * dn), rel=1e-13)
    fluid = -1e-3 * R * t * np.sum(c_bath) * dv  # -Pi_b dV.
    assert float(new.lumen_fluid_work_pJ[CLEFT]) == pytest.approx(fluid, rel=1e-13)
    heat = float(new.lumen_fill_dissipated_energy_pJ[CLEFT])
    assert 0.0 <= heat <= 1e-12 * abs(fluid)  # The lumen is at the bath's composition.
    volume = model.view(p, new, xp=np).extracellular_volume
    assert volume[CLEFT] == p.extracellular_volume[CLEFT] + dv and volume[BATH] == 1.0
    assert_ledgers_close(model, new, p, energy=1e-15)
    # The second half-step of the step finds the area where the first left it: it selects.
    again, ok = fill(model, new, p)
    assert ok
    for a, b in zip(again, new, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()
    history = type(state)(*(np.stack(v) for v in zip(state, grown, new, strict=True)))
    diagnostics = model.check_values(history, spec, steps=[0, 1, 1])
    assert diagnostics["max_lumen_fill_balance_error_fmol"] == 0.0


def k_enriched_and_grown(model, state, p, rate=3e-9):
    """The opened cleft cell after a neutral K-for-Na exchange through the furrow (the cleft's
    K rises from 0.05 to 0.07 fmol, its Na falls by as much; the furrow's heat set so that
    every ledger closes), then one insertion half-step: a fill of another composition pending."""
    ins = model.operators[1]
    state, ok = ins.event(state, controls(rate), p, xp=np)
    na, k, x = 0, 1, 0.02
    amount, outside = state.amount_increment.copy(), state.extracellular_amount_increment.copy()
    moved = state.membrane_transferred.copy()
    amount[k, 0], amount[na, 0] = -x, x
    outside[k, CLEFT], outside[na, CLEFT] = x, -x
    moved[k, FURROW], moved[na, FURROW] = x, -x  # Outward positive.
    row = state._replace(
        amount_increment=amount, extracellular_amount_increment=outside, membrane_transferred=moved
    )
    released = -model.balances(row, p)["energy"]
    assert released > 0  # Both ions moved down their gradients.
    heat = row.membrane_dissipated_energy_pJ.copy()
    heat[FURROW] = released
    row = row._replace(membrane_dissipated_energy_pJ=heat)
    assert_ledgers_close(model, row, p, energy=1e-15)
    grown, ok = ins.half_step(row, H, controls(rate), p, xp=np)
    assert ok
    return grown


def test_the_fill_heat_is_the_mixing_gap_at_another_composition():
    """A fill mixes bath fluid into a K-enriched lumen: its heat is W - dG of the fill from the
    free energy written out here, and every ledger still closes."""
    spec, model, state, p = bind(world(rate=3e-9))
    grown = k_enriched_and_grown(model, state, p)
    new, ok = fill(model, grown, p)
    assert ok
    t = float(p.temperature)
    v = float(model.view(p, grown, xp=np).extracellular_volume[CLEFT])
    dv = float(new.lumen_volume_increment_pL[CLEFT] - grown.lumen_volume_increment_pL[CLEFT])
    n = p.extracellular_amount_reference[:, CLEFT] + grown.extracellular_amount_increment[:, CLEFT]
    c_bath = bath_composition(p)
    dn = c_bath * dv
    supply = 1e-3 * R * t * float(np.sum(np.log(c_bath) * dn)) - 1e-3 * R * t * np.sum(c_bath) * dv
    gap = supply - (free_energy(n + dn, v + dv, t) - free_energy(n, v, t))
    booked = float(new.lumen_fill_dissipated_energy_pJ[CLEFT])
    assert booked > 0 and booked == pytest.approx(gap, rel=1e-9)
    scale = abs(float(new.lumen_fluid_work_pJ[CLEFT]))
    assert booked > 1e-4 * scale  # Far above rounding: K differs from the bath by 40%.
    rounding = 1e-14 * float(np.sum(new.lumen_energy_magnitude_pJ))  # Of the booked terms.
    assert_ledgers_close(model, new, p, energy=rounding)


def test_the_observer_reads_the_lumen_filled_to_the_area():
    """Q5's observer (the lead, 13 November): with a fill pending, the readouts are the lumen
    filled to its patch's area, (n + c_b (T - dV)) / (V_on + T), bitwise what a NumPy fill of
    the state gives; once filled, they are the state's own lumen."""
    spec, model, state, p = bind(world(rate=3e-9))
    grown = k_enriched_and_grown(model, state, p)
    op = model.operators[2]
    pending = op.observe(None, grown, None, p, model.view(p, grown, xp=np), model, spec)
    new, ok = lumen.filled(grown, p, xp=np)
    assert ok
    view = model.view(p, new, xp=np)
    volume = view.extracellular_volume[CLEFT]
    amounts = (
        view.extracellular_amount_reference[:, CLEFT] + new.extracellular_amount_increment[:, CLEFT]
    )
    assert np.asarray(pending["lumen_volume_pL"][CLEFT]).tobytes() == volume.tobytes()
    concentration = pending["lumen_concentration_mM"][:, CLEFT]
    assert concentration.tobytes() == (amounts / volume).tobytes()
    target = 0.5e15 * WIDTH * float(grown.membrane_area_increment_m2[FURROW])
    assert volume == pytest.approx(p.extracellular_volume[CLEFT] + target, rel=1e-12)
    # The state's own lumen (before the fill) holds more K than the filled one reads.
    held = model.view(p, grown, xp=np)
    raw = (held.extracellular_amount_reference[:, CLEFT] + grown.extracellular_amount_increment[
        :, CLEFT
    ]) / held.extracellular_volume[CLEFT]  # fmt: skip
    assert raw[1] > concentration[1] > bath_composition(p)[1]
    filled_state = op.observe(None, new, None, p, view, model, spec)
    for name in ("lumen_volume_pL", "lumen_concentration_mM"):
        assert np.asarray(filled_state[name]).tobytes() == np.asarray(pending[name]).tobytes()


def test_zero_growth_selects_the_start_state_bitwise():
    _, model, state, p = bind(world(rate=0.0))
    grown = opened_and_grown(model, state, p, rate=0.0)
    new, ok = fill(model, grown, p)
    assert ok
    for a, b in zip(new, grown, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()
    view, declared = model.view(p, new, xp=np), adapter.inner_layout(p)
    for name in declared._fields:  # Open, nothing grown: the declared layout bitwise.
        a, b = np.asarray(getattr(view, name)), np.asarray(getattr(declared, name))
        assert a.tobytes() == b.tobytes(), name
    assert_ledgers_close(model, new, p)


def test_before_the_onset_the_lumen_is_closed_and_empty():
    _, model, state, p = bind(world())
    new, ok = fill(model, state, p)  # The furrow is closed: no area, no fill.
    assert ok
    for a, b in zip(new, state, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()
    view = model.view(p, state, xp=np)
    assert not view.outside_active[CLEFT] and view.extracellular_volume[CLEFT] == 0.01
    # A volume above its area's is refused (no fill before the onset).
    early = state._replace(lumen_volume_increment_pL=np.array([0.0, 1e-9]))
    assert not model.domain_valid(early, p, p.active, xp=np)


def with_second_furrow(raw):
    """A second onset patch on the cleft, inserted with the first."""
    m = raw["model"]
    second = copy.deepcopy(m["membranes"][1])
    second.update(id="furrow_b")
    m["membranes"].append(second)
    raw["experiment"]["membrane_controls"].append(
        dict(membrane_id="furrow_b", schedule=[dict(time=0.0, availability=1.0)])
    )
    raw["execution"]["membrane_capacity"] = 3
    ins = m["operators"][1]
    ins["patches"].append(dict(ins["patches"][0], membrane_id="furrow_b"))
    schedules = raw["experiment"]["insertion_controls"]
    schedules.append(dict(schedules[0], membrane_id="furrow_b"))
    return raw


def charged_bath(raw):
    bath = raw["model"]["extracellular"][0]
    bath["initial_amount_fmol"]["K"] += 1.0  # 1 mM in its 1 pL, with the background to match.
    bath["fixed_charge_equivalent_fmol"] -= 1.0
    return raw


def without_onset(raw):
    raw["experiment"]["insertion_controls"][0].update(
        onset_time=None, schedule=[dict(time=0.0, rate_m2_per_s=RATE)]
    )
    return raw


def reordered(raw):
    ops = raw["model"]["operators"]
    ops[1], ops[2] = ops[2], ops[1]
    return raw


def without_insertion(raw):
    raw["model"]["operators"].pop(1)
    del raw["experiment"]["insertion_controls"]
    return raw


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r["model"]["operators"][2].update(block(node="bath_0")), "finite outside node"),
        (lambda r: r["model"]["operators"][2].update(block(source="cleft")), "held bath"),
        (lambda r: r["model"]["operators"][2].update(block(width=3e-6)), "onset volume"),
        (with_second_furrow, "more than one patch"),
        (charged_bath, "electroneutral"),
        (without_onset, "finite onset node of the insertion"),
        (reordered, "requires scheduled_membrane_insertion@1 before it"),
        (without_insertion, "requires scheduled_membrane_insertion@1"),
        (lambda r: r["model"]["operators"][2].update(lumens=[]), "non-empty list"),
        (
            lambda r: r["model"]["operators"][2]["lumens"].append(
                r["model"]["operators"][2]["lumens"][0]
            ),
            "One lumen entry per node",
        ),
    ],
)
def test_definition_refusals(change, message):
    raw = world()
    change(raw)
    with pytest.raises(ConfigError, match=message):
        parse_spec(raw)


def test_another_provider_of_the_volume_is_refused():
    """Water also provides the cleft's volume: the composite refuses two providers."""
    from cells.models import pump_composite

    laws = (fx.STATE, fx.INSERTION, lumen.LAW_ID, "ideal_osmosis_linear_compliance_water@1")
    with pytest.raises(ConfigError, match="two providers of the view field extracellular_volume"):
        pump_composite.implementation(adapter.MODEL_ID, laws)


def test_insertions_onset_rule_admits_an_onset_anchored_volume():
    spec, model, _, _ = bind(world())
    (_, declaration, schedule) = cs.entries(spec)[1]
    insertion.check_definition(spec, declaration, schedule, model)  # The lumen is admitted.

    class VolumeProvider(Operator):
        LAW_ID = "volume_provider@1"
        EVENT = True
        VIEW_FIELDS = ("extracellular_volume",)

    with pytest.raises(ConfigError, match="declared anchor"):
        insertion.check_definition(
            spec, declaration, schedule, SimpleNamespace(operators=(VolumeProvider(),))
        )

    class Misdeclared(VolumeProvider):
        LAW_ID = "misdeclared@1"
        VIEW_FIELDS = ()
        ONSET_ANCHORED_VIEWS = ("extracellular_volume",)

    with pytest.raises(ValueError, match="onset-anchored view field is one it provides"):
        check_declarations(Misdeclared)


def test_declarations_round_trip_and_summary():
    spec, model, _, _ = bind(world())
    assert parse_spec(spec.to_dict()) == spec
    assert cs.to_dict(spec)["model"]["operators"][2] == block()
    assert model.batch_signature(spec.model)[-2:] == (lumen.LAW_ID, (("cleft", "bath_0"),))
    summary = model.operators[2].summary(spec, spec.model.operators[2], (), None)
    assert summary["lumens"] == {"cleft": dict(source_id="bath_0", gap_width_m=WIDTH)}
    owners = model.field_owners(spec)
    assert owners["views"]["extracellular_volume"] == {"provider": lumen.LAW_ID, "readers": []}
    assert lumen.LAW_ID in owners["views"]["membrane_area"]["readers"]
    assert lumen.LAW_ID in owners["state"]["reservoir_supplied"]["writers"]
