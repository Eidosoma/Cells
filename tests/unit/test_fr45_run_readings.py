"""The FR-4/FR-5 lane's run readings: FR-5's world-agreement check and the FR-5 summary's cost.

Host only, on synthetic files (tier 1). worlds_check passes an arm only with both worlds admitted
and completed over the full step and record counts, bitwise equal; each planted fault fails its
own flag and its arm alone, a missing comparison fails its arm, and a written reading is never
overwritten. The summary's cost per step is the execution time over the steps taken.
"""

import json

from validation.compartment_ph_engine import summarize_reading_fr5 as summary
from validation.compartment_ph_engine import worlds_check

HORIZON_S, DT_S = 400.0, 5e-4  # FR-5's arms: 800000 steps and 401 records


def comparison(arm, **declared):
    """One arm's comparison as world_agreement --compare writes it, both worlds complete and
    bitwise equal; `declared` overrides the declared world's run."""
    runs = {w: dict(admitted=True, completed=True, refusal=None, steps=800000, records=401)
            for w in ("development", "declared")}
    runs["declared"].update(declared)
    return dict(arm=arm, path="vector", horizon_s=HORIZON_S, window_s=[60.0, 120.0],
                start=dict(producer="engine", time_s=1800.0, extract_sha256="a" * 64),
                runs=runs, bitwise=True, differences=[], series_max_abs={})


def folder(path, **arms):
    path.mkdir()
    for arm, data in arms.items():
        (path / f"{arm}.json").write_text(json.dumps(data))
    return path


def test_worlds_check_passes_complete_bitwise_arms_and_each_planted_fault_fails_its_arm(tmp_path):
    good = worlds_check.check(folder(tmp_path / "good", T=comparison("T"), R=comparison("R")),
                              HORIZON_S, HORIZON_S, DT_S)
    assert good["passed"]
    assert (good["arms"]["R"]["expected_steps"], good["arms"]["R"]["expected_records"]) == (
        800000, 401)
    one_world = comparison("R")
    del one_world["runs"]["declared"]
    faults = dict(
        full_steps=comparison("R", steps=799999),
        full_records=comparison("R", records=400),
        both_completed=comparison("R", completed=False, refusal="refused at step 9"),
        both_admitted=comparison("R", admitted=False),
        bitwise=dict(comparison("R"), bitwise=False, differences=[".series.X_L[200]"]),
        both_worlds=one_world)
    for flag, bad in faults.items():
        out = worlds_check.check(folder(tmp_path / flag, T=comparison("T"), R=bad), HORIZON_S,
                                 HORIZON_S, DT_S)
        assert not out["passed"] and out["arms"]["T"]["passed"], flag
        assert not out["arms"]["R"]["passed"] and not out["arms"]["R"][flag], flag
        assert [k for k, v in out["arms"]["R"].items() if v is False] == ["passed", flag], flag
    missing = worlds_check.check(folder(tmp_path / "missing", T=comparison("T")), HORIZON_S,
                                 HORIZON_S, DT_S)
    assert not missing["passed"] and missing["arms"]["R"] == dict(
        passed=False, why="no comparison written (see ARM.log)")


def test_worlds_check_exits_on_the_reading_and_never_overwrites_one(tmp_path, capsys):
    good = folder(tmp_path / "good", T=comparison("T"), R=comparison("R"))
    bad = folder(tmp_path / "bad", T=comparison("T"), R=comparison("R", steps=1))
    args = [str(HORIZON_S), str(HORIZON_S), str(DT_S)]
    assert worlds_check.main([str(good), *args, str(tmp_path / "good.json")]) == 0
    assert worlds_check.main([str(bad), *args, str(tmp_path / "bad.json")]) == 1
    assert json.loads((tmp_path / "bad.json").read_text())["arms"]["R"]["full_steps"] is False
    capsys.readouterr()
    written = (tmp_path / "good.json").read_text()
    try:
        worlds_check.main([str(bad), *args, str(tmp_path / "good.json")])
    except SystemExit as refusal:
        assert "exists" in str(refusal)
    else:
        raise AssertionError("an existing reading was not refused")
    assert (tmp_path / "good.json").read_text() == written


def test_the_summarys_cost_is_execution_time_over_steps_on_engine_parts_only():
    engine = dict(kind="engine", admitted=True, completed=True, steps=800000, wall_s=1100.4,
                  timings=dict(compile_seconds=55.0, execute_seconds=1040.0), refusal=None)
    assert summary.ms_per_step(engine) == 1.3
    assert summary.ms_per_step(dict(engine, timings={})) is None
    assert summary.ms_per_step(dict(engine, steps=0)) is None
    lines = summary.part_lines(dict(parts=dict(T_rung_0p5ms=engine,
                                               reference=dict(kind="reference"))))
    assert len(lines) == 1 and lines[0].startswith("T_rung_0p5ms: admitted True")
    assert "wall 1100 s compile 55.0 s execute 1040.0 s (1.3 ms per step)" in lines[0]
