"""Actual saved-pilot evidence, rehashed corruptions and offline orchestration gates."""

import copy
import hashlib
import json
import os
import shutil
import struct
import subprocess
import zipfile

import contact as c
import full_loop_audit as audit
import full_loop_audit_context as ctx
import full_loop_audit_job as job
import full_loop_bridge_context as pilot
import pytest
import trajectory_check as arithmetic
import trajectory_evidence as previous


@pytest.fixture(scope="module")
def registered():
    return audit.trusted_registration()


@pytest.fixture(scope="module")
def saved(registered):
    return {
        (pilot.key(row), mode): audit.read_row(ctx.SESSION, row, mode)
        for row in registered["rows"]
        for mode in pilot.MODES
    }


@pytest.fixture(scope="module")
def prepared(registered):
    return audit.prepared_rows(registered)


def test_prior_capture_sources_and_all_earlier_evidence_remain_unchanged():
    assert len(ctx.authenticate()["implementation_files_sha256"]) == 352
    assert len(ctx.packet_hashes()) == 142


def test_actual_manifest_and_provenance():
    registered, capture = audit.inspect_packet(ctx.SESSION)
    assert len(capture["files_sha256"]) == 138 and len(registered["sources"]) == 58
    assert capture["trajectory_qualified"] is False


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("mode", pilot.MODES)
def test_actual_saved_row_event_and_lifecycle_gates(registered, saved, prepared, index, mode):
    row = registered["rows"][index]
    steps = audit.audit_row(
        row,
        mode,
        saved[pilot.key(row), mode],
        prepared[pilot.key(row)],
        c.read(pilot.retained_path(row, mode)),
        previous.trusted_registration(),
        audit.voltage_nonce(),
    )
    assert steps == (40 if mode == "observed" else 0)


def test_actual_observer_and_variant_controls(saved, registered):
    assert audit.audit_controls(saved, registered) == {
        "observer_pairs": 6,
        "variant_comparisons": 4,
    }


def modify(data, path, value):
    for key in path[:-1]:
        data = data[key]
    data[path[-1]] = value


@pytest.mark.parametrize(
    "path,value",
    [
        (("result", "mode"), "unobserved"),
        (("result", "status"), "qualified"),
        (("result", "lifecycle", "run_returns"), 0),
        (("entry", "pre_loop_calls", "init_dynamics"), 2),
        (("entry", "sampled_indices"), []),
        (("events", "mode"), "preparation_dispatch_only"),
        (("events", "integration_calls"), 0),
        (("events", "hook_restored"), False),
        (("events", "events", 0, "index"), 1),
        (("events", "events", 0, "raw_label_s"), 0.001),
        (("events", "events", 0, "flux_ion_indices"), [0, 1, 2]),
        (("events", "events", 0, "after", "temperature_K"), 311.0),
        (("events", "events", 0, "before_update", "arrays", "vm", "dtype"), "<f4"),
        (("events", "events", 0, "before_update", "arrays", "cc_cells", "shape"), [7, 6]),
        (("result", "final_metadata", "pickles_present", "init"), True),
        (("result", "final_metadata", "cut_event_enabled"), True),
        (("result", "hook_restored"), False),
        (("checks", "observed_steps"), 5),
    ],
)
def test_corrupt_saved_row_is_not_accepted(registered, saved, prepared, path, value):
    row = registered["rows"][0]
    changed = copy.deepcopy(saved[pilot.key(row), "observed"])
    modify(changed, path, value)
    with pytest.raises(ValueError):
        audit.audit_row(
            row,
            "observed",
            changed,
            prepared[pilot.key(row)],
            c.read(pilot.retained_path(row)),
            previous.trusted_registration(),
            audit.voltage_nonce(),
        )


@pytest.mark.parametrize("field", ["vm", "cc_cells", "Dm_scheduled", "fluxes_mem", "I_mem"])
def test_rehashed_event_values_still_need_physical_links(registered, saved, prepared, field):
    row = registered["rows"][0]
    changed = copy.deepcopy(saved[pilot.key(row), "observed"])
    record = changed["events"]["events"][0]["before_update"]["arrays"][field]
    values = record["values"]
    while isinstance(values[0], list):
        values = values[0]
    values[0] += 0.001
    record["bytes_sha256"] = hashlib.sha256(
        b"".join(struct.pack("<d", v) for v in arithmetic.numbers(record["values"]))
    ).hexdigest()
    arithmetic.unpack(record)
    with pytest.raises(ValueError):
        audit.audit_row(
            row,
            "observed",
            changed,
            prepared[pilot.key(row)],
            c.read(pilot.retained_path(row)),
            previous.trusted_registration(),
            audit.voltage_nonce(),
        )


def test_native_nonce_is_not_replaced_by_an_unchanged_voltage_assumption(
    registered, saved, prepared
):
    row = registered["rows"][0]
    with pytest.raises(ValueError, match="nonce"):
        audit.audit_row(
            row,
            "observed",
            saved[pilot.key(row), "observed"],
            prepared[pilot.key(row)],
            c.read(pilot.retained_path(row)),
            previous.trusted_registration(),
            0.0,
        )


@pytest.fixture(scope="module")
def packet_source(tmp_path_factory):
    output = tmp_path_factory.mktemp("pilot-copy-source") / "packet"
    shutil.copytree(ctx.SESSION, output)
    return output


@pytest.fixture
def packet(tmp_path, packet_source):
    output = tmp_path / "packet"
    # Hardlinks only between pytest-owned copies. Never modify a retained inode.
    shutil.copytree(packet_source, output, copy_function=os.link)
    yield output
    assert all(c.sha(ctx.SESSION / n) == h for n, h in ctx.ANCHORS.items())


