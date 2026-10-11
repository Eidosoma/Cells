"""Software-only solver, record, refinement and integration-interface checks."""

import ast
import copy
import importlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ctx = importlib.import_module("feedback_context")
io = importlib.import_module("feedback_io")
ref = importlib.import_module("feedback_reference")
refcheck = importlib.import_module("feedback_reference_check")
compare = importlib.import_module("feedback_compare")
cells_driver = importlib.import_module("feedback_cells")
job = importlib.import_module("feedback_job")
c = ctx.c


def parameters(enabled=(True, True), maximum=1e-8):
    return {
        "F": 96485.33212331001,
        "R": 8.31446261815324,
        "temperature_K": 298.15,
        "volume_pL": [0.5, 0.8],
        "area_m2": [3e-10, 4e-10],
        "cm_F_per_m2": 0.01,
        "initial_K_fmol": [70.0, 112.0],
        "outside_volume_pL": 5.0,
        "outside_K_fmol": 20.0,
        "initial_voltage_V": [-0.035, -0.05],
        "channel_enabled": list(enabled),
        "Pmax_m_per_s": [maximum if value else 0.0 for value in enabled],
    }


@pytest.fixture(scope="module")
def protocol():
    return c.read(ctx.PROTOCOL)


@pytest.fixture(scope="module")
def reference_records(protocol):
    return {
        s["id"]: ref.integrate(parameters(), s, protocol) for s in protocol["reference"]["solves"]
    }


@pytest.mark.parametrize("mask", [(True, True), (False, False), (True, False), (False, True)])
def test_reference_active_axes_do_not_perturb_absent_gates(mask):
    p = parameters(mask)
    state = ref.initial_state(p)
    q, m, h, energy = ref.unpack(p, state)
    assert len(state) == 4 + 2 * sum(mask)
    assert q == energy == [0.0, 0.0]
    assert m == [0.2 if value else 0.0 for value in mask]
    assert h == [0.6 if value else 0.0 for value in mask]
    assert len(ref.derivative(p, state)) == len(state)


def test_shared_bath_and_gate_state_are_coupled():
    p = parameters()
    state = ref.initial_state(p)
    base = ref.readout(p, state)
    state[0] = -1e-5
    changed = ref.readout(p, state)
    assert changed["voltage_V"][0] < base["voltage_V"][0]
    assert changed["voltage_V"][1] == base["voltage_V"][1]
    assert changed["bath_K_fmol"] > base["bath_K_fmol"]
    assert changed["flux_fmol_per_s"][1] != base["flux_fmol_per_s"][1]


@pytest.mark.parametrize("setting", ["dop853_base", "dop853_tight", "radau_check"])
def test_reference_dense_and_domain_contract(reference_records, protocol, setting):
    record = reference_records[setting]
    chosen = next(s for s in protocol["reference"]["solves"] if s["id"] == setting)
    refcheck.validate_record(record, parameters(), chosen, protocol)
    assert record["stats"]["accepted_steps"] > 0
    assert record["stats"]["rhs_calls_including_jacobian"] >= record["stats"]["nfev"]
    for time_s, expected in zip(record["sample_times_s"], record["sample_states"], strict=True):
        np.testing.assert_allclose(
            refcheck.sample_state(record, time_s), expected, atol=5e-14, rtol=2e-13
        )


def test_independent_reference_methods_converge_on_synthetic_coupling(reference_records, protocol):
    primary = reference_records["dop853_tight"]
    ledger = io.Ledger(protocol["reference"]["comparison_absolute"])
    for key in ("dop853_base", "radau_check"):
        for i, (left, right) in enumerate(
            zip(reference_records[key]["readouts"], primary["readouts"], strict=True)
        ):
            for field, a, b in refcheck.point_pairs(left, right):
                ledger.compare(f"{key}/{i}/{field}", a, b, field)
    assert ledger.failed == 0, ledger.failures[:5]


