"""S5's judge entries refuse a judged run of an unregistered protocol or outside a clean snapshot.

As S3's judge does (test_cleft_egg_engine.py): validation/division/s5_protocol.registered,
every judge entry's first call, refuses an unregistered protocol and a source that is not a
clean execution snapshot, before anything is computed or written. The refusal is tested on
edited copies of the protocol with tmp_path roots, never through a judge entry on the checked-in
protocol: once it is registered, a judge entry run from a clean snapshot would start the judged
run inside pytest.
"""

import hashlib
import json

import pytest

from validation.division import egg_division_world as egg
from validation.division import q2_rops_comparison as q2
from validation.division import q3_tissue_comparison as q3
from validation.division import q5_order as q5
from validation.division import s5_protocol


def copy(tmp_path, name, status):
    protocol = json.loads(s5_protocol.PROTOCOL.read_text())
    path = tmp_path / name
    path.write_text(json.dumps(dict(protocol, status=status)))
    return path


def test_the_checked_in_protocol_is_registered(tmp_path):
    """Registered by the lead (14 November): the status names the registrar, and only the
    source check now stands between a judge entry and its judged run."""
    status = json.loads(s5_protocol.PROTOCOL.read_text())["status"]
    assert status.startswith("registered by the lead")
    refusal = s5_protocol.judged_run_refusal({"status": status}, tmp_path)
    assert "clean execution snapshot" in refusal


def test_the_refusal_follows_s3s(tmp_path):
    protocol = json.loads(s5_protocol.PROTOCOL.read_text())
    proposed = dict(protocol, status="PROPOSED (test)")
    assert "not registered" in s5_protocol.judged_run_refusal(proposed, tmp_path)
    registered = dict(protocol, status="registered at a lead's commit (test)")
    assert "clean execution snapshot" in s5_protocol.judged_run_refusal(registered, tmp_path)
    clean = dict(status="complete", patch_sha256=hashlib.sha256(b"").hexdigest())
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(clean))
    assert s5_protocol.judged_run_refusal(registered, tmp_path) is None
    dirty = dict(clean, patch_sha256=hashlib.sha256(b"a change").hexdigest())
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(dirty))
    assert "uncommitted changes" in s5_protocol.judged_run_refusal(registered, tmp_path)
    incomplete = dict(clean, status="partial")
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(incomplete))
    assert "incomplete" in s5_protocol.judged_run_refusal(registered, tmp_path)


def entries(out, root):
    return {
        "Q2": lambda path: q2.judge(out, path, root),
        "Q3": lambda path: q3.judge(out, path, root),
        "Q5": lambda path: q5.judge(out, path, root),
        "Q1 and Q11": lambda path: egg.main(
            [str(out), "--judge", "--protocol", str(path), "--root", str(root)]
        ),
    }


@pytest.mark.parametrize("item", ("Q2", "Q3", "Q5", "Q1 and Q11"))
def test_each_judge_entry_refuses_first(item, tmp_path):
    out = tmp_path / "out"
    judge = entries(out, tmp_path)[item]
    with pytest.raises(SystemExit, match="not registered"):
        judge(copy(tmp_path, "proposed.json", "PROPOSED (test)"))
    with pytest.raises(SystemExit, match="clean execution snapshot"):
        judge(copy(tmp_path, "registered.json", "registered at a lead's commit (test)"))
    assert not out.exists()  # Refused before anything was written.
