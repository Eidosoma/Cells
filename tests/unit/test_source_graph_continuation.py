"""Continuation engineering fixtures; no test runs a 1000-unit path."""

import copy
import inspect
import os

import pytest

from scripts import audit_source_graph_continuation as audit
from scripts import continue_source_graph_paths as continuation
from scripts import qualify_source_graph_paths as campaign
from tests import reference_source_graph_numerics as ref


def test_pinned_old_receipt_tamper_refused_without_reading_or_mutating_real_evidence(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(continuation, "PRIOR", tmp_path)
    ref.write_json(tmp_path / "registration.json", {})
    with pytest.raises(ValueError, match="Prior evidence changed"):
        continuation.prior_evidence()


@pytest.fixture
def fixture_campaign(monkeypatch, tmp_path):
    """Mock only old-evidence discovery; exercise real registration/run/integrity logic."""
    old = campaign.specification()
    prior = tmp_path / "sessions/old"
    prior.mkdir(parents=True)
    (prior / "retained.log").write_text("retained incomplete attempt\n")
    imports = {
        case: {"directory": f"sessions/old/{case}", "receipt_hashes": {}}
        for case in list(dict.fromkeys(k.rsplit("/", 1)[0] for k in old["planned_attempts"]))[:8]
    }
    stopped = {"attempts": [{"key": "M_to_E/blocked/radau", "status": "incomplete_timeout"}]}
    integrity = {"artifact_bytes": continuation.tree_bytes(prior)}
    monkeypatch.setattr(continuation, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(continuation, "PRIOR", prior)
    monkeypatch.setattr(continuation, "PRIOR_AUDIT", tmp_path / "old-audit.json")
    monkeypatch.setattr(
        continuation,
        "prior_evidence",
        lambda: (
            copy.deepcopy(old),
            copy.deepcopy(stopped),
            integrity.copy(),
            copy.deepcopy(imports),
        ),
    )
    monkeypatch.setattr(continuation, "SOURCES", ["fixture-source.txt"])
    (tmp_path / "fixture-source.txt").write_text("registered fixture source\n")
    for key, value in campaign.THREADS.items():
        monkeypatch.setenv(key, value)
    return prior.parent / "new"


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "linked_root"])
def test_linked_artifacts_cannot_hide_or_alias_retained_evidence(tmp_path, kind):
    directory = tmp_path / "data"
    directory.mkdir()
    source = directory / "source"
    source.write_bytes(b"evidence")
    if kind == "symlink":
        (directory / "alias").symlink_to(source)
    elif kind == "hardlink":
        os.link(source, directory / "alias")
    else:
        alias = tmp_path / "alias"
        alias.symlink_to(directory, target_is_directory=True)
        directory = alias
    with pytest.raises(ValueError, match="[Ll]ink|real directory"):
        continuation.tree_bytes(directory)


def test_continuation_is_reference_only_and_auditor_has_no_rhs():
    for module in (continuation, audit):
        source = inspect.getsource(module)
        assert "import cells" not in source and "from cells" not in source
        assert "import bitsey" not in source
    assert "model.derivative" not in inspect.getsource(audit)
