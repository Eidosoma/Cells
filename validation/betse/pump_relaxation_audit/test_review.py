"""Saved-data smoke checks and explicit controller fixtures, never new simulations."""

import copy
import importlib
import subprocess
import sys
from contextlib import closing
from types import SimpleNamespace as NS

import native_read
import pytest
import review_context as ctx
import review_job as job
import saved_review as work

c, e, d = ctx.c, ctx.e, work.d


@pytest.fixture(scope="module")
def inputs():
    return (
        *ctx.preparation(),
        c.read(ctx.path("range") / "comparison.json", None),
        c.read(ctx.path("matched") / "comparison.json", None),
        c.read(ctx.path("range") / "registration.json", None),
    )


@pytest.mark.parametrize(
    "change",
    [
        None,
        "clock",
        "trajectory",
        "accounting",
        "refinement",
        "case",
        "range",
        "old_verdict",
        "qualification",
    ],
)
def test_contract(inputs, change):
    reference, old, result, previous, registered = copy.deepcopy(inputs)
    if change == "clock":
        reference["protocol"]["duration_s"] *= 2
    elif change in ("trajectory", "accounting", "refinement"):
        reference["protocol"][change] = {}
    elif change == "case":
        reference["cases"]["pump_only"]["volume_pL"][0] *= 2
    elif change == "range":
        registered["scope"]["native_step_ranges_s"]["pump_only"][0] *= 2
    elif change == "old_verdict":
        previous["producer_passed"] = True
    elif change == "qualification":
        result["matched_10ms_qualified"] = True
    if change is None:
        ctx.contract(reference, old, result, previous, registered)
    else:
        with pytest.raises(ValueError):
            ctx.contract(reference, old, result, previous, registered)


def test_row_selection():
    rows = ctx.rows()
    assert len(rows) == 18 and sum(round(0.01 / v["dt_s"]) for v in rows) == 235200
    assert sum(v["quiet"] is not None for v in rows) == 6
    for link in rows:
        directory = c.child(ctx.ROOT, link["directory"])
        capture = c.read(directory / "capture.json", None)
        assert capture["id"] == link["case"] and capture["mode"] == "observed"
        assert capture["steps"] == round(0.01 / link["dt_s"])
        assert c.read(directory / "comparison.json", None)["dt_s"] == link["dt_s"]
        if link["quiet"]:
            quiet = c.read(c.child(ctx.ROOT, link["quiet"]) / "capture.json", None)
            assert quiet["steps"] == capture["steps"] and quiet["mode"] == "unobserved"


def test_real_stream():
    # A complete real 160-step recording also has a separately saved original JSON.
    directory = c.NATIVE / "native/04/stream"
    with e.model_fence():
        row, facts = native_read.read(directory)
        paths = c.read(c.LEGACY / "betse.json", None)["records"]
        source = c.read(c.child(c.LEGACY, paths["all_blocked/dt_6.25e-06/observed"]), None)
        ctx.original.same_record(row, source, "Independent row assembly")
        pair = native_read.pair(directory, c.NATIVE / "native/05/stream")
    assert facts["observed_updates"] == 160 and pair["records"] == 161
    assert ctx.reader() is not c.wire.Stream and c.wire.STREAM_BYTES == 32 * 1024**2


@pytest.mark.parametrize("change", [None, "order", "missing", "history", "footer"])
def test_stream_corruption(change):
    records = list(ctx.reader()(c.NATIVE / "native/04/stream"))
    if change == "order":
        records[1], records[2] = records[2], records[1]
    elif change == "missing":
        records.pop(1)
    elif change == "history":
        history = next(r for r in records if r["kind"] == "native_history")
        history["values"]["vm_time"][0] += 1
    elif change == "footer":
        records[-1]["histories_sha256"]["vm_time"] = "0" * 64

    def check():
        row = native_read.assemble(records)
        c.exact.compare_row(row, records)

    if change is None:
        check()
    else:
        with pytest.raises((ValueError, StopIteration)):
            check()


@pytest.fixture(scope="module")
def prefix():
    stream = ctx.reader()(ctx.path("range") / "native/pump_only/coarse/stream")
    # Prefix smoke only; the detached review must exhaust/authenticate whole streams.
    with closing(iter(stream)) as iterator:
        header = next(iterator)
        steps = []
        for value in iterator:
            if value["kind"] == "native_step":
                steps.append(value)
            if len(steps) == 12:
                break
    row = dict(
        header["row"],
        steps=12,
        trace=dict(
            initial=header["trace"]["initial"],
            steps=[v["step"] for v in steps],
            raw_steps=[v["raw_step"] for v in steps],
        ),
        final=steps[-1]["step"]["after_voltage"],
    )
    return row


