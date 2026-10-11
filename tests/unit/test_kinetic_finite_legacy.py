"""Old-family fingerprints and numeric composition against pre-edit source bytes."""

import hashlib
import json
import os
import subprocess
import sys
import zipfile

from tests.finite_extracellular_fixtures import definition, load_cases
from tests.kinetic_finite_fixtures import ROOT

PRESERVED = ROOT / "runs/spec-010-family-2026-09-16/pre-integration-01"
PROBE = """
import json, sys
import numpy as np
from cells.core.specs import parse_spec
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.models import finite_extracellular as model
result = []
for raw in json.load(sys.stdin):
    spec = parse_spec(raw)
    y, layout = model.initial_values(spec)
    u = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0.])))
    rate = model.rhs(y, u, layout, layout.active, xp=np)
    result.append(dict(fingerprint=spec.fingerprint, resolved=spec.to_dict(),
                       state=[v.tolist() for v in y], layout=[v.tolist() for v in layout],
                       rate=[v.tolist() for v in rate]))
print(json.dumps(result, allow_nan=False, sort_keys=True))
"""


def test_all_fourteen_old_family_initial_states_are_byte_equivalent(tmp_path):
    receipt = PRESERVED / "completion.json"
    assert hashlib.sha256(receipt.read_bytes()).hexdigest() == (
        "d9ba2cea129119b8caa96d0cf2d1e45e12811ffd368a1183a26f8011759132a9"
    )
    preserved = json.loads(receipt.read_text())
    capsule = PRESERVED / "worktree.zip"
    assert hashlib.sha256(capsule.read_bytes()).hexdigest() == preserved["worktree_zip_sha256"]
    with zipfile.ZipFile(capsule) as archive:
        names = [
            n
            for n in preserved["worktree_files_sha256"]
            if n.startswith("src/cells/") and n.endswith(".py")
        ]
        assert len(names) == 52
        for name in names:
            assert (
                hashlib.sha256(archive.read(name)).hexdigest()
                == preserved["worktree_files_sha256"][name]
            )
            assert ".." not in name.split("/")
            archive.extract(name, tmp_path)
    _, cases = load_cases()
    definitions = json.dumps([definition(c) for c in cases])
    outputs = []
    for src in (tmp_path / "src", ROOT / "src"):
        worker = subprocess.run(
            [sys.executable, "-B", "-c", PROBE],
            input=definitions,
            cwd=tmp_path,
            text=True,
            capture_output=True,
            env=os.environ | {"PYTHONPATH": str(src)},
            check=True,
            timeout=30,
        )
        assert not worker.stderr
        outputs.append(worker.stdout)
    assert outputs[0] == outputs[1]
