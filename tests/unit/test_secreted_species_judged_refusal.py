"""D150 v1's judged entries refuse a run of an unregistered protocol or outside a clean snapshot.

As S3's and S5's judges do (test_cleft_egg_engine.py, test_s5_judged_refusal.py):
validation/tissue/secreted_species_protocol.registered, every judged entry's first call, refuses an
unregistered protocol and a source that is not a clean execution snapshot before anything is
computed or written, and every entry (judge, judge_q5, combine) refuses an existing output
directory (the attempt rule: every attempt writes its own). Tested on edited copies of the protocol
with tmp_path roots, never through an entry on the registered protocol from a clean snapshot,
which would start the judged run here. judge_q5 runs only throwaway test files written here, and
combine only verdicts written here: a failing file is a verdict, a file killed by a signal is an
infrastructure ending (no verdict), and combine refuses a part from another snapshot.
"""

import hashlib
import json

import pytest

from validation.tissue import secreted_species_protocol as protocol


def copy(tmp_path, name, status, **changes):
    data = json.loads(protocol.PROTOCOL.read_text())
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
    snapshot once registered. Registration changes the status alone, so this test's outcome does not
    change with it, and Q5 runs it at the judged snapshot."""
    data = json.loads(protocol.PROTOCOL.read_text())
    refusal = protocol.judged_run_refusal(data, tmp_path)
    if data["status"].startswith("registered"):
        assert "clean execution snapshot" in refusal
    else:
        assert "not registered" in refusal


def test_the_refusal_follows_s3s_and_s5s(tmp_path):
    data = json.loads(protocol.PROTOCOL.read_text())
    registered = dict(data, status="registered at a lead's commit (test)")
    assert "clean execution snapshot" in protocol.judged_run_refusal(registered, tmp_path)
    clean = dict(status="complete", patch_sha256=hashlib.sha256(b"").hexdigest())
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(clean))
    assert protocol.judged_run_refusal(registered, tmp_path) is None
    dirty = dict(clean, patch_sha256=hashlib.sha256(b"a change").hexdigest())
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(dirty))
    assert "uncommitted changes" in protocol.judged_run_refusal(registered, tmp_path)
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(dict(clean, status="partial")))
    assert "incomplete" in protocol.judged_run_refusal(registered, tmp_path)


ENTRIES = (
    ("judge", lambda out, path, root: protocol.judge(out, path, root)),
    ("judge_q5", lambda out, path, root: protocol.judge_q5(out, path, root)),
    ("combine", lambda out, path, root: protocol.combine(out, root / "a", root / "b", path, root)),
)


@pytest.mark.parametrize(("name", "entry"), ENTRIES)
def test_every_entry_refuses_first_and_refuses_an_existing_output(tmp_path, name, entry):
    out = tmp_path / "out"
    with pytest.raises(SystemExit, match="not registered"):
        entry(out, copy(tmp_path, "proposed.json", "PROPOSED (test)"), tmp_path)
    registered = copy(tmp_path, "registered.json", "registered at a lead's commit (test)")
    with pytest.raises(SystemExit, match="clean execution snapshot"):
        entry(out, registered, tmp_path)
    assert not out.exists()  # Refused before anything was written.
    clean_snapshot(tmp_path)
    out.mkdir()  # An earlier attempt's directory: refused before anything runs.
    with pytest.raises(SystemExit, match="output directory exists"):
        entry(out, registered, tmp_path)
    assert list(out.iterdir()) == []


def q5_world(tmp_path, files):
    """A clean snapshot root holding throwaway test files, and a registered copy whose Q5 lists
    them."""
    root = tmp_path / "root"
    clean_snapshot(root)
    for name, body in files.items():
        (root / "tests").mkdir(exist_ok=True)
        (root / "tests" / name).write_text(body)
    data = json.loads(protocol.PROTOCOL.read_text())
    q5 = dict(data["Q5"], tests=[f"tests/{name}" for name in files])
    return root, copy(tmp_path, "registered.json", "registered (test)", Q5=q5)


def test_judge_q5_writes_its_verdict_and_a_failing_file_is_a_verdict(tmp_path):
    root, path = q5_world(
        tmp_path,
        {
            "test_pass.py": "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n",
            "test_fail.py": "def test_c():\n    assert False\n",
        },
    )
    verdict = protocol.judge_q5(tmp_path / "q5", path, root)
    assert [f["counts"] for f in verdict["files"]] == [{"passed": 2}, {"failed": 1}]
    assert [f["exit_code"] for f in verdict["files"]] == [0, 1]
    assert all(f["seconds"] > 0 for f in verdict["files"])
    assert verdict["passed"] is False and verdict["source"] == protocol.snapshot_identity(root)
    assert json.loads((tmp_path / "q5" / "verdict.json").read_text()) == verdict


def test_judge_q5_ends_without_a_verdict_when_a_file_is_killed(tmp_path):
    killed = (
        "import os\nimport signal\n\n\ndef test_k():\n    os.kill(os.getpid(), signal.SIGKILL)\n"
    )
    root, path = q5_world(tmp_path, {"test_killed.py": killed})
    with pytest.raises(SystemExit, match="Infrastructure ending"):
        protocol.judge_q5(tmp_path / "q5", path, root)
    assert not (tmp_path / "q5" / "verdict.json").exists()
    ending = json.loads((tmp_path / "q5" / "infrastructure.json").read_text())
    assert ending["files"][0]["exit_code"] < 0


def test_combine_writes_the_one_verdict_and_refuses_another_snapshots_part(tmp_path):
    clean_snapshot(tmp_path)
    path = copy(tmp_path, "registered.json", "registered (test)")
    data = json.loads(path.read_text())
    source = protocol.snapshot_identity(tmp_path)
    named = dict(protocol_id=data["id"], protocol_status=data["status"], source=source)
    items = {k: dict(passed=True) for k in ("Q1_imex", "Q1_rk4", "Q2", "Q3")}
    step_map = {"Q1_imex_step_map": dict(fraction_of_bound=0.005)}
    q123, q5 = tmp_path / "q123", tmp_path / "q5"
    q123.mkdir()
    q5.mkdir()
    q123_verdict = dict(named, refused_arms=[], items=items, passed=True)
    (q123 / "verdict.json").write_text(json.dumps(dict(q123_verdict, reported_not_judged=step_map)))
    files = [dict(file="tests/x.py", exit_code=0, seconds=1.0, counts={"passed": 1}, log="x")]
    (q5 / "verdict.json").write_text(json.dumps(dict(named, item="Q5", files=files, passed=True)))
    verdict = protocol.combine(tmp_path / "all", q123, q5, path, tmp_path)
    assert verdict["passed"] and set(verdict["items"]) == {*items, "Q5"}
    assert verdict["scope"] == data["scope"] and verdict["snapshot_revision"] == "1" * 40
    assert verdict["not_judged"]["step_map"] == step_map
    assert json.loads((tmp_path / "all" / "verdict.json").read_text()) == verdict
    other = dict(source, git_revision="2" * 40)
    (q5 / "verdict.json").write_text(
        json.dumps(dict(named, source=other, files=files, passed=True))
    )
    with pytest.raises(SystemExit, match="another source"):
        protocol.combine(tmp_path / "all2", q123, q5, path, tmp_path)
    assert not (tmp_path / "all2").exists()
