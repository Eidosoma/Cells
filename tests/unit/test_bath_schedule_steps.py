"""Milestone 2 of cells.operator.scheduled_bath_composition@1 (FR-10; docs/BATH_SCHEDULE_DESIGN.md §7, §8), NumPy.

A step is admitted only if a measured passing point of its key and direction dominates it in both
ratio and level, and only within the measured conditions: ARS(2,2,2) at dt <= 1 ms or RK4 at
dt <= 0.1 ms, beside faces at kappa/V <= 10/s. Neutral species are keyed by class, ions by species
ID. The measured points come from §7's staircase probe and milestone 2's probes I (ion steps) and
D (neutral steps down). Here, at the definition:
* every measured point is admitted, and the region ends 1% past each corner;
* just outside each corner refuses, and the staircase probe's measured failures refuse;
* unmeasured kinds refuse: an ion or direction never measured (Na up, K down, Cl), a face faster
  than measured, ARS at 2 ms, RK4 at 0.2 ms, and another solver;
* §7's admissible protocol (six stairs of 100 from 1e-15 to 1e-3 mM) is admitted whole, and a
  washout after it within the down region;
* M1's tested uses stay admitted: B3's step, the salt substitution and the isosmotic water step lie
  inside the measured regions (probe I's r = 3 arm);
* its call to the species cap (1,024 since FR-43 / D315, set to 16 for the test): 8 species
  admitted, 17 refused.
"""

import copy

import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.operators import bath_schedule as bs
from cells.operators import species_common
from validation.tissue import bath_schedule_fixtures as bfx
from validation.tissue import secreted_species_fixtures as fx

ARS, DT_ARS, DT_RK4 = fx.IMEX, 1e-3, 1e-4
FACE_10 = (1e-9, 1e-5)  # kappa/V = 10/s beside the bath (the staircase's face).


def neutral(c0, c1, *, solver=ARS, dt=DT_ARS, face=FACE_10):
    """The dose leg from c0 to c1 mM (the bath's S) at step 10."""
    raw = bfx.dosed_world(c0=c0, dt=dt, end=50 * dt, solver=solver, face=face)
    return bfx.with_bath_schedule(
        raw, ["bath"], bfx.CARGO, [(10 * dt, ["bath"], {"cargo": c1 - c0})]
    )


def staircase(levels, *, dt=DT_ARS, trace=1e-15):
    raw = bfx.dosed_world(
        dt=dt,
        end=(len(levels) + 2) * 0.3,
        trace_mM=trace,
        face=FACE_10,
        profile=dict(bath=trace, ecs_0=trace, cell_0=trace),
    )
    events = [
        (round((0.3 * k + 10 * dt) / dt) * dt, ["bath"], {"cargo": c - trace})
        for k, c in enumerate(levels)
    ]
    return bfx.with_bath_schedule(raw, ["bath"], bfx.CARGO, events)


def salt(x, *, units=None):
    """KCl for NaCl by x mM at the dose leg's bath (K 5, Na 145, Cl 150 mM)."""
    raw = bfx.dosed_world(dt=DT_ARS, end=0.05)
    offsets = units if units is not None else {"NaCl": -x, "KCl": x}
    salts = {**bfx.SALTS, "NaCl_up": {"Na": 1, "Cl": 1}}
    return bfx.with_bath_schedule(raw, ["bath"], salts, [(10 * DT_ARS, ["bath"], offsets)])


ADMITTED = {
    "the neutral corner (100, 1e-3)": lambda: neutral(1e-5, 1e-3),
    "the neutral corner (10, 1e-2)": lambda: neutral(1e-3, 1e-2),
    "the staircase's (3, 3e-3) and (1.5, 1.5e-3)": lambda: neutral(1e-3, 3e-3),
    "a neutral step down (100, 1e-2)": lambda: neutral(1e-2, 1e-4),
    "a neutral step down (10, 1e-3)": lambda: neutral(1e-3, 1e-4),
    "K up (10, 50) with Na down (1.45, 145)": lambda: salt(45.0),
    "K up (3, 15) with Na down (145/135, 145): M1's salt step": lambda: salt(10.0),
    "K up (1.5, 7.5)": lambda: salt(2.5),
    "RK4 at 0.1 ms": lambda: neutral(1e-3, 1e-2, solver="rk4", dt=DT_RK4),
    "a slower face (1/s)": lambda: neutral(1e-3, 1.5e-3, face=(1e-10, 1e-5)),
}


@pytest.mark.parametrize("name", sorted(ADMITTED))
def test_steps_inside_the_measured_region_are_admitted(name):
    parse_spec(ADMITTED[name]())


