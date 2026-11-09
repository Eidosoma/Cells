"""Protocol parts of the projective qualification driver, end to end (slow).

The patch-voltage map matches the readouts' per-row voltages; one shortened
protocol case runs both parts (projective, checked reference) and is judged; the
F2 pre-scan builds its world and runs one short scale.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from cells.core.specs import parse_spec
from validation.tissue import projective_study as study

PROTOCOL = json.loads(
    (Path(study.__file__).parent / "protocols" / "projective_c_qualification_v1.json").read_text()
)


def test_patch_voltage_map_matches_the_readouts():
    from cells.core.runner import run
    from cells.models import surface_pump_projective as readouts
    from validation.tissue import projective_fixtures

    raw = projective_fixtures.pump_cells(
        [projective_fixtures.H, projective_fixtures.LOADED], end_time=0.05,
        observation_times=[0.0, 0.05],
    )  # fmt: skip
    value = run(parse_spec(raw))
    p = readouts.host_layout(value.final.layout)
    vm = study.row_voltages(value.history, p, study.voltage_map(p))
    for i in (0, len(value.times) - 1):
        row = type(value.history)(*(np.asarray(v[i]) for v in value.history))
        np.testing.assert_allclose(vm[i], readouts.membrane_voltage(row, p), rtol=1e-12, atol=0)


def short_protocol():
    """The registered protocol with A1 shortened to 3 s and a small burst (test only)."""
    protocol = json.loads(json.dumps(PROTOCOL))
    params = protocol["projective_parameters"]
    params.update(burst_steps=200, slope_steps=50)
    params["jump"].update(min_steps=50, max_steps=1000)
    params["tolerance"] = dict(concentration_mM=1e-2, membrane_voltage_V=2e-3, gate=1e-2)
    params["safety"].update(max_membrane_voltage_rate_V_per_s=10.0, max_gate_distance=1.0)
    for case in protocol["cases"]:
        if case["id"] == "A1-pump-pair":
            case.update(horizon_s=3.0, windows=[[0.5, 3.0]], observation_every_s=1.0)
    return protocol


def test_protocol_parts_run_and_pair_by_the_fine_definition(tmp_path):
    from validation.tissue import projective_judge as judge

    protocol = short_protocol()
    projective = study.run_protocol_part(protocol, "projective", "A1-pump-pair", tmp_path)
    reference = study.run_protocol_part(protocol, "reference", "A1-pump-pair", tmp_path)
    assert projective["status"] == reference["status"] == "completed", (projective, reference)
    assert projective["fine_definition_sha256"] == reference["fine_definition_sha256"]
    assert projective["report"]["jumps"] >= 1
    with np.load(tmp_path / "A1-pump-pair-reference-rates.npz") as rates:
        assert len(rates["max_abs_dvm_dt_V_per_s"]) == reference["steps"] + 1
        assert rates["max_abs_dvm_dt_V_per_s"][0] == 0.0
    times = [o["time_s"] for o in reference["observations"]]
    assert times == [o["time_s"] for o in projective["observations"]] == [0.0, 1.0, 2.0, 3.0]
    case = judge.judge_case(protocol, tmp_path, next(
        c for c in protocol["cases"] if c["id"] == "A1-pump-pair"
    ))  # fmt: skip
    outcomes = {c["id"]: c["outcome"] for c in case["criteria"]}
    assert set(outcomes) == {"conservation", "energy", "accuracy", "absolute_caps"}
    assert outcomes["conservation"] == "pass" and outcomes["energy"] == "pass"
    with pytest.raises(FileExistsError):  # A result is never overwritten.
        study.run_protocol_part(protocol, "reference", "A1-pump-pair", tmp_path)


def test_f2_prescan_world_and_one_short_scale():
    """F2's world (one D cell, NaV1.2 scaled) and a 2 s scan record (CPU, selection only)."""
    from validation.tissue import projective_prescan as prescan
    from validation.tissue import surface_pump_v3_fixtures as heredity

    spec = parse_spec(prescan.f2_definition(0.9, end_time=2.0))
    assert len(spec.model.cells) == 1
    record = prescan.lingering(1.0, backend="cpu", horizon=2.0)
    assert record["valid"] and not record["switched"] and record["steps"] == 2000
    assert record["final_vm_V"] > -0.035  # Still on the D branch at the nominal NaV1.2.
    assert heredity.HEREDITY_NAV_M_S == 2.5e-7
