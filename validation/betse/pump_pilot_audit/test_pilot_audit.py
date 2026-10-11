"""Bounded reader/controller checks; saved numbers only, no simulator reruns."""

import copy
import importlib
import math
import subprocess
from pathlib import Path

import audit_evidence as context
import audit_job as job
import native_energy
import native_records as native
import pilot_audit as audit
import pytest

e, d = context.e, context.diagnostic


@pytest.fixture(scope="module")
def saved():
    r = e.read(context.CAPTURE / "registration.json")
    original = e.read(d.CAPTURE / "registration.json")
    baseline = e.read(e.CAPTURE / "betse.json")["rows"]
    return r, original, baseline


def test_all_capture_and_prior_identities_authenticate():
    with e.model_fence():
        r, sources, files = context.authenticate()
    assert len(r["sources_sha256"]) == 641
    assert len(sources) == 55 and len(files) == 448


@pytest.mark.parametrize(
    "key",
    [
        "trajectory",
        "accounting",
        "mapping",
        "reference",
        "refinement",
        "duration_s",
        "common_times_s",
        "cells_steps_s",
    ],
)
def test_scientific_contract_mutation_refused(saved, key):
    r, original, _ = saved
    changed = copy.deepcopy(r)
    changed["protocol"][key] = None
    with pytest.raises(ValueError, match="Scientific contract"):
        context.contract(changed, original)


def test_original_contract_preserved(saved):
    context.contract(saved[0], saved[1])


@pytest.mark.parametrize(
    "name",
    [
        "cells",
        "betse",
        "numpy",
        "scipy",
        "jax",
        "pilot_compare",
        "refinement_check",
        "refinement_job",
        "coupled_reference",
    ],
)
def test_independence_fence(name):
    with e.model_fence(), pytest.raises(ImportError):
        importlib.import_module(name)


@pytest.mark.parametrize("name", ["../escape.json", "/tmp/escape.json"])
def test_path_escape_refused(tmp_path, name):
    with pytest.raises(ValueError, match="Unsafe evidence"):
        context.child(tmp_path, name)


def test_payload_mutation_and_link_refused(tmp_path):
    p = tmp_path / "value.json"
    e.write(p, {"number": 1})
    context.hashes(tmp_path, {p.name: e.sha(p)})
    with pytest.raises(ValueError, match="Changed payload"):
        context.hashes(tmp_path, {p.name: "0" * 64})
    (tmp_path / "linked.json").symlink_to(p)
    with pytest.raises(ValueError, match="linked evidence"):
        context.child(tmp_path, "linked.json")


def test_exact_records_preserve_signed_zero():
    with pytest.raises(ValueError, match="zero"):
        context.same_record({"x": 0.0}, {"x": -0.0}, "zero")


def test_registered_cumulative_budget_does_not_change_rate_tolerance(saved):
    plan = saved[0]["protocol"]
    assert native.material_budget(plan, 1000.0, 10) == 2e-12 + 8 * math.ulp(1.0) * 10 * 1000
    ledger = e.Ledger()
    wrapper = native.PhysicalLedger(ledger, 1e-7)
    wrapper.compare("global_material_fmol", 5e-8, 0.0, 2e-12)
    with pytest.raises(ValueError):
        wrapper.compare("raw_pump_density", 5e-8, 0.0, 2e-18)


@pytest.mark.parametrize(
    "identifier",
    ["pump_leak", "pump_only", "leak_only", "all_blocked", "half_density", "closed_boundary"],
)
def test_all_six_short_native_controls(saved, identifier):
    r, _, baseline = saved
    row, quiet = (baseline[identifier + "/" + mode] for mode in ("observed", "unobserved"))
    variant = next(
        v for v in r["native_preparation"]["protocol"]["variants"] if v["id"] == identifier
    )
    plan = dict(r["protocol"], duration_s=0.0002)
    native.identity(row, row, 2.5e-5, 0.0002, "observed")
    native.exact_pair(row, quiet)
    ledger = e.Ledger()
    result = native.inspect(row, row, plan, variant, ledger)
    points = native_energy.reconstruct(row, variant, [i * 2.5e-5 for i in range(9)], ledger)
    assert result == dict(steps=8, physical_records=25)
    assert len(points["states"]) == 9 and points["energy"]["max_unexplained_pJ"] < 1e-10


@pytest.mark.parametrize("change", ["clock", "settings", "history", "raw_flux", "gate", "order"])
def test_corrupt_native_records_refused(saved, change):
    r, _, baseline = saved
    original = baseline["pump_leak/observed"]
    row = copy.deepcopy(original)
    if change == "clock":
        row["dt_s"] *= 2
    elif change == "settings":
        row["settings"]["alpha_NaK"] *= 2
    elif change == "history":
        row["histories"]["time"]["values"][0] += 1
    elif change == "raw_flux":
        row["trace"]["raw_steps"][0]["calls"][0]["returned"][0][0] += 1
    elif change == "gate":
        row["trace"]["gate_initializations"] = 1
    else:
        row["trace"]["steps"][0]["order"].reverse()
    with pytest.raises(ValueError):
        native.identity(row, original, 2.5e-5, 0.0002, "observed")
        native.inspect(
            row,
            original,
            dict(r["protocol"], duration_s=0.0002),
            r["native_preparation"]["protocol"]["variants"][0],
            e.Ledger(),
        )


