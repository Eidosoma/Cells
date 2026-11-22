"""neutral_arrival_labels@1 (FR-42 stage 1, D289): neutral arrival-time labels as shares of a
physical row (operators/species_labels.py, numerics/label_shares.py).

The share update alone, in NumPy (no world; about 2 s):
- exact for a constant per-molecule rate with arrivals, and the shares kept bit for bit without
  arrivals;
- its domain on random and extreme inputs: zero shares, tiny amounts, a large survival exponent and
  16 labels;
- its order when the rates vary within an application: the split between old and new material is
  off by (a' k - a k') h^3 / 12, halving by 8 with h.

Compiled worlds, each run labelled and unlabelled (about 80 s in all; they are FR-42's own checks
as engine rows, so a regression in the composite's hook or a reporter shows here):
- the reference case dN/dt = -N^2 (2A -> B mass action, local_species_reactions@1) in five
  independent pools: one label, the reference's two (older and new, 2:1), several unequal with an
  empty one, and two near the edges of the range (dt L = 0.9 under the stage condition, and the
  trace). Every physical field, record and diagnostic is the unlabelled run's bit for bit, and with
  no arrivals the shares are kept bit for bit: the new cohort is 1/4 of 3/4 at t = 1 (blank
  subtraction would give 1/12);
- a window of arrivals with older material present (FR-42's check 2): production and clearance
  in a cell (turnover, exact), a reaction source and sink at an outside node, and a second,
  unlabelled population with its own loss (check 3). The cohort matches the analytic solution at
  rounding in the cell, including the window's two boundaries (arrivals in the step that starts
  at its start join it; in the step that starts at its end they do not); a checkpoint resumes bit
  for bit through a snapshot.

Definitions refused, each naming the FR-42 stage that lifts it (parses only).
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


# ------------------------------------------------------------------ the reference case, -N^2

DT, END = 5e-3, 1.0
# Five independent pools of 2A -> B (k = 0.5 /(mM s) in the 1 pL cell: dN/dt = -N^2 in fmol and s):
# (mM, labels, the cell's initial shares).
POOLS = {
    "A1": (3.0, ["all"], {"all": 1.0}),
    "A2": (3.0, ["older", "new"], {"older": 2 / 3, "new": 1 / 3}),
    "A3": (3.0, ["base", "x", "y", "empty"], {"base": 0.5, "x": 0.3, "y": 0.2}),
    "A4": (180.0, ["older", "new"], {"older": 0.9, "new": 0.1}),  # dt L = 0.9: the stage edge.
    "A5": (1e-6, ["older", "new", "empty"], {"older": 0.25, "new": 0.75}),  # Near the trace.
}


def pools():
    raw = fx.world(faces=(), end=END, dt=DT, observation_times=[0.0, 0.25, 0.5, END])
    for name, (mM, _, _) in POOLS.items():
        raw = add_inventory_species(
            raw,
            name,
            trace_mM=fx.TRACE_mM,
            diffusivity_m2_per_s=fx.D_S,
            floor_fmol=fx.FLOOR_FMOL,
            concentrations_mM={"cell_0": mM},
        )
    raw = add_inventory_species(
        raw, "B", trace_mM=fx.TRACE_mM, diffusivity_m2_per_s=fx.D_S, floor_fmol=fx.FLOOR_FMOL
    )
    species = [rfx.species(name, moieties={"X": 1}) for name in POOLS]
    species.append(rfx.species("B", moieties={"X": 2}))
    cell = {"cells": ["cell_0"]}
    reactions = [rfx.mass_action(f"decay_{n}", cell, {n: 2}, {"B": 1}, 0.5) for n in POOLS]
    return rfx.with_reactions(raw, species, reactions, rfx.always([r["id"] for r in reactions]))


@pytest.fixture(scope="module")
def reference_runs():
    raw = pools()
    labelled = with_labels(raw, [(n, labels, {"cell_0": s}) for n, (_, labels, s) in POOLS.items()])
    return run(parse_spec(labelled)), run(parse_spec(raw))


def test_minus_n_squared_labels_leave_every_record_and_keep_the_cohort(reference_runs):
    labelled, plain = reference_runs
    same_physics(labelled, plain)
    share = np.asarray(labelled.observations.label_share)  # [time, species, label, cell]
    initial = share[0]
    for i in range(share.shape[0]):
        assert bits(share[i]) == bits(initial)  # No arrivals: kept bit for bit.
    width = share.shape[2]
    for j, (_, labels, given) in enumerate(POOLS.values()):
        declared = [given.get(label, 0.0) for label in labels] + [0.0] * (width - len(labels))
        assert bits(initial[j, :, 0]) == bits(np.asarray(declared))
    species = list(labelled.spec.model.species_ids)
    n = np.asarray(labelled.observations.amount)[:, species.index("A2"), 0]
    assert abs(n[-1] - 0.75) < 1e-6  # N(1) = 3 / (1 + 3).
    assert abs(n[-1] * share[-1, 1, 1, 0] - 0.25) < 1e-6  # The new cohort: 1/4, not 1/12.
    assert np.all(np.asarray(labelled.observations.label_closure_relative) <= 64 * EPS)


# ------------------------------------------------------------------ a window of arrivals

H = 1 / 64  # dt, exact in binary, so every time below is a grid point exactly.
TS, TE, END_W = 16 * H, 32 * H, 64 * H  # The window [0.25, 0.5) and the end, 1.0 s.
OBSERVE = [0.0, TS, TS + H, TE, TE + H, END_W]
P, K = 0.4, 0.5  # The cell: production (fmol/s) and clearance (1/s), turnover, exact.
SOURCE, SINK = 0.2, 0.3  # The outside node: a source (mM/s in 1 pL) and a sink (1/s), reactions.
C_SINK = 2.0  # The second population's own first-order loss (1/s), unlabelled.


def window_world():
    raw = fx.world(
        faces=(),
        concentrations_mM={"cell_0": 1.0, "ecs_0": 0.5},
        end=END_W,
        dt=H,
        observation_times=OBSERVE,
    )
    raw = add_inventory_species(
        raw,
        "C",
        trace_mM=fx.TRACE_mM,
        diffusivity_m2_per_s=fx.D_S,
        floor_fmol=fx.FLOOR_FMOL,
        concentrations_mM={"cell_0": 2.0},
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
    ]
    species = [rfx.species("S", moieties={"X": 1}), rfx.species("C", moieties={"Y": 1})]
    return rfx.with_reactions(raw, species, reactions, rfx.always([r["id"] for r in reactions]))


def window_labels(raw):
    return with_labels(
        raw,
        [("S", ["base", "cohort", "empty"], {"ecs_0": {"base": 0.25, "cohort": 0.75}})],
        [("S", [(0.0, "base"), (TS, "cohort"), (TE, "base")])],
    )


@pytest.fixture(scope="module")
def window_runs():
    raw = window_world()
    spec = parse_spec(window_labels(raw))
    return spec, run(spec), run(parse_spec(raw))


def cell_cohort(t):
    """The window's production in the cell, cleared at K (the arrivals of the steps that start in
    [TS, TE))."""
    made = (P / K) * -math.expm1(-K * min(max(t - TS, 0.0), TE - TS))
    return made * math.exp(-K * max(t - TE, 0.0))


def node_cohort(t):
    """The node's initial 3/4 and the window's source, each lost at SINK."""
    made = (SOURCE / SINK) * -math.expm1(-SINK * min(max(t - TS, 0.0), TE - TS))
    return 0.75 * 0.5 * math.exp(-SINK * t) + made * math.exp(-SINK * max(t - TE, 0.0))


def test_a_window_follows_its_cohort_exactly_at_both_boundaries(window_runs):
    spec, labelled, plain = window_runs
    same_physics(labelled, plain)
    s = list(spec.model.species_ids).index("S")
    obs = labelled.observations
    cell = np.asarray(obs.amount)[:, s, 0] * np.asarray(obs.label_share)[:, 0, 1, 0]
    node = (
        np.asarray(obs.extracellular_amount)[:, s, 1]
        * np.asarray(obs.label_outside_share)[:, 0, 1, 1]
    )
    for i, t in enumerate(OBSERVE):
        assert cell[i] == pytest.approx(cell_cohort(t), rel=1e-13, abs=0), t
        assert node[i] == pytest.approx(node_cohort(t), rel=1e-9), t
    assert cell[1] == 0.0  # At the window's start nothing has arrived yet.
    assert cell[2] == pytest.approx((P / K) * -math.expm1(-K * H), rel=1e-13)  # Its first step.
    assert cell[4] == pytest.approx(cell[3] * math.exp(-K * H), rel=1e-13)  # The end's step: none.
    shares = np.asarray(obs.label_share)[:, 0, :, 0]
    assert np.all(shares[:, 2] == 0.0)  # The empty label.
    assert np.all(np.abs(shares.sum(axis=1) - 1) <= 64 * EPS)  # All of S's material.
    assert np.all(np.asarray(obs.label_closure_relative) <= 64 * EPS)


def test_a_labelled_checkpoint_resumes_bit_for_bit(window_runs, tmp_path):
    """Through a written snapshot, from inside the window (the cohort's share nonzero), so the
    resumed steps carry the shares and cross the window's end (one compile, about 20 s)."""
    from cells.records.io import load_snapshot, write_snapshot

    _, labelled, _ = window_runs
    checkpoint = labelled.checkpoint_at(TS + H)
    assert np.asarray(checkpoint.state.label_share)[0, 1, 0] > 0
    write_snapshot(tmp_path / "checkpoint", labelled.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(resumed.history, labelled.history, strict=True):
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


REFUSED = {
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
