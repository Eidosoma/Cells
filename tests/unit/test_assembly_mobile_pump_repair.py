"""Cell-owned assembly with complete mobile pump/Kv1.5/calcium/injury state."""

import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.assembly.io import digest
from cells.assembly.spec import AssemblyError
from cells.assembly_cell.io import flatten, load_checkpoint, write_checkpoint
from cells.assembly_cluster import controls, engine
from cells.assembly_cluster.mobile_channels import AXES
from cells.assembly_cluster.mobile_pumps import AXES as PUMP_AXES
from cells.assembly_cluster.spec import channel_owners, parse_spec
from cells.core.schedule import control_values
from cells.ensemble.cluster import aggregate
from cells.ensemble.families import bind_definition
from cells.ensemble.plan import jupiter_plan, plan
from cells.models import surface_mobile_pump_repair as model
from tests.unit.test_assembly_cluster import ensemble_definition, event_histories, same
from tests.unit.test_surface_mobile_channel import error_budget
from tests.unit.test_surface_repair_full import compare_backend
from validation.tissue import assembly_mobile_pump_repair_fixtures as fixtures
from validation.tissue import assembly_repair_recovery as event_reference
from validation.tissue import surface_mobile_pump_repair_reference as reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
PUBLISHED = os.environ.get("CELLS_COMPONENT_PUBLISHED_EVIDENCE")
PREFIX = "assembly-mobile-pump-repair"


def evidence(name, value, arrays=None):
    if EVIDENCE:
        root = Path(EVIDENCE) / BACKEND
        root.mkdir(parents=True, exist_ok=True)
        (root / (PREFIX + "-" + name + ".json")).write_text(
            json.dumps(value, indent=2, allow_nan=False) + "\n"
        )
        if arrays is not None:
            np.savez_compressed(root / (PREFIX + "-" + name + ".npz"), **arrays)


def report_row(spec, state):
    return engine.summary(spec, state) | dict(
        execute_seconds=0.0, arm="mobile", wall_start=0.0, wall_end=1.0
    )


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
@pytest.mark.parametrize("padded", [False, True])
def test_roundtrip_full_state_and_readout_ownership(backend, padded):
    spec = parse_spec(fixtures.definition(backend=backend, padded=padded))
    assert parse_spec(spec.to_dict()) == spec
    state = engine.initial_state(spec)
    row = report_row(spec, state)
    assert len(state.ionic._fields) == 53
    assert set(
        ("calcium", "calcium_channels", "ip3", "injury", "mobile_channels", "mobile_pumps")
    ) <= set(row)
    assert row["physical_model"] == "resolved_repair@3"
    mobile = row["mobile_channels"]
    assert mobile["patch_ids"] == row["voltage_owner_ids"]
    assert mobile["patch_cell_ids"] == row["injury"]["cell_ids"]
    total = aggregate([row, row])["mobile"]
    assert total["worlds"] == 2 * spec.pool.worlds
    for name in AXES:
        np.testing.assert_array_equal(
            total["mobile_channels"][name + "_sum_over_worlds"],
            2 * np.asarray(mobile[name]).sum(axis=0),
        )
    assert mobile["initial_total_by_cell_fmol"][1][-1] == 0
    pumps = row["mobile_pumps"]
    assert pumps["initial_total_by_cell_fmol"][1][-1] == 0
    for name in PUMP_AXES:
        np.testing.assert_array_equal(
            total["mobile_pumps"][name + "_sum_over_worlds"],
            2 * np.asarray(pumps[name]).sum(axis=0),
        )
    evidence("owners", dict(status="passed", state_fields=list(state.ionic._fields), report=row))