OUTSIDE = "lies outside the measured region"
REFUSED = {
    "just past the ratio of (100, 1e-3)": (lambda: neutral(1e-3 / 101, 1e-3), OUTSIDE),
    "just past the level of (100, 1e-3)": (lambda: neutral(1.01e-5, 1.01e-3), OUTSIDE),
    "just past the ratio of (10, 1e-2)": (lambda: neutral(1e-2 / 10.1, 1e-2), OUTSIDE),
    "just past the level of (10, 1e-2)": (lambda: neutral(1.01e-3, 1.01e-2), OUTSIDE),
    "the measured failure (1e3, 1e-3)": (lambda: neutral(1e-6, 1e-3), OUTSIDE),
    "the measured failure (100, 0.1)": (lambda: neutral(1e-3, 0.1), OUTSIDE),
    "the measured failure (1e4, 10)": (lambda: neutral(1e-3, 10.0), OUTSIDE),
    "the dose from nothing in one step": (lambda: neutral(1e-15, 1e-3), OUTSIDE),
    "a neutral step down past (100, 1e-2)": (lambda: neutral(2e-2, 2e-4), OUTSIDE),
    "K up past (10, 50)": (lambda: salt(50.0), OUTSIDE),
    "Na up, never measured": (lambda: salt(0.0, units={"NaCl_up": 5.0}), "no step of that kind"),
    "K down, never measured": (lambda: salt(0.0, units={"KCl": -1.0, "NaCl_up": 1.0}), "no step"),
    "a face faster than measured": (lambda: neutral(1e-3, 1.5e-3, face=(1.1e-9, 1e-5)), "a face"),
    "ARS at 2 ms": (lambda: neutral(1e-3, 1.5e-3, dt=2e-3), "measured only under"),
    "RK4 at 0.2 ms": (lambda: neutral(1e-3, 1.5e-3, solver="rk4", dt=2e-4), "measured only under"),
}


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_steps_outside_the_measured_region_are_refused_with_the_reason(name):
    build, message = REFUSED[name]
    with pytest.raises(ConfigError, match=message):
        parse_spec(build())


def test_the_admissible_protocol_doses_through_stairs_and_washes_out_within_the_region():
    levels = [1e-15 * (1e-3 / 1e-15) ** ((k + 1) / 6) for k in range(6)]
    parse_spec(staircase(levels))  # Six stairs of 100 to 1e-3 mM.
    parse_spec(staircase([*levels, 1e-5]))  # Then down by 100 at 1e-3 mM.
    with pytest.raises(ConfigError, match=OUTSIDE):
        parse_spec(staircase([1e-3]))  # The dose from nothing.


def test_an_idle_schedule_is_admitted_whatever_the_solver():
    raw = bfx.dosed_world(dt=5e-3, end=0.05)
    parse_spec(bfx.with_bath_schedule(raw, ["bath"], bfx.CARGO, []))


def test_every_measured_point_is_admitted_and_the_region_ends_at_its_corners():
    """Every point is admitted; 1% further out than a corner (a point no other point of its key
    dominates) is not."""
    for (key, direction), points in bs.MEASURED_POINTS.items():
        for ratio, level in points:
            assert bs.admitted(key, direction, ratio, level), (key, direction, ratio, level)
            dominated = any(
                (r, c) != (ratio, level) and ratio <= r and level <= c for r, c in points
            )
            if not dominated:
                assert not bs.admitted(key, direction, ratio * 1.01, level * 1.01)


def with_neutral_species(raw, count):
    """count more neutral species, 1e-3 mM at every node, immobile and impermeant."""
    out = copy.deepcopy(raw)
    m, x = out["model"], out["execution"]
    for k in range(count):
        name = f"N{k}"
        m["species"].append(dict(id=name, valence=0))
        for node in (*m["cells"], *m["extracellular"]):
            node["initial_amount_fmol"][name] = 1e-3 * node["volume_pL"]
        for patch in m["membranes"]:
            patch["permeability_m_per_s"][name] = 0.0
        for face in m["faces"]:
            face["diffusivity_m2_per_s"][name] = 0.0
        x["material_balance_atol_fmol"][name] = 1e-10
    return out


def test_the_species_cap_admits_eight_and_refuses_seventeen(monkeypatch):
    monkeypatch.setattr(species_common, "MAX_SPECIES", 16)  # The operator's call, not the value.
    raw = neutral(1e-3, 1.5e-3, face=(1e-10, 1e-5))  # Na, K, Cl and S: 4 species.
    spec = parse_spec(with_neutral_species(raw, 4))
    assert len(spec.model.species_ids) == 8
    with pytest.raises(ConfigError, match="at most 16 species"):
        parse_spec(with_neutral_species(raw, 13))