@pytest.fixture(scope="module")
def synthetic_gate_data(reference_records, protocol):
    plan = copy.deepcopy(protocol)
    plan["reference"]["sample_dt_s"] = 0.001
    parameters_by_variant, records = {}, {}
    for variant in plan["variants"]:
        enabled = variant in ("blocked_channel", "active_channel")
        p = parameters((enabled, enabled), 1e-8 if variant == "active_channel" else 0)
        parameters_by_variant[variant] = p
        for setting in plan["reference"]["solves"]:
            if variant == "active_channel":
                row = copy.deepcopy(reference_records[setting["id"]])
                for field in ("sample_times_s", "sample_states", "readouts"):
                    row[field] = row[field][::160]
            else:
                row = ref.integrate(p, setting, plan)
            records[variant + "/" + setting["id"]] = row
    return {"protocol": plan, "reference_parameters": parameters_by_variant}, records


@pytest.mark.parametrize("fault", [None, "saved_readout", "dense_coefficient"])
def test_full_reference_gate_from_saved_synthetic_records(synthetic_gate_data, tmp_path, fault):
    r, originals = synthetic_gate_data
    records = copy.deepcopy(originals)
    if fault == "saved_readout":
        records["active_channel/dop853_tight"]["readouts"][-1]["voltage_V"][0] += 1e-4
    elif fault == "dense_coefficient":
        records["active_channel/dop853_tight"]["dense_intervals"][0]["coefficients"][0][0] += 1e-4
    aggregate = {"reference_solves": 12, "records": {}}
    for i, (key, record) in enumerate(records.items()):
        name = f"reference-{i}.json.gz"
        io.write_compressed(tmp_path / name, record)
        aggregate["records"][key] = name
    result = refcheck.check(r, tmp_path, aggregate)
    assert (result["status"] == "pass") is (fault is None)
    assert result["reference_convergence_checked"] is (fault is None)
    assert result["coupled_trajectory_qualified"] is False
    assert io.read_compressed(tmp_path / "reference-gate.json.gz") == result


def test_dissipation_matches_independent_closed_system_free_energy(reference_records):
    for state in reference_records["dop853_tight"]["sample_states"][::40]:
        q, _m, _h, energy = ref.unpack(parameters(), state)
        assert math.fsum(energy) == pytest.approx(
            refcheck.thermodynamic_dissipation(parameters(), q), abs=1e-11
        )


@pytest.mark.parametrize(
    "mask,maximum", [((False, False), 0), ((True, True), 0), ((True, False), 0)]
)
def test_blocked_reference_preserves_amount_and_keeps_present_gates(protocol, mask, maximum):
    p = parameters(mask, maximum)
    record = ref.integrate(p, protocol["reference"]["solves"][2], protocol)
    q, m, h, energy = ref.unpack(p, record["sample_states"][-1])
    assert q == energy == [0.0, 0.0]
    assert all(m[i] != 0.2 and h[i] != 0.6 for i, enabled in enumerate(mask) if enabled)


@pytest.mark.parametrize(
    "fault", ["rhs_limit", "step_limit", "temperature", "gate_domain", "state_shape"]
)
def test_reference_rejects_invalid_or_overbudget_work(protocol, fault):
    p, plan = parameters(), copy.deepcopy(protocol)
    if fault == "rhs_limit":
        plan["reference"]["max_rhs_calls_per_solve"] = 1
    elif fault == "step_limit":
        plan["reference"]["max_accepted_steps_per_solve"] = 1
    elif fault == "temperature":
        p["temperature_K"] = 310.0
    elif fault == "gate_domain":
        state = ref.initial_state(p)
        state[2] = 1.1
        with pytest.raises(ValueError):
            ref.derivative(p, state)
        return
    else:
        with pytest.raises(ValueError):
            ref.unpack(p, [0.0])
        return
    with pytest.raises(ValueError):
        ref.integrate(p, plan["reference"]["solves"][0], plan)


@pytest.mark.parametrize("case", ["coefficients", "method", "left", "right", "outside"])
def test_dense_corruptions_rejected(reference_records, case):
    interval = copy.deepcopy(reference_records["dop853_tight"]["dense_intervals"][0])
    if case == "coefficients":
        interval["coefficients"] = interval["coefficients"][:-1]
    elif case == "method":
        interval["method"] = "unknown"
    elif case == "left":
        interval["left_s"] = interval["right_s"]
    elif case == "right":
        interval["right_s"] = -1
    if case == "outside":
        time_s = interval["right_s"] + 1
    else:
        time_s = 0.0
    with pytest.raises(ValueError):
        refcheck.dense_value(interval, time_s)


