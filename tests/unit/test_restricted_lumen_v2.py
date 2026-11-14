"""Tier-1 smoke test of restricted_cleft_lumen@2 (docs/CELL_DIVISION_S5_DESIGN.md §5.2, A.5).

In NumPy (no compile), on the furrow division world (tests/partition_fixtures.cleft_divided):
* two facing patches and continuity across a birth: the target over the live facing patches is
  the same before and after the partition, exactly for a = 1/2 and within rounding for a = 0.6;
  the first fill after the birth is no fill, selected bitwise, and valid;
* closed facing patches hold no growth (the domain bound's premise): the pending daughters'
  furrows before the division and the retired parent's after it show exactly zero, so the bound
  over every facing patch equals the live target;
* the closed lumen is @3 padding (the padded-slot test owed since S3): before the onset the
  cleft is closed with zero reference amounts, @3's domain holds at the view and the observer's
  lumen columns read 0; after it they read the declared content;
* @2 reproduces @1's fills on S2's cleft cell (one facing patch), with every ledger equal;
* the combined world walked through onset, insertion, fill, an asymmetric partition, insertion
  on the daughters and fill, with every ledger closed at each stage and the cleft open across
  the event;
* refusals: a facing patch neither an onset patch nor a partition-born descendant of one, an
  onset volume other than w A_on / 2, and a lumen node that is not an onset node;
* 1 -> 2 -> 4 with second onsets (cleft_quartered) walked through both onsets and both
  partitions: every cleft opens at its onset, every ledger closes.
"""

import copy
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.core.specs import ConfigError, parse_spec
from cells.models import pump_composite_adapter as adapter
from cells.models.operators import membrane_insertion as insertion_v1
from cells.models.operators import membrane_insertion_v2 as insertion_v2
from cells.models.operators import restricted_lumen as v1
from cells.models.operators import restricted_lumen_v2 as v2
from cells.models.registry import get_model
from tests import membrane_insertion_fixtures as ifx
from tests import partition_fixtures as fx

H = 0.5 * fx.DT
COULOMBS = ("charge", "electrode", "global_charge")


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def bind(raw):
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return spec, model, state, p


def operator(model, law):
    return next(op for op in model.operators if op.LAW_ID == law)


def control_at(spec, model, time):
    values = fx.cs.control_values(spec, [time])
    return model.CONTROL_TYPE(*(np.asarray(v[0]) for v in values))


def worst(balances):
    return {k: float(np.max(np.abs(np.asarray(v)), initial=0.0)) for k, v in balances.items()}


def closes(model, state, p, label):
    for name, value in worst(model.balances(state, p)).items():
        assert value <= (1e-26 if name in COULOMBS else 1e-15), (label, name, value)


def at_view(model, p, state):
    return model.view(p, state, xp=np)


def opened_and_filled(model, spec, state, p, steps=4):
    """The onset, then insertion and fill half-steps on the parent's furrow."""
    control = control_at(spec, model, fx.ONSET)
    ins, lum = operator(model, insertion_v2.LAW_ID), operator(model, v2.LAW_ID)
    state, ok = ins.event(state, control, p, xp=np, view=lambda s: at_view(model, p, s))
    assert ok
    for _ in range(steps):
        state, ok = ins.half_step(state, H, control, p, xp=np, view=at_view(model, p, state))
        assert ok
        state, ok = lum.half_step(state, H, control, p, xp=np, view=at_view(model, p, state))
        assert ok
    return state


def divide(model, state, p):
    return operator(model, fx.PARTITION).event(
        state,
        SimpleNamespace(partition_due=np.ones(1)),
        p,
        xp=np,
        view=lambda s: at_view(model, p, s),
    )


@pytest.mark.parametrize("asymmetric", [False, True])
def test_the_lumen_is_continuous_across_a_birth(asymmetric):
    kw = dict(f=0.75, area_fraction=0.6, carriers={"Na": 0.5, "K": 0.5}) if asymmetric else {}
    spec, model, state, p = bind(fx.cleft_divided(**kw))
    grown = opened_and_filled(model, spec, state, p)
    live = at_view(model, p, grown).membrane_active
    before = v2.target_increment(grown, p, live, xp=np)
    born, ok = divide(model, grown, p)
    assert ok
    after = v2.target_increment(born, p, at_view(model, p, born).membrane_active, xp=np)
    cleft = [c.id for c in spec.model.extracellular].index("cleft")
    assert before[cleft] > 0
    if asymmetric:
        allowance = v2.rounding(born, p, at_view(model, p, born).membrane_active, xp=np)
        assert abs(after[cleft] - before[cleft]) <= allowance[cleft]
    else:
        assert after[cleft] == before[cleft]
    control = control_at(spec, model, fx.EVENT)
    filled, ok = operator(model, v2.LAW_ID).half_step(
        born, H, control, p, xp=np, view=at_view(model, p, born)
    )
    assert ok
    for a, b in zip(filled, born, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b))  # No fill: selected bitwise.


