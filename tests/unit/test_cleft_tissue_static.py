"""R-tissue's static entry point reproduces R-full on synthetic cells (S5 design §7.2).

R-tissue runs here through R-full's runner hook (cleft_tissue_reference.runner, which calls
simulate_static): the potential at every pulse edge, the lumen, the heat, the state, and R-full's
own Rm and calibration functions. Every cell is a synthetic fixture (tests/division_fixtures.py),
not the J1 egg. This module holds no division (the J2 bright line, design §10.1).
"""

import ast
import math
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from tests.division_fixtures import growing, synthetic
from validation.division import cleft_egg_reference as ref
from validation.division import cleft_tissue_reference as rt

ROOT = Path(__file__).resolve().parents[2]

TARGET_V = 1e-10  # Design §7.2: R-tissue reproduces R-full to 1e-10 V on every pulse edge.
FAST = ref.Pulses(amplitude_A=2e-10, duration_s=0.12, period_s=0.5, sample_s=0.1)
KW = dict(rtol=1e-9, method="LSODA")  # As R-full's own calibration tests.


def pulse_edges(a, b):
    assert set(a.onset_V) == set(b.onset_V) and set(a.sample_V) == set(b.sample_V)
    front = max(abs(a.onset_V[k] - b.onset_V[k]) for k in a.onset_V)
    sample = max(abs(a.sample_V[k] - b.sample_V[k]) for k in a.sample_V)
    return front, sample


@pytest.mark.parametrize("law", ["logmean", "constant_field"])
def test_every_pulse_edge_the_lumen_and_the_state_reproduce_r_full(law):
    egg = growing(access_law=law)
    record = (0.25, 0.5, 1.0, 2.0, 3.0)
    a = ref.simulate(egg, 3.0, record=record)
    b = rt.runner(egg, 3.0, record=record)
    front, sample = pulse_edges(a, b)
    assert len(a.onset_V) == 7 and len(a.sample_V) == 6
    assert front <= TARGET_V and sample <= TARGET_V
    assert b.v0 == pytest.approx(a.v0, abs=1e-15)
    assert b.background_fmol == pytest.approx(a.background_fmol, rel=1e-12)
    for t in record:
        x, y = a.at[t], b.at[t]
        assert y["V"] == pytest.approx(x["V"], abs=TARGET_V)
        assert y["cytosol_mM"] == pytest.approx(x["cytosol_mM"], rel=1e-12)
        assert y["heat_pJ"] == pytest.approx(x["heat_pJ"], rel=1e-8, abs=1e-15)
        assert y["capacitor_energy_J"] == pytest.approx(x["capacitor_energy_J"], rel=1e-8)
        if t < egg.onset_s:
            assert x["lumen_mM"] is None and y["lumen_mM"] is None
            continue
        assert y["lumen_mM"] == pytest.approx(x["lumen_mM"], rel=1e-9)
        assert y["phi_lumen"] == pytest.approx(x["phi_lumen"], abs=TARGET_V)
        assert y["area"] == pytest.approx(x["area"], rel=1e-14)
        assert y["c_new"] == pytest.approx(x["c_new"], rel=1e-14)
        sx, sy = np.array(x["state"]), np.array(y["state"])
        charge_tol = TARGET_V * egg.old_capacitance_F / (ref.F * ref.FMOL)
        for i in (ref.QI, ref.QC):
            assert abs(sy[i] - sx[i]) <= charge_tol
        for i in (ref.NAI, ref.KI, ref.NAC, ref.KC):
            assert sy[i] == pytest.approx(sx[i], rel=1e-10)


def test_a_cell_before_its_onset_reproduces_r_full():
    egg = synthetic(onset_s=1e9, pulses=FAST)
    a = ref.simulate(egg, 2.0, record=(2.0,))
    b = rt.runner(egg, 2.0, record=(2.0,))
    assert max(pulse_edges(a, b)) <= TARGET_V
    assert b.at[2.0]["lumen_mM"] is None and b.at[2.0]["heat_pJ"] == 0.0


