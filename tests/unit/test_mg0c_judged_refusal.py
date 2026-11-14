"""MG0c's judged entries refuse a run of an unregistered protocol or outside a clean snapshot.

As D150's (test_secreted_species_judged_refusal.py), S3's and S5's:
- mg0c_turing.registered is every judged entry's first call. Before anything is computed or written,
  it refuses an unregistered protocol (its status, and a registration record matching it), a source
  that is not a clean execution snapshot, and an existing output directory (the attempt rule: each
  attempt writes its own).
- mg0c_protocol.register changes a PROPOSED protocol's status and adds the lead's record, and
  nothing else.
- The judge refuses runs of another protocol, from another snapshot or incomplete. judge-guards
  treats a failing file as a verdict and a file killed by a signal as an infrastructure ending.
  combine refuses a part from another snapshot.

Tested on edited copies of the protocol with tmp_path roots, never through an entry on the
registered protocol from a clean snapshot, which would start the judged run here. No engine run:
tier 1.
"""

import hashlib
import json

import pytest

from validation.morphogenesis import mg0c_protocol as generator
from validation.morphogenesis import mg0c_turing as mg


def copy(tmp_path, name, status, **changes):
    """The checked-in protocol with another status: a registered one carries its matching
    registration record, any other none."""
    data = json.loads(mg.PROTOCOL.read_text())
    data.pop("registration", None)
    if status.startswith("registered"):
        data["registration"] = dict(status=status)
    path = tmp_path / name
    path.write_text(json.dumps(dict(data, status=status, **changes)))
    return path


def clean_snapshot(root, revision="1" * 40):
    root.mkdir(parents=True, exist_ok=True)
    manifest = dict(
        status="complete", patch_sha256=hashlib.sha256(b"").hexdigest(), git_revision=revision
    )
    (root / "SNAPSHOT.json").write_text(json.dumps(manifest))


def test_the_checked_in_protocol_is_refused_outside_a_clean_snapshot(tmp_path):
    """Whatever its status: refused as unregistered while it is (PROPOSED now), and for the missing
    snapshot once registered (its record matching its status). Registration changes the status and
    adds the record alone, so this test's outcome does not change with it."""
    data = json.loads(mg.PROTOCOL.read_text())
    refusal = mg.judged_run_refusal(data, tmp_path)
    if data["status"].lower().startswith("registered"):
        assert data["registration"]["status"] == data["status"]
        assert "clean execution snapshot" in refusal
    else:
        assert "not registered" in refusal and "registration" not in data


def test_the_refusal_reads_the_registration_record_and_register_changes_only_the_status(tmp_path):
    registered = json.loads(
        copy(tmp_path, "registered.json", "registered at a lead's commit").read_text()
    )
    unrecorded = {k: v for k, v in registered.items() if k != "registration"}
    mismatched = dict(registered, registration=dict(status="registered, another one"))
    for changed in (unrecorded, mismatched):  # A registered status needs its matching record.
        assert "registration record" in mg.judged_run_refusal(changed, tmp_path)
    assert "clean execution snapshot" in mg.judged_run_refusal(registered, tmp_path)
    clean_snapshot(tmp_path)
    assert mg.judged_run_refusal(registered, tmp_path) is None
    clean = json.loads((tmp_path / "SNAPSHOT.json").read_text())
    dirty = dict(clean, patch_sha256=hashlib.sha256(b"a change").hexdigest())
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(dirty))
    assert "uncommitted changes" in mg.judged_run_refusal(registered, tmp_path)
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(dict(clean, status="partial")))
    assert "incomplete" in mg.judged_run_refusal(registered, tmp_path)
    # Registration through the generator's path: the lead's record, the status and the record
    # alone, and only once.
    proposed = copy(tmp_path, "proposed.json", "PROPOSED (test)")
    before = json.loads(proposed.read_text())
    record = dict(status="registered by the lead (test)", by="the lead", date="(test)")
    (tmp_path / "record.json").write_text(json.dumps(record))
    (tmp_path / "bad.json").write_text(json.dumps(dict(record, status="accepted")))
    with pytest.raises(SystemExit, match="must begin 'registered'"):
        generator.register(proposed, tmp_path / "bad.json")
    after = generator.register(proposed, tmp_path / "record.json")
    assert after["status"] == record["status"] and after["registration"] == record
    assert list(after)[list(after).index("status") + 1] == "registration"
    assert {k: v for k, v in after.items() if k not in ("status", "registration")} == {
        k: v for k, v in before.items() if k != "status"
    }
    assert json.loads(proposed.read_text()) == after
    assert mg.judged_run_refusal(after, tmp_path) is not None  # The snapshot is partial here.
    with pytest.raises(SystemExit, match="only a PROPOSED protocol"):
        generator.register(proposed, tmp_path / "record.json")