def test_closed_facing_patches_hold_no_growth():
    spec, model, state, p = bind(fx.cleft_divided())
    patches = [m.id for m in spec.model.membranes]
    kids = [patches.index(k) for k in ("furrow_d1", "furrow_d2")]
    grown = opened_and_filled(model, spec, state, p)
    every = np.ones_like(p.lumen_facing)
    increment = np.asarray(grown.membrane_area_increment_m2)
    assert not increment[kids].any() and increment[patches.index("furrow")] > 0
    live = at_view(model, p, grown).membrane_active
    assert np.array_equal(
        v2.target_increment(grown, p, live, xp=np), v2.target_increment(grown, p, every, xp=np)
    )
    born, _ = divide(model, grown, p)
    assert np.asarray(born.membrane_area_increment_m2)[patches.index("furrow")] == 0.0  # Retired.
    live = at_view(model, p, born).membrane_active
    assert np.array_equal(
        v2.target_increment(born, p, live, xp=np), v2.target_increment(born, p, every, xp=np)
    )


def test_the_closed_lumen_is_padding():
    spec, model, state, p = bind(fx.cleft_divided())
    cleft = [c.id for c in spec.model.extracellular].index("cleft")
    q = at_view(model, p, state)
    assert not q.outside_active[cleft] and not q.extracellular_amount_reference[:, cleft].any()
    assert adapter.domain_valid(adapter.inner_state(state), q, q.active, xp=np)
    op = operator(model, v2.LAW_ID)
    control = control_at(spec, model, 0.0)
    columns = op.observe(None, state, control, p, q, model, spec)
    assert (
        not columns["lumen_volume_pL"][cleft]
        and not columns["lumen_concentration_mM"][:, cleft].any()
    )
    opened, _ = operator(model, insertion_v2.LAW_ID).event(
        state, control_at(spec, model, fx.ONSET), p, xp=np, view=lambda s: at_view(model, p, s)
    )
    q = at_view(model, p, opened)
    columns = op.observe(None, opened, control, p, q, model, spec)
    declared = p.extracellular_amount_reference[:, cleft] / p.extracellular_volume[cleft]
    assert columns["lumen_volume_pL"][cleft] == p.extracellular_volume[cleft]
    assert np.allclose(columns["lumen_concentration_mM"][:, cleft], declared, rtol=1e-15)


def as_v2(raw):
    raw = copy.deepcopy(raw)
    for block in raw["model"]["operators"]:
        block["law"] = {insertion_v1.LAW_ID: insertion_v2.LAW_ID, v1.LAW_ID: v2.LAW_ID}.get(
            block["law"], block["law"]
        )
    return raw


def test_v2_reproduces_v1_fills_with_one_facing_patch():
    raw = ifx.with_operators(ifx.cleft_cell(), ifx.furrow_insertion(onset=0.002))
    raw["model"]["operators"].append(
        dict(law=v1.LAW_ID, lumens=[dict(node_id="cleft", source_id="bath_0", gap_width_m=2e-6)])
    )
    spec1, m1, s1, p1 = bind(raw)
    spec2, m2, s2, p2 = bind(as_v2(raw))
    c1, c2 = control_at(spec1, m1, 0.002), control_at(spec2, m2, 0.002)
    i1, i2 = operator(m1, insertion_v1.LAW_ID), operator(m2, insertion_v2.LAW_ID)
    l1, l2 = operator(m1, v1.LAW_ID), operator(m2, v2.LAW_ID)
    s1, _ = i1.event(s1, c1, p1, xp=np)
    s2, _ = i2.event(s2, c2, p2, xp=np, view=lambda s: m2.view(p2, s, xp=np))
    for _ in range(3):
        s1, _ = i1.half_step(s1, H, c1, p1, xp=np)
        s2, _ = i2.half_step(s2, H, c2, p2, xp=np, view=m2.view(p2, s2, xp=np))
        s1, ok1 = l1.half_step(s1, H, c1, p1, xp=np, view=m1.view(p1, s1, xp=np))
        s2, ok2 = l2.half_step(s2, H, c2, p2, xp=np, view=m2.view(p2, s2, xp=np))
        assert ok1 and ok2
    assert s1.lumen_volume_increment_pL.max() > 0
    for name in type(s1)._fields:
        a, b = np.asarray(getattr(s1, name)), np.asarray(getattr(s2, name))
        assert np.allclose(a, b, rtol=1e-14, atol=0), name
    b1, b2 = m1.balances(s1, p1), m2.balances(s2, p2)
    for name in b1:
        tol = 1e-26 if name in COULOMBS else 1e-15
        diff = np.max(np.abs(np.asarray(b1[name]) - np.asarray(b2[name])), initial=0.0)
        assert diff <= tol and worst(b2)[name] <= tol, name


