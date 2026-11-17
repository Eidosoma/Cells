"""OL5 references for OL2 (no ruling needed): geometry from the counts, the lumen's tension as a
derivative of F, the end states, and the admission thresholds.

Planted controls: a_L off by a factor of two, a wrong Laplace factor, a wrong sphere constant.
"""

from __future__ import annotations

import math

import pytest

from validation.ool.references import geometry as G

A_L = 0.3e-18              # m^2 per molecule per leaflet (the design's assumed value, §2.5)
N_100NM = 209440           # oleate in a 100 nm vesicle at that a_L
C_EXT = 0.2                # mol/L


def _vesicle(excess: float, planted=None) -> G.Vesicle:
    v_sph = G.Vesicle((N_100NM,), (A_L,), 0, C_EXT).v_sph()
    n_imp = int(excess * v_sph * C_EXT * G.L_PER_M3 * G.N_A)
    return G.Vesicle((N_100NM,), (A_L,), n_imp, C_EXT, planted=planted)


def test_closed_forms_at_registered_states():
    for excess in (0.8, 1.0, 1.2):
        ves = _vesicle(excess)
        A = N_100NM * A_L / 2
        assert ves.area == pytest.approx(A, rel=1e-15)
        assert ves.v_sph() == pytest.approx(A ** 1.5 / (6 * math.sqrt(math.pi)), rel=1e-15)
        assert ves.radius == pytest.approx(50e-9, rel=1e-4)
        assert ves.reduced_volume == pytest.approx(min(1.0, ves.v_osm / ves.v_sph()), rel=1e-14)
        assert ves.tense == (excess > 1)
    tense = _vesicle(1.2)
    dp = G.K_B * 298.15 * (tense.n_imp / tense.v_sph() - C_EXT * 1000 * G.N_A)
    assert tense.tension == pytest.approx(dp * tense.radius / 2, rel=1e-13)
    # the design's number: 10 dyn/cm at a_L = 0.3 nm^2 is a drop of 0.364 k_BT (E3)
    assert 1e-2 * A_L / 2 / (G.K_B * 298.15) == pytest.approx(0.3644, abs=1e-4)


@pytest.mark.parametrize("excess", [0.95, 1.05, 1.3])
def test_the_potential_drop_is_minus_the_derivative_of_F(excess):
    """sigma a_L/2 = -dF_lumen/dn, on both sides of the floppy-tense boundary."""
    ves = _vesicle(excess)
    h = 50
    up = G.Vesicle((N_100NM + h,), (A_L,), ves.n_imp, C_EXT)
    dn = G.Vesicle((N_100NM - h,), (A_L,), ves.n_imp, C_EXT)
    dF = (G.lumen_free_energy(up) - G.lumen_free_energy(dn)) / (2 * h)
    assert -dF == pytest.approx(ves.potential_drop_kT(0), rel=1e-4, abs=1e-9)


def test_planted_geometry_errors_move_the_registered_quantities():
    honest = _vesicle(1.2).derived()
    for form in G.PLANTED_GEOMETRY:
        planted = _vesicle(1.2, planted=form).derived()
        moved = [k for k in honest if not math.isclose(honest[k], planted[k], rel_tol=1e-9, abs_tol=0.0)]
        assert moved, form
    assert _vesicle(1.2, "laplace_double").tension == pytest.approx(2 * _vesicle(1.2).tension, rel=1e-14)


def test_zero_tension_and_two_vesicle_end_states():
    n1 = _vesicle(1.4).n_imp          # swollen: tense at the 100 nm area
    n2 = _vesicle(0.7).n_imp          # isotonic-like: floppy at the 100 nm area
    a1, a2 = G.zero_tension_area(n1, C_EXT), G.zero_tension_area(n2, C_EXT)
    assert G.tension_at_area(a1 * (1 - 1e-9), n1, C_EXT) > 0 and G.tension_at_area(a1, n1, C_EXT) == 0
    A_tot = 2 * N_100NM * A_L / 2
    split = G.two_vesicle_split(A_tot, (n1, n2), C_EXT)
    assert A_tot < a1 + a2 and not split["degenerate"]
    assert split["A1"] + split["A2"] == pytest.approx(A_tot, rel=1e-15)
    s1 = G.tension_at_area(split["A1"], n1, C_EXT)
    s2 = G.tension_at_area(split["A2"], n2, C_EXT)
    assert s1 == pytest.approx(s2, rel=1e-9) and s1 > 0
    assert split["A1"] > A_tot / 2      # the swollen vesicle gains area
    relaxed = G.two_vesicle_split(1.1 * (a1 + a2), (n1, n2), C_EXT)
    assert relaxed["degenerate"] and relaxed["tension"] == 0.0


def test_admission_thresholds():
    assert [round(G.admission_threshold(k), 12) for k in (2, 3, 4)] == [0.707106781187, 0.57735026919, 0.5]
    A = 1.0
    for k in (2, 3, 4):
        total = k * (A / k) ** 1.5 / (6 * math.sqrt(math.pi))
        assert total / (A ** 1.5 / (6 * math.sqrt(math.pi))) == pytest.approx(G.admission_threshold(k), rel=1e-14)
    with pytest.raises(ValueError):
        G.admission_threshold(1)
