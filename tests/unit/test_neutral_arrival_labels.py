"""neutral_arrival_labels@1 (FR-42 stage 1, D289): neutral arrival-time labels as shares of a
physical row (operators/species_labels.py, numerics/label_shares.py).

The share update alone, in NumPy (no world; about 2 s):
- exact for a constant per-molecule rate with arrivals, and the shares kept bit for bit without
  arrivals;
- its domain on random and extreme inputs: zero shares, tiny amounts, a large survival exponent and
  16 labels;
- its order when the rates vary within an application: the split between old and new material is
  off by (a' k - a k') h^3 / 12, halving by 8 with h.

One compiled world, run labelled and unlabelled, and one resume (three compiles, about 70 s;
FR-42's own checks as engine rows, so a regression in the composite's hook or a reporter shows
here). Every physical field, observation and diagnostic of the labelled run is the unlabelled
run's bit for bit. It holds:
- the reference case dN/dt = -N^2 (2A -> B mass action, local_species_reactions@1) in five
  independent pools: one label, the reference's two (older and new, 2:1), several unequal with an
  empty one, and two near the edges of the range (dt L = 0.9 under the stage condition, and the
  trace). With no arrivals the shares are kept bit for bit: the new cohort is 1/4 of 3/4 at t = 1
  (blank subtraction would give 1/12);
- S, with a window of arrivals and older material present (FR-42's check 2): production and
  clearance in a cell (turnover, exact) and a reaction source and sink at an outside node. The
  cell's cohort matches the analytic solution at rounding, at the window's two boundaries too
  (arrivals in the step that starts at its start join it; in the step that starts at its end they
  do not), with its label reused for a second window, and a checkpoint resumes bit for bit
  through a snapshot;
- C, a second population with its own loss, unlabelled (check 3).

Definitions refused, each naming the FR-42 stage that lifts it (parses only): in-step movers (a
face, a membrane and a junction route, a transporter kind's role and finite fuel), exchange, a
passive reaction, a bath schedule, D1's families, a second owner and malformed declarations.
"""

import copy
import math

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.runner import run
from cells.numerics import label_shares as ls
from cells.registry.inventory_species import add_inventory_species
from validation.tissue import bath_schedule_fixtures as bfx
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rfx

LAW = "neutral_arrival_labels@1"
EPS = math.ulp(1.0)


def bits(value):
    return np.asarray(value).tobytes()


def with_labels(raw, species, arrivals=()):
    """species: (id, labels, {node: {label: share}}); arrivals: (species, [(time, label), ...])."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(
        dict(
            law=LAW,
            species=[
                dict(
                    id=name,
                    labels=list(labels),
                    initial=[dict(node=n, shares=dict(s)) for n, s in initial.items()],
                )
                for name, labels, initial in species
            ],
        )
    )
    out["experiment"]["label_arrivals"] = [
        dict(species=name, schedule=[dict(time=t, label=label) for t, label in changes])
        for name, changes in arrivals
    ]
    return out


def same_physics(labelled, plain):
    """Every field, observation and diagnostic of the unlabelled run, bit for bit, in the labelled
    one; the labelled run adds only the label owner's fields."""
    for name in type(plain.history)._fields:
        assert bits(getattr(labelled.history, name)) == bits(getattr(plain.history, name)), name
    for name, value in vars(plain.observations).items():
        assert bits(getattr(labelled.observations, name)) == bits(value), name
    assert labelled.diagnostics == plain.diagnostics
    extra = set(type(labelled.history)._fields) - set(type(plain.history)._fields)
    assert extra == {"label_share", "label_outside_share", "label_closure_relative"}


# ------------------------------------------------------------------ the share update alone