ENTRIES = (
    ("parts", lambda path, out, root: mg.registered(path, out, root)),
    ("judge", lambda path, out, root: mg.judge(path, out, [], root)),
    ("judge_guards", lambda path, out, root: mg.judge_guards(path, out, root)),
    ("combine", lambda path, out, root: mg.combine(path, out, root / "a", root / "b", root)),
)


@pytest.mark.parametrize(("name", "entry"), ENTRIES)
def test_every_entry_refuses_first_and_refuses_an_existing_output(tmp_path, name, entry):
    out = tmp_path / "out"
    with pytest.raises(SystemExit, match="not registered"):
        entry(copy(tmp_path, "proposed.json", "PROPOSED (test)"), out, tmp_path)
    registered = copy(tmp_path, "registered.json", "registered at a lead's commit (test)")
    with pytest.raises(SystemExit, match="clean execution snapshot"):
        entry(registered, out, tmp_path)
    assert not out.exists()  # Refused before anything was written.
    clean_snapshot(tmp_path)
    out.mkdir()  # An earlier attempt's directory: refused before anything runs.
    with pytest.raises(SystemExit, match="output directory exists"):
        entry(registered, out, tmp_path)
    assert list(out.iterdir()) == []


def judged_run(path, protocol, source, parts, *, complete=True, requested=None):
    data = dict(
        status="Judged run of " + protocol["id"],
        quick=False,
        source=source,
        requested_parts=requested or sorted(parts),
        complete=complete,
        parts=parts,
    )
    path.write_text(json.dumps(data))
    return path


def test_the_judge_merges_complete_runs_and_refuses_incomplete_or_foreign_ones(tmp_path):
    root = tmp_path / "root"
    clean_snapshot(root)
    data = json.loads(mg.PROTOCOL.read_text())
    d147 = next(c for c in data["criteria"] if c["id"] == "D147_no_free_field_offsets")
    path = copy(tmp_path, "registered.json", "registered (test)", judged_parts=["d147"])
    small = json.loads(path.read_text())
    small["criteria"] = [d147]
    path.write_text(json.dumps(small))
    source = mg.snapshot_identity(root)
    parts = dict(d147=dict(ok=True, max_free_field_offsets=0))
    run = judged_run(tmp_path / "run.json", small, source, parts)
    verdict = mg.judge(path, tmp_path / "judge", [run], root)
    assert verdict["passed"] and verdict["source"] == source
    assert json.loads((tmp_path / "judge" / "verdict.json").read_text()) == verdict
    incomplete = judged_run(tmp_path / "incomplete.json", small, source, parts, complete=False)
    with pytest.raises(SystemExit, match="incomplete"):
        mg.judge(path, tmp_path / "judge2", [incomplete], root)
    short = judged_run(tmp_path / "short.json", small, source, parts, requested=["d147", "q1"])
    with pytest.raises(SystemExit, match="incomplete"):
        mg.judge(path, tmp_path / "judge3", [short], root)
    foreign = judged_run(
        tmp_path / "foreign.json", small, dict(source, git_revision="2" * 40), parts
    )
    with pytest.raises(SystemExit, match="another source"):
        mg.judge(path, tmp_path / "judge4", [foreign], root)
    for out in ("judge2", "judge3", "judge4"):
        assert not (tmp_path / out).exists()  # No verdict written.