@pytest.mark.parametrize(
    "value",
    [
        {"x": [0.0, -0.0, 1e-200, 1.2345678901234567]},
        {"a": [], "b": None},
        [1, 2, {"long": "x" * 20000}],
    ],
)
def test_lossless_compressed_records_are_deterministic_and_exclusive(tmp_path, value):
    a, b = tmp_path / "a.gz", tmp_path / "b.gz"
    io.write_compressed(a, value)
    io.write_compressed(b, value)
    assert io.read_compressed(a) == value
    assert a.read_bytes() == b.read_bytes()
    with pytest.raises(FileExistsError):
        io.write_compressed(a, value)


def test_compressed_read_limit_and_strict_json(tmp_path):
    path = tmp_path / "data.gz"
    io.write_compressed(path, {"field": "x" * 1000})
    with pytest.raises(ValueError, match="limit"):
        io.read_compressed(path, limit=20)
    for text in ('{"a": 1, "a": 2}', '{"a": NaN}'):
        with pytest.raises(ValueError):
            io.parse(text)


def test_summary_ledger_keeps_every_numerical_rejection(tmp_path):
    path = tmp_path / "failures.jsonl"
    ledger = io.Ledger({"q": 1e-10}, failure_path=path)
    ledger.compare("pass", [1.0, 2.0], [1.0, 2.0], "q")
    ledger.compare("bad", [3.0, 4.0], [1.0, 2.0], "q")
    assert ledger.count == 4 and ledger.failed == 2
    assert len(path.read_text().splitlines()) == 2
    assert ledger.failures == []


@pytest.mark.parametrize(
    "case", ["shrinking", "floor", "growing", "false_floor", "own_not_shrinking"]
)
def test_refinement_cannot_be_replaced_by_fine_pair_agreement(protocol, case):
    fields = protocol["refinement"]["required_fields"]
    values = [1e-5, 5e-6, 2.5e-6]
    changes = [5e-6, 2.5e-6]
    expected = True
    if case == "floor":
        values, changes = [1e-15, 2e-15, 3e-15], [1e-15, 1e-15]
    elif case == "growing":
        values, expected = [1e-5, 2e-5, 3e-5], False
    elif case == "false_floor":
        values, expected = [1e-15, 1e-5, 2e-5], False
    elif case == "own_not_shrinking":
        changes, expected = [5e-6, 8e-6], False
    result = compare.refinement(
        [dict.fromkeys(fields, v) for v in values],
        [dict.fromkeys(fields, v) for v in changes],
        dict.fromkeys(fields, 1e-15),
        protocol,
    )
    assert (result["status"] == "pass") is expected


@pytest.fixture(scope="module")
def synthetic_cells_case(protocol):
    """Same padded interface, different declared -35 mV test state and 100 us horizon."""
    from cells.core.runner import run
    from cells.core.specs import parse_spec

    r = {
        "protocol": copy.deepcopy(protocol),
        "preparation_registration": c.read(ctx.audit.CAPTURE / "registration.json"),
    }
    r["protocol"].update({"duration_s": 0.0001, "common_times_s": [0.0, 0.00005, 0.0001]})
    key = ctx.key("active_channel", 50e-6, "jax_jit")
    definition = ctx.cells_definitions(protocol)[key]
    definition["experiment"].update(
        {"end_time": 0.0001, "observation_times": [0.0, 0.00005, 0.0001]}
    )
    p = copy.deepcopy(ctx.parameters()["active_channel"])
    p["initial_voltage_V"] = [-0.035] * 7
    for entry in definition["model"]["cells"]:
        cell, membrane = entry["cell"], entry["membrane"]
        cell["initial_voltage_V"] = -0.035
        amounts = cell["initial_amount_fmol"]
        cell["fixed_charge_equivalent_fmol"] = membrane["area_m2"] * 0.01 * -0.035 / (
            p["F"] * 1e-15
        ) - math.fsum([amounts["Na"], amounts["K"], -amounts["Cl"]])
    # Explicit initial bath countercharge for this DIFFERENT synthetic voltage.
    # The production guard does not repair it, and pilot data are untouched.
    bath = definition["model"]["extracellular"]
    capacitor_charge = math.fsum(
        entry["membrane"]["area_m2"] * 0.01 * entry["cell"]["initial_voltage_V"]
        for entry in definition["model"]["cells"]
    )
    amounts = bath["initial_amount_fmol"]
    bath["fixed_charge_equivalent_fmol"] = -capacitor_charge / (p["F"] * 1e-15) - math.fsum(
        [amounts["Na"], amounts["K"], -amounts["Cl"]]
    )
    r["reference_parameters"] = {"active_channel": p}
    r["cells_definitions"] = {key: definition}
    result = run(parse_spec(definition))
    return r, key, definition, result