@pytest.mark.parametrize("change", [None, "clock", "raw_flux", "source", "disconnect"])
def test_saved_updates(prefix, inputs, change):
    row = copy.deepcopy(prefix)
    variant = next(
        v for v in inputs[1]["native_preparation"]["protocol"]["variants"] if v["id"] == "pump_only"
    )
    if change == "clock":
        row["trace"]["steps"][1]["after_elapsed_s"] += 1
    elif change == "raw_flux":
        row["trace"]["raw_steps"][0]["calls"][0]["returned"][0][0] += 1
    elif change == "source":
        row["trace"]["raw_steps"][0]["calls"][1]["inputs"]["rho"] = 2.0
    elif change == "disconnect":
        row["trace"]["raw_steps"][1]["before"]["physical"]["outside_mM"][0][0] += 1

    def check():
        ledger = e.Ledger()
        with e.model_fence():
            for step, raw in zip(row["trace"]["steps"], row["trace"]["raw_steps"], strict=True):
                work.native_records.live_laws(raw, step["before_ordinary"], row, variant, ledger)
            points = work.native_energy.reconstruct(
                row, variant, [i * row["dt_s"] for i in range(13)], ledger
            )
        assert points["steps"] == 12 and len(points["states"]) == 13 and ledger.count > 0

    if change is None:
        check()
    else:
        with pytest.raises(ValueError):
            check()


def test_saved_cells():
    reader = ctx.cells_reader()
    packet = c.read(ctx.path("matched") / "cells.json", None)
    key = "pump_only/dt_2.5e-05/jax_jit"
    saved = packet["records"][key]
    registration = c.read(ctx.path("matched") / "registration.json", None)
    sources = {
        n.removeprefix("src/cells/"): h
        for n, h in registration["sources_sha256"].items()
        if n.startswith("src/cells/")
    }
    directory = c.child(ctx.path("matched"), saved["directory"])
    with e.model_fence():
        arrays = reader.run_arrays(directory, sources)
        assert [reader.canonical(arrays, i) for i in range(41)] == saved["states"]
        resume = packet["resumes"][key]
        restarted = reader.run_arrays(c.child(ctx.path("matched"), resume["directory"]), sources)
        checkpoint = ctx.original.arrays.decode_npz(directory / "snapshots/step-000200/state.npz")
        for name in reader.FIELDS:
            assert d.bitwise_equal(arrays[name]["values"][200:], restarted[name]["values"])
            assert d.bitwise_equal(arrays[name]["values"][200], checkpoint[name]["values"])
    assert ctx.original.diagnostic.CAPTURE != reader.CAPTURE


@pytest.mark.parametrize("change", [None, "amount", "voltage", "dissipation"])
def test_cells_accounting_dispatch(monkeypatch, change):
    if change is not None:
        # Archive binding is exercised above and by the positive full dispatch.
        # These copies isolate the independently recomputed physical constraints.
        records = c.read(ctx.path("matched") / "cells.json", None)["records"]
        row = records["pump_only/dt_2.5e-05/jax_jit"]
        if change == "amount":
            row["states"][20][0] += 1
        elif change == "voltage":
            row["voltage_V"][20][0] += 1
        else:
            row["states"][20][52] = -1.0
        monkeypatch.setattr(ctx.cells_reader(), "cells_records", lambda *_: records)
    with e.model_fence():
        if change is None:
            result, rows = work.cells(ctx.preparation())
            assert len(rows) == result["decoded_trajectories"] == 24
            assert result["restart_suffixes"] == result["checkpoint_links"] == 6
            assert result["independent_accounting_states"] == 984
            assert all(
                not v["failures"] for checks in result["rows"].values() for v in checks.values()
            )
        else:
            with pytest.raises(ValueError):
                work.cells(ctx.preparation())


@pytest.fixture(scope="module")
def wiring(inputs):
    # Uses producer rows as explicit dispatch fixtures, NOT independent numerical evidence.
    plan = inputs[0]["protocol"]
    native = {}
    for link in ctx.rows():
        saved = c.read(c.child(ctx.ROOT, link["directory"]) / "comparison.json", None)
        n = round(0.01 / link["dt_s"])
        native[link["case"] + "/" + str(link["index"])] = dict(
            case=link["case"],
            index=link["index"],
            dt_s=link["dt_s"],
            physical=dict(steps=n, physical_records=3 * n + 1),
            points=saved["common_points"],
            reference_checks=work.state_checks(
                saved["common_points"], work.primary(link["case"], plan), plan
            ),
            finest_energy_check=d.discrepancy(
                saved["accounting"]["energy_pJ"], 0.0, plan["accounting"]["native_finest_energy_pJ"]
            ),
            observer_pair=dict(records=n + 1, failed_comparisons=0) if link["quiet"] else None,
            independent_comparisons=1,
        )
    records = c.read(ctx.path("matched") / "cells.json", None)["records"]
    cells = dict(
        rows={
            k: work.state_checks(v, work.primary(v["case"], plan), plan, cells=True)
            for k, v in records.items()
        }
    )
    return native, cells, records


