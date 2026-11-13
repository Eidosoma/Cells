"""Tier-1 smoke test of scheduled_membrane_insertion@2 (docs/CELL_DIVISION_S5_DESIGN.md §5.1).

In NumPy (no compile):
* the onset with a pending facing patch: in the furrow division world the cleft and the furrow
  open at the onset, while the daughters' furrows facing the cleft stay closed (the partition's
  closure); the onset moves no charge, @3's domain holds at the view and every ledger stays 0;
* rates only on live patches: refused at the definition against the partition's schedule (a
  daughter's furrow before its birth, the parent's after it retires) and at run time against
  the view's mask;
* the generalised onset rule's refusals: a patch of a live cell facing the onset node, an onset
  on a pending daughter, an onset at a division's time, and a partition listed before the
  insertion (its step-check share reads the inserted area);
* @2 reproduces @1's half-steps where @1 applies, with image charge and heat at stake: S2's two
  clamps, and the cleft cell with a charged history; each ledger equals @1's;
* every ledger is 0 at row 0 and across the onset (no double booking of the view's terms).
The compiled guards are test_cleft_division_runs.py.
"""

import copy
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.core.specs import ConfigError, parse_spec
from cells.models import pump_composite_adapter as adapter
from cells.models.operators import membrane_insertion as v1
from cells.models.operators import membrane_insertion_v2 as v2
from cells.models.registry import get_model
from tests import membrane_insertion_fixtures as ifx
from tests import partition_fixtures as fx

H = 0.5 * fx.DT
COULOMBS = (
    "charge",
    "electrode",
    "global_charge",
)  # Ledgers in C; the others' rounding is pJ-scale.


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


def onset(model, state, p, control):
    op = operator(model, v2.LAW_ID)
    return op.event(state, control, p, xp=np, view=lambda s: model.view(p, s, xp=np))


def worst(balances):
    return {k: float(np.max(np.abs(np.asarray(v)), initial=0.0)) for k, v in balances.items()}


def test_the_onset_opens_with_a_pending_facing_patch():
    spec, model, state, p = bind(fx.cleft_divided())
    patches = [m.id for m in spec.model.membranes]
    furrow, kids = patches.index("furrow"), [patches.index(k) for k in ("furrow_d1", "furrow_d2")]
    cleft = [c.id for c in spec.model.extracellular].index("cleft")
    q = model.view(p, state, xp=np)
    assert not q.membrane_active[furrow] and not q.outside_active[cleft]
    assert not q.extracellular_amount_reference[:, cleft].any()  # Padding.
    opened, ok = onset(model, state, p, control_at(spec, model, fx.ONSET))
    assert ok
    q = model.view(p, opened, xp=np)
    assert q.membrane_active[furrow] and q.outside_active[cleft]
    assert not q.membrane_active[kids].any()  # Pending daughters stay closed.
    assert np.array_equal(
        q.extracellular_amount_reference[:, cleft], p.extracellular_amount_reference[:, cleft]
    )
    assert adapter.domain_valid(adapter.inner_state(opened), q, q.active, xp=np)
    v = adapter.patch_voltages(adapter.node_potentials(opened, q, xp=np), q, xp=np)
    assert abs(v[furrow]) <= 1e-12 * abs(v[0])  # The node follows its cell: no charge moves.
    for name, value in worst(model.balances(opened, p)).items():
        assert value <= (1e-26 if name in ("charge", "electrode") else 1e-16), name


def daughter_rate_before_birth(raw):
    row = next(
        c for c in raw["experiment"]["insertion_controls"] if c["membrane_id"] == "furrow_d1"
    )
    row["schedule"].insert(1, dict(time=fx.ONSET, rate_m2_per_s=fx.FURROW_RATE))


def parent_rate_after_retirement(raw):
    row = next(c for c in raw["experiment"]["insertion_controls"] if c["membrane_id"] == "furrow")
    row["schedule"] = row["schedule"][:2]  # The furrow's rate never stops.