@pytest.mark.parametrize(
    "n0, kh, arrived, older",
    [
        (1.0, 0.5, 0.2, 0.6),  # A typical half-step.
        (3.0, 1e-7, 1e-4, 1.0),  # A slow loss: phi's series.
        (1e-9, 3.0, 1e-9, 0.3),  # A trace pool.
        (1.0, 1e3, 5.0, 0.5),  # Stiff clearance: the pool replaced within the step.
        (2.0, 0.0, 0.1, 0.7),  # No loss: arrivals add.
    ],
)
def test_the_update_is_exact_for_a_constant_rate(n0, kh, arrived, older):
    """With a constant per-molecule rate k and arrival rate over the application, the old material
    is n0 s e^(-kh) and the new I (1 - e^(-kh)) / (kh); the update recovers both from n0, n1 and I
    alone. Without arrivals the shares are the start's, bit for bit, whatever n1."""
    phi = 1.0 if kh == 0 else -math.expm1(-kh) / kh
    n1 = n0 * math.exp(-kh) + arrived * phi
    shares = np.array([[[older], [1 - older], [0.0]]])
    present = np.ones((1, 3), dtype=bool)
    into = np.array([[[0.0], [0.0], [arrived]]])
    new = ls.advance(shares, np.array([[n0]]), np.array([[n1]]), into, present, xp=np)
    expected = np.array([older, 1 - older, 0.0]) * n0 * math.exp(-kh) + [0.0, 0.0, arrived * phi]
    assert np.allclose(new[0, :, 0], expected / expected.sum(), rtol=1e-13, atol=0)
    kept = ls.advance(shares, np.array([[n0]]), np.array([[0.3 * n0]]), 0 * into, present, xp=np)
    assert bits(kept) == bits(shares)


def test_the_domain_holds_on_random_and_extreme_inputs():
    """Shares in [0, 1] summing to 1 within the domain's ulps, an undeclared label 0 and a zero
    share kept zero where its label received nothing: amounts from 1e-15 to 1e3 fmol, survival
    exponents to 1e6, 16 labels, arrivals at one label or spread."""
    rng = np.random.default_rng(42)
    m, labels, nodes = 3, 16, 400
    present = np.ones((m, labels), dtype=bool)
    present[2, 9:] = False
    shares = rng.dirichlet(np.full(labels, 0.3), size=(m, nodes)).transpose(0, 2, 1)
    shares[rng.random(shares.shape) < 0.3] = 0.0
    shares = np.where(present[:, :, None], shares, 0.0)
    shares[:, 0, :] += 1.0 - shares.sum(axis=1)  # The base takes the rest: sums of exactly 1.
    shares = np.maximum(shares, 0.0)
    shares /= shares.sum(axis=1, keepdims=True)
    n0 = 10.0 ** rng.uniform(-15, 3, size=(m, nodes))
    u = np.where(rng.random((m, nodes)) < 0.1, 0.0, 10.0 ** rng.uniform(-8, 6, size=(m, nodes)))
    arrived = np.where(
        rng.random((m, nodes)) < 0.2, 0.0, n0 * 10.0 ** rng.uniform(-6, 4, (m, nodes))
    )
    spread = rng.random((m, labels, nodes)) * present[:, :, None]
    one = np.zeros_like(spread)
    one[:, 1, :] = 1.0
    weights = np.where(rng.random((m, 1, nodes)) < 0.5, one, spread)
    weights /= weights.sum(axis=1, keepdims=True)
    into = arrived[:, None, :] * weights
    n1 = n0 * np.exp(-u) + arrived * ls.phi(u, xp=np)
    assert ls.domain_valid(shares, present, xp=np)
    new = ls.advance(shares, n0, n1, into, present, xp=np)
    assert ls.domain_valid(new, present, xp=np)
    untouched = (shares == 0) & (into == 0)
    assert np.all(new[untouched] == 0)
    quiet = arrived == 0
    for j in range(m):
        assert bits(new[j][:, quiet[j]]) == bits(shares[j][:, quiet[j]])


