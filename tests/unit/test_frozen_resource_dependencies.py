"""Frozen data must be present without executing consumers or guessing dynamic paths."""

import hashlib

import pytest

from validation.frozen_resource_dependencies import audit_literal_sibling_reads


def source(root, text):
    path = root / "consumer.py"
    path.write_text(text)
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.mark.parametrize(
    "import_line,constructor",
    (
        ("from pathlib import Path", "Path"),
        ("from pathlib import Path as P", "P"),
        ("import pathlib", "pathlib.Path"),
        ("import pathlib as paths", "paths.Path"),
    ),
)
def test_missing_literal_resource_is_found_without_importing_consumer(
    tmp_path, import_line, constructor
):
    pins = source(
        tmp_path,
        f'{import_line}\nraise RuntimeError("must not execute")\n'
        f'data = {constructor}(__file__).with_name("catalog.json").read_text()\n',
    )
    result = audit_literal_sibling_reads(tmp_path, pins)
    assert result["missing_resources"] == ["catalog.json"]
    assert result["unresolved_reads"] == []
    assert result["scientific_imports_or_evaluations"] == 0


def test_present_binary_resource_is_hashed_exactly(tmp_path):
    pins = source(
        tmp_path,
        'from pathlib import Path\ndata = Path(__file__).with_name("data.bin").read_bytes()\n',
    )
    raw = b"\x00\xff\x80\x00"
    (tmp_path / "data.bin").write_bytes(raw)
    result = audit_literal_sibling_reads(tmp_path, pins)
    assert result["missing_resources"] == []
    assert result["required_resources"][0]["sha256"] == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize(
    "expression",
    (
        "Path(__file__).with_name(name).read_text()",
        'Path("relative.json").read_text()',
        "some_path.open(mode)",
    ),
)
def test_dynamic_reads_remain_explicitly_unresolved(tmp_path, expression):
    pins = source(tmp_path, f"from pathlib import Path\ndata = {expression}\n")
    result = audit_literal_sibling_reads(tmp_path, pins)
    assert result["required_resources"] == []
    assert len(result["unresolved_reads"]) == 1
    assert result["complete_dependency_closure_claim"] is False


@pytest.mark.parametrize("mode", ("w", "a", "xb"))
def test_output_files_are_not_required_input_resources(tmp_path, mode):
    pins = source(
        tmp_path,
        "from pathlib import Path\n"
        f'file = Path(__file__).with_name("output.json").open("{mode}")\n',
    )
    result = audit_literal_sibling_reads(tmp_path, pins)
    assert result["required_resources"] == result["unresolved_reads"] == []


def test_read_mode_open_requires_resource(tmp_path):
    pins = source(
        tmp_path,
        'from pathlib import Path\nfile = Path(__file__).with_name("input.json").open(mode="r")\n',
    )
    assert audit_literal_sibling_reads(tmp_path, pins)["missing_resources"] == ["input.json"]


def test_builtin_open_with_literal_sibling_requires_resource(tmp_path):
    pins = source(
        tmp_path,
        'from pathlib import Path\nfile = open(Path(__file__).with_name("input.json"), "rb")\n',
    )
    assert audit_literal_sibling_reads(tmp_path, pins)["missing_resources"] == ["input.json"]


def test_builtin_open_with_dynamic_filename_is_unresolved(tmp_path):
    pins = source(tmp_path, 'file = open(filename, "r")\n')
    result = audit_literal_sibling_reads(tmp_path, pins)
    assert len(result["unresolved_reads"]) == 1
    assert result["required_resources"] == []


def test_resource_size_limit_is_checked_before_hashing(tmp_path, monkeypatch):
    from validation import frozen_resource_dependencies as audit

    pins = source(
        tmp_path,
        'from pathlib import Path\nfile = Path(__file__).with_name("input.json").read_bytes()\n',
    )
    (tmp_path / "input.json").write_bytes(b"12345")
    monkeypatch.setattr(audit, "MAX_RESOURCE_BYTES", 4)
    with pytest.raises(ValueError, match="byte bound"):
        audit_literal_sibling_reads(tmp_path, pins)


def test_changed_consumer_is_rejected_before_resolving_dependencies(tmp_path):
    pins = source(tmp_path, "pass\n")
    (tmp_path / "consumer.py").write_text("changed = True\n")
    with pytest.raises(ValueError, match="source hash differs"):
        audit_literal_sibling_reads(tmp_path, pins)


@pytest.mark.parametrize("name", ("../outside.json", "", ".", "..", "/absolute.json"))
def test_non_sibling_literal_is_not_normalized_into_a_different_owner(tmp_path, name):
    pins = source(
        tmp_path,
        f"from pathlib import Path\nfile = Path(__file__).with_name({name!r}).read_text()\n",
    )
    with pytest.raises(ValueError, match="sibling filename"):
        audit_literal_sibling_reads(tmp_path, pins)


def test_resource_symlink_is_refused(tmp_path):
    pins = source(
        tmp_path,
        'from pathlib import Path\nfile = Path(__file__).with_name("alias.json").read_text()\n',
    )
    (tmp_path / "target.json").write_text("{}")
    (tmp_path / "alias.json").symlink_to("target.json")
    with pytest.raises(ValueError, match="symlinks"):
        audit_literal_sibling_reads(tmp_path, pins)
