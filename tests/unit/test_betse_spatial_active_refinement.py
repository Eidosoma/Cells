"""Long active native trajectories and resolved temporal self-refinement."""

import copy
import json
import os
import subprocess
from pathlib import Path

import jax
import numpy as np
import pytest

from tests.unit import test_betse_spatial_active as short
from tests.unit.test_betse_tissue_contact import load_capture
from validation.betse.spatial_active import fixtures, reference, refinement

PROTOCOL_PATH = short.PROTOCOL_PATH.with_name("refinement_protocol.json")
PROTOCOL = json.loads(PROTOCOL_PATH.read_text())
CASES = [(case["id"], index) for case in PROTOCOL["cases"] for index in range(3)]
common = short.short


@pytest.fixture(scope="module")
def prior():
    return refinement.completed_prior(PROTOCOL["prior_binding"])


@pytest.fixture(scope="module")
def device():
    jax.config.update("jax_enable_x64", True)
    return jax.devices(common.BACKEND)[0]


def test_completed_prior_binding(prior):
    common.evidence("long-active-prerequisite", prior)


@pytest.fixture(scope="module")
def captured(prior, tmp_path_factory):
    assert prior["status"] == "passed"
    if common.BACKEND == "gpu":
        assert common.EVIDENCE
        path = Path(common.EVIDENCE) / "cpu/long-active-native"
    else:
        root = (
            Path(common.EVIDENCE) / "cpu"
            if common.EVIDENCE
            else tmp_path_factory.mktemp("long-active")
        )
        root.mkdir(parents=True, exist_ok=True)
        path = root / "long-active-native"
        with (
            (root / "long-active-native.stdout.log").open("x") as out,
            (root / "long-active-native.stderr.log").open("x") as err,
        ):
            subprocess.run(
                [
                    "/mnt/workspaces/Cells/venv-betse/bin/python",
                    "-B",
                    str(short.ROOT / "validation/betse/spatial_active/native.py"),
                    "--output",
                    str(path),
                    "--protocol",
                    str(PROTOCOL_PATH),
                ],
                check=True,
                timeout=PROTOCOL["resources"]["native_timeout_seconds"],
                stdout=out,
                stderr=err,
                env=dict(
                    os.environ, MPLBACKEND="Agg", MPLCONFIGDIR=str(root / "matplotlib-long-active")
                ),
            )
    rows = load_capture(path, PROTOCOL)
    for case, index in CASES:
        row, trace = rows[f"{case}/step-{index}/observed"]
        other, _ = rows[f"{case}/step-{index}/bare"]
        for key in (
            "case",
            "dt_s",
            "steps",
            "fixture",
            "geometry",
            "parameters",
            "arrays",
            "species",
            "final",
        ):
            assert row[key] == other[key], key
        assert trace is not None
        assert row["steps"] == round(PROTOCOL["duration_s"] / row["dt_s"])
    return rows


@pytest.fixture(scope="module")
def computed(captured, device):
    values = {}
    for case, index in CASES:
        row, trace = captured[f"{case}/step-{index}/observed"]
        state, layout = fixtures.prepare(row, trace, PROTOCOL)
        final, (states, rates, accepted), valid = common.selected(
            short.RUN, (state, layout, np.asarray(row["dt_s"])), device, row["steps"]
        )
        assert valid and accepted.all()
        fields = common.selected(common.FIELDS, (states.tissue, layout.tissue), device)
        observed = common.observed_history(states.tissue, rates.ordinary, fields, layout.tissue)
        values[(case, index)] = dict(
            row=row,
            trace=trace,
            initial=state,
            layout=layout,
            final=final,
            states=states,
            rates=rates,
            observed=observed,
        )
    return values


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


@pytest.mark.parametrize("case,index", CASES)
def test_long_active_native_trajectory(case, index, computed):
    value = computed[(case, index)]
    native = reference.native_check(value["row"], value["trace"], PROTOCOL)
    report = short.compare(value)
    report.update(
        backend=common.BACKEND,
        observer_neutrality="bitwise",
        native_update_max_errors=native["max_errors"],
        independent_native_pump_error_fmol_s=native["max_pump_error_fmol_s"],
    )
    common.evidence(
        f"long-active-native-trajectory-{case}-{index}",
        report,
        fixtures.arrays(value["states"], value["rates"], value["observed"]),
    )


def test_original_active_prefixes_are_unchanged(prior, computed):
    root = Path(prior["root"])
    old = load_capture(root / "evidence/cpu/active-native", short.PROTOCOL)
    native_count = cells_count = readout_count = 0
    for case in (c["id"] for c in PROTOCOL["cases"]):
        for index in (0, 1):
            value = computed[(case, index)]
            _, trace = old[f"{case}/step-{index}/observed"]
            assert set(trace) == set(value["trace"])
            for name, expected in trace.items():
                if name == "raw_label_s":
                    continue
                actual = value["trace"][name]
                common.bits(
                    actual if name.startswith("initial_") else actual[: len(expected)], expected
                )
                native_count += expected.size
            saved_path = (
                root / f"evidence/{common.BACKEND}/active-native-trajectory-{case}-{index}.npz"
            )
            actual = fixtures.arrays(value["states"], value["rates"], value["observed"])
            with np.load(saved_path, allow_pickle=False) as saved:
                assert set(saved) == set(actual)
                for name in saved:
                    if not name.startswith("observed__"):
                        common.bits(actual[name][: len(saved[name])], saved[name])
                        cells_count += saved[name].size
                derived = {
                    name: actual[name][: len(saved[name])]
                    for name in saved
                    if name.startswith("observed__")
                }
                readout_count += short.compare_cpu_gpu_arrays(
                    derived,
                    {name: saved[name] for name in derived},
                    value["layout"].tissue.membrane_area,
                )
    common.evidence(
        "long-active-native-prefix",
        dict(
            status="passed",
            native_scalars=native_count,
            cells_state_and_rate_scalars=cells_count,
            derived_readout_scalars=readout_count,
            native_and_cells_state_comparison="bitwise",
            derived_readout_comparison="registered_CPU_GPU_tolerances",
            completed_duration_s=64e-6,
            raw_linspace_labels_excluded=True,
        ),
    )


