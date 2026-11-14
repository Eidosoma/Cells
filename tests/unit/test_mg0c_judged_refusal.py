"""MG0c's driver refuses a judged run of an unregistered protocol or outside a clean snapshot.

As D150's (test_secreted_species_judged_refusal.py) and Rm1's: mg0c_turing.registered, the judged
entry's first call, refuses an unregistered protocol, a source that is not a clean execution
snapshot and an existing output directory (each attempt writes its own) before anything is computed
or written. Tested on edited copies of the protocol with tmp_path roots, never on a registered
protocol from a clean snapshot, which would start the judged run here. No engine run: tier 1.
"""

import hashlib
import json

import pytest

from validation.morphogenesis import mg0c_turing as mg


def copy(tmp_path, name, status):
    data = json.loads(mg.PROTOCOL.read_text())
    path = tmp_path / name
    path.write_text(json.dumps(dict(data, status=status)))
    return path


def test_the_checked_in_protocol_is_refused_outside_a_clean_snapshot(tmp_path):
    """Whatever its status: refused as unregistered while it is (PROPOSED now), and for the missing
    snapshot once registered. Registration changes the status alone, so this test's outcome does not
    change with it."""
    data = json.loads(mg.PROTOCOL.read_text())
    refusal = mg.judged_run_refusal(data, tmp_path)
    if data["status"].lower().startswith("registered"):
        assert "clean execution snapshot" in refusal
    else:
        assert "not registered" in refusal


def test_the_refusal_follows_d150s_and_rm1s(tmp_path):
    data = json.loads(mg.PROTOCOL.read_text())
    registered = dict(data, status="registered at a lead's commit (test)")
    assert "clean execution snapshot" in mg.judged_run_refusal(registered, tmp_path)
    clean = dict(status="complete", patch_sha256=hashlib.sha256(b"").hexdigest())
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(clean))
    assert mg.judged_run_refusal(registered, tmp_path) is None
    dirty = dict(clean, patch_sha256=hashlib.sha256(b"a change").hexdigest())
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(dirty))
    assert "uncommitted changes" in mg.judged_run_refusal(registered, tmp_path)
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(dict(clean, status="partial")))
    assert "incomplete" in mg.judged_run_refusal(registered, tmp_path)


def test_the_judged_entry_refuses_first_and_refuses_an_existing_output(tmp_path):
    out = tmp_path / "out"
    with pytest.raises(SystemExit, match="not registered"):
        mg.registered(copy(tmp_path, "proposed.json", "PROPOSED (test)"), out, tmp_path)
    registered = copy(tmp_path, "registered.json", "registered at a lead's commit (test)")
    with pytest.raises(SystemExit, match="clean execution snapshot"):
        mg.registered(registered, out, tmp_path)
    assert not out.exists()  # Refused before anything was written.
    clean = dict(status="complete", patch_sha256=hashlib.sha256(b"").hexdigest())
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(clean))
    assert mg.registered(registered, out, tmp_path)["status"].startswith("registered")
    out.mkdir()  # An earlier attempt's directory.
    with pytest.raises(SystemExit, match="output directory exists"):
        mg.registered(registered, out, tmp_path)
    assert list(out.iterdir()) == []


def test_main_refuses_a_proposed_protocol_before_writing(tmp_path):
    out = tmp_path / "run"
    with pytest.raises(SystemExit, match="not registered"):
        mg.main(["theory", "--output", str(out), "--protocol", str(mg.PROTOCOL)])
    assert not out.exists()
