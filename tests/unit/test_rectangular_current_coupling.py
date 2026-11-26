"""The runtime evidence inventory hashes every loaded file by streaming it.

The file's rectangular current-coupling cases retired with their kernels (D198); this case tests
validation/betse's runtime inventory, which stays.
"""

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from validation.betse import loaded_module_inventory as runtime_inventory


def test_evidence_inventory_hashes_full_files_without_read_bytes(tmp_path, monkeypatch):
    payload = bytes(range(256)) * 8192
    library = tmp_path / "library.bin"
    executable = tmp_path / "interpreter.bin"
    library.write_bytes(payload)
    executable.write_bytes(b"declared interpreter bytes")
    monkeypatch.setattr(
        runtime_inventory,
        "sys",
        SimpleNamespace(
            modules={
                "compiled": SimpleNamespace(__file__=str(library)),
                "alias": SimpleNamespace(__file__=str(library)),
                "builtin": SimpleNamespace(),
                "missing": SimpleNamespace(__file__=str(tmp_path / "absent")),
            },
            executable=str(executable),
        ),
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Runtime evidence hashing must stream, never read a whole file")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    observed = runtime_inventory.inventory()
    assert observed["loaded_files"]["compiled"]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert observed["loaded_files"]["alias"] == observed["loaded_files"]["compiled"]
    assert (
        observed["executable"]["sha256"]
        == hashlib.sha256(b"declared interpreter bytes").hexdigest()
    )
    assert observed["modules_without_files"] == ["builtin"]
    assert observed["loaded_files"]["missing"]["unavailable"] is True