@pytest.mark.parametrize("opening", [(0.0, 0.0), (0.2, 0.8), (1.0, 1.0)])
@pytest.mark.parametrize("padded", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_independent_rates_and_cell_owned_conduction(opening, padded, reverse):
    raw = fixtures.definition("release", padded=padded)
    if padded:
        raw["ionic"]["model"]["ionic"]["species"].reverse()
    if reverse:
        for pop in raw["ionic"]["model"]["mobile_pumps"]:
            pop["metabolism"]["delta_g0_J_per_mol"] = 0.0
    raw["ionic"]["model"]["injury_patches"][0]["initial_damage"] = 0.25
    spec = parse_spec(raw)
    state, layout = model.initial_values(spec.ionic)
    table = control_values(spec.ionic, [19.5e-6])
    control = type(table)(*(v[0] for v in table))
    before = tuple(v.copy() for v in control)
    owners = channel_owners(spec)
    assert isinstance(owners, controls.ChannelOwners)
    held = controls.modulate(control, np.asarray(opening), owners)
    np.testing.assert_array_equal(held.mobile_pump, control.mobile_pump)
    actual = model.readouts(state, held, layout, xp=np)
    c = reference.bind(spec.ionic.to_dict())
    expected, _, proof = reference.evaluate(
        c, reference.initial(c), 19.5e-6, channel_levels=opening
    )
    ratio = error_budget(
        c,
        reference.flatten(c, actual.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    for before_value, after in zip(before, control, strict=True):
        np.testing.assert_array_equal(before_value, after)
    blocked = model.readouts(
        state, held._replace(mobile_channel=np.zeros_like(held.mobile_channel)), layout, xp=np
    )
    for name in (
        "damage",
        "damage_closed",
        "channel_state_amount_increment",
        "channel_gate_transferred",
        "mobile_pump_amount_increment",
        "mobile_pump_surface_transferred",
    ):
        np.testing.assert_array_equal(
            getattr(actual.derivative, name), getattr(blocked.derivative, name)
        )
    assert np.any(actual.derivative.injury_transferred)
    assert np.all(blocked.derivative.mobile_channel_transferred == 0)
    assert np.any(actual.derivative.mobile_pump_cycles)
    if reverse:
        assert np.min(actual.derivative.mobile_pump_cycles) < 0
        assert np.min(actual.derivative.mobile_pump_metabolic_work_pJ) < 0
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-10
    evidence(
        f"stage-{int(reverse)}-{int(padded)}-{opening[0]}",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            availability=opening,
            max_error_over_budget=ratio,
        ),
    )


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "axes",
        "patch",
        "owner",
        "population",
        "species",
        "gate",
        "edge",
        "shape",
        "negative",
        "nonfinite",
        "inventory",
        "calcium",
        "injury",
        "ip3",
    ],
)
def test_mobile_reports_reject_lost_ownership_or_invalid_state(fault):
    spec = parse_spec(fixtures.definition())
    row = report_row(spec, engine.initial_state(spec))
    data = row["mobile_channels"]
    if fault == "missing":
        row.pop("mobile_channels")
    elif fault in ("calcium", "injury", "ip3"):
        row.pop(fault)
    elif fault == "axes":
        data["axes"] = {}
    elif fault == "patch":
        data["patch_ids"].reverse()
    elif fault == "owner":
        data["patch_cell_ids"][0] = "missing"
    elif fault == "population":
        data["population_ids"][1] = data["population_ids"][0]
    elif fault == "species":
        data["species_ids"][0] = "Na"
    elif fault == "gate":
        data["joint_state_ids"].reverse()
    elif fault == "edge":
        data["surface_edge_receivers"][0] = data["patch_ids"][-1]
    elif fault == "shape":
        data["mobile_channel_transferred"] = []
    elif fault == "negative":
        data["channel_gate_dissipated_energy_pJ"][0][0][0][0] = -1
    elif fault == "nonfinite":
        data["amount_fmol"][0][0][0][0] = float("nan")
    else:
        data["amount_fmol"][0][0][0][0] += 1e-5
    with pytest.raises(ValueError):
        aggregate([row])


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "axes",
        "owner",
        "population",
        "roles",
        "stoichiometry",
        "edge",
        "shape",
        "amount",
        "increment",
        "ions",
        "work",
        "heat",
        "nonfinite",
        "initial",
        "policy",
    ],
)
def test_pump_reports_reject_invalid_ownership_and_ledgers(fault):
    spec = parse_spec(fixtures.definition())
    row = report_row(spec, engine.initial_state(spec))
    data = row["mobile_pumps"]
    if fault == "missing":
        row.pop("mobile_pumps")
    elif fault == "axes":
        data["axes"] = {}
    elif fault == "owner":
        data["patch_cell_ids"][0] = "missing"
    elif fault == "population":
        data["population_ids"][1] = data["population_ids"][0]
    elif fault == "roles":
        data["roles"][0]["sodium"] = "Ca"
    elif fault == "stoichiometry":
        data["stoichiometry"][0][0] = 0
    elif fault == "edge":
        data["surface_edge_receivers"][0] = data["patch_ids"][-1]
    elif fault == "shape":
        data["mobile_pump_cycles"] = []
    elif fault == "amount":
        data["amount_fmol"][0][0][0] += 1e-5
    elif fault == "increment":
        data["mobile_pump_amount_increment"][0][0][0] += 1e-5
    elif fault == "ions":
        data["outward_ion_transfer_fmol"][0][0][0][0] += 1e-5
    elif fault == "work":
        data["mobile_pump_metabolic_work_pJ"][0][0][0] += 1e-5
    elif fault == "heat":
        data["mobile_pump_dissipated_energy_pJ"][0][0][0] = -1
    elif fault == "nonfinite":
        data["amount_fmol"][0][0][0] = float("nan")
    elif fault == "initial":
        data["initial_total_by_cell_fmol"][0][0] += 1e-5
    else:
        data["assembly_coupling"] = "assembly scales pumps"
    with pytest.raises(ValueError):
        aggregate([row])


