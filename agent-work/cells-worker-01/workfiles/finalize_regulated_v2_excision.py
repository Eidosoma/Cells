"""Verify the focused host cut receipt and unchanged inherited accounting AST."""

import argparse
import ast
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = "agent-work/cells-worker-01/workfiles/"
CORE = "src/cells/core/calcium_energy_regulated_v2_tissue_excision.py"
OLD = "src/cells/core/calcium_energy_tissue_excision.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def functions(path):
    return {n.name: n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}


def dump(node):
    return ast.dump(node, include_attributes=False)


def inherited_proof(snapshot):
    original, current = functions(snapshot / OLD), functions(snapshot / CORE)
    exact = ("_point_check", "capture_source", "decode_source", "experiment")
    for name in exact:
        assert dump(original[name]) == dump(current[name]), name
    physical = current["physical"]
    call = physical.body[-1].value
    extra = {"regulation_factors", "regulator_samples_mM"}
    assert extra <= {k.arg for k in call.keywords}
    call.keywords = [k for k in call.keywords if k.arg not in extra]
    assert dump(original["physical"]) == dump(physical)
    derive = current["derive_tissue"]
    added = derive.body[-2]
    expected = ast.parse(
        'raw["network_regulation"]["rules"] = [asdict(rule) for rule in retained_rules(spec,plan)]'
    ).body[0]
    assert dump(added) == dump(expected)
    del derive.body[-2]
    assert dump(original["derive_tissue"]) == dump(derive)
    report = current["_physical_transition_report"]
    report.name = "transition_report"
    assert dump(original["transition_report"]) == dump(report)
    tree = ast.parse((snapshot / CORE).read_text())
    assert any(
        isinstance(n, ast.ImportFrom)
        and n.module == "cells.core.calcium_energy_tissue_excision"
        and any(a.name == "histories" for a in n.names)
        for n in tree.body
    )
    assert any(
        isinstance(n, ast.ImportFrom)
        and n.module == "cells.models"
        and any(
            a.name == "surface_calcium_energy_regulated_v2" and a.asname == "active"
            for a in n.names
        )
        for n in tree.body
    )
    return dict(
        status="passed",
        exact_functions=list(exact),
        physical_equations="Exact AST after removing two regulation readout keywords",
        derive_equations="Exact AST after removing one target-based rule filtering assignment",
        transition_accounting="Exact AST after normalizing function name",
        history_routing="Direct frozen finite-fuel history function import",
        active_field_model="surface_calcium_energy_regulated_v2",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    component, output = args.component.resolve(), args.output.resolve()
    assert component.parent == output.parent == Path("/mnt/workspaces/Cells")
    assert output.name.startswith("regulated-v2-excision-handoff-")
    report, inputs = (read(component / n) for n in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and report["error"] is None
    assert report["tests"]["tests"] >= 25
    assert all(report["tests"][k] == 0 for k in ("failures", "errors", "skipped"))
    assert inputs["affinity"] == [7] and not inputs["compiled_execution"]
    assert inputs["environment"]["JAX_DISABLE_JIT"] == "true"
    assert inputs["environment"]["CUDA_VISIBLE_DEVICES"] == ""
    for relative, expected in report["output_sha256"].items():
        assert sha(component / relative) == expected, relative
    snapshot = component / "snapshot"
    frozen = read(component / "frozen-sources.json")
    for relative, expected in frozen["after_sha256"].items():
        assert sha(snapshot / relative) == expected, relative
    for relative, expected in report["source_sha256"].items():
        assert sha(ROOT / relative) == expected == sha(snapshot / relative), relative
    proof = inherited_proof(snapshot)
    protocol = read(
        snapshot / "validation/regulation/integrated_network_regulation_v2_protocol.json"
    )
    for relative, expected in protocol["readonly_source_sha256"].items():
        assert sha(snapshot / relative) == expected, relative
    guard = read(component / "host-guard/result.json")
    assert guard["status"] == "completed"
    assert guard["sampled_peak_process_tree_rss_bytes"] <= 2**30
    assert guard["minimum_available_host_memory_bytes"] >= 8 * 2**30
    dispatch = read(ROOT / (WORK + "regulated_v2_excision_dispatch.json"))
    assert dispatch["status"] == "prepared-not-applied"
    assert sha(ROOT / dispatch["patch_path"]) == dispatch["patch_sha256"]
    evidence = {}
    for path in sorted((component / "evidence").glob("*.json")):
        assert read(path)["status"] == "passed"
        evidence[path.name] = dict(path=str(path), sha256=sha(path))
    output.mkdir(exist_ok=False)
    for relative in (
        WORK + "REGULATED_V2_EXCISION_HANDOFF.md",
        WORK + "regulated_v2_excision_dispatch.patch",
        WORK + "regulated_v2_excision_dispatch.json",
    ):
        shutil.copyfile(ROOT / relative, output / Path(relative).name)
    shutil.copyfile(Path(__file__), output / "finalize.py")
    result = dict(
        status="passed",
        model_id=inputs["model_id"],
        exact_parent=inputs["parent"],
        state_fields=38,
        tests=report["tests"],
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=sha(component / "result.json"),
        verified_component_artifacts=len(report["output_sha256"]),
        owned_source_sha256=report["source_sha256"],
        inherited_accounting_proof=proof,
        readonly_equations_sha256=protocol["readonly_source_sha256"],
        unapplied_dispatch=dispatch,
        host_guard=guard,
        evidence=evidence,
        independent_reference_scope="Separate Chief-owned handoff; not claimed here",
        compiled_cut_qualified=False,
        gpu_executed=False,
        automatic_followup=False,
        shared_dispatch_current={
            p: dict(
                current_sha256=sha(ROOT / p),
                matches_prepared_before=sha(ROOT / p) == v["before_sha256"],
            )
            for p, v in dispatch["shared_files"].items()
        },
    )
    result["handoff_artifact_sha256"] = {
        p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()
    }
    (output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(
                status="passed",
                receipt=str(output / "result.json"),
                sha256=sha(output / "result.json"),
                tests=report["tests"],
            )
        )
    )


if __name__ == "__main__":
    main()