def onset_on_a_pending_daughter(raw):
    for row in raw["experiment"]["insertion_controls"]:
        if row["membrane_id"] == "furrow":
            row.update(onset_time=None, schedule=[dict(time=0.0, rate_m2_per_s=0.0)])
        if row["membrane_id"] == "furrow_d1":
            row.update(onset_time=fx.ONSET)
    lumen = next(op for op in raw["model"]["operators"] if op["law"] == fx.LUMEN2)
    raw["model"]["operators"].remove(lumen)


def onset_at_the_division(raw):
    row = next(c for c in raw["experiment"]["insertion_controls"] if c["membrane_id"] == "furrow")
    row.update(onset_time=fx.EVENT, schedule=[dict(time=0.0, rate_m2_per_s=0.0)])


def partition_first(raw):
    ops = raw["model"]["operators"]
    partition = next(op for op in ops if op["law"] == fx.PARTITION)
    ops.remove(partition)
    ops.insert(1, partition)


@pytest.mark.parametrize(
    "change, message",
    [
        (daughter_rate_before_birth, "outside its cell's living interval"),
        (parent_rate_after_retirement, "outside its cell's living interval"),
        (onset_on_a_pending_daughter, "its cell is live at its onset"),
        (onset_at_the_division, "at a division's time"),
        (partition_first, "precedes isopotential_partition@1"),
    ],
)
def test_definition_refusals(change, message):
    raw = fx.cleft_divided()
    change(raw)
    with pytest.raises(ConfigError, match=message):
        parse_spec(raw)


def test_a_live_patch_facing_an_onset_node_is_refused():
    """Without a partition (S2's cleft cell), a second, ordinary patch of the cell facing the
    cleft would open with the node at a nonzero voltage."""
    base = ifx.cleft_cell()
    extra = copy.deepcopy(next(m for m in base["model"]["membranes"] if m["id"] == "furrow"))
    extra.update(id="side", area_m2=1e-12, capacitance_F=0.05e-12)
    base["model"]["membranes"].append(extra)
    base["experiment"]["membrane_controls"].append(
        dict(membrane_id="side", schedule=[dict(time=0.0, availability=1.0)])
    )
    base["execution"]["membrane_capacity"] += 1
    raw = as_v2(ifx.with_operators(base, ifx.furrow_insertion(onset=0.002)))
    with pytest.raises(ConfigError, match="opens with the node at its onset, or is closed then"):
        parse_spec(raw)


def test_a_rate_on_a_closed_patch_is_refused_at_run_time():
    spec, model, state, p = bind(fx.cleft_divided())
    control = control_at(spec, model, fx.ONSET)
    opened, _ = onset(model, state, p, control)
    rate = np.array(control.insertion_rate_m2_s, copy=True)
    rate[[m.id for m in spec.model.membranes].index("furrow_d1")] = fx.FURROW_RATE
    op = operator(model, v2.LAW_ID)
    _, ok = op.half_step(
        opened,
        H,
        control._replace(insertion_rate_m2_s=rate),
        p,
        xp=np,
        view=model.view(p, opened, xp=np),
    )
    assert not ok
    _, ok = op.half_step(opened, H, control, p, xp=np, view=model.view(p, opened, xp=np))
    assert ok


def as_v2(raw):
    raw = copy.deepcopy(raw)
    for block in raw["model"]["operators"]:
        if block["law"] == v1.LAW_ID:
            block["law"] = v2.LAW_ID
    return raw


def charged(state, p, cells, cleft=None):
    """A history: K moved into the cells (and the cleft), so the patches hold voltages."""
    s = state._replace(
        amount_increment=np.array(state.amount_increment, copy=True),
        extracellular_amount_increment=np.array(state.extracellular_amount_increment, copy=True),
    )
    s.amount_increment[1, cells] += 3e-4
    if cleft is not None:
        s.extracellular_amount_increment[1, cleft] -= 1e-6
    return s


