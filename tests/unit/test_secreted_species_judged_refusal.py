"""D150 v1's judge refuses a judged run of an unregistered protocol or outside a clean snapshot.

As S3's and S5's judges do (test_cleft_egg_engine.py, test_s5_judged_refusal.py):
validation/tissue/secreted_species_protocol.registered, the judge entry's first call, refuses an
unregistered protocol and a source that is not a clean execution snapshot before anything is
computed or written, and the judge refuses an existing output directory (the attempt rule: every
attempt writes its own). Tested on edited copies of the protocol with tmp_path roots, never through
the judge on a registered protocol from a clean snapshot, which would start the judged run here.
"""

import hashlib
import json

import pytest

from validation.tissue import secreted_species_protocol as protocol


def copy(tmp_path, name, status):
    data = json.loads(protocol.PROTOCOL.read_text())
    path = tmp_path / name
    path.write_text(json.dumps(dict(data, status=status)))
    return path


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


def test_the_judge_refuses_first_and_refuses_an_existing_output(tmp_path):
    out = tmp_path / "out"
    with pytest.raises(SystemExit, match="not registered"):
        protocol.judge(out, copy(tmp_path, "proposed.json", "PROPOSED (test)"), tmp_path)
    registered = copy(tmp_path, "registered.json", "registered at a lead's commit (test)")
    with pytest.raises(SystemExit, match="clean execution snapshot"):
        protocol.judge(out, registered, tmp_path)
    assert not out.exists()  # Refused before anything was written.
    clean = dict(status="complete", patch_sha256=hashlib.sha256(b"").hexdigest())
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(clean))
    out.mkdir()  # An earlier attempt's directory: refused before any arm runs.
    with pytest.raises(SystemExit, match="output directory exists"):
        protocol.judge(out, registered, tmp_path)
    assert list(out.iterdir()) == []