def replace(path, value):
    path.unlink()
    c.write(path, value)


def rehash(output):
    capture = c.read(output / "capture.json")
    capture["files_sha256"] = {
        str(p.relative_to(output)): c.sha(p)
        for p in output.rglob("*")
        if p.is_file() and str(p.relative_to(output)) not in audit.OPERATIONAL | {"capture.json"}
    }
    capture["artifact_bytes_before_receipt"] = sum(
        p.stat().st_size for p in output.rglob("*") if p.is_file() and p.name != "capture.json"
    )
    replace(output / "capture.json", capture)


@pytest.mark.parametrize(
    "name,path,value",
    [
        ("capture.json", ("status",), "pass"),
        ("capture.json", ("trajectory_qualified",), True),
        ("capture.json", ("observed_steps",), 80),
        ("capture.json", ("native_runs",), 72),
        ("capture.json", ("elapsed_seconds",), 151),
        ("capture.json", ("cells_runs",), 8),
        ("capture.json", ("finished_utc",), "2026-09-11T00:00:00+00:00"),
        ("worker.json", ("enabled_target_event_dispatches_observed",), 240),
        ("worker.json", ("environment", "packages", "numpy"), "0.0.0"),
        ("worker.json", ("installed_python_sha256", "betse/science/sim.py"), "0" * 64),
        ("worker.json", ("warnings",), [{"category": "RuntimeWarning", "message": "unexpected"}]),
        ("worker.json", ("observer_pairs",), []),
        ("worker.json", ("results",), []),
        ("started.json", ("pid",), 1),
        ("launch.json", ("automatic_polling",), True),
    ],
)
def test_rehashed_capture_metadata_is_independently_checked(packet, registered, name, path, value):
    changed = c.read(packet / name)
    modify(changed, path, value)
    replace(packet / name, changed)
    rehash(packet)
    audit.verify_manifest(packet, registered)
    with pytest.raises(ValueError):
        audit.inspect_packet(packet)


def test_rehashed_registration_cannot_expand_scope(packet):
    changed = c.read(packet / "registration.json")
    changed["plan"]["dt_s"] = 0.00000625
    replace(packet / "registration.json", changed)
    rehash(packet)
    with pytest.raises(ValueError, match="registration"):
        audit.inspect_packet(packet)


def test_missing_payload_cannot_be_hidden_by_rehashing(packet, registered):
    (packet / "native/passive/matched_constants/0.00002500/baseline/observed/events.json").unlink()
    rehash(packet)
    with pytest.raises(ValueError, match="coverage"):
        audit.verify_manifest(packet, registered)


def test_symlink_payload_is_rejected(packet, registered):
    target = packet / "worker.log"
    target.unlink()
    target.symlink_to(ctx.SESSION / "worker.log")
    with pytest.raises(ValueError, match="link"):
        audit.verify_manifest(packet, registered)


def test_altered_capsule_is_rejected_even_with_rehashed_manifest(packet, registered):
    path = packet / "sources.zip"
    with zipfile.ZipFile(path) as archive:
        contents = {n: archive.read(n) for n in archive.namelist()}
    contents["full_loop_observer.py"] += b"\n# unexpected source\n"
    path.unlink()
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in contents.items():
            archive.writestr(name, content)
    rehash(packet)
    audit.verify_manifest(packet, registered)
    with pytest.raises(ValueError, match="capsule bytes"):
        audit.inspect_packet(packet)


@pytest.mark.parametrize("module", ["cells", "betse.science.sim", "numpy", "jax.numpy"])
def test_model_and_array_imports_are_refused(module):
    with pytest.raises(RuntimeError, match="forbids"):
        audit.ImportFence().find_spec(module)


def test_metadata_inspection_needs_no_model_or_array_library_import():
    code = """
import sys
import full_loop_audit as a
sys.meta_path.insert(0, a.ImportFence())
a.inspect_packet(a.ctx.SESSION)
assert not any(n.split('.')[0] in a.FORBIDDEN for n in sys.modules)
print('offline metadata checked')
"""
    result = subprocess.run(
        [str(c.CELLS_PYTHON), "-B", "-c", code],
        cwd=c.HERE,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert result.stdout.strip() == "offline metadata checked"


def test_job_has_only_offline_audit_and_scoped_regression_commands(tmp_path):
    commands = job.stage_commands(tmp_path)
    assert [n for n, _ in commands] == ["audit", "regression"]
    text = json.dumps(commands)
    assert str(c.REFERENCE_PYTHON) not in text and '"full_loop_bridge.py"' not in text
    assert "test_full_loop_bridge.py" in text and "test_saved_full_loop.py" in text
    assert "--receipt" in commands[0][1]


def test_detached_job_failure_keeps_receipt_and_never_retries(tmp_path, monkeypatch):
    c.write(tmp_path / "registration.json", {"synthetic": True})
    monkeypatch.setattr(job, "validate_registration", lambda registered: None)
    attempts = []

    def timeout(*args, **kwargs):
        attempts.append(kwargs)
        raise subprocess.TimeoutExpired("synthetic audit", kwargs["timeout"])

    monkeypatch.setattr(job.subprocess, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        job.execute(tmp_path)
    receipt = c.read(tmp_path / "failure.json")
    assert len(attempts) == 1 and attempts[0]["timeout"] <= 90
    assert receipt["status"] == "failed_not_qualified"
    assert receipt["automatic_retry"] is receipt["capture_rerun"] is False
    assert "audit.log" in receipt["files_sha256"]
    assert not (tmp_path / "completion.json").exists()