def test_the_split_is_second_order_when_the_rates_vary():
    """Over one application of length h with k(t) = k0 + k1 t and arrivals a(t) = a0 + a1 t, the
    update's new material exceeds the exact by (a0 k1 - a1 k0) h^3 / 12 + O(h^4) (the module
    docstring): the error falls 8-fold per halving (7.7 to 7.9 here) and is within 2% of that
    coefficient at the smallest h (0.8%)."""
    k0, k1, a0, a1, n0 = 0.8, 3.0, 0.5, -2.0, 1.0
    nodes, weights = np.polynomial.legendre.leggauss(40)

    def exact(h):
        big_k = lambda t: k0 * t + k1 * t * t / 2  # noqa: E731
        t = 0.5 * h * (nodes + 1)
        new = 0.5 * h * np.sum(weights * (a0 + a1 * t) * np.exp(-(big_k(h) - big_k(t))))
        return n0 * math.exp(-big_k(h)), new

    errors = []
    for h in (0.1, 0.05, 0.025, 0.0125):
        old, new = exact(h)
        arrived = a0 * h + a1 * h * h / 2
        shares = np.array([[[1.0], [0.0]]])
        into = np.array([[[0.0], [arrived]]])
        n1 = old + new
        present = np.ones((1, 2), dtype=bool)
        out = ls.advance(shares, np.array([[n0]]), np.array([[n1]]), into, present, xp=np)
        errors.append(float(out[0, 1, 0]) * n1 - new)
    errors = np.asarray(errors)
    assert np.allclose(errors[:-1] / errors[1:], 8.0, rtol=0.05)
    leading = (a0 * k1 - a1 * k0) * 0.0125**3 / 12
    assert abs(errors[-1] / leading - 1) < 0.02


# ------------------------------------------------------------------ one compiled world

H = 1 / 64  # dt, exact in binary, so every time below is a grid point exactly.
TS, TE, END = 16 * H, 32 * H, 64 * H  # S's window [0.25, 0.5) and the end, 1.0 s.
TR = 48 * H  # The cohort's label reused from 0.75 s to the end: its older material survives.
WINDOWS = ((TS, TE), (TR, END))
OBSERVE = [0.0, TS, TS + H, TE, TE + H, TR, END]
# The -N^2 reference in five independent pools: 2A -> B at k = 0.5 /(mM s) in the 1 pL cell, so
# dN/dt = -N^2 in fmol and s, each A's per-molecule loss rate its concentration in mM per s:
# (mM, labels, the cell's initial shares).
POOLS = {
    "A1": (3.0, ["all"], {"all": 1.0}),
    "A2": (3.0, ["older", "new"], {"older": 2 / 3, "new": 1 / 3}),
    "A3": (3.0, ["base", "x", "y", "empty"], {"base": 0.5, "x": 0.3, "y": 0.2}),
    "A4": (57.6, ["older", "new"], {"older": 0.9, "new": 0.1}),  # dt L = 0.9: the stage edge.
    "A5": (1e-6, ["older", "new", "empty"], {"older": 0.25, "new": 0.75}),  # Near the trace.
}
P, K = 0.4, 0.5  # S in the cell: production (fmol/s) and clearance (1/s), turnover, exact.
SOURCE, SINK = 0.2, 0.3  # S at the outside node: a source (mM/s in 1 pL) and a sink (1/s).
C_SINK = 2.0  # C, the second population, unlabelled: its own first-order loss (1/s).


def world():
    """The face-free world: S (turnover in the cell, reactions at ecs_0), C and the pools."""
    raw = fx.world(
        faces=(),
        concentrations_mM={"cell_0": 1.0, "ecs_0": 0.5},
        end=END,
        dt=H,
        observation_times=OBSERVE,
    )
    extra = {"C": 2.0, **{name: mM for name, (mM, _, _) in POOLS.items()}, "B": None}
    for name, mM in extra.items():
        raw = add_inventory_species(
            raw,
            name,
            trace_mM=fx.TRACE_mM,
            diffusivity_m2_per_s=fx.D_S,
            floor_fmol=fx.FLOOR_FMOL,
            concentrations_mM=None if mM is None else {"cell_0": mM},
        )
    raw = fx.with_turnover(
        raw,
        [("make", "cell_0", "production"), ("clear", "cell_0", "clearance")],
        [("make", "cell_0", [(0.0, P)]), ("clear", "cell_0", [(0.0, K)])],
    )
    node, cell = {"outside": ["ecs_0"]}, {"cells": ["cell_0"]}
    reactions = [
        rfx.mass_action("source", node, {}, {"S": 1}, SOURCE),
        rfx.mass_action("sink", node, {"S": 1}, {}, SINK),
        rfx.mass_action("sink_c", cell, {"C": 1}, {}, C_SINK),
        *(rfx.mass_action(f"decay_{n}", cell, {n: 2}, {"B": 1}, 0.5) for n in POOLS),
    ]
    species = [rfx.species("S", moieties={"Y": 1}), rfx.species("C", moieties={"Z": 1})]
    species += [rfx.species(name, moieties={"X": 1}) for name in POOLS]
    species.append(rfx.species("B", moieties={"X": 2}))
    return rfx.with_reactions(raw, species, reactions, rfx.always([r["id"] for r in reactions]))


