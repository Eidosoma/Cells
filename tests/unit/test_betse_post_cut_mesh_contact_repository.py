"""Repository source resolution checks; no native equations are executed."""

import hashlib
import json

import pytest

from validation.topology import betse_post_cut_mesh_contact_native as native


@pytest.mark.parametrize("override", [False, True])
def test_native_source_location_and_changed_bytes_refusal(tmp_path, monkeypatch, override):
    source = tmp_path / "originals"
    source.mkdir()
    relative = "unused_native_body.py"
    payload = b"raise AssertionError('native source must never execute in this test')\n"
    (source / relative).write_bytes(payload)
    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "native_source": {
                    "checkout": str(tmp_path / "absent") if override else str(source),
                    "source_sha256": {relative: hashlib.sha256(payload).hexdigest()},
                }
            }
        )
    )
    monkeypatch.setattr(native, "PROTOCOL", protocol)
    monkeypatch.delenv("CELLS_BETSE_SOURCE", raising=False)
    if override:
        monkeypatch.setenv("CELLS_BETSE_SOURCE", str(source))

    root, texts = native.source_texts({"test": relative})
    assert root == source
    assert texts == {"test": payload.decode("utf-8")}
    (source / relative).write_bytes(payload + b"# modified\n")
    with pytest.raises(ValueError, match="Native post-cut source pin changed"):
        native.source_texts({"test": relative})
