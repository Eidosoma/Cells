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


def test_the_judged_run_needs_a_registered_protocol_and_a_clean_snapshot(tmp_path):
    import hashlib
    import json

    protocol = json.loads(engine.PROTOCOL.read_text())
    assert protocol["status"].startswith("PROPOSED")  # The draft, until the lead registers it.
    assert "not registered" in engine.judged_run_refusal(protocol, tmp_path)
    registered = dict(protocol, status="registered at a lead's commit (test)")
    assert "clean execution snapshot" in engine.judged_run_refusal(registered, tmp_path)
    clean = dict(status="complete", patch_sha256=hashlib.sha256(b"").hexdigest())
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(clean))
    assert engine.judged_run_refusal(registered, tmp_path) is None
    dirty = dict(clean, patch_sha256=hashlib.sha256(b"a change").hexdigest())
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(dirty))
    assert "uncommitted changes" in engine.judged_run_refusal(registered, tmp_path)
    # The draft names every quantity the driver computes, and judges those it judges.
    assert set(protocol["values"]) == set(protocol["quantities"])
    assert set(protocol["judged"]) == set(engine.JUDGED)
    assert {k for k, v in protocol["values"].items() if v["judged"]} == set(engine.JUDGED)


def synthetic(dt):
    """Pulse samples and a lumen whose errors are c dt^2 (second order), for the term logic."""
    from validation.division import cleft_egg_reference as ref

    egg, _, d = engine.rfull()
    error = 1e3 * dt**2
    front = {k: -0.01 - 1e-5 * k + error for k in range(211)}
    sample = {
        k: front[k] + egg.pulses.sign(k) * (0.02 + 1e-6 * k) * (1 + error) for k in range(211)
    }
    lumen = dict(zip(ref.SPECIES, (21.0 + error, 29.0 - error, 50.0), strict=True))
    return egg, d, front, sample, lumen


def test_quantities_terms_and_verdicts_follow_the_plan():
    egg, d, front, sample, lumen = synthetic(0.0)
    q = engine.quantities(front, sample, lumen, egg, d)
    assert q["Q1_em_at_j1_V"] == front[180]
    rm = (abs(sample[179] - front[179]) + abs(sample[180] - front[180])) / 6e-8
    assert q["Q2_rm_at_j1_ohm"] == pytest.approx(rm, rel=1e-15)
    assert q["Q3_rm1_ohm"] == pytest.approx((0.02 + 0.020001) / 6e-8, rel=1e-12)
    assert len(q["Q4_em_trajectory_V"]) == 211
    assert q["Q5_lumen_at_j1_mM"] == {"K": 29.0, "Na": 21.0}
    studies = []
    for dt in engine.STUDY_DTS:
        egg, d, front, sample, lumen = synthetic(dt)
        studies.append(dict(dt=dt, quantities=engine.quantities(front, sample, lumen, egg, d)))
    result = engine.terms(studies)
    assert result["judged_dt"] == engine.JUDGED_DT
    for name in ("Q1_em_at_j1_V", "Q4_em_trajectory_V", "Q5_lumen_K_mM", "Q5_lumen_Na_mM"):
        term = result["terms"][name]
        assert term["observed_order"] == pytest.approx(2.0, abs=1e-6), name
        assert term["step_term"] == pytest.approx(1e3 * 0.75 * engine.JUDGED_DT**2, rel=1e-6)
    assert (
        not result["terms"]["Q3_rm1_ohm"]["judged"] and result["terms"]["Q2_rm_at_j1_ohm"]["judged"]
    )
    # The registered stop condition: every judged step term decreases here, so no stop.
    assert not result["stop"] and result["non_converging"] == []
    # A judged step term that grows from the coarse pair to the judged pair stops the study.
    growing = [dict(s, quantities=dict(s["quantities"])) for s in studies]
    growing[2]["quantities"]["Q1_em_at_j1_V"] = studies[1]["quantities"]["Q1_em_at_j1_V"] + 1.0
    stopped = engine.terms(growing)
    assert stopped["stop"] and stopped["non_converging"] == ["Q1_em_at_j1_V"]
    # The protocol's values: both terms, the order, and 3 x (step term + reference term).
    reference_values = dict(
        reference=engine.flat(studies[2]["quantities"]),
        reference_terms={name: 1e-7 for name in result["terms"]},
    )
    values = engine.protocol_values(result, reference_values)
    for name, entry in values.items():
        step = result["terms"][name]["step_term"]
        assert entry["tolerance"] == 3 * (step + 1e-7), name
        assert entry["observed_order"] == result["terms"][name]["observed_order"], name
        assert entry["judged"] == (name in engine.JUDGED), name
    engine_q = engine.flat(studies[1]["quantities"])
    protocol = dict(values={})
    for name, value in engine_q.items():
        reference = [x + 1e-9 for x in value] if isinstance(value, list) else value + 1e-9
        protocol["values"][name] = dict(
            reference=reference, tolerance=2e-9, judged=name in engine.JUDGED
        )
    items, verdict = engine.verdicts(engine_q, protocol)
    assert verdict == "pass" and all(v["verdict"] == "pass" for v in items.values())
    protocol["values"]["Q5_lumen_K_mM"]["tolerance"] = 1e-10
    assert engine.verdicts(engine_q, protocol)[1] == "fail"
    protocol["values"]["Q5_lumen_K_mM"]["tolerance"] = 2e-9
    protocol["values"]["Q3_rm1_ohm"]["tolerance"] = 0.0  # Reported only: it never fails the run.
    assert engine.verdicts(engine_q, protocol)[1] == "pass"


def test_fill_writes_a_proposed_draft_and_refuses_a_stopped_study(tmp_path):
    import json

    studies = []
    for dt in engine.STUDY_DTS:
        egg, d, front, sample, lumen = synthetic(dt)
        studies.append(dict(dt=dt, quantities=engine.quantities(front, sample, lumen, egg, d)))
    result = engine.terms(studies)
    reference_values = dict(
        reference=engine.flat(studies[2]["quantities"]),
        reference_terms={name: 1e-7 for name in result["terms"]},
    )
    (tmp_path / "terms.json").write_text(json.dumps(result))
    (tmp_path / "reference.json").write_text(json.dumps(reference_values))
    filled = engine.fill(tmp_path / "terms.json", tmp_path / "reference.json")
    assert filled["status"].startswith("PROPOSED")
    assert set(filled["values"]) == set(json.loads(engine.PROTOCOL.read_text())["values"])
    assert all(v["tolerance"] > 0 for v in filled["values"].values())
    stopped = dict(result, stop=True, non_converging=["Q1_em_at_j1_V"])
    (tmp_path / "terms.json").write_text(json.dumps(stopped))
    with pytest.raises(SystemExit, match="stop condition"):
        engine.fill(tmp_path / "terms.json", tmp_path / "reference.json")