def test_rm_and_the_old_membrane_calibration_through_the_runner():
    # The onset moved after the Rm1 pair, as calibrate_old requires.
    egg = growing(onset_s=1.2)
    rm_full, _ = ref.rm_at(egg, (0, 1), **KW)
    rm_tissue, _ = ref.rm_at(egg, (0, 1), runner=rt.runner, **KW)
    assert rm_tissue == pytest.approx(rm_full, rel=1e-8)
    p_full = ref.calibrate_old(egg, 2.0e8, (0, 1), **KW)
    p_tissue = ref.calibrate_old(egg, 2.0e8, (0, 1), runner=rt.runner, **KW)
    assert p_tissue == pytest.approx(p_full, rel=1e-8)
    rm, _ = ref.rm_at(replace(egg, p_old=p_tissue), (0, 1), runner=rt.runner, **KW)
    assert rm == pytest.approx(2.0e8, rel=1e-8)


def test_the_access_calibration_through_the_runner():
    egg = synthetic(
        onset_s=0.5,
        new_permeability=(1e-10, 1e-6, 0.0),
        schedule=((0.5, 0.0),),
        pulses=FAST,
        activation_area_m2=1e-9,
    )
    sealed, _ = ref.rm_at(replace(egg, a_over_l_m=0.0), (2, 3), runner=rt.runner, **KW)
    open_, _ = ref.rm_at(replace(egg, a_over_l_m=1e-3), (2, 3), runner=rt.runner, **KW)
    target = math.sqrt(sealed * open_)
    full, _ = ref.calibrate_access(egg, target, (2, 3), guess=1e-7, xtol=1e-8, **KW)
    tissue, _ = ref.calibrate_access(
        egg, target, (2, 3), guess=1e-7, xtol=1e-8, runner=rt.runner, **KW
    )
    assert sealed > 2 * target and target > 2 * open_
    assert tissue == pytest.approx(full, rel=1e-6)


def test_a_schedule_that_starts_before_the_onset_opens_with_r_fulls_area():
    egg = growing(onset_s=1.2)  # The schedule starts at 0.5 s.
    world = rt.from_egg(egg)
    new = world.patches["new"]
    assert new.area_m2 == egg.area(1.2) and new.schedule == ((1.2, 2e-10),)
    a = ref.simulate(egg, 2.0, record=(1.2, 2.0))
    b = rt.runner(egg, 2.0, record=(1.2, 2.0))
    assert b.at[2.0]["area"] == pytest.approx(a.at[2.0]["area"], rel=1e-14)
    assert max(pulse_edges(a, b)) <= TARGET_V


def test_from_egg_reads_r_fulls_fields_and_refuses_its_extensions():
    egg = growing()
    world = rt.from_egg(egg)
    old, new = world.patches["old"], world.patches["new"]
    assert old.permeability_m_s == tuple(egg.p_old * w for w in egg.old_relative)
    assert (old.area_m2, old.capacitance_F) == (egg.old_area_m2, egg.old_capacitance_F)
    assert new.permeability_m_s == egg.new_permeability and new.onset_s == egg.onset_s
    assert world.faces["access"].a_over_l_m == egg.a_over_l_m
    assert world.injections[0].carriers == {"K": 0.4912, "Cl": 0.5088}
    assert world.cells["egg"].volume_pL == egg.cytosol_volume_m3 / 1e-15
    assert world.origin == rt.ORIGIN_EGG and not world.divisions
    for change in (
        dict(bath_fraction=0.1),
        dict(zone_ratio=0.2, zone_reference_area_m2=1e-9),
        dict(access_shape=("ramp", 0.5, 0.0, 1.0)),
        dict(new_faces="bath"),
        dict(old_capacitance_rate_F_s=1e-12),
        dict(schedule=((0.7, 1e-10),)),
    ):
        with pytest.raises(ValueError):
            rt.from_egg(replace(egg, **change))


def test_the_static_entry_point_never_loads_the_partition_map():
    """The J2 bright line at run time: a static run (a synthetic egg through the runner hook, in
    a fresh process) leaves every partition module unloaded, as in the J1 cross-check's process."""
    code = (
        "import sys\n"
        "from tests.division_fixtures import growing\n"
        "from validation.division import cleft_tissue_reference as rt\n"
        "rt.runner(growing(), 1.0)\n"
        "print(sorted(m for m in sys.modules if m.startswith('validation.division')))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True
    )
    loaded = ast.literal_eval(out.stdout.strip().splitlines()[-1])
    assert "validation.division.cleft_tissue_reference" in loaded
    assert not [m for m in loaded if "partition" in m]
