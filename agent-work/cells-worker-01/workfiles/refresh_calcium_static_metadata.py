"""Create immutable CaATP02 from frozen01; only declared prose/queue pins change."""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path("/home/robert/Cells")
BASE = Path("/mnt/workspaces/Cells/betse-normal-calcium-prepared-20261030-01")
OUT = Path("/mnt/workspaces/Cells/betse-normal-calcium-prepared-20261030-02")
PROTOCOL = "validation/betse/betse_normal_calcium_join_protocol.json"
QUEUE = "agent-work/cells-worker-01/workfiles/betse_normal_calcium_join_workqueue.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main():
    original = json.loads((BASE / "inputs.json").read_text())
    for name, expected in original["source_hashes"].items():
        assert sha(BASE / "source" / name) == expected, name
    for name, expected in original["native_snapshot_sha256"].items():
        assert sha(BASE / name) == expected, name
    assert sha(BASE / "driver.py") == original["driver_sha256"]
    old = json.loads((BASE / "source" / PROTOCOL).read_text())
    new = json.loads((ROOT / PROTOCOL).read_text())
    expected = json.loads(json.dumps(old))
    expected["diagnostics"]["carried"] = new["diagnostics"]["carried"]
    expected["reference"] = new["reference"]
    assert expected == new, "Only the two declared diagnostic/reference prose fields may change"
    for name, expected_sha in original["owned_sha256"].items():
        if name != PROTOCOL:
            assert sha(ROOT / name) == expected_sha, name
    OUT.mkdir(exist_ok=False)
    shutil.copytree(BASE / "source", OUT / "source")
    shutil.copytree(BASE / "native-inputs", OUT / "native-inputs")
    shutil.copy2(BASE / "driver.py", OUT / "driver.py")
    for name in ("tmp", "cache", "evidence"):
        (OUT / name).mkdir()
    (OUT / "source" / PROTOCOL).write_bytes((ROOT / PROTOCOL).read_bytes())
    queue = json.loads((OUT / "source" / QUEUE).read_text())
    queue["owned_sha256"][PROTOCOL] = sha(ROOT / PROTOCOL)
    queue["authorized_metadata_refresh"] = json.loads((ROOT / QUEUE).read_text())[
        "authorized_metadata_refresh"
    ]
    (OUT / "source" / QUEUE).write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n")
    result = dict(original)
    result["owned_sha256"] = dict(original["owned_sha256"])
    result["owned_sha256"][PROTOCOL] = sha(ROOT / PROTOCOL)
    result["source_hashes"] = {
        str(path.relative_to(OUT / "source")): sha(path)
        for path in sorted((OUT / "source").rglob("*"))
        if path.is_file()
    }
    changed = {
        name
        for name, expected_sha in original["source_hashes"].items()
        if result["source_hashes"][name] != expected_sha
    }
    assert changed == {PROTOCOL, QUEUE}, changed
    result["metadata_successor"] = dict(
        prior_inputs=str(BASE / "inputs.json"),
        prior_inputs_sha256=sha(BASE / "inputs.json"),
        authority="Chief relay of independent static CaATP preflight",
        changed_source_files=sorted(changed),
        protocol_fields=["diagnostics/carried", "reference"],
        zero_carried_reference_forms=True,
        conditional_pre_handler_only=True,
        equations_budgets_and_all_protected_source_pins_unchanged=True,
        numerical_runs=0,
    )
    for name, expected_sha in result["source_hashes"].items():
        assert sha(OUT / "source" / name) == expected_sha, name
    for name, expected_sha in result["protected_sha256"].items():
        assert sha(OUT / "source" / name) == expected_sha, name
    write(OUT / "inputs.json", result)
    print(
        json.dumps(
            dict(
                inputs=str(OUT / "inputs.json"),
                sha256=sha(OUT / "inputs.json"),
                source_files=len(result["source_hashes"]),
                numerical_runs=0,
            )
        )
    )


if __name__ == "__main__":
    main()