def test_pump_report_preserves_signed_cycles_and_work():
    spec = parse_spec(fixtures.definition())
    row = report_row(spec, engine.initial_state(spec))
    data = row["mobile_pumps"]
    cycles = np.asarray(data["mobile_pump_cycles"])
    cycles[0, 0, 0] = -1e-6
    data["mobile_pump_cycles"] = cycles.tolist()
    data["mobile_pump_metabolic_work_pJ"] = (
        cycles * np.asarray(data["work_per_cycle_pJ_per_fmol"])[None, :, None]
    ).tolist()
    data["outward_ion_transfer_fmol"] = (
        -np.asarray(data["stoichiometry"])[None, :, :, None] * cycles[:, None, :, :]
    ).tolist()
    result = aggregate([row])["mobile"]["mobile_pumps"]
    assert np.min(result["mobile_pump_cycles_sum_over_worlds"]) < 0
    np.testing.assert_array_equal(
        result["mobile_pump_metabolic_work_pJ_sum_over_worlds"],
        np.asarray(data["mobile_pump_metabolic_work_pJ"]).sum(axis=0),
    )
    evidence("signed-pump-reports", dict(status="passed", signed_work_preserved=True))


def test_independent_reference_open_coupling_reduces_to_standalone():
    raw = fixtures.definition()["ionic"]
    c = reference.bind(raw)
    state = reference.initial(c)
    plain = reference.evaluate(c, state, 0.0)
    opened = reference.evaluate(c, state, 0.0, channel_levels=[1.0, 1.0])
    for a, b in zip(plain[:2], opened[:2], strict=True):
        np.testing.assert_array_equal(a, b)
    evidence("reference-default", dict(status="passed", fully_open_matches_standalone=True))


def test_checkpoint_retains_all_fields_and_rejects_changed_execution_policy(tmp_path, monkeypatch):
    spec = parse_spec(fixtures.definition(backend=BACKEND))
    state = engine.initial_state(spec)
    write_checkpoint(tmp_path / "checkpoint", spec, state, backend=BACKEND)
    restored, actual, _ = load_checkpoint(tmp_path / "checkpoint", backend=BACKEND)
    same(state, actual)
    assert restored.fingerprint == spec.fingerprint
    manifest = json.loads((tmp_path / "checkpoint/manifest.json").read_text())
    assert manifest["runtime"]["numerical_environment"]["XLA_FLAGS"] == os.environ.get("XLA_FLAGS")
    monkeypatch.setenv("XLA_FLAGS", "--xla_gpu_autotune_level=1")
    with pytest.raises(AssemblyError, match="runtime"):
        load_checkpoint(tmp_path / "checkpoint", backend=BACKEND)
    evidence(
        "checkpoint-policy", dict(status="passed", ionic_fields=53, changed_policy_rejected=True)
    )


def test_event_clocks_and_one_to_sixteen_gpu_planning():
    raw = ensemble_definition()
    raw["arms"][0].update(worlds=16, batch_worlds=1)
    definition = fixtures.definition("release", backend="gpu")
    for binding in definition["pools"]:
        for name in ("worlds", "world_id_start", "seed"):
            binding["pool"].pop(name)
    raw["arms"][0]["definition"] = definition
    local, future = plan(raw, 1), jupiter_plan(raw, 4)
    assert local["tasks"] == future["tasks"]
    assert future["deployment"]["maximum_target_gpus"] == 16
    assert not future["deployment"]["remote_execution_qualified"]
    ids = []
    for task in future["tasks"]:
        spec = parse_spec(task["definition"])
        assert controls.extra_boundaries(spec.ionic) == 6
        assert isinstance(channel_owners(spec), controls.ChannelOwners)
        ids.extend(range(spec.pool.world_id_start, spec.pool.world_id_start + spec.pool.worlds))
    assert sorted(ids) == list(range(16))
    evidence(
        "planning",
        dict(status="passed", world_ids=ids, maximum_target_gpus=16, gpu_execution=False),
    )