def labelled(raw):
    """The pools as declared (no arrivals), and S with a window of arrivals into its cohort."""
    pools = [(n, labels, {"cell_0": s}) for n, (_, labels, s) in POOLS.items()]
    return with_labels(
        raw,
        [*pools, ("S", ["base", "cohort", "empty"], {"ecs_0": {"base": 0.25, "cohort": 0.75}})],
        [("S", [(0.0, "base"), (TS, "cohort"), (TE, "base"), (TR, "cohort")])],
    )


@pytest.fixture(scope="module")
def runs():
    raw = world()
    spec = parse_spec(labelled(raw))
    return spec, run(spec), run(parse_spec(raw))


def test_labels_leave_every_record_of_the_unlabelled_run(runs):
    """Every field, observation and diagnostic, bit for bit (FR-42's check 1 and check 3: C, the
    unlabelled population, keeps its own trajectory; so does each labelled one)."""
    from cells.records import run_view
    from cells.registry.models import get_model

    spec, labelled_run, plain = runs
    same_physics(labelled_run, plain)
    assert np.all(np.asarray(labelled_run.observations.label_closure_relative) <= 64 * EPS)
    # The run view takes the owner's two axes' sets and its label switches as events.
    run_view.prepare(spec, layout=get_model(spec.model).initial_values(spec)[1])


def test_minus_n_squared_keeps_the_shares_and_the_cohort_is_a_quarter(runs):
    """No arrivals: every pool's shares are kept bit for bit, as declared, so the reference's new
    cohort is 1/3 of N(1) = 3/4 (blank subtraction would give 1/12); SSPRK(3,3) at dt = 1/64 puts
    N(1) within 4e-7 of 3/4."""
    spec, labelled_run, _ = runs
    share = np.asarray(labelled_run.observations.label_share)  # [time, species, label, cell]
    for i in range(share.shape[0]):
        assert bits(share[i, : len(POOLS)]) == bits(share[0, : len(POOLS)])
    width = share.shape[2]
    for j, (_, labels, given) in enumerate(POOLS.values()):
        declared = [given.get(label, 0.0) for label in labels] + [0.0] * (width - len(labels))
        assert bits(share[0, j, :, 0]) == bits(np.asarray(declared))
    n = np.asarray(labelled_run.observations.amount)[:, list(spec.model.species_ids).index("A2"), 0]
    assert abs(n[-1] - 0.75) < 1e-6
    assert abs(n[-1] * share[-1, 1, 1, 0] - 0.25) < 1e-6


def arrived(t, rate, loss):
    """What a constant arrival rate into each of WINDOWS (the arrivals of the steps that start in
    it) leaves at t under a first-order loss: each window's own, carried to t."""
    return sum(
        (rate / loss)
        * -math.expm1(-loss * min(max(t - a, 0.0), b - a))
        * math.exp(-loss * max(t - b, 0.0))
        for a, b in WINDOWS
    )


def cell_cohort(t):
    """The windows' production in the cell, cleared at K."""
    return arrived(t, P, K)


def node_cohort(t):
    """The node's initial 3/4 and the windows' source, each lost at SINK."""
    return 0.75 * 0.5 * math.exp(-SINK * t) + arrived(t, SOURCE, SINK)