def test_actual_production_short_trajectory_records_and_full_state(synthetic_cells_case):
    r, key, definition, result = synthetic_cells_case
    record = cells_driver.record_result(result, key, definition)
    ledger = io.Ledger(compare.cells_tolerances(r))
    points = compare.cells_points_and_checks(r, record, ledger)
    assert ledger.failed == 0, ledger.failures[:5]
    assert len(points) == 3
    assert points[-1]["gate"] != points[0]["gate"]
    assert points[-1]["transfer_fmol"] != points[0]["transfer_fmol"]


def test_actual_complete_checkpoint_resume(synthetic_cells_case, tmp_path):
    from cells.core.runner import run
    from cells.io import load_snapshot, write_snapshot

    _r, key, definition, result = synthetic_cells_case
    checkpoint = result.checkpoint_at(0.00005)
    write_snapshot(tmp_path / "checkpoint", result.spec, checkpoint)
    restored = load_snapshot(tmp_path / "checkpoint")
    resumed = run(restored.spec, restored.checkpoint)
    a = cells_driver.record_result(result, key, definition)
    b = cells_driver.record_result(resumed, key, definition)
    summary = compare.compare_histories(
        key, a, b, {"state": 2e-12, "gate": 2e-13}, 2e-11, tmp_path / "failures.jsonl", 1
    )
    assert summary["status"] == "pass"


@pytest.mark.parametrize(
    "field", ["gate", "amount_increment", "leak_transferred", "extracellular_amount_increment"]
)
def test_corrupt_history_or_padding_is_rejected(synthetic_cells_case, field):
    r, key, definition, result = synthetic_cells_case
    record = cells_driver.record_result(result, key, definition)
    record["history"][field]["values"][-1][0][-1] += 0.01
    with pytest.raises(ValueError):
        compare.cells_points_and_checks(r, record, io.Ledger(compare.cells_tolerances(r)))


@pytest.mark.parametrize("fault", ["absolute_charge", "channel_array", "extra_array"])
def test_native_saved_state_corruption_is_rejected(fault):
    record = c.read(ctx.audit.CAPTURE / "betse.json")["rows"]["active_channel/observed"]
    constants = c.read(ctx.audit.CAPTURE / "registration.json")["transport_protocol"]["constants"]
    assert compare.native_saved_state_contract(record, constants) == 9
    if fault == "absolute_charge":
        record["trace"]["steps"][-1]["after_voltage"]["physical"]["rho_C_per_m3"][0] += 1
    elif fault == "channel_array":
        record["final_arrays"]["channel/m"]["values"][0] += 0.01
    else:
        record["final_arrays"]["undeclared"] = record["final_arrays"]["channel/m"]
    with pytest.raises(ValueError):
        compare.native_saved_state_contract(record, constants)


