"""Active temporal refinement and prerequisite authentication; no model imports."""

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from validation.betse.spatial_trajectory import refinement as passive

ACTIVE_FIELDS = (
    "m_gate",
    "h_gate",
    "pump_cycles_fmol_s",
    "channel_inward_fmol_s",
    "pump_cycles_fmol",
    "channel_inward_fmol",
)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def completed_prior(binding, *, current_root=None):
    """Refuse unfinished/failed evidence and changes to the production model.

    The known registration binds the intended source and acceptance criteria;
    completion must bind passing reports, complete evidence and those sources.
    This never waits, writes to the predecessor or schedules a continuation.
    """
    root = Path(binding["root"])
    current_root = Path(__file__).resolve().parents[3] if current_root is None else current_root

    def require(ok, message):
        if not ok:
            raise ValueError(message)

    def read(name):
        path = root / name
        require(path.is_file(), "Predecessor is incomplete: missing " + name)
        return json.loads(path.read_text())

    def verify(base, records):
        for name, expected in records.items():
            path = base / name
            require(path.resolve().is_relative_to(base.resolve()), "Unsafe prerequisite path")
            require(path.is_file() and digest(path) == expected, "Changed prerequisite: " + name)

    require(binding["require_completed_cpu_and_gpu"] is True, "Complete CPU/L4 evidence required")
    reg = read("registration.json")
    require(
        digest(root / "registration.json") == binding["registration_sha256"],
        "Predecessor registration changed",
    )
    require(not (root / "failure.json").exists(), "Predecessor qualification failed")
    done, result = read("completion.json"), read("result.json")
    require(done["status"] == result["status"] == "completed", "Predecessor is not completed")
    require(digest(root / "result.json") == done["result_sha256"], "Predecessor result changed")
    require(
        result["registration_sha256"] == binding["registration_sha256"], "Wrong result registration"
    )
    protocol = reg["component_protocol"]
    require(
        digest(root / "component-protocol.json") == reg["component_protocol_sha256"],
        "Predecessor protocol changed",
    )
    require(read("component-protocol.json") == protocol, "Predecessor protocol differs")
    verify(root, done["evidence_sha256"])
    verify(root / "source", reg["sources_sha256"])
    verify(root / "gpu-metrics", result["gpu_metrics"]["evidence_sha256"])
    production = {
        name: sha for name, sha in reg["sources_sha256"].items() if name.startswith("src/")
    }
    require(bool(production), "Predecessor has no production source binding")
    verify(current_root, production)
    expected_nodes = reg["test_nodes"]
    require(
        bool(expected_nodes) and len(set(expected_nodes)) == len(expected_nodes),
        "Invalid test inventory",
    )
    require(
        protocol["expected_cpu_skips"] == len(protocol["expected_cpu_skip_nodes"]),
        "Inconsistent predecessor skip registration",
    )
    required = 0
    for backend in ("cpu", "gpu"):
        xml = root / (backend + ".xml")
        require(backend + ".xml" in done["evidence_sha256"], "Unbound test report")
        tree = ET.parse(xml).getroot()
        suites = [tree] if tree.tag == "testsuite" else list(tree.iter("testsuite"))
        totals = {
            key: sum(int(s.attrib[key]) for s in suites)
            for key in ("tests", "errors", "failures", "skipped")
        }
        cases = list(tree.iter("testcase"))
        nodes = [
            case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"]
            for case in cases
        ]
        skipped = [
            name
            for name, case in zip(nodes, cases, strict=True)
            if case.find("skipped") is not None
        ]
        expected_skips = protocol["expected_cpu_skip_nodes"] if backend == "cpu" else []
        require(totals == result["suites"][backend], "Result and test report disagree")
        require(
            totals["tests"] == len(nodes) == len(expected_nodes)
            and set(nodes) == set(expected_nodes),
            "Incomplete predecessor test inventory",
        )
        require(
            totals["errors"] == totals["failures"] == 0
            and not any(
                c.find("failure") is not None or c.find("error") is not None for c in cases
            ),
            "Predecessor tests failed",
        )
        require(
            sorted(skipped) == sorted(expected_skips) and totals["skipped"] == len(skipped),
            "Unexpected predecessor skip",
        )
        names = protocol["required_evidence"] + (
            protocol["required_gpu_evidence"] if backend == "gpu" else []
        )
        for name in names:
            relative = f"evidence/{backend}/{name}.json"
            require(relative in done["evidence_sha256"], "Unbound required evidence")
            require(read(relative)["status"] == "passed", "Required predecessor evidence failed")
            required += 1
    return dict(
        status="passed",
        root=str(root),
        completion_sha256=digest(root / "completion.json"),
        registration_sha256=binding["registration_sha256"],
        verified_evidence=len(done["evidence_sha256"]),
        verified_sources=len(reg["sources_sha256"]),
        unchanged_production_files=len(production),
        required_passing_evidence=required,
    )