@pytest.mark.parametrize(
    "change", [None, "energy", "contraction", "pair", "missing", "old_verdict"]
)
def test_conclusion(wiring, inputs, change):
    native, cells, records = copy.deepcopy(wiring)
    reference, old, result, previous, _ = copy.deepcopy(inputs)
    if change == "energy":
        native["pump_only/2"]["finest_energy_check"] = d.discrepancy(1.0, 0.0, 1e-7)
    elif change == "contraction":
        native["pump_only/1"]["reference_checks"]["amount"]["max_error"] = 1.0
    elif change == "pair":
        native["pump_only/2"]["observer_pair"]["failed_comparisons"] = 1
    elif change == "missing":
        del native["pump_only/0"]
    elif change == "old_verdict":
        previous["producer_passed"] = True
    if change not in (None, "energy"):
        with pytest.raises(ValueError):
            work.conclude(native, cells, records, (reference, old), result, previous)
    else:
        verdict = work.conclude(native, cells, records, (reference, old), result, previous)
        assert verdict["passed"] is (change is None) and len(verdict["refinements"]) == 36
        assert (
            not verdict["original_common_range_passed"] and not verdict["original_verdict_changed"]
        )


@pytest.mark.parametrize(
    "name",
    [
        "cells",
        "betse",
        "numpy",
        "scipy",
        "jax",
        "matched_work",
        "range_work",
        "refinement_check",
        "pilot_math",
        "native_row",
    ],
)
def test_import_fence(name):
    with e.model_fence(), pytest.raises(ImportError):
        importlib.import_module(name)


@pytest.mark.parametrize("change", [None, "scope", "source", "input", "digest"])
def test_binding(tmp_path, monkeypatch, change):
    proof = dict(path="runs/review-software-fixture/completion.json", sha256="1" * 64)
    r = dict(
        schema="cells.saved_relaxation_review@1",
        scope=copy.deepcopy(ctx.SCOPE),
        bounds=job.BOUNDS,
        rows=ctx.rows(),
        sources_sha256={},
        python=sys.version,
        inputs={},
        software=proof,
    )
    if change == "scope":
        r["scope"]["native_updates"] -= 1
    elif change == "source":
        r["sources_sha256"]["changed.py"] = "0" * 64
    elif change == "input":
        r["inputs"]["changed"] = True
    monkeypatch.setattr(ctx, "sources", lambda: {})
    monkeypatch.setattr(ctx, "authenticate_inputs", lambda: {})
    monkeypatch.setattr(c, "capsule", lambda *_: None)
    monkeypatch.setattr(job, "software", lambda _: proof)
    job.write(tmp_path / "registration.json", r)
    digest = "0" * 64 if change == "digest" else c.sha(tmp_path / "registration.json")
    if change is None:
        assert job.authenticate(tmp_path, digest) == r
    else:
        with pytest.raises(ValueError):
            job.authenticate(tmp_path, digest)


def test_detached(tmp_path, monkeypatch):
    def register(output, _):
        output.mkdir()
        job.write(output / "registration.json", {})

    calls = []
    monkeypatch.setattr(job, "register", register)
    monkeypatch.setattr(
        job.subprocess, "Popen", lambda *a, **kw: calls.append((a, kw)) or NS(pid=123)
    )
    result = job.launch(tmp_path / "job", tmp_path / "proof")
    assert not result["automatic_polling"] and calls[0][1]["start_new_session"]
    assert calls[0][1]["stdin"] == subprocess.DEVNULL


def harmless_limits(monkeypatch):
    monkeypatch.setattr(job.resource, "setrlimit", lambda *_: None)
    monkeypatch.setattr(job.signal, "signal", lambda *_: None)
    monkeypatch.setattr(job.signal, "setitimer", lambda *_: None)
    monkeypatch.setattr(job.os, "sched_getaffinity", lambda _: {0, 1, 2, 3})
    monkeypatch.setattr(job, "authenticate", lambda *_: {})
    monkeypatch.setattr(job, "budget", lambda _: None)


def test_failure(tmp_path, monkeypatch):
    harmless_limits(monkeypatch)

    def fail(*_):
        raise ValueError("intentional independent mismatch")

    monkeypatch.setattr(work, "run", fail)
    with pytest.raises(ValueError, match="intentional"):
        job.execute(tmp_path, "fixture")
    assert (tmp_path / "failure.json").is_file() and not (tmp_path / "completion.json").exists()


def test_completion(tmp_path, monkeypatch, wiring, inputs):
    harmless_limits(monkeypatch)
    result = work.conclude(*wiring, inputs[:2], inputs[2], inputs[3])

    def run(output, write, budget):
        write(output / "review.json", result)
        return result

    monkeypatch.setattr(work, "run", run)
    job.execute(tmp_path, "fixture")
    done = c.read(tmp_path / "completion.json", None)
    assert done["matched_10ms_qualified"] and not done["original_common_range_passed"]
    assert done["files_sha256"]["review.json"] == c.sha(tmp_path / "review.json")
