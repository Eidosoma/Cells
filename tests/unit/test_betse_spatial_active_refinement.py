"""The long active panel's protocol, its self-refinement rule and its predecessor check.

The 21 rows on the long native captures left on 25 November 2026. They could not start: the
predecessor check refuses since the src files it binds changed (11 October 2026). The tag
pre-cleanup-2026-11-25 keeps them; it does not run them either.
"""

import copy
import json

import numpy as np
import pytest

from tests.unit import test_betse_spatial_active as short
from validation.betse.spatial_active import refinement

PROTOCOL_PATH = short.PROTOCOL_PATH.with_name("refinement_protocol.json")
PROTOCOL = json.loads(PROTOCOL_PATH.read_text())
CASES = [(case["id"], index) for case in PROTOCOL["cases"] for index in range(3)]


def test_long_protocol_keeps_physics_and_tolerances():
    assert PROTOCOL["tolerances"] == short.PROTOCOL["tolerances"]
    assert PROTOCOL["native_update_tolerances"] == short.PROTOCOL["native_update_tolerances"]
    assert PROTOCOL["duration_s"] == 4 * short.PROTOCOL["duration_s"] == 256e-6
    assert PROTOCOL["native_steps_s"] == [1e-6, 5e-7, 2.5e-7]
    assert PROTOCOL["automatic_followup"] is False
    assert PROTOCOL["expected_cpu_skips"] == 3
    assert len(CASES) == 12
    assert PROTOCOL["cases"] == [
        case
        for case in short.PROTOCOL["cases"]
        if case["id"] in ("pump", "channel", "coupled", "partial")
    ]
    for name in (
        "species",
        "initial_gate",
        "pump_parameters",
        "temperature_K",
        "gj_surface_fraction",
        "initial_voltage_extent_V",
        "base_concentration_mM",
        "outside_mM",
        "concentration_gradient_mM",
    ):
        assert PROTOCOL[name] == short.PROTOCOL[name]


def synthetic_series():
    protocol = copy.deepcopy(PROTOCOL)
    protocol.update(duration_s=4.0, native_steps_s=[1.0, 0.5, 0.25])
    protocol["refinement"]["common_completed_times_s"] = [1.0, 2.0, 4.0]
    values = []
    for step in protocol["native_steps_s"]:
        n = round(4 / step)
        history = np.full((n, 2), 0.2 + 0.01 * step)
        values.append(
            dict(
                states={"membrane_inward_fmol": history.copy()},
                observed={key: history.copy() for key in ("vm", "fluxes_mem", "fluxes_gj")},
                active={key: history.copy() for key in refinement.ACTIVE_FIELDS},
            )
        )
    return protocol, values


def test_active_refinement_resolves_gate_and_flux_units():
    protocol, values = synthetic_series()
    report = refinement.check("coupled", values, np.ones(2), protocol)
    for checkpoint in report["checkpoints"]:
        assert all(
            v["first_order_resolved"] and v["ratio"] == pytest.approx(2)
            for v in checkpoint["fields"].values()
        )
    assert refinement.tolerance("m_gate", short.TOL) == (
        short.TOL["gate_atol"],
        short.TOL["gate_rtol"],
    )
    assert refinement.tolerance("channel_inward_fmol_s", short.TOL) == (
        short.TOL["flux_atol_fmol_s"],
        short.TOL["flux_rtol"],
    )


@pytest.mark.parametrize(
    "fault",
    [
        "missing_gate",
        "unresolved_gate",
        "gate_nonfinite",
        "wrong_order",
        "worse",
        "truncated",
        "zero_time",
        "off_grid",
        "wrong_steps",
        "shape",
    ],
)
def test_active_refinement_rejects_false_claims(fault):
    protocol, values = synthetic_series()
    if fault == "missing_gate":
        del values[0]["active"]["m_gate"]
    elif fault == "unresolved_gate":
        for value in values:
            value["active"]["m_gate"][:] = 0.2
    elif fault == "gate_nonfinite":
        values[2]["active"]["m_gate"][-1, 0] = np.nan
    elif fault == "wrong_order":
        values[2]["active"]["m_gate"][:] = 0.201
    elif fault == "worse":
        values[2]["active"]["m_gate"][:] = 0.5
    elif fault == "truncated":
        values[2]["active"]["m_gate"] = values[2]["active"]["m_gate"][:-1]
    elif fault == "zero_time":
        protocol["refinement"]["common_completed_times_s"][0] = 0
    elif fault == "off_grid":
        protocol["refinement"]["common_completed_times_s"][0] = 0.9
    elif fault == "wrong_steps":
        protocol["native_steps_s"][0] = 0.75
    else:
        values[2]["active"]["m_gate"] = values[2]["active"]["m_gate"][:, :1]
    with pytest.raises(AssertionError):
        refinement.check("coupled", values, np.ones(2), protocol)


