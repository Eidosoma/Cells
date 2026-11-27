"""FR-45's shared site sets beside the design note's §15 partners, compiled through the runner (D327,
the lead's ruling 2 of 27 November 2026; invented values only, FR-45's first-run rule).

Seconds and reason (D224): about 47 s on two cores, measured at landing (the passivity row's two runs 27 s,
the omnibus row 18 s). Each admitted partner is enabled with its check, and these are the checks that need a
run. test_site_competition_runs.py holds the wash, the run paths and the batch paths; test_site_occupancy.py
holds the parse rows and every refusal by name.

* The omnibus row: turnover (Q2 made in the cell and cleared at the set's node), exchange (Q2 exported
  through the set's patch), D152's reactions (Q1 <-> Q3 at the set's node) and a face at the set's node,
  all writing the set's ligand rows. The runner's host checks close every ledger and the dissipation on
  every row; the row asserts each partner acted, the books at rounding, the moiety per set, and a site
  heat that never falls.
* The passivity row: the bath schedule (a dose of S in the held bath) and replacement@1 (cell_1 replaced,
  the set on cell_0's patch, off the slot) leave the set's fields and its ligands' rows bit for bit.
"""

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.operators import site_occupancy as so
from cells.registry.models import get_model
from validation.tissue import bath_schedule_fixtures as bfx
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import site_occupancy_fixtures as sfx
from validation.tissue import species_reactions_fixtures as rfx

EPS = np.finfo(float).eps


def _identities(*names):
    return [dict(id=g, catalogue=None, evidence=None) for g in names]


def omnibus(end=0.2, dt=2e-3):
    pops = [sfx.member("m1", ligand="Q1", k_on=2.2e3, k_off=0.7, theta0=0.2),
            sfx.member("m2", ligand="Q2", k_on=1.3e3, k_off=0.35)]  # fmt: skip
    raw = sfx.set_world(pops, [sfx.site_set(copies=4e5)], ligands=("Q1", "Q2", "Q3"),
                        node_mM={"Q1": 1.6e-3, "Q2": 4e-4, "Q3": 3e-4}, cell_mM={"Q2": 2.1e-3},
                        dt=dt, end=end, observation_times=[0.0, end],
                        faces=(("face_0", "ecs_0", "bath", 1.2e-10, 1.5e-5),))  # fmt: skip
    raw = fx.with_turnover(raw, [("make_q2", "cell_0", "production"), ("clear_q2", "ecs_0", "clearance")],
                           [("make_q2", "cell_0", [(0.0, 3e-5)]), ("clear_q2", None, [(0.0, 0.6)])],
                           species=_identities("Q2"))  # fmt: skip
    for route in raw["model"]["operators"][-1]["routes"]:
        route["species"] = "Q2"
    raw = fx.with_exchange(raw, [("out_q2", "contact_0", "export", "first_order")],
                           [("out_q2", "cell_0", [(0.0, 0.9)])], species=_identities("Q2"))  # fmt: skip
    raw["model"]["operators"][-1]["routes"][0]["species"] = "Q2"
    moiety = {"M": 1}
    return rfx.with_reactions(
        raw,
        [rfx.species("Q1", moieties=moiety), rfx.species("Q3", moieties=moiety)],
        [rfx.passive("conv", {"outside": ["ecs_0"]}, {"Q1": 1}, {"Q3": 1}, 0.45)],
        [("conv", None, [(0.0, 1.0)])],
    )


