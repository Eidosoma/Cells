"""R-full extensions for the J1 diagnostic arms (A1, A2, A3, A7): null settings and limits.

Every case is a synthetic cell (tests/division_fixtures.py), not the J1 egg.
"""

import math
from dataclasses import replace

import numpy as np
import pytest

from tests.division_fixtures import BATH, T, growing, synthetic
from validation.division import cleft_egg_reference as ref
from validation.division import cleft_rings_reference as rings


def pulses_of(run):
    ks = sorted(k for k in run.onset_V if k in run.sample_V)
    return np.array([run.onset_V[k] for k in ks]), np.array([run.sample_V[k] for k in ks])


def test_access_scale_formulas():
    egg = synthetic()
    assert ref.access_scale(egg, 3.0, 1e-9) == 1.0
    depth = replace(egg, access_shape=("depth", 1.0, 0.65e-3, 0.55e-3, 0.36e-3))
    area = 2 * math.pi * (0.55e-3**2 - 0.30e-3**2)  # inner edge at 0.30 mm
    assert ref.access_scale(depth, 0.0, area) == pytest.approx(0.36e-3 / 0.35e-3, rel=1e-12)
    flat = replace(egg, access_shape=("depth", 0.0, 0.65e-3, 0.55e-3, 0.36e-3))
    assert ref.access_scale(flat, 0.0, area) == 1.0
    ramp = replace(egg, access_shape=("ramp", 0.4, 10.0, 20.0))
    assert ref.access_scale(ramp, 5.0, 0.0) == 1.0
    assert ref.access_scale(ramp, 15.0, 0.0) == pytest.approx(0.7, rel=1e-12)
    assert ref.access_scale(ramp, 25.0, 0.0) == pytest.approx(0.4, rel=1e-12)


@pytest.mark.parametrize(
    "change",
    [
        dict(access_shape=("ramp", 1.0, 1e9, 2e9)),
        dict(access_shape=("depth", 0.0, 1e-5, 1e-5, 1e-5)),
        dict(bath_fraction=1e-15),
        dict(zone_ratio=1e-15, zone_reference_area_m2=1e-9),
    ],
)
def test_extended_path_with_null_settings_matches_the_registered_model(change):
    base = growing()
    ext = replace(base, **change)
    assert ext.extended and not base.extended
    a = ref.simulate(base, 2.1, method="LSODA")
    b = ref.simulate(ext, 2.1, method="LSODA")
    for x, y in zip(pulses_of(a), pulses_of(b), strict=True):
        assert np.max(np.abs(x - y)) < 1e-9


def test_bath_facing_fraction_with_a_sealed_lumen_gives_the_parallel_potential():
    """A1 limit: with A/L = 0 only f x A of new membrane carries net current, against the bath."""
    f, area = 0.3, 1e-9
    egg = synthetic(bath_fraction=f, a_over_l_m=0.0, new_permeability=(1e-11, 4e-8, 0.0))
    run = ref.simulate(egg, 1.5, record=(1.5,), method="LSODA")
    s = run.at[1.5]
    pa = tuple(
        egg.p_old * w * egg.old_area_m2 + f * area * p
        for w, p in zip(egg.old_relative, egg.new_permeability, strict=True)
    )
    expected = ref.zero_current_potential(pa, tuple(s["cytosol_mM"]), BATH, T)
    old_only = ref.zero_current_potential(
        tuple(egg.p_old * w * egg.old_area_m2 for w in egg.old_relative),
        tuple(s["cytosol_mM"]),
        BATH,
        T,
    )
    assert abs(expected - old_only) > 1e-3
    assert s["V"] == pytest.approx(expected, abs=1e-7)


def test_bath_facing_insertion_heat_at_fixed_charge():
    """A1 at zero transport: V = q / (C_old + c f A(t)); heat = q^2 (1/C_old - 1/C(t)) / 2."""
    f, c0, v0, a0, rate = 0.5, 1e-10, -0.05, 1e-9, 1e-9
    egg = synthetic(
        p_old=0.0,
        new_permeability=(0.0, 0.0, 0.0),
        a_over_l_m=0.0,
        initial_V=v0,
        bath_fraction=f,
        activation_area_m2=a0,
        schedule=((1.0, rate),),
    )
    run = ref.simulate(egg, 3.0, record=(3.0,), method="LSODA")
    c1 = c0 + egg.new_specific_capacitance_F_m2 * f * (a0 + 2.0 * rate)
    q = c0 * v0
    assert run.at[3.0]["V"] == pytest.approx(q / c1, rel=1e-9)
    assert run.at[3.0]["heat_pJ"] * 1e-12 == pytest.approx(
        0.5 * q * q * (1 / c0 - 1 / c1), rel=1e-8
    )