def fake_completed(tmp_path):
    """Small synthetic receipt tree for checking rejection, never scientific evidence."""
    root, current = tmp_path / "prior", tmp_path / "current"

    def write(name, value):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n")

    write("source/src/physics.py", "registered source")
    (current / "src").mkdir(parents=True)
    (current / "src/physics.py").write_bytes((root / "source/src/physics.py").read_bytes())
    protocol = dict(
        expected_cpu_skips=0,
        expected_cpu_skip_nodes=[],
        required_evidence=["report"],
        required_gpu_evidence=[],
    )
    write("component-protocol.json", protocol)
    nodes = ["tests/unit/test_fixture.py::test_source"]
    reg = dict(
        component_protocol=protocol,
        component_protocol_sha256=refinement.digest(root / "component-protocol.json"),
        sources_sha256={"src/physics.py": refinement.digest(root / "source/src/physics.py")},
        test_nodes=nodes,
    )
    write("registration.json", reg)
    names = ["component-protocol.json"]
    suites = {}
    for backend in ("cpu", "gpu"):
        write(f"evidence/{backend}/report.json", {"status": "passed"})
        xml = f"{backend}.xml"
        (root / xml).write_text(
            '<testsuites><testsuite tests="1" errors="0" failures="0" skipped="0">'
            '<testcase classname="tests.unit.test_fixture" name="test_source"/>'
            "</testsuite></testsuites>"
        )
        names.extend([xml, f"evidence/{backend}/report.json"])
        suites[backend] = dict(tests=1, errors=0, failures=0, skipped=0)
    write("gpu-metrics/raw.jsonl", {"sample": 1})
    write(
        "result.json",
        dict(
            status="completed",
            registration_sha256=refinement.digest(root / "registration.json"),
            suites=suites,
            gpu_metrics={
                "evidence_sha256": {"raw.jsonl": refinement.digest(root / "gpu-metrics/raw.jsonl")}
            },
        ),
    )
    write(
        "completion.json",
        dict(
            status="completed",
            result_sha256=refinement.digest(root / "result.json"),
            evidence_sha256={name: refinement.digest(root / name) for name in names},
        ),
    )
    binding = dict(
        root=str(root),
        registration_sha256=refinement.digest(root / "registration.json"),
        require_completed_cpu_and_gpu=True,
    )
    return root, current, binding, write


def test_prerequisite_authentication_accepts_complete_synthetic_receipt(tmp_path):
    _, current, binding, _ = fake_completed(tmp_path)
    report = refinement.completed_prior(binding, current_root=current)
    assert report["status"] == "passed" and report["required_passing_evidence"] == 2
    assert report["unchanged_production_files"] == 1


@pytest.mark.parametrize(
    "fault",
    [
        "unfinished",
        "failed",
        "result_status",
        "source",
        "current_source",
        "metric",
        "unbound_evidence",
        "failed_evidence",
        "unexpected_skip",
    ],
)
def test_prerequisite_authentication_refuses_invalid_receipts(tmp_path, fault):
    root, current, binding, write = fake_completed(tmp_path)
    if fault == "unfinished":
        (root / "completion.json").unlink()
    elif fault == "failed":
        write("failure.json", {"status": "failed"})
    elif fault == "source":
        write("source/src/physics.py", "changed")
    elif fault == "current_source":
        (current / "src/physics.py").write_text("changed")
    elif fault == "metric":
        write("gpu-metrics/raw.jsonl", {"sample": 2})
    else:
        done = json.loads((root / "completion.json").read_text())
        if fault == "result_status":
            result = json.loads((root / "result.json").read_text())
            result["status"] = "failed"
            write("result.json", result)
            done["result_sha256"] = refinement.digest(root / "result.json")
        elif fault == "unbound_evidence":
            del done["evidence_sha256"]["evidence/gpu/report.json"]
        elif fault == "failed_evidence":
            write("evidence/gpu/report.json", {"status": "failed"})
            done["evidence_sha256"]["evidence/gpu/report.json"] = refinement.digest(
                root / "evidence/gpu/report.json"
            )
        else:
            xml = root / "cpu.xml"
            xml.write_text(
                xml.read_text()
                .replace('skipped="0"', 'skipped="1"')
                .replace("/></testsuite>", "><skipped/></testcase></testsuite>")
            )
            result = json.loads((root / "result.json").read_text())
            result["suites"]["cpu"]["skipped"] = 1
            write("result.json", result)
            done["result_sha256"] = refinement.digest(root / "result.json")
            done["evidence_sha256"]["cpu.xml"] = refinement.digest(xml)
        write("completion.json", done)
    with pytest.raises(ValueError):
        refinement.completed_prior(binding, current_root=current)