def guards_world(tmp_path, files):
    """A clean snapshot root holding throwaway test files, and a registered copy whose guards of
    record list them."""
    root = tmp_path / "root"
    clean_snapshot(root)
    for name, body in files.items():
        (root / "tests").mkdir(exist_ok=True)
        (root / "tests" / name).write_text(body)
    data = json.loads(mg.PROTOCOL.read_text())
    guards = dict(data["guards_of_record"], tests=[f"tests/{name}" for name in files])
    return root, copy(tmp_path, "registered.json", "registered (test)", guards_of_record=guards)


def test_judge_guards_writes_its_verdict_and_a_failing_file_is_a_verdict(tmp_path):
    root, path = guards_world(
        tmp_path,
        {
            "test_pass.py": "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n",
            "test_fail.py": "def test_c():\n    assert False\n",
        },
    )
    verdict = mg.judge_guards(path, tmp_path / "guards", root)
    assert [f["counts"] for f in verdict["files"]] == [{"passed": 2}, {"failed": 1}]
    assert [f["exit_code"] for f in verdict["files"]] == [0, 1]
    assert verdict["passed"] is False and verdict["source"] == mg.snapshot_identity(root)
    assert json.loads((tmp_path / "guards" / "verdict.json").read_text()) == verdict


def test_judge_guards_ends_without_a_verdict_when_a_file_is_killed(tmp_path):
    killed = (
        "import os\nimport signal\n\n\ndef test_k():\n    os.kill(os.getpid(), signal.SIGKILL)\n"
    )
    root, path = guards_world(tmp_path, {"test_killed.py": killed})
    with pytest.raises(SystemExit, match="Infrastructure ending"):
        mg.judge_guards(path, tmp_path / "guards", root)
    assert not (tmp_path / "guards" / "verdict.json").exists()
    ending = json.loads((tmp_path / "guards" / "infrastructure.json").read_text())
    assert ending["files"][0]["exit_code"] < 0


def test_combine_writes_the_one_verdict_and_refuses_another_snapshots_part(tmp_path):
    clean_snapshot(tmp_path)
    path = copy(tmp_path, "registered.json", "registered (test)")
    data = json.loads(path.read_text())
    source = mg.snapshot_identity(tmp_path)
    named = dict(protocol_id=data["id"], protocol_status=data["status"], source=source)
    parts, guards = tmp_path / "parts", tmp_path / "guards"
    parts.mkdir()
    guards.mkdir()
    criteria = [dict(id="D147_no_free_field_offsets", passed=True, values=[0])]
    (parts / "verdict.json").write_text(
        json.dumps(dict(named, item="parts", criteria=criteria, passed=True))
    )
    files = [dict(file="tests/x.py", exit_code=0, seconds=1.0, counts={"passed": 1}, log="x")]
    (guards / "verdict.json").write_text(
        json.dumps(dict(named, item="guards", files=files, passed=True))
    )
    verdict = mg.combine(path, tmp_path / "all", parts, guards, tmp_path)
    assert verdict["passed"] and verdict["criteria"] == criteria
    assert verdict["scope"] == data["scope"] and verdict["snapshot_revision"] == "1" * 40
    assert json.loads((tmp_path / "all" / "verdict.json").read_text()) == verdict
    other = dict(source, git_revision="2" * 40)
    (guards / "verdict.json").write_text(
        json.dumps(dict(named, source=other, files=files, passed=True))
    )
    with pytest.raises(SystemExit, match="another source"):
        mg.combine(path, tmp_path / "all2", parts, guards, tmp_path)
    assert not (tmp_path / "all2").exists()


def test_main_refuses_a_proposed_protocol_before_writing(tmp_path):
    """On a PROPOSED copy, never the checked-in file: once that is registered, main from the
    judged snapshot (judge-guards runs this file there) would start a judged part here."""
    out = tmp_path / "run"
    proposed = copy(tmp_path, "proposed.json", "PROPOSED (test)")
    with pytest.raises(SystemExit, match="not registered"):
        mg.main(["theory", "--output", str(out), "--protocol", str(proposed)])
    assert not out.exists()