def test_a_window_follows_its_cohort_exactly_at_both_boundaries(runs):
    """FR-42's check 2, with older material present, and the label reused for a second window, so
    its first window's survivors count with the second's arrivals: in the cell, where turnover's
    half-steps and the update are both exact, at rounding of the analytic solution; at the node,
    at SSPRK(3,3)'s accuracy."""
    spec, labelled_run, _ = runs
    s, j = list(spec.model.species_ids).index("S"), len(POOLS)
    obs = labelled_run.observations
    cell = np.asarray(obs.amount)[:, s, 0] * np.asarray(obs.label_share)[:, j, 1, 0]
    node = (
        np.asarray(obs.extracellular_amount)[:, s, 1]
        * np.asarray(obs.label_outside_share)[:, j, 1, 1]
    )
    for i, t in enumerate(OBSERVE):
        assert cell[i] == pytest.approx(cell_cohort(t), rel=1e-13, abs=0), t
        assert node[i] == pytest.approx(node_cohort(t), rel=1e-9), t
    assert cell[1] == 0.0  # At the window's start nothing has arrived yet.
    assert cell[2] == pytest.approx((P / K) * -math.expm1(-K * H), rel=1e-13)  # Its first step.
    assert cell[4] == pytest.approx(cell[3] * math.exp(-K * H), rel=1e-13)  # The end's step: none.
    assert cell[5] == pytest.approx(cell[3] * math.exp(-K * (TR - TE)), rel=1e-13)  # Survivors.
    shares = np.asarray(obs.label_share)[:, j, :, 0]
    assert np.all(shares[:, 2:] == 0.0)  # The empty label and the padding.
    assert np.all(np.abs(shares.sum(axis=1) - 1) <= 64 * EPS)  # All of S's material.


