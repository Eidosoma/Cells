"""Authenticate explicit lifecycle parents and reviewed reference overrides only."""
# ruff: noqa: E501 -- Exact dependency-resolution policy is retained as metadata.

import ast
import hashlib
import json
from pathlib import Path

BASE = Path("/mnt/workspaces/Cells")
WORK = Path(__file__).parent
PINS = {
    "dispatch01": (
        "betse-normal-ecm-molecule-dispatch-prepared-20261031-01",
        "e51f7eead8d6bfe3a0e4f669005386e6f4271632f0531084754320025b1ed922",
    ),
    "transport01": (
        "betse-normal-ecm-molecule-transport-prepared-20261031-01",
        "166e53330a63866f42897029daafde64b3b957bb1ec1771191e46b8c458b5ba6",
    ),
    "transition02": (
        "betse-normal-ecm-init-sim-transition-prepared-20261031-02",
        "fab41871bfaf8e457141bd76a491926577f1a84d16a6052aee2538e0e5eec312",
    ),
    "INIT04": (
        "betse-normal-ecm-init-phase-prepared-20261031-04",
        "a6495a39ff5af284a0dce6df146d949f0f772f605bcdd8d998409a84a026f017",
    ),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def functions(path):
    tree = ast.parse(path.read_text())
    return {
        n.name: hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest()
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef))
    }


def main():
    parents = {}
    for key, (name, pin) in PINS.items():
        path = BASE / name
        assert sha(path / "MANIFEST.json") == pin, key
        parents[key] = dict(
            path=str(path), manifest_sha256=pin, inputs_sha256=sha(path / "inputs.json")
        )
    handoff = BASE / "ecm-init-event-reference-successor-20261031-01/HANDOFF.json"
    assert sha(handoff) == "2825a1310b1dc8f6426406cf36fe5e2012b1ad3ed514a7784c7eb94e75a9b58f"
    receipt = json.loads(handoff.read_text())
    assert receipt["status"] == "explicit_INIT04_source_frozen_held"
    review = receipt["dependency_review"]
    assert sha(Path(review["path"])) == review["sha256"]
    old = BASE / "betse-normal-ecm-init-phase-prepared-20261031-02"
    old_inputs = json.loads((old / "inputs.json").read_text())
    new = BASE / PINS["INIT04"][0]
    new_inputs = json.loads((new / "inputs.json").read_text())
    changed = {
        k
        for k, pin in old_inputs["source_sha256"].items()
        if new_inputs["source_sha256"].get(k) != pin
    }
    allowed = {
        "validation/betse/betse_normal_ecm_event_join_reference.py",
        "validation/betse/betse_normal_ecm_init_phase_reference.py",
    }
    assert changed == allowed
    overrides = {}
    for name in sorted(changed):
        before = old / "source" / name
        after = new / "source" / name
        assert sha(before) == old_inputs["source_sha256"][name]
        assert sha(after) == new_inputs["source_sha256"][name]
        a, b = functions(before), functions(after)
        overrides[name] = dict(
            historical_INIT02_sha256=sha(before),
            INIT04_sha256=sha(after),
            changed_top_level_ASTs=[k for k in sorted(a.keys() | b.keys()) if a.get(k) != b.get(k)],
            adopted_for_new_lifecycle_only=True,
        )
    transition = BASE / PINS["transition02"][0]
    inputs = json.loads((transition / "inputs.json").read_text())
    old_ref = "validation/betse/betse_normal_ecm_init_phase_reference.py"
    assert inputs["source_sha256"][old_ref] == old_inputs["source_sha256"][old_ref]
    assert sha(transition / "source" / old_ref) == old_inputs["source_sha256"][old_ref]
    result = dict(
        kind="cells.explicit_molecule_lifecycle_dependencies@1",
        status="source_dependencies_authenticated",
        parents=parents,
        INIT04_handoff=dict(path=str(handoff), sha256=sha(handoff)),
        INIT04_dependency_review=review,
        reviewed_reference_overrides=overrides,
        historical_transition02_INIT02_unchanged=True,
        resolution_policy="New lifecycle source uses explicit transport01 and copied transition02 bodies; only the two exact INIT04 reference members override older references in the new proposal. Old packets and their lineage are unchanged. No whole transition02 requalification or silent historical rebase is claimed.",
        scientific_imports=0,
        scientific_AST_executions=0,
        scientific_evaluations=0,
        inherited_scientific_passes=0,
        numerical_launches=0,
    )
    output = WORK / "betse_normal_ecm_molecule_lifecycle_dependencies_01.json"
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            dict(output=str(output), sha256=sha(output), overrides=overrides), sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