def series(value):
    return dict(
        states=value["states"].tissue._asdict(),
        observed=value["observed"],
        active={
            **{name: x for name, x in value["states"]._asdict().items() if name != "tissue"},
            **{name: x for name, x in value["rates"]._asdict().items() if name != "ordinary"},
        },
    )


@pytest.mark.parametrize("case", [c["id"] for c in PROTOCOL["cases"]])
def test_native_and_cells_active_refinement(case, computed):
    values = [computed[(case, index)] for index in range(3)]
    for value in values[1:]:
        common.bits(value["initial"], values[0]["initial"])
        common.bits(value["layout"], values[0]["layout"])
    area = values[0]["layout"].tissue.membrane_area
    report = refinement.check(case, [series(v) for v in values], area, PROTOCOL)
    report["native"] = refinement.check(
        case, [refinement.native_series(v["row"], v["trace"]) for v in values], area, PROTOCOL
    )
    report["backend"] = common.BACKEND
    common.evidence("long-active-native-refinement-" + case, report)


def test_long_active_disk_windows_and_worlds(computed, device, tmp_path):
    value = computed[("coupled", 2)]
    state, p, dt = value["initial"], value["layout"], np.asarray(value["row"]["dt_s"])
    assert value["row"]["steps"] == 1024
    for i, length in enumerate((257, 389, 378)):
        state, (_, rates, _), valid = common.selected(short.RUN, (state, p, dt), device, length)
        assert valid
        path = tmp_path / f"long-active-restart-{i}.npz"
        np.savez_compressed(path, **fixtures.arrays(state, rates, {}))
        with np.load(path, allow_pickle=False) as saved:
            state = fixtures.restore(saved)
    common.bits(state, value["final"])
    values = [computed[(case, 0)] for case in ("coupled", "pump", "channel")]
    states = jax.tree.map(lambda *x: np.stack(x), *(v["initial"] for v in values))
    layouts = jax.tree.map(lambda *x: np.stack(x), *(v["layout"] for v in values))
    dt = np.asarray(values[0]["row"]["dt_s"])
    together, _, valid = common.selected(short.MAPPED, (states, layouts, dt), device, 256)
    assert valid.all()
    for i, value in enumerate(values):
        common.bits(jax.tree.map(lambda x, i=i: x[i], together), value["final"])
    order = np.asarray([2, 0, 1])
    reordered, _, valid = common.selected(
        short.MAPPED, (*jax.tree.map(lambda x: x[order], (states, layouts)), dt), device, 256
    )
    assert valid.all()
    common.bits(reordered, jax.tree.map(lambda x: x[order], together))
    for i in range(3):
        alone, _, valid = common.selected(
            short.MAPPED,
            (*jax.tree.map(lambda x, i=i: x[i : i + 1], (states, layouts)), dt),
            device,
            256,
        )
        assert valid.all()
        common.bits(alone, jax.tree.map(lambda x, i=i: x[i : i + 1], together))
    common.evidence(
        "long-active-native-replay",
        dict(
            status="passed",
            comparison="bitwise",
            state_arrays=len(jax.tree.leaves(state)),
            disk=True,
            windows=[257, 389, 378],
            mapped_worlds=3,
            reordered=True,
            partitions=True,
            completed_duration_s=256e-6,
        ),
    )


def test_long_active_missing_material_is_rejected(computed):
    value = computed[("coupled", 2)]
    controls = {}
    for name in (
        "reservoir_reset_fmol",
        "stencil_exchange_fmol",
        "pump_cycles_fmol",
        "channel_inward_fmol",
    ):
        changed = copy.deepcopy(value)
        array = (
            getattr(changed["states"].tissue, name)
            if hasattr(changed["states"].tissue, name)
            else getattr(changed["states"], name)
        )
        array[-1].flat[0] += 1e-6
        with pytest.raises(AssertionError):
            short.compare(changed)
        controls[name] = "rejected"
    common.evidence(
        "long-active-native-negative-controls",
        dict(status="passed", corrupted_fmol=1e-6, controls=controls),
    )


def test_long_active_cpu_gpu(computed):
    if common.BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved long active histories")
    assert common.EVIDENCE
    count = 0
    for (case, index), value in computed.items():
        actual = fixtures.arrays(value["states"], value["rates"], value["observed"])
        path = Path(common.EVIDENCE) / "cpu" / f"long-active-native-trajectory-{case}-{index}.npz"
        with np.load(path, allow_pickle=False) as saved:
            count += short.compare_cpu_gpu_arrays(
                actual, saved, value["layout"].tissue.membrane_area
            )
    common.evidence("long-active-native-cpu-gpu", dict(status="passed", compared_scalars=count))


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