def test_the_combined_world_walks_through_onset_partition_and_fill():
    """Onset, insertion and fill on the parent, an asymmetric partition, then insertion on the
    daughters' furrows and fill: every ledger closes at each stage, and the cleft stays open."""
    spec, model, state, p = bind(
        fx.cleft_divided(f=0.75, area_fraction=0.6, carriers={"Na": 0.5, "K": 0.5})
    )
    cleft = [c.id for c in spec.model.extracellular].index("cleft")
    closes(model, state, p, "row 0")
    grown = opened_and_filled(model, spec, state, p)
    closes(model, grown, p, "before the division")
    born, ok = divide(model, grown, p)
    assert ok and at_view(model, p, born).outside_active[cleft]
    closes(model, born, p, "after the division")
    control = control_at(spec, model, fx.EVENT)
    ins, lum = operator(model, insertion_v2.LAW_ID), operator(model, v2.LAW_ID)
    state = born
    for _ in range(4):
        state, ok = ins.half_step(state, H, control, p, xp=np, view=at_view(model, p, state))
        assert ok
        state, ok = lum.half_step(state, H, control, p, xp=np, view=at_view(model, p, state))
        assert ok
    assert state.lumen_volume_increment_pL[cleft] > born.lumen_volume_increment_pL[cleft]
    closes(model, state, p, "after the daughters' insertion")
    q = at_view(model, p, state)
    assert adapter.domain_valid(adapter.inner_state(state), q, q.active, xp=np)
    assert model.domain_valid(state, p, p.active, xp=np)


def retired_ancestor_facing(raw):
    """The daughters' furrows open at an onset after the division, so the parent's furrow, retired
    before it, faces the cleft without being an onset patch or a descendant of one (insertion@2
    admits it: it is closed at the onset)."""
    for row in raw["experiment"]["insertion_controls"]:
        if row["membrane_id"] == "furrow":
            row.update(onset_time=None, schedule=[dict(time=0.0, rate_m2_per_s=0.0)])
        else:
            row.update(
                onset_time=0.003,
                schedule=[dict(time=0.0, rate_m2_per_s=0.0), dict(time=0.003, rate_m2_per_s=1e-12)],
            )


def wrong_onset_volume(raw):
    lumen = next(op for op in raw["model"]["operators"] if op["law"] == fx.LUMEN2)
    lumen["lumens"][0]["gap_width_m"] *= 1.5


def not_an_onset_node(raw):
    lumen = next(op for op in raw["model"]["operators"] if op["law"] == fx.LUMEN2)
    lumen["lumens"][0]["node_id"] = "bath_0"


@pytest.mark.parametrize(
    "change, message",
    [
        (retired_ancestor_facing, "neither an onset patch nor a partition-born descendant"),
        (wrong_onset_volume, "onset volume must be w A_on / 2"),
        (not_an_onset_node, "finite outside node"),
    ],
)
def test_definition_refusals(change, message):
    raw = fx.cleft_divided()
    change(raw)
    with pytest.raises(ConfigError, match=message):
        parse_spec(raw)


def test_the_quartered_world_walks_through_two_onsets_and_partitions():
    """1 -> 2 -> 4 with second onsets (tests/partition_fixtures.cleft_quartered), walked in
    NumPy one step's split parts at a time: the first cleft opens at its onset, the daughters'
    second clefts at theirs, and every cleft stays open across both partitions. Every ledger
    closes and @3's domain holds at the view at each record."""
    spec, model, state, p = bind(fx.cleft_quartered(injection=1e-12))
    ops = {op.LAW_ID: op for op in model.operators}
    nodes = [c.id for c in spec.model.extracellular]
    s = state
    for t in (0.0, 0.001, 0.002, 0.003, 0.004, 0.005):
        control = control_at(spec, model, t)
        for law in (insertion_v2.LAW_ID, fx.PARTITION):
            s, ok = ops[law].event(s, control, p, xp=np, view=lambda x: at_view(model, p, x))
            assert ok, (law, t)
        for _ in range(2):
            for law in (insertion_v2.LAW_ID, v2.LAW_ID, fx.BRIDGE, fx.INJECTION):
                kw = dict(view=at_view(model, p, s)) if ops[law].BOOKS_AT_VIEW else {}
                s, ok = ops[law].half_step(s, H, control, p, xp=np, **kw)
                assert ok is None or ok, (law, t)
        q = at_view(model, p, s)
        assert adapter.domain_valid(adapter.inner_state(s), q, q.active, xp=np), t
        closes(model, s, p, f"t = {t}")
        lumens = {k: s.lumen_volume_increment_pL[nodes.index(k)] for k in nodes[1:]}
        assert (lumens["cleft"] > 0) == (t >= fx.ONSET)
        assert (lumens["cleft2_d1"] > 0) == (lumens["cleft2_d2"] > 0) == (t >= fx.SECOND_ONSET)
    assert list(q.active.astype(int)) == [0, 0, 0, 1, 1, 1, 1]
    assert q.outside_active.all()