def test_zone_adds_old_like_conductance():
    """A2: equal compositions make the I-V linear, so Rm = 1/(G_old (1 + zeta))."""
    zeta, area = 0.6, 1e-9
    pulses = ref.Pulses(amplitude_A=1e-10, duration_s=0.12, period_s=0.5, sample_s=0.1)
    egg = synthetic(
        cytosol_mM=BATH,
        cytosol_volume_m3=1e-10,
        old_relative=(1.0, 1.0, 1.0),
        new_permeability=(0.0, 0.0, 0.0),
        a_over_l_m=0.0,
        onset_s=0.5,
        activation_area_m2=area,
        schedule=((0.5, 0.0),),
        zone_ratio=zeta,
        zone_reference_area_m2=area,
        pulses=pulses,
    )
    rm, _ = ref.rm_at(egg, (2, 3), method="LSODA")
    g_old = ref.F**2 / (ref.R * T) * egg.p_old * egg.old_area_m2 * sum(BATH)
    assert rm == pytest.approx(1.0 / (g_old * (1 + zeta)), rel=1e-5)


def test_ring_model_with_one_ring_is_the_registered_lumen():
    egg = growing()
    geom = rings.Rings(1, 2e-6, 1.5e-5)
    a = ref.simulate(egg, 2.1, method="LSODA")
    b = rings.simulate(egg, 2.1, rings=geom, method="LSODA")
    for x, y in zip(pulses_of(a), pulses_of(b), strict=True):
        assert np.max(np.abs(x - y)) < 1e-9


def test_ring_geometry_holds_the_scheduled_face_area():
    egg = growing()
    geom = rings.Rings(4, 3e-6, 9e-6, seed_face_m2=1e-14)
    model = rings.RingModel(egg, geom, 0.0)
    assert model.on_face[0] == 0.0
    assert sum(model.full_face) == pytest.approx(math.pi * (9e-6**2 - 3e-6**2), rel=1e-12)
    face_total = model.on_face[2] + 0.4 * model.full_face[2]  # inner edge inside ring 2
    active = np.array([True, True, True, False])
    face, geo = model.faces(face_total, active)
    assert geo.sum() == pytest.approx(face_total, rel=1e-12)
    assert face.sum() == pytest.approx(face_total + 2 * 1e-14, rel=1e-12)  # seeds of rings 1, 2
    t = rings.time_of_area(egg, 2.0 * model.on_face[2])
    assert egg.area(t) == pytest.approx(2.0 * model.on_face[2], rel=1e-12)


def test_ring_model_on_an_egg_scale_cell_stays_near_the_well_mixed_lumen():
    """N = 3 rings of an egg-scale slit: the same Em as one lumen to well under 0.1 mV over 90 s
    of insertion, with no less K+ in the deep ring than at the mouth."""
    egg = synthetic(
        cytosol_volume_m3=7.8e-10,
        old_area_m2=8.7e-6,
        old_capacitance_F=3.2e-8,
        old_relative=(1.0, 1.0, 0.0),
        p_old=2e-10,
        new_permeability=(4e-9, 1e-7, 0.0),
        new_specific_capacitance_F_m2=6.2e-3,
        onset_s=10.0,
        schedule=((10.0, 1e-9),),
        gap_width_m=2e-6,
        a_over_l_m=1e-6,
    )
    face_end = egg.area(100.0) / 2.0
    r_b, r_m = rings.ring_geometry(0.26e-6, 0.9 * face_end)
    one = ref.simulate(egg, 100.0, record=(100.0,), method="LSODA")
    three = rings.simulate(
        egg, 100.0, rings=rings.Rings(3, r_b, r_m), record=(100.0,), method="LSODA"
    )
    s = three.at[100.0]
    assert all(s["ring_active"])
    k = [c[1] for c in s["ring_mM"]]
    assert k[2] >= k[0] - 1e-9
    assert s["V"] == pytest.approx(one.at[100.0]["V"], abs=1e-4)
