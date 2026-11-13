"""Tier-1 test of S3's engine egg definition (validation/division/cleft_egg_engine.py).

The definition is R-full's own egg (cleft_egg_reference.build with the record's P_old and A/L):
the composite accepts it, and compare finds every field equal to R-full's to 1e-12 relative,
apart from the cytosol's charge anchor, which carries R-full's C_old v0 to its egg-scale
granularity (a declared difference with its bound). Its event and observation times lie on each
step of the study, at R-full's times.
"""

import jax
import pytest

from cells.core.specs import parse_spec
from validation.division import cleft_egg_engine as engine

EXACT = (
    "temperature_K",
    "cytosol_mM_activity_basis",
    "bath_mM_activity_basis",
    "lumen_onset_mM_activity_basis",
    "lumen_onset_charge_C",
    "old_area_m2_folded",
    "old_capacitance_F",
    "old_permeability_m_s_per_area",
    "new_activation_area_m2",
    "new_capacitance_at_onset_F",
    "new_specific_capacitance_F_m2",
    "new_permeability_m_s_per_area",
    "access_m3_s",
    "gap_width_m",
    "lumen_onset_volume_m3",
    "onset_s",
    "insertion_rate_m2_s",
    "pulse_currents_A",
    "carriers",
)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def test_the_engine_egg_is_rfulls_field_by_field():
    raw = engine.definition()
    parse_spec(raw)  # Every definition check of the composition passes.
    report = engine.compare_report(raw)
    assert report["mismatched"] == [], report["mismatched"]
    assert set(report["declared"]) <= set(engine.ANCHORED_ROWS)
    assert report["matched"] + len(report["declared"]) == report["fields"]
    rows = report["differences"]
    assert rows["access_law"]["equal"]
    for name in EXACT:
        assert rows[name]["max_relative_difference"] == 0.0, name
    assert engine.anchor_granularity(raw) < 1e-8  # The declared bound stays small.


def test_event_and_observation_times_lie_on_each_study_step():
    for dt in engine.STUDY_DTS:
        raw = engine.definition(dt)
        experiment = raw["experiment"]
        times = [c["time"] for c in experiment["injection_controls"][0]["schedule"]]
        times += [experiment["insertion_controls"][0]["onset_time"]]
        times += experiment["observation_times"]
        assert all(round(t / dt) * dt == t for t in times), dt
        rows = engine.compare(raw)
        for name in ("pulse_times_s", "observation_times_s"):
            assert rows[name]["max_relative_difference"] <= 1e-15, (dt, name)
        assert rows["onset_s"]["max_relative_difference"] == 0.0, dt