def test_a_labelled_checkpoint_resumes_bit_for_bit(runs, tmp_path):
    """Through a written snapshot, from inside the window (the cohort's share nonzero), so the
    resumed steps carry the shares and cross the window's end (one compile)."""
    from cells.records.io import load_snapshot, write_snapshot

    _, labelled_run, _ = runs
    checkpoint = labelled_run.checkpoint_at(TS + H)
    assert np.asarray(checkpoint.state.label_share)[len(POOLS), 1, 0] > 0
    write_snapshot(tmp_path / "checkpoint", labelled_run.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(resumed.history, labelled_run.history, strict=True):
        assert bits(a) == bits(np.asarray(b)[checkpoint.step_index :])


# ------------------------------------------------------------------ refused definitions


def face_free():
    return fx.world(faces=(), concentrations_mM={"cell_0": 1.0}, end=0.004, dt=1e-3)


def labelled_s(raw, labels=("base", "new"), initial=None, arrivals=()):
    return with_labels(raw, [("S", list(labels), initial or {})], arrivals)


def family(raw):
    for name in ("L", "U"):
        raw = add_inventory_species(
            raw, name, trace_mM=1e-3, diffusivity_m2_per_s=fx.D_S, floor_fmol=fx.FLOOR_FMOL
        )
    raw["model"]["label_families"] = [{"id": "fam", "rows": ["L", "U"]}]
    return with_labels(raw, [("L", ["base"], {})])


def mover(kind):
    """S moved by a membrane or a junction route; a transporter kind's moved role Y, or its finite
    fuel's ATP (tests/unit/test_transporter_kind.py's held world)."""
    from cells.definitions import pump_composite_spec as cs
    from cells.kinds import transporter
    from tests.unit import test_transporter_kind as tk

    if kind in ("role", "fuel"):
        fuel = dict(tk.population()["fuel"], kind=transporter.FINITE)
        raw = cs.frozen_definition(tk.held_world(tk.population(fuel=fuel)))
        return with_labels(raw, [("Y" if kind == "role" else "ATP", ["base"], {})])
    cells = (("cell_0", 1.0), ("cell_1", 1.0))
    contacts = (("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_0"))
    raw = fx.world(
        cells=cells,
        contacts=contacts,
        junctions=(("gj_0", "cell_0", "cell_1"),),
        faces=(),
        concentrations_mM={"cell_0": 1.0},
        end=0.004,
        dt=1e-3,
    )
    for entity in raw["model"]["membranes" if kind == "membrane" else "junctions"]:
        if entity["id"] in ("contact_0", "gj_0"):
            entity["permeability_m_per_s"]["S"] = 1e-12
    return labelled_s(raw)


REFUSED = {
    "a membrane route moves it (stage 2)": (
        lambda: mover("membrane"),
        r"moved inside the inner step by membrane contact_0.*FR-42's stage 2",
    ),
    "a junction route moves it (stage 2)": (
        lambda: mover("junction"),
        r"moved inside the inner step by junction gj_0.*FR-42's stage 2",
    ),
    "a kind moves its role (stage 2)": (
        lambda: mover("role"),
        r"Y is moved inside the inner step by cells.transporter@1 .*FR-42's stage 2",
    ),
    "a kind moves its finite fuel (stage 2)": (
        lambda: mover("fuel"),
        r"ATP is moved inside the inner step by cells.transporter@1 .*FR-42's stage 2",
    ),
    "a face moves it (stage 2)": (
        lambda: labelled_s(fx.world(end=0.004, dt=1e-3)),
        r"moved inside the inner step by face face_0.*FR-42's stage 2",
    ),
    "exchange moves it (stage 3)": (
        lambda: labelled_s(
            fx.with_exchange(
                face_free(),
                [("secrete", "contact_0", "export", "first_order")],
                [("secrete", "cell_0", [(0.0, 0.1)])],
            )
        ),
        r"scheduled_species_exchange@1 beside .*FR-42's stage 3 adds them",
    ),
    "a passive reaction moves it (stage 3)": (
        lambda: labelled_s(
            rfx.with_reactions(
                add_inventory_species(
                    face_free(), "P", trace_mM=1e-3, diffusivity_m2_per_s=fx.D_S, floor_fmol=1e-20
                ),
                [rfx.species("S", moieties={"X": 1}), rfx.species("P", moieties={"X": 1})],
                [rfx.passive("relax", {"cells": ["cell_0"]}, {"S": 1}, {"P": 1}, 1.0)],
                rfx.always(["relax"]),
            )
        ),
        r"reaction relax is a passive route on labelled S.*FR-42's stage 3",
    ),
    "a bath schedule changes amounts": (
        lambda: labelled_s(
            bfx.with_bath_schedule(
                fx.world(faces=(), concentrations_mM={"bath": 1e-5}, end=0.004, dt=1e-3),
                ["bath"],
                bfx.CARGO,
                [(2e-3, ["bath"], {"cargo": 5e-4})],  # Inside the dose's measured region.
            )
        ),
        r"its view changes species amounts \(no FR-42 stage plans it yet\)",
    ),
    "beside D1's label families": (
        lambda: family(face_free()),
        r"neutral_arrival_labels@1 is composed beside label families",
    ),
    "a second label owner": (
        lambda: labelled_s(labelled_s(face_free())),
        r"Two operators declare the same experiment key",
    ),
    "a switch off the grid": (
        lambda: labelled_s(face_free(), arrivals=[("S", [(0.0, "base"), (1.5e-3, "new")])]),
        r"exact multiple of dt",
    ),
    "a switch to an undeclared label": (
        lambda: labelled_s(face_free(), arrivals=[("S", [(0.0, "other")])]),
        r"S has no label 'other'",
    ),
    "shares that do not sum to 1": (
        lambda: labelled_s(face_free(), initial={"cell_0": {"base": 0.5, "new": 0.4}}),
        r"shares at cell_0 sum to 1",
    ),
    "shares at a held bath": (
        lambda: labelled_s(face_free(), initial={"bath": {"base": 1.0}}),
        r"a held bath",
    ),
}


@pytest.mark.parametrize("case", sorted(REFUSED))
def test_a_labelled_definition_is_refused_where_stage_1_cannot_follow_it(case):
    make, message = REFUSED[case]
    with pytest.raises(ConfigError, match=message):
        parse_spec(make())