@pytest.mark.parametrize(
    "field",
    ["channel_flux_fmol_per_s", "channel_effective_permeability_m_per_s", "membrane_current_A"],
)
def test_sampled_constitutive_readout_must_match_own_state(synthetic_cells_case, field):
    r, key, definition, result = synthetic_cells_case
    record = cells_driver.record_result(result, key, definition)
    record["observations"][field]["values"][-1][0] += 1e-4
    ledger = io.Ledger(compare.cells_tolerances(r))
    with pytest.raises(ValueError, match="Array bytes disagree"):
        compare.cells_points_and_checks(r, record, ledger)
    # A well-formed but numerically false synthetic export must also fail.
    record["observations"][field] = ctx.audit.preparation.array_record(
        np.asarray(record["observations"][field]["values"], dtype=np.float64)
    )
    compare.cells_points_and_checks(r, record, ledger)
    assert ledger.failed > 0
    assert any("constitutive" in row["id"] for row in ledger.failures)


def test_production_eager_and_jit_use_the_same_full_state(synthetic_cells_case, tmp_path):
    from cells.core.runner import run
    from cells.core.specs import parse_spec

    _r, key, definition, result = synthetic_cells_case
    eager_definition = copy.deepcopy(definition)
    eager_definition["execution"]["jit"] = False
    eager = run(parse_spec(eager_definition))
    summary = compare.compare_histories(
        "backend",
        cells_driver.record_result(result, key, definition),
        cells_driver.record_result(eager, key, eager_definition),
        {"state": 2e-12, "gate": 2e-13},
        2e-11,
        tmp_path / "failures.jsonl",
    )
    assert summary["status"] == "pass"