def test_turnover_exchange_reactions_and_a_face_write_a_sets_ligands_with_every_book_closed():
    spec = parse_spec(omnibus())
    result = run(spec)  # Every row's host checks: each ledger, the moiety, the dissipation.
    _, p = get_model(spec.model).initial_values(spec)
    h = result.history
    ids = list(spec.model.species_ids)
    node = [c.id for c in spec.model.extracellular].index("ecs_0")
    end = len(result.times) - 1
    # Each partner acted on a set's ligand.
    assert float(np.sum(np.asarray(h.turnover_produced_fmol)[end])) > 0
    assert float(np.asarray(h.turnover_outside_cleared_fmol)[end, ids.index("Q2"), node]) > 0
    assert float(np.sum(np.abs(np.asarray(h.exchange_moved_fmol)[end]))) > 0
    assert float(np.asarray(h.reaction_outside_consumed_fmol)[end, ids.index("Q1"), node]) > 0
    face = np.asarray(h.face_transferred)[end]
    assert all(float(face[ids.index(g)].sum()) > 0 for g in ("Q1", "Q2", "Q3"))
    # The books at rounding: each species' ledgers (local, outside and total) and the set's.
    reference = np.asarray(p.extracellular_amount_reference)[:, node]
    scale = float(max(reference[ids.index(g)] for g in ("Q1", "Q2", "Q3")))
    for key in ("max_balance_error_fmol", "max_extracellular_balance_error_fmol",
                "max_global_balance_error_fmol"):  # fmt: skip
        assert result.diagnostics[key] <= 64 * EPS * scale, key
    R = np.asarray(p.site_free_anchor_fmol) + np.asarray(h.site_free_increment_fmol)
    B = np.asarray(p.site_bound_anchor_fmol) + np.asarray(h.site_bound_increment_fmol)
    S = float(np.asarray(p.site_set_capacity_fmol)[0])
    k = np.arange(end + 1)
    assert np.all(np.abs(R[:, 0] + B.sum(axis=1) - S) <= 16 * EPS * (k + 1) * S)
    assert B[end, 1] > B[0, 1]  # Q2 bound from the cell's export.
    # The site heat never falls, and rises at the set's node.
    for name in ("site_dissipated_energy_pJ", "site_outside_dissipated_energy_pJ"):
        assert np.all(np.diff(np.asarray(getattr(h, name)), axis=0) >= 0), name
    outside = np.asarray(h.site_outside_dissipated_energy_pJ)[:, node]
    assert outside[end] > outside[0]
    assert so.LAW_ID in {o.LAW_ID for o in get_model(spec.model).operators}


def test_the_bath_schedule_and_a_replacement_off_the_slot_leave_the_set_bit_for_bit():
    dt, end = 1e-3, 0.012
    times = [round(i * dt, 3) for i in range(13)]
    plain = sfx.two_cell_set_world(replaced=False, dt=dt, end=end, observation_times=times)
    partners = sfx.two_cell_set_world(replaced=True, dt=dt, end=end, observation_times=times)
    partners = bfx.with_bath_schedule(partners, ["bath"], bfx.CARGO,
                                      [(bfx.on_grid(0.008, dt), ["bath"], {"cargo": 9e-12})])  # fmt: skip
    without, beside = run(parse_spec(plain)), run(parse_spec(partners))
    spec = parse_spec(partners)
    ids = list(spec.model.species_ids)
    outside = [c.id for c in spec.model.extracellular]
    node, bath = outside.index("ecs_0"), outside.index("bath")
    # The partners acted: S rose in the held bath, and cell_1's slot took its newcomer.
    dose = np.asarray(beside.history.bath_dose_fmol)[:, ids.index(fx.SPECIES), bath]
    assert dose[0] == 0 and dose[-1] > 0
    cells = [c.id for c in spec.model.cells]
    assert np.asarray(beside.history.generation)[-1, cells.index("cell_1")] == 1
    for name in so.STATE_AXES:
        a, b = np.asarray(getattr(beside.history, name)), np.asarray(getattr(without.history, name))
        assert a.tobytes() == b.tobytes(), name
    for g in ("Q1", "Q2"):
        a = np.asarray(beside.history.extracellular_amount_increment)[:, ids.index(g), node]
        b = np.asarray(without.history.extracellular_amount_increment)[:, ids.index(g), node]
        assert a.tobytes() == b.tobytes(), g