def native_series(row, trace):
    result = passive.native_series(row, trace)
    indices = np.flatnonzero((trace["method"] == 3) & trace["after"])
    area = np.asarray(row["geometry"]["mem_sa"])
    cycles = trace["rate_NaKATP"][indices] * area * 1e15 / 3
    if not row["parameters"]["cluster_open"]:
        cycles[:, np.asarray(row["geometry"]["bflags_mems"], dtype=int)] = 0
    channel = trace["channel_flux"][indices] * area * 1e15
    result["active"] = dict(
        m_gate=trace["m_gate"][indices],
        h_gate=trace["h_gate"][indices],
        pump_cycles_fmol_s=cycles,
        channel_inward_fmol_s=channel,
        pump_cycles_fmol=np.cumsum(cycles * row["dt_s"], axis=0),
        channel_inward_fmol=np.cumsum(channel * row["dt_s"], axis=0),
    )
    return result


def quantities(series, index, area):
    values = passive.quantities(series, index, area)
    assert set(series["active"]) == set(ACTIVE_FIELDS), "Incomplete active history"
    for key in ACTIVE_FIELDS:
        data = np.asarray(series["active"][key])
        assert data.ndim == 2 and data.shape[1:] == np.asarray(area).shape
        assert 0 <= index < len(data), "Completed-time checkpoint is outside the history"
        values[key] = data[index]
    return values


def tolerance(name, tol):
    if name in ("m_gate", "h_gate"):
        return tol["gate_atol"], tol["gate_rtol"]
    if name.endswith("fmol_s"):
        return tol["flux_atol_fmol_s"], tol["flux_rtol"]
    return passive.tolerance(name, tol)


def check(case, series, area, protocol):
    rule, tol = protocol["refinement"], protocol["tolerances"]
    steps = np.asarray(protocol["native_steps_s"], dtype=float)
    times = np.asarray(rule["common_completed_times_s"], dtype=float)
    assert len(series) == len(steps) == 3
    assert np.isfinite(steps).all() and (steps > 0).all()
    assert steps[0] == 2 * steps[1] == 4 * steps[2]
    assert times.ndim == 1 and times.size > 0 and np.isfinite(times).all()
    assert (times > 0).all() and (np.diff(times) > 0).all()
    assert times[-1] == protocol["duration_s"]
    for values, h in zip(series, steps, strict=True):
        expected = round(protocol["duration_s"] / h)
        for section in ("states", "observed", "active"):
            assert all(np.asarray(v).shape[0] == expected for v in values[section].values()), (
                "Incomplete common-time history"
            )
    checkpoints = []
    for time in times:
        indices = [round(time / step) - 1 for step in steps]
        assert all(
            abs((i + 1) * h - time) < 1e-18 and i >= 0 for i, h in zip(indices, steps, strict=True)
        )
        values = [quantities(s, index, area) for s, index in zip(series, indices, strict=True)]
        assert set(values[0]) == set(values[1]) == set(values[2])
        fields = {
            name: passive.differences(*(v[name] for v in values), *tolerance(name, tol), rule)
            for name in values[0]
        }
        checkpoints.append(dict(completed_time_s=float(time), fields=fields))
    for name in rule["required_resolved_final_fields"][case]:
        assert checkpoints[-1]["fields"][name]["first_order_resolved"], (
            "Required active refinement signal unresolved: " + name
        )
    return dict(
        status="passed",
        case=case,
        checkpoints=checkpoints,
        first_order_scope=(
            "Resolved fields only; temporal self-refinement, not continuum or spatial accuracy"
        ),
    )
