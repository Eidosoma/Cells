"""T8 of cells.operator.scheduled_membrane_trafficking@1 (FR-2 version 1): the seven-cell sheet (pumps, Kir, NaV,
gated junctions, a held bath per cell), with one pool per cell (21 field nodes), a frozen
regulatory state at s = 1/2 coupled to every Kir population, and retrieval of every plasma patch,
through the runner and its host checks.

- The factor and the removal both act on @3's inputs: each Kir population's effective
  abundance-weighted availability is F N(t) / (A rho), with N(t) = N0 A(t)/A0 (e = 1).
- Planted: the same world without the coupling, and without the retrieval, each moves it off.
- Against the code-blind references (D224): the 42 T8 rows (start and factor) on the coupled
  run, and the 70 plant rows on the runs without the coupling and without the retrieval, through
  validation/tissue/membrane_trafficking_comparison.py. A row passes when |engine - reference| <=
  its registered band; a plant must fail its row where must_refuse holds, and a zero-power row
  (the retrieval's plant at t = 0) carries its reason. The three runs are made once, in a module
  fixture.

"""

from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.operators import membrane_state
from cells.registry.models import get_model
from validation.tissue import membrane_trafficking_comparison as mc
from validation.tissue import membrane_trafficking_fixtures as fx
from validation.tissue import regulated_availability_fixtures as rafx

END = 0.004
TIMES = [0.0, 0.001, 0.002, 0.003, END]


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


# ------------------------------------------------------------------ T8: a composed world

HALF = 0.5  # The frozen state's level: F = s on every Kir population.


def sheet(*, coupling=True, retrieval=True):
    raw = rafx.sheet(end=END, observation_times=TIMES)
    n = len(raw["model"]["cells"])
    for i in range(n):
        fx.add_pool(raw, i)
    raw["model"]["operators"] = [
        fx.membrane_state(raw),
        dict(law=fx.COMPARTMENTS, compartments=[fx.compartment(i) for i in range(n)]),
    ]
    if coupling:
        cells = [c["id"] for c in raw["model"]["cells"]]
        kir = [c["id"] for c in raw["model"]["channels"] if c["id"].startswith("kir_")]
        raw = rafx.with_coupling(
            raw,
            species=[rafx.REGULATOR],
            states=[rafx.frozen("s", cells, HALF)],
            couplings=[rafx.fraction("kir", "channel", kir, "s")],
        )
    routes = [fx.route(raw, i, retrieval={f"kir_{i}": 1.0, f"nav_{i}": 0.0}) for i in range(n)]
    rate = 0.1 if retrieval else 0.0
    plans = [
        fx.schedule(r["id"], [(0.0, fx.rate(raw, i, rate, over=END))]) for i, r in enumerate(routes)
    ]
    return fx.with_trafficking(raw, routes, plans)


def made(raw):
    spec = parse_spec(raw)
    result = run(spec)  # 21 field nodes, under the 64-node cap; every host check holds.
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    controls = cs.control_values(spec, list(result.times))
    return SimpleNamespace(raw=raw, spec=spec, model=model, p=p, result=result, controls=controls)


@pytest.fixture(scope="module")
def sheets():
    """The three runs: the coupled sheet, and the plants without the coupling and without the
    retrieval."""
    return dict(
        main=made(sheet()),
        no_coupling=made(sheet(coupling=False)),
        no_retrieval=made(sheet(retrieval=False)),
    )


def test_the_coupling_factor_and_the_retrieval_both_act_on_kir(sheets):
    s = sheets["main"]
    spec, result, model, p = s.spec, s.result, s.model, s.p
    kir = [i for i, c in enumerate(spec.model.channels) if c.id.startswith("kir_")]
    h = result.history
    rows = [type(h)(*(np.asarray(v)[t] for v in h)) for t in range(len(result.times))]
    controls = s.controls

    def conducting(row, t):
        """F x availability x abundance x area, per Kir population: @3's conductance factor."""
        control = model.CONTROL_TYPE(*(np.asarray(v)[t] for v in controls))
        view = model.view(p, row, xp=np)
        effective = np.asarray(model.control_view(control, row, p, xp=np).channel)[kir]
        patch = np.asarray(p.channel_membranes)[kir]
        return (
            effective
            * np.asarray(view.channel_abundance)[kir]
            * np.asarray(view.membrane_area)[patch]
        )

    start = conducting(rows[0], 0)
    patch = np.asarray(p.channel_membranes)[kir]
    for t, row in enumerate(rows):
        ratio = (
            np.asarray(membrane_state.area(row, p, xp=np))[patch]
            / np.asarray(p.membrane_area)[patch]
        )
        # e = 1: N(t) = N0 A(t)/A0; the factor F = 1/2 throughout (frozen state).
        np.testing.assert_allclose(conducting(row, t), start * ratio, rtol=1e-12)
    scheduled = np.asarray(controls.channel)[0][kir]
    n0 = np.asarray(p.channel_abundance)[kir] * np.asarray(p.membrane_area)[patch]
    np.testing.assert_allclose(start, HALF * scheduled * n0, rtol=1e-14)
    assert np.all(ratio < 1)  # The retrieval acted.
    # Planted: without the coupling the factor is gone; without the retrieval the removal is.
    for name, broken in (("no_coupling", "factor"), ("no_retrieval", "removal")):
        o = sheets[name]
        other, out, model2, p2 = o.spec, o.result, o.model, o.p
        last = type(out.history)(*(np.asarray(v)[-1] for v in out.history))
        control = model2.CONTROL_TYPE(*(np.asarray(v)[-1] for v in o.controls))
        view = model2.view(p2, last, xp=np)
        kir2 = [i for i, c in enumerate(other.model.channels) if c.id.startswith("kir_")]
        value = (
            np.asarray(model2.control_view(control, last, p2, xp=np).channel)[kir2]
            * np.asarray(view.channel_abundance)[kir2]
            * np.asarray(view.membrane_area)[np.asarray(p2.channel_membranes)[kir2]]
        )
        assert not np.allclose(value, conducting(rows[-1], len(rows) - 1), rtol=1e-6, atol=0.0), (
            broken
        )


# ------------------------------------------------------------------ T8 against the references

T8_ROWS = [r["id"] for r in mc.rows("t8")]
T8_PLANTS = [(p["plant"], p["row"]) for p in mc.plants("t8")]
PLANT_RUN = {"T8 without the coupling": "no_coupling", "T8 without the retrieval": "no_retrieval"}


def t8_verdict(s, row):
    r = mc.row_by_id()[row]
    return mc.verdict(r, mc.t8_value(r, s.raw, s.spec, s.model, s.p, s.result, s.controls))


@pytest.mark.parametrize("row", T8_ROWS)
def test_t8_row(sheets, row):
    v = t8_verdict(sheets["main"], row)
    assert v["passed"], (row, v["engine"], v["deviation"], v["band"], v["margin"])


@pytest.mark.parametrize(
    "kind, row", T8_PLANTS, ids=[f"plant{i:03d}:{row}" for i, (_, row) in enumerate(T8_PLANTS)]
)
def test_t8_plant(sheets, kind, row):
    (plant,) = [q for q in mc.plants("t8") if (q["plant"], q["row"]) == (kind, row)]
    v = t8_verdict(sheets[PLANT_RUN[kind]], row)
    if not plant["must_refuse"]:  # Zero power: reported with its reason, never asserted refused.
        assert mc.interface()[0]["plant_kinds"][kind]["zero_power"], (kind, row)
        return
    assert not v["passed"], (kind, row, v["engine"], v["deviation"], v["band"])