def collect(arm, *, spec=None, label=None):
    spec = spec or parse_spec(fixtures.definition(arm, backend=BACKEND))
    label = label or arm
    initial = engine.initial_state(spec)
    snapshots = [initial]
    wanted = {round(t / spec.ionic.execution.dt) for t in spec.ionic.experiment.observation_times}
    last = [initial]

    def capture(_, current):
        last[0] = jax.tree.map(lambda v: np.array(v, copy=True), current)
        if int(current.tick[0]) in wanted:
            snapshots.append(last[0])

    try:
        state, report = engine.run(spec, backend=BACKEND, callback=capture)
    except BaseException:
        evidence("partial-" + label, dict(status="failed", inputs=spec.to_dict()), flatten(last[0]))
        raise
    observed = {k: np.stack([flatten(s)[k] for s in snapshots]) for k in flatten(initial)}
    evidence(
        "history-" + label,
        dict(status="captured", inputs=fixtures.normalized(spec.to_dict()), report=report),
        observed,
    )
    np.testing.assert_array_equal(observed["tick"][:, 0], sorted(wanted))
    assert report["backend"] == BACKEND and report["precision"] == "float64"
    for snapshot in snapshots:
        engine.validate_state(spec, snapshot)
    aggregate([report_row(spec, state)])
    return SimpleNamespace(
        spec=spec, state=state, report=report, observed=observed, snapshots=snapshots
    )


@lru_cache(maxsize=None)
def trajectory(arm):
    return collect(arm)


def saved_history(arm, backend=BACKEND):
    candidates = [Path(v) / backend for v in (EVIDENCE, PUBLISHED) if v]
    for directory in candidates:
        path = directory / (PREFIX + "-history-" + arm)
        if path.with_suffix(".json").exists():
            receipt = json.loads(path.with_suffix(".json").read_text())
            assert receipt["inputs"] == fixtures.normalized(
                parse_spec(fixtures.definition(arm)).to_dict()
            )
            with np.load(path.with_suffix(".npz"), allow_pickle=False) as data:
                arrays = {k: v.copy() for k, v in data.items()}
            return (
                receipt,
                arrays,
                {
                    str(path.with_suffix(suffix)): digest(path.with_suffix(suffix))
                    for suffix in (".json", ".npz")
                },
            )
    raise AssertionError("Require recorded complete trajectory for " + arm + "/" + backend)


def independent(arm, value, world, *, refinement=1):
    events = event_histories(value.spec, value.state, world)
    segments = event_reference.segments(value.spec, events)
    name = f"reference-{arm}-world-{world}-r{refinement}"
    inputs = dict(
        inputs=fixtures.normalized(value.spec.to_dict()),
        events=json.loads(json.dumps(events, default=lambda v: np.asarray(v).tolist())),
        channel_segments=json.loads(json.dumps(segments)),
        refinement=refinement,
        world_id=value.spec.pool.world_id_start + world,
    )
    if BACKEND == "gpu":
        path = Path(EVIDENCE) / "cpu" / (PREFIX + "-" + name)
        receipt = json.loads(path.with_suffix(".json").read_text())
        assert receipt["status"] == "passed" and all(receipt[k] == v for k, v in inputs.items())
        with np.load(path.with_suffix(".npz"), allow_pickle=False) as data:
            arrays = {k: v.copy() for k, v in data.items()}
        evidence(name, receipt | dict(reused_cpu_reference=True), arrays)
    else:
        result = reference.integrate(
            value.spec.ionic.to_dict(), channel_segments=segments, refinement=refinement
        )
        arrays = dict(
            state=result["state"],
            potential_V=result["potential_V"],
            exposure_s=event_reference.exposure(result["times"], segments),
        )
        evidence(
            name,
            inputs
            | dict(status="passed", method=result["method"], evaluations=result["evaluations"]),
            arrays,
        )
    return arrays, inputs


