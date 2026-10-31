"""Saved-evidence inventory controls, with no simulation or case credit."""

import hashlib

import pytest

from validation.geometry.qualification_inventory import inventory


def setup_tree(tmp_path):
    root = tmp_path / "run"
    owner = root / "tmp/check-042"
    target = owner / "test_generated_0"
    target.mkdir(parents=True)
    (target / "input.json").write_bytes(b'{"unchanged":true}\n')
    (root / "failure.json").write_bytes(b'{"status":"failed"}\n')
    return root, owner, target


@pytest.mark.parametrize("absolute", [False, True])
def test_valid_alias_is_bound_separately_without_duplicate_files(tmp_path, absolute):
    root, owner, target = setup_tree(tmp_path)
    link = owner / "test_generated_current"
    link.symlink_to(target if absolute else target.name, target_is_directory=True)
    value = inventory(root, pytest_tmp_roots=["tmp/check-042"])
    assert set(value["files_sha256"]) == {
        "failure.json",
        "tmp/check-042/test_generated_0/input.json",
    }
    assert (
        value["files_sha256"]["failure.json"]
        == hashlib.sha256(b'{"status":"failed"}\n').hexdigest()
    )
    record = value["pytest_tmp_links"]["tmp/check-042/test_generated_current"]
    assert record["target_relative"] == "tmp/check-042/test_generated_0"
    assert record["target_text_sha256"] == hashlib.sha256(record["target"].encode()).hexdigest()
    assert value["links_followed"] is False and link.is_symlink()
    assert (root / "failure.json").read_bytes() == b'{"status":"failed"}\n'


@pytest.mark.parametrize(
    "kind", ["undeclared", "outside", "dangling", "chain", "self", "file", "wrong-name", "evidence"]
)
def test_other_links_are_rejected(tmp_path, kind):
    root, owner, target = setup_tree(tmp_path)
    link = owner / "test_generated_current"
    declared = ["tmp/check-042"]
    destination = target
    if kind == "undeclared":
        declared = []
    elif kind == "outside":
        destination = tmp_path / "test_generated_1"
        destination.mkdir()
    elif kind == "dangling":
        destination = owner / "test_generated_9"
    elif kind == "chain":
        destination = owner / "test_generated_1"
        destination.symlink_to(target, target_is_directory=True)
    elif kind == "self":
        destination = link
    elif kind == "file":
        destination = owner / "test_generated_2"
        destination.write_bytes(b"not a directory")
    elif kind == "wrong-name":
        link = owner / "arbitrary_current"
    elif kind == "evidence":
        link = root / "test_generated_current"
    link.symlink_to(destination, target_is_directory=True)
    with pytest.raises(ValueError):
        inventory(root, pytest_tmp_roots=declared)


@pytest.mark.parametrize(
    "declared", ["../tmp/check-042", "/tmp/check-042", "tmp//check-042", "evidence"]
)
def test_noncanonical_or_non_temporary_allowances_are_rejected(tmp_path, declared):
    root, _, _ = setup_tree(tmp_path)
    with pytest.raises(ValueError):
        inventory(root, pytest_tmp_roots=[declared])


def test_linked_root_and_linked_allowed_directory_are_rejected(tmp_path):
    root, owner, _ = setup_tree(tmp_path)
    linked = tmp_path / "alias"
    linked.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError):
        inventory(linked)
    (root / "tmp/check-043").symlink_to(owner, target_is_directory=True)
    with pytest.raises(ValueError):
        inventory(root, pytest_tmp_roots=["tmp/check-043"])


def test_file_changes_are_visible_and_entry_bounds_remain_enforced(tmp_path):
    root, _, target = setup_tree(tmp_path)
    original = inventory(root)
    (target / "input.json").write_bytes(b'{"changed":true}\n')
    assert inventory(root)["files_sha256"] != original["files_sha256"]
    with pytest.raises(ValueError, match="entry bound"):
        inventory(root, max_entries=1)