def test_native_fresh_constitutive_probe_only_mutates_copies():
    p = ctx.parameters()["active_channel"]
    transport = c.read(ctx.audit.CAPTURE / "registration.json")["transport_protocol"]
    saved = c.read(ctx.audit.CAPTURE / "betse.json")["rows"]["active_channel/observed"]
    initial = copy.deepcopy(saved["trace"]["initial"])
    initial["physical"]["voltage_V"] = [-0.035] * 30
    payload = {
        "trace": {"initial": initial},
        "geometry": saved["geometry"],
        "parameters": p,
        "r": {
            "protocol": {"common_times_s": [0.0]},
            "preparation_registration": {"transport_protocol": transport},
        },
    }
    code = (
        "import copy,json,sys; from types import SimpleNamespace\n"
        "sys.path.insert(0,sys.argv[1]); import feedback_native as native\n"
        "data=json.load(sys.stdin); before=copy.deepcopy(data)\n"
        "p=SimpleNamespace(F=data['parameters']['F'],R=data['parameters']['R'],T=298.15,tm=7.5e-9,dt=25e-6)\n"
        "out=native.fresh_probes(data['trace'],data['geometry'],SimpleNamespace(p=p),{'permeability_fraction':1},data['r'])\n"
        "assert data == before; assert len(out)==1\n"
        "assert all(v < 0 for v in out[0]['inward_density_mol_per_m2_s'])\n"
        "print(json.dumps(out))\n"
    )
    result = subprocess.run(
        [str(c.REFERENCE_PYTHON), "-B", "-c", code, str(HERE)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    probes = json.loads(result.stdout.strip().splitlines()[-1])
    row = {
        "geometry": saved["geometry"],
        "trace": payload["trace"],
        "fresh_probes": probes,
        "dt_s": 25e-6,
    }
    variant = {"id": "active_channel", "permeability_fraction": 1}
    ledger = io.Ledger(transport["tolerances"])
    compare.native_points(payload["r"], row, variant, ledger)
    assert ledger.failed == 0
    assert ledger.count == 60
    for field, nested in (("permeability_m_per_s", True), ("inward_density_mol_per_m2_s", False)):
        bad = copy.deepcopy(row)
        target = bad["fresh_probes"][0]
        if nested:
            target = target["inputs_before"]
        # Preserve owner uniformity to isolate the constitutive-law rejection.
        target[field] = [2 * value for value in target[field]]
        ledger = io.Ledger(transport["tolerances"])
        compare.native_points(payload["r"], bad, variant, ledger)
        assert ledger.failed > 0


def test_missing_bath_countercharge_is_not_silently_repaired(synthetic_cells_case):
    from cells.core.specs import ConfigError, parse_spec

    _r, _key, definition, _result = synthetic_cells_case
    bad = copy.deepcopy(definition)
    bad["model"]["extracellular"]["fixed_charge_equivalent_fmol"] = -195.75
    with pytest.raises(ConfigError, match="oppose the membrane capacitors"):
        parse_spec(bad)


def test_both_stages_have_one_explicit_reference_gate_before_launching_models():
    source = (HERE / "feedback_job.py").read_text()
    tree = ast.parse(source)
    execute = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "execute")
    loop = next(
        n for n in ast.walk(execute) if isinstance(n, ast.For) and isinstance(n.target, ast.Tuple)
    )
    assert isinstance(loop.body[0], ast.If)
    assert "reference_gate" in ast.unparse(loop.body[0])
    assert "Independent reference gate is not passed" in ast.unparse(loop.body[0])
    assert "automatic_followup" in source


def test_failed_reference_gate_never_launches_either_simulator(protocol, tmp_path, monkeypatch):
    r = {"protocol": protocol, "preparation_registration": {}}
    launched = []
    monkeypatch.setattr(job, "authenticate", lambda _: r)
    monkeypatch.setattr(job.signal, "signal", lambda *_: None)
    monkeypatch.setattr(job.signal, "setitimer", lambda *_: None)
    monkeypatch.setattr(job.resource, "setrlimit", lambda *_: None)
    monkeypatch.setattr(job.os, "sched_getaffinity", lambda _: {0, 1, 2, 3})
    monkeypatch.setattr(ctx.audit.preparation.old.ctx, "worker_environment", lambda *_: {})
    monkeypatch.setattr(job.subprocess, "run", lambda command, **_: launched.append(command[4]))
    monkeypatch.setattr(job, "validate_worker", lambda *_: {})
    monkeypatch.setattr(refcheck, "check", lambda *_: {"status": "fail"})
    with pytest.raises(ValueError, match="simulators not launched"):
        job.execute(tmp_path)
    assert launched == ["reference"]
    assert c.read(tmp_path / "failure.json")["stage"] == "reference_convergence_gate"
    assert not (tmp_path / "betse-started.json").exists()
    assert not (tmp_path / "cells-started.json").exists()
    assert not (tmp_path / "completion.json").exists()


def test_reference_module_has_no_simulator_comparator_or_compiler_import():
    source = (HERE / "feedback_reference.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                n.name.split(".")[0]
                not in ("cells", "betse", "jax", "feedback_context", "feedback_compare")
                for n in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            assert node.module.split(".")[0] not in (
                "cells",
                "betse",
                "jax",
                "feedback_context",
                "feedback_compare",
            )
    assert 'import_module("pilot_reference")' in source


@pytest.mark.parametrize(
    "field,value",
    [
        ("duration_s", 0.004),
        ("automatic_followup", True),
        ("reference_gate_before_simulators", False),
        ("native_runs", 1),
    ],
)
def test_changed_protocol_is_rejected(protocol, field, value):
    changed = copy.deepcopy(protocol)
    changed[field] = value
    with pytest.raises(ValueError):
        ctx.validate_protocol(changed)


def test_preservation_and_grid_scope(protocol):
    prerequisite, _previous = ctx.prerequisite()
    assert len(prerequisite["files_sha256"]) == 9
    assert len(prerequisite["preparation_files_sha256"]) == 74
    assert len(ctx.sources()) == 112
    assert len(ctx.cells_definitions(protocol)) == 16
    assert ctx.reference_runtime()["packages"]["scipy"] == "1.18.1"
    assert not any(name.startswith("src/") for name in ctx.FILES)


def test_existing_capture_is_not_reused(tmp_path):
    with pytest.raises(ValueError, match="fresh"):
        job.register(ctx.PRIOR, tmp_path / "unused.xml")


def test_native_accumulation_budget_is_derived_before_new_trajectories(protocol):
    prior = c.read(ctx.audit.CAPTURE / "betse.json")["rows"]["network_off/observed"]
    r = {"protocol": protocol, "geometry": prior["geometry"]}
    a, b = compare.accumulation_tolerance(r, 80), compare.accumulation_tolerance(r, 160)
    base = protocol["native_conservation"]["base_atol_fmol"]
    assert b - base == pytest.approx(2 * (a - base), rel=1e-14)
    assert a < 1e-8