@pytest.mark.parametrize("arm", fixtures.ARMS)
def test_compiled_trajectory_against_independent_events_and_all_fields(arm):
    value = trajectory(arm)
    c = reference.bind(value.spec.ionic.to_dict())
    ratios, event_counts, stability = [], [], []
    for world in range(value.spec.pool.worlds):
        expected, inputs = independent(arm, value, world)
        actual = reference.flatten(
            c, {k: value.observed["ionic_" + k][:, world] for k in model.STATE_TYPE._fields}
        )
        evidence(
            f"errors-{arm}-world-{world}",
            inputs,
            dict(
                actual=actual, reference=expected["state"], signed_error=actual - expected["state"]
            ),
        )
        ratios.append(error_budget(c, actual, expected["state"]))
        np.testing.assert_allclose(
            value.observed["availability_exposure_s"][:, world],
            expected["exposure_s"],
            rtol=0,
            atol=2e-14,
        )
        event_counts.append({k: len(v) for k, v in inputs["events"].items()})
        assert sum(event_counts[-1].values()) > 0
        if arm != "uncoupled":
            assert len({tuple(levels) for _, levels in inputs["channel_segments"]}) > 1
        if arm == "release":
            tight, _ = independent(arm, value, world, refinement=4)
            stability.append(
                error_budget(
                    c, expected["state"], tight["state"], atol=3e-14, charge_atol=3e-28, rtol=3e-11
                )
            )
    evidence(
        "trajectory-" + arm,
        dict(
            status="passed",
            max_error_over_budget=ratios,
            reference_stability_over_budget=stability,
            complete_ionic_fields=53,
            assembly_events=event_counts,
            inputs=fixtures.normalized(value.spec.to_dict()),
            scope="50-us synthetic one-way composition; no biological repair or protein exchange",
        ),
    )


def test_one_way_coupling_preserves_assembly_and_damage():
    a, coupled, sources_a = saved_history("mobile")
    b, uncoupled, sources_b = saved_history("uncoupled")
    for name in coupled:
        if name.startswith("pool_") or name in (
            "tick",
            "segments",
            "ionic_damage",
            "ionic_damage_opened",
            "ionic_damage_closed",
            "ionic_mobile_pump_amount_increment",
            "ionic_mobile_pump_surface_transferred",
            "ionic_mobile_pump_surface_dissipated_energy_pJ",
        ):
            np.testing.assert_array_equal(coupled[name], uncoupled[name], err_msg=name)
    assert (
        np.max(
            np.abs(
                coupled["ionic_mobile_channel_transferred"]
                - uncoupled["ionic_mobile_channel_transferred"]
            )
        )
        > 1e-13
    )
    delta = float(
        np.max(
            np.abs(
                np.asarray(a["report"]["final_voltage_V"])
                - np.asarray(b["report"]["final_voltage_V"])
            )
        )
    )
    assert delta > 1e-10
    pump_delta = float(
        np.max(np.abs(coupled["ionic_mobile_pump_cycles"] - uncoupled["ionic_mobile_pump_cycles"]))
    )
    assert pump_delta > 1e-16
    evidence(
        "coupling",
        dict(
            status="passed",
            unchanged_assembly_paths=True,
            unchanged_damage=True,
            voltage_difference_V=delta,
            pump_cycle_difference_fmol=pump_delta,
            unchanged_pump_protein=True,
            history_sources=[sources_a, sources_b],
        ),
    )


def test_cpu_gpu_complete_joint_histories():
    if BACKEND == "cpu":
        pytest.skip("Requires saved CPU and L4 histories")
    count, sources = 0, {}
    for arm in fixtures.ARMS:
        _, actual, gpu_sources = saved_history(arm)
        _, expected, cpu_sources = saved_history(arm, "cpu")
        count += compare_backend(actual, expected)
        sources[arm] = dict(cpu=cpu_sources, gpu=gpu_sources)
    evidence("cpu-gpu", dict(status="passed", compared_values=count, history_sources=sources))


