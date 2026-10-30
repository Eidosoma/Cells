# ruff: noqa: E501 -- frozen repair provenance metadata.
import ast
import hashlib
import json
from pathlib import Path

R = Path("/home/robert/Cells")
W = R / "agent-work/cells-worker-01/workfiles"
family = "betse_normal_charged_grn_join"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(p, v):
    Path(p).write_text(json.dumps(v, indent=2, sort_keys=True) + "\n")


qpath = W / (family + "_workqueue.json")
q = json.loads(qpath.read_text())
before = Path(q["prepared_inputs"]).parent
p = R / "tests/unit/test_betse_normal_charged_grn_join.py"
old = p.read_text()
needle = 'gross = inputs["F"] * np.sum(abs(z) * (abs(after) + abs(before)), axis=0)'
assert old.count(needle) == 1
new = old.replace(
    needle,
    'gross = inputs["F"] * np.sum(abs(z) * (abs(np.asarray(target["ionic_state"][key])) + abs(before)), axis=0)',
)
t = ast.parse(new)
for n in ast.walk(t):
    if (
        isinstance(n, ast.Assign)
        and any(isinstance(a, ast.Name) and a.id == "gross" for a in n.targets)
        and "target['ionic_state']" in ast.unparse(n.value)
    ):
        n.value = ast.parse(
            'inputs["F"] * np.sum(abs(z) * (abs(after) + abs(before)), axis=0)', mode="eval"
        ).body
assert ast.dump(t, include_attributes=False) == ast.dump(ast.parse(old), include_attributes=False)
p.write_text(new)
for rel, d in q["owned_sha256"].items():
    if rel != str(p.relative_to(R)):
        assert sha(R / rel) == d, rel
witness = dict(
    kind="cells.charged_grn_reference_fixed_budget_repair@1",
    prior_inputs=dict(path=str(before / "inputs.json"), sha256=sha(before / "inputs.json")),
    before_test_sha256=hashlib.sha256(old.encode()).hexdigest(),
    after_test_preformat_sha256=sha(p),
    inverse_AST_equal=True,
    change="Cold ionic charge gross uses independent target ionic_state rather than actual model after",
    numeric_factors_targets_equations_case_order_unchanged=True,
    other_cold_budget_audit=dict(
        factor="128*eps*(ions+cells+membranes+64)",
        concentration="floor+factor*(abs(before)+abs(predicted_after))",
        boundary="floor+factor*(abs(before)+abs(predicted_after))",
        counts="factor*independent_before_after_gross+1e-40",
        gene_count="2*factor*abs(predicted_amount)+1e-40; unchanged before/after cold gene inventory",
        simulator_fields="1e-25+factor*F*max(independent_source_Q_gross)",
        ionic_charge="1e-25+factor*(F*sum(abs(z)*(abs(before)+abs(predicted_after)))+abs(independent_formal_charge))",
        all_data_dependent_budget_terms_reference_fixed=True,
    ),
    scientific_imports=0,
    numerical_runs=0,
    pytest_collection_runs=0,
)
wpath = W / "betse_normal_charged_grn_budget_witness_02.json"
assert not wpath.exists()
dump(wpath, witness)
for suffix in ("protocol", "source_map"):
    path = R / ("validation/betse/" + family + "_" + suffix + ".json")
    value = json.loads(path.read_text())
    value["reference_fixed_cold_budget_repair02"] = dict(
        witness_path=str(wpath.relative_to(R)),
        witness_sha256=sha(wpath),
        change=witness["change"],
        inverse_AST_equal=True,
        no_numerical_failure=True,
        numeric_factors_targets_case_order_unchanged=True,
    )
    dump(path, value)
q["reference_fixed_cold_budget_repair02"] = dict(
    witness=witness["change"],
    inverse_AST_equal=True,
    prior_inputs=str(before / "inputs.json"),
    prior_inputs_sha256=sha(before / "inputs.json"),
)
q["binding_evidence"]["held_charged01_inputs"] = dict(
    path=str(before / "inputs.json"), sha256=sha(before / "inputs.json")
)
q["binding_evidence"]["held_charged01_static_receipt"] = dict(
    path=str(R / q["static_receipt"]), sha256=q["static_receipt_sha256"]
)
q["binding_evidence"]["charged_reference_fixed_budget_witness02"] = dict(
    path=str(wpath), sha256=sha(wpath)
)
q["workfiles"] += [
    str(wpath.relative_to(R)),
    "agent-work/cells-worker-01/workfiles/prepare_native_charged_grn_budget_repair_02.py",
]
protocol = R / ("validation/betse/" + family + "_protocol.json")
value = json.loads(protocol.read_text())
value["binding_evidence"] = q["binding_evidence"]
dump(protocol, value)
q["status"] = "narrow_cold_budget_repair_ready_for_static_audit_no_numerics"
dump(qpath, q)
print(json.dumps(witness))
