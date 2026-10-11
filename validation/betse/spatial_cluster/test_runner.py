"""Regression receipts preserve pytest aliases without accepting linked evidence."""

import importlib.util
import os
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "spatial_runner_context", Path(__file__).with_name("context.py")
)
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)


@pytest.fixture
def evidence(tmp_path):
    root = tmp_path / "regression"
    output = root / "pytest/test_example0"
    output.mkdir(parents=True)
    (output / "state.json").write_text('{"amount": 1}\n')
    context.u.write(root / "result.json", dict(tests=1, failures=0))
    alias = output.with_name("test_examplecurrent")
    alias.symlink_to(output)
    try:
        yield root, output, alias
    finally:
        alias.unlink()  # Only this fixture's alias; all real evidence stays present.


def test_receipt_keeps_alias_and_hashes_real_evidence(evidence):
    root, output, alias = evidence
    receipt = context.artifacts(root, pytest_links=True)
    assert receipt["pytest_internal_links"] == {"pytest/test_examplecurrent": str(output)}
    assert receipt["files_sha256"] == {
        "result.json": context.u.sha(root / "result.json"),
        "pytest/test_example0/state.json": context.u.sha(output / "state.json"),
    }
    context.u.write(root / "completion.json", receipt)
    context.check_artifacts(root, receipt, pytest_links=True)
    assert alias.is_symlink() and (output / "state.json").is_file()
    with pytest.raises(ValueError, match="Linked evidence"):
        context.artifacts(root)


@pytest.mark.parametrize("kind", ["escape", "file", "nested", "unrelated", "broken"])
def test_unexpected_links_are_rejected(evidence, kind):
    root, output, alias = evidence
    if kind == "nested":
        alias = output / "nestedcurrent"
        target = output / "nested0"
        target.mkdir()
    elif kind == "unrelated":
        alias = output.parent / "shortcut"
        target = output
    else:
        alias = output.parent / "test_othercurrent"
        target = {
            "escape": root.parent,
            "file": output / "state.json",
            "broken": output.parent / "test_other0",
        }[kind]
    alias.symlink_to(target)
    try:
        with pytest.raises(ValueError, match="Unexpected pytest artifact link"):
            context.artifacts(root, pytest_links=True)
    finally:
        alias.unlink()  # Never unlink a target or evidence from an earlier run.


@pytest.mark.parametrize("change", ["content", "missing", "extra", "alias"])
def test_receipt_detects_evidence_changes(evidence, change):
    root, output, alias = evidence
    second = output.with_name("test_example1")
    second.mkdir()
    receipt = context.artifacts(root, pytest_links=True)
    context.u.write(root / "completion.json", receipt)
    if change == "content":
        (output / "state.json").write_text('{"amount": 2}\n')
    elif change == "missing":
        (output / "state.json").unlink()
    elif change == "extra":
        (output / "extra.json").write_text("{}\n")
    else:
        alias.unlink()
        alias.symlink_to(second)
        assert os.readlink(alias) == str(second)
    with pytest.raises(ValueError, match="Spatial phase artifact changed"):
        context.check_artifacts(root, receipt, pytest_links=True)