def test_actual_refined_grid_and_producer_state_links(saved):
    r, _, baseline = saved
    # A full real 640-step control exercises the new grid, not a rewritten trace.
    variant = next(
        v for v in r["native_preparation"]["protocol"]["variants"] if v["id"] == "all_blocked"
    )
    label = "all_blocked/dt_1.5625e-06"
    records = e.read(context.CAPTURE / "betse.json")["records"]
    row, quiet = (
        e.read(context.CAPTURE / records[label + "/" + mode]) for mode in ("observed", "unobserved")
    )
    native.identity(row, baseline["all_blocked/observed"], 1.5625e-6, 0.001, "observed")
    native.exact_pair(row, quiet)
    ledger = e.Ledger()
    assert (
        native.inspect(row, baseline["all_blocked/observed"], r["protocol"], variant, ledger)[
            "physical_records"
        ]
        == 1921
    )
    rebuilt = native_energy.reconstruct(row, variant, [i * row["dt_s"] for i in range(641)], ledger)
    recorded = e.read(context.CAPTURE / "comparison_rows" / label / "result.json")["points"]
    assert rebuilt["times_s"] == recorded["times_s"]
    ledger.compare("state", rebuilt["states"], recorded["states"], 2e-12, 0.0)
    ledger.compare("voltage", rebuilt["voltage_V"], recorded["voltage_V"], 2e-12, 0.0)
    assert rebuilt["energy"]["max_defect_pJ"] == 0


def test_original_decoded_cells_and_checkpoint_links(saved):
    sources = {
        k.removeprefix("src/cells/"): v
        for k, v in saved[0]["sources_sha256"].items()
        if k.startswith("src/cells/")
    }
    assert len(d.cells_records(e.read(context.CAPTURE / "cells.json"), sources)) == 24


@pytest.mark.parametrize("bad", ["numerical", "refinement", "overlap", "steps", "physical"])
def test_independent_pass_gate_refuses_bad_result(bad):
    result = dict(
        failed_comparisons=0,
        failed_groups={},
        refinements={str(i): dict(passed=True) for i in range(36)},
        native_observed_steps=6720,
        observer_pairs=18,
        physical_records=20178,
        exact_overlap_records={str(i): "digest" for i in range(12)},
    )
    audit.all_pass(result)
    if bad == "numerical":
        result["failed_comparisons"] = 1
    elif bad == "refinement":
        result["refinements"]["0"]["passed"] = False
    elif bad == "overlap":
        result["exact_overlap_records"].pop("0")
    elif bad == "steps":
        result["native_observed_steps"] -= 1
    else:
        result["physical_records"] -= 1
    with pytest.raises(ValueError):
        audit.all_pass(result)


def test_known_notices_counted_not_called_warning_free():
    assert audit.notice_check(context.CAPTURE) == 72


def test_fresh_destination_and_wrong_receipt_refused(tmp_path):
    with pytest.raises(ValueError, match="Fresh"):
        job.fresh(tmp_path)
    with pytest.raises(ValueError, match="Fresh"):
        job.fresh(context.CAPTURE)
    with pytest.raises(ValueError, match="Wrong audit suite"):
        job.receipt(e.ROOT / "reports/ref-005c-refinement-checks-02.xml")


def test_per_file_and_total_budget(tmp_path, monkeypatch):
    e.write(tmp_path / "value.json", dict(value="bounded"))
    assert job.budget(tmp_path) > 0
    monkeypatch.setitem(job.BOUNDS, "per_file_bytes", 1)
    with pytest.raises(ValueError, match="artifact budget"):
        job.budget(tmp_path)


def test_detached_launcher_has_no_poll_or_wait(tmp_path, monkeypatch):
    output = tmp_path / "job"

    def registration(target, _tests):
        target.mkdir()
        e.write(target / "registration.json", {"test": True})

    calls = []

    def popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return type("Child", (), {"pid": 123})()

    monkeypatch.setattr(job, "register", registration)
    monkeypatch.setattr(subprocess, "Popen", popen)
    ack = job.launch(output, Path("unused"))
    assert ack["pid"] == 123 and ack["automatic_polling"] is False
    assert len(calls) == 1 and calls[0][1]["start_new_session"] is True
    assert "execute" in calls[0][0] and calls[0][1]["stdin"] == subprocess.DEVNULL