@pytest.mark.parametrize("world", ["two_clamps", "cleft"])
def test_v2_reproduces_v1_half_steps(world):
    if world == "two_clamps":
        insertion = {"membrane_b": ({}, None, [(0.0, 2e-12)])}
        raw = ifx.with_operators(ifx.two_clamps(), insertion)
    else:
        raw = ifx.with_operators(ifx.cleft_cell(), ifx.furrow_insertion(onset=0.002))
    spec1, m1, s1, p1 = bind(raw)
    spec2, m2, s2, p2 = bind(as_v2(raw))
    time = 0.0 if world == "two_clamps" else 0.002
    c1, c2 = control_at(spec1, m1, time), control_at(spec2, m2, time)
    op1, op2 = operator(m1, v1.LAW_ID), operator(m2, v2.LAW_ID)
    if world == "cleft":
        s1, _ = op1.event(s1, c1, p1, xp=np)
        s2, _ = op2.event(s2, c2, p2, xp=np, view=lambda s: m2.view(p2, s, xp=np))
    s1, s2 = (
        charged(s1, p1, [0], 1 if world == "cleft" else None),
        charged(s2, p2, [0], 1 if world == "cleft" else None),
    )
    for _ in range(3):
        s1, ok1 = op1.half_step(s1, H, c1, p1, xp=np)
        s2, ok2 = op2.half_step(s2, H, c2, p2, xp=np, view=m2.view(p2, s2, xp=np))
        assert ok1 and ok2
    assert np.abs(s1.insertion_image_charge_C).max() > 0 or world == "cleft"
    assert s1.insertion_dissipated_energy_pJ.max() > 0  # Heat is at stake.
    for name in type(s1)._fields:
        a, b = np.asarray(getattr(s1, name)), np.asarray(getattr(s2, name))
        assert np.allclose(a, b, rtol=1e-14, atol=0), name
    b1, b2 = m1.balances(s1, p1), m2.balances(s2, p2)
    for name in b1:  # Equal ledgers: no term is booked twice or missed (the history is synthetic,
        # so they need not close; test_every_ledger_is_zero... checks closure).
        tol = 1e-26 if name in COULOMBS else 1e-15
        diff = np.max(np.abs(np.asarray(b1[name]) - np.asarray(b2[name])), initial=0.0)
        assert diff <= tol, name


def test_every_ledger_is_zero_at_row_zero_and_across_the_onset():
    raw = as_v2(ifx.with_operators(ifx.cleft_cell(), ifx.furrow_insertion(onset=0.002)))
    spec, model, state, p = bind(raw)
    for name, value in worst(model.balances(state, p)).items():
        assert value <= (1e-26 if name == "charge" else 0.0), name
    control = control_at(spec, model, 0.002)
    opened, ok = onset(model, state, p, control)
    assert ok
    for name, value in worst(model.balances(opened, p)).items():
        assert value <= (1e-26 if name in ("charge", "electrode") else 1e-16), name
    grown = opened
    op = operator(model, v2.LAW_ID)
    for _ in range(4):
        grown, ok = op.half_step(grown, H, control, p, xp=np, view=model.view(p, grown, xp=np))
        assert ok
    for name, value in worst(model.balances(grown, p)).items():
        assert value <= (1e-26 if name in ("charge", "electrode", "global_charge") else 1e-15), name


def test_the_view_is_the_partitions_and_the_onsets_conjunction():
    """Before the division the daughters' furrows are closed by the partition even after the
    onset; after it the parent's furrow is closed by the partition while the onset keeps the
    cleft open."""
    spec, model, state, p = bind(fx.cleft_divided())
    opened, _ = onset(model, state, p, control_at(spec, model, fx.ONSET))
    partition = operator(model, fx.PARTITION)
    born, ok = partition.event(
        opened,
        SimpleNamespace(partition_due=np.ones(1)),
        p,
        xp=np,
        view=lambda s: model.view(p, s, xp=np),
    )
    assert ok
    patches = [m.id for m in spec.model.membranes]
    assert patches == [
        "membrane_0",
        "furrow",
        "membrane_0_d1",
        "membrane_0_d2",
        "furrow_d1",
        "furrow_d2",
    ]
    assert list(model.view(p, opened, xp=np).membrane_active.astype(int)) == [1, 1, 0, 0, 0, 0]
    q = model.view(p, born, xp=np)
    assert list(q.membrane_active.astype(int)) == [0, 0, 1, 1, 1, 1]
    assert q.outside_active[[c.id for c in spec.model.extracellular].index("cleft")]
