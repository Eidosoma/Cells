"""Hand checks of the G2-Q1 references (validation/tissue/cell_replacement_reference.py)."""

import numpy as np

from validation.tissue import cell_replacement_fixtures as fx
from validation.tissue import cell_replacement_reference as ref

F_FMOL = ref.F * ref.MOL_PER_FMOL


def w7(formation=None, events=None):
    raw = fx.heredity_sheet(1, 0, scale=0.1, dt=1e-3, end_time=2.0)
    raw["experiment"]["observation_times"] = [0.0, 2.0]
    templates = [
        fx.template_from_cell(raw, "cell_1", "h"),
        fx.template_from_cell(raw, "cell_3", "d"),
    ]
    events = events or [(1.0, "cell_0", "d", "w1"), (1.0, "cell_3", "h", "w2")]
    return fx.with_replacement(raw, templates, events, formation=formation)


def test_formation_closed_form():
    f = dict(initial_abundance=0.25, lag_s=1.0, time_constant_s=40.0)
    start = np.array([np.nan, 0.0, 0.0])
    a = ref.abundance(3.0, start, f)
    assert a[0] == 1.0
    assert abs(a[1] - (1 - 0.75 * np.exp(-2.0 / 40.0))) < 1e-15
    assert ref.abundance(0.5, start, f)[1] == 0.25  # Inside the lag.


def test_water_is_closed():
    raw = ref.closed_water(w7())
    m = raw["model"]
    assert all(r["hydraulic_permeability_m_per_Pa_s"] == 0 for r in m["water"]["membranes"])
    assert "replacement" not in m and "replacement_events" not in raw["experiment"]


def test_event_operator_by_hand():
    raw = w7()
    model = ref.ReplacementReference(raw)
    y0 = model.ref.initial()
    events = [e for e in model.events if e["time"] == 1.0]
    y, booking = model.apply(1.0, y0, events)
    cells = raw["model"]["cells"]
    species = model.ref.w.species
    d = [raw["model"]["replacement"]["templates"][1]["amounts_fmol"][s] for s in species]
    before = [cells[0]["initial_amount_fmol"][s] for s in species]
    assert booking["supplied_fmol"][0] == d and booking["removed_fmol"][0] == before
    z = np.array([1, 1, -1, -1])
    dq = F_FMOL * float(np.sum(z * (np.array(d) - np.array(before))))
    assert abs(booking["charge_C"][0] - dq) <= 1e-12 * abs(dq)
    image = np.asarray(booking["image_charge_C"])
    assert abs(image[0] + dq) <= 1e-12 * abs(dq)  # Its own bath carries the image.
    amount = model.observe(y)["cell_amount_fmol"]
    assert np.allclose(amount[0], d, rtol=1e-15, atol=0)
    jg = np.asarray(model.observe(y)["junction_gate"])
    incident = (
        (model.ref.j_send == 0)
        | (model.ref.j_send == 3)
        | (model.ref.j_recv == 0)
        | (model.ref.j_recv == 3)
    )
    target = ref.junction_target(0.0, model.ref.j_thr[0], model.ref.j_min[0])
    assert np.allclose(jg[incident], target, rtol=0, atol=1e-15)
    assert np.isfinite(booking["free_energy_pJ"])


def test_donor_copy_reads_the_state_before_same_time_events():
    raw = w7(events=[(1.0, "cell_0", None, "c0", "cell_3"), (1.0, "cell_3", "h", "c1")])
    model = ref.ReplacementReference(raw)
    y, booking = model.apply(1.0, model.ref.initial(), model.events)
    cells = raw["model"]["cells"]
    species = model.ref.w.species
    assert booking["supplied_fmol"][0] == [cells[3]["initial_amount_fmol"][s] for s in species]


def test_reduced_chain_is_symmetric():
    raw = fx.heredity_sheet(1, 0, scale=0.1, dt=1e-3, end_time=1.0)
    from validation.stationary import worlds
    from validation.tissue import surface_pump_v3_fixtures as v3fx

    states = {k: v[:4] for k, v in v3fx.HEREDITY_STATES.items()}
    written = [states["H"], states["D"], states["H"]]
    raw = worlds.ionic_background(
        worlds.e07_sheet_definition(
            written, [(0, 1), (1, 2)], scale=0.1, gated=False, dt=1e-3, end_time=1.0
        )
    )
    raw = fx.with_replacement(
        raw, [fx.template_from_cell(raw, "cell_0", "h")], [(0.5, "cell_1", "h", "x")]
    )
    chain = ref.ReducedChain(raw)
    v = chain.integrate(0.4, [0.4])[0.4]
    assert abs(v[0] - v[2]) < 1e-12