def test_compiled_three_grid_refinement_with_unchanged_assembly_events():
    _, baseline, sources = saved_history("release")
    original = parse_spec(fixtures.definition("release", backend=BACKEND))
    c = reference.bind(original.ionic.to_dict())
    expected = []
    for world in range(original.pool.worlds):
        path = Path(EVIDENCE) / "cpu" / f"{PREFIX}-reference-release-world-{world}-r4"
        if BACKEND == "cpu":
            path = Path(PUBLISHED or EVIDENCE) / "cpu" / path.name
        receipt = json.loads(path.with_suffix(".json").read_text())
        assert (
            receipt["inputs"] == fixtures.normalized(original.to_dict())
            and receipt["refinement"] == 4
        )
        with np.load(path.with_suffix(".npz"), allow_pickle=False) as data:
            expected.append(data["state"].copy())
    errors, charges, ratios = [], [], []
    for i, dt in enumerate(fixtures.STEPS):
        spec = parse_spec(fixtures.definition("release", backend=BACKEND, dt=dt))
        observed = (
            baseline if i == 0 else collect("release", spec=spec, label=f"refinement-{i}").observed
        )
        for name in baseline:
            if name.startswith("pool_"):
                np.testing.assert_array_equal(observed[name], baseline[name], err_msg=name)
        row_errors, row_charges, row_ratios = [], [], []
        for world, target in enumerate(expected):
            actual = reference.flatten(
                c, {k: observed["ionic_" + k][:, world] for k in model.STATE_TYPE._fields}
            )
            evidence(
                f"grid-{i}-world-{world}",
                dict(inputs=spec.to_dict()),
                dict(actual=actual, reference=target, signed_error=actual - target),
            )
            row_ratios.append(error_budget(c, actual, target))
            difference = reference.unpack(c, actual - target)
            row_errors.append(
                max(float(np.max(np.abs(v))) for k, v in difference.items() if not k.endswith("_C"))
            )
            row_charges.append(
                max(float(np.max(np.abs(v))) for k, v in difference.items() if k.endswith("_C"))
            )
        errors.append(row_errors)
        charges.append(row_charges)
        ratios.append(row_ratios)
    assert np.all(np.asarray(errors[-1]) <= np.maximum(0.2 * np.asarray(errors[0]), 3e-13))
    assert np.all(np.asarray(charges[-1]) <= np.maximum(0.2 * np.asarray(charges[0]), 3e-27))
    evidence(
        "refinement",
        dict(
            status="passed",
            steps_s=fixtures.STEPS,
            noncharge_errors=errors,
            charge_errors_C=charges,
            max_error_over_budget=ratios,
            baseline_sources=sources,
        ),
    )


def test_independent_world_partition_and_reverse_order():
    _, expected, sources = saved_history("release")
    original = parse_spec(fixtures.definition("release", backend=BACKEND))
    pieces = {}
    for world_id in reversed(
        range(original.pool.world_id_start, original.pool.world_id_start + original.pool.worlds)
    ):
        spec = parse_spec(
            bind_definition(
                original.to_dict(), worlds=1, world_id_start=world_id, seed=original.pool.seed
            )
        )
        pieces[world_id] = collect("release", spec=spec, label=f"world-{world_id}").observed
    for name in expected:
        actual = np.concatenate([pieces[k][name] for k in sorted(pieces)], axis=1)
        np.testing.assert_array_equal(actual, expected[name], err_msg=name)
    evidence(
        "worlds",
        dict(
            status="passed",
            scalar_partition_bitwise=True,
            reversed_order_bitwise=True,
            world_ids=sorted(pieces),
            history_sources=sources,
        ),
    )


def test_fresh_checkpoint_restart_changed_windows_and_terminal_state(tmp_path):
    _, _, sources = saved_history("release")
    baseline = next(Path(p) for p in sources if p.endswith(".npz"))
    for phase in ("prepare", "resume"):
        command = [
            sys.executable,
            "-B",
            "-m",
            "validation.tissue.assembly_mobile_pump_repair_replay",
            str(tmp_path),
            "--backend",
            BACKEND,
            "--phase",
            phase,
            "--baseline",
            str(baseline),
        ]
        with (
            (tmp_path / f"{phase}.stdout.log").open("x") as out,
            (tmp_path / f"{phase}.stderr.log").open("x") as err,
        ):
            subprocess.run(command, stdout=out, stderr=err, check=True, timeout=1800)
    reports = {
        phase: json.loads((tmp_path / (phase + ".json")).read_text())
        for phase in ("prepare", "resume")
    }
    assert all(row["status"] == "passed" for row in reports.values())
    evidence(
        "replay",
        dict(
            status="passed",
            complete_fresh_history_bitwise=True,
            changed_windows_bitwise=True,
            terminal_bitwise=True,
            ionic_fields=53,
            phases=reports,
            history_sources=sources,
        ),
    )
