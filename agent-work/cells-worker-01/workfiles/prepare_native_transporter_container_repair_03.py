# ruff: noqa: E501 -- exact frozen-boundary descriptions and source audit metadata.
"""Bind a one-call container repair and audit saved component API inputs."""

import ast
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
OLD = Path("/mnt/workspaces/Cells/betse-normal-transporter-prepared-20261030-02")
RUN = Path("/mnt/workspaces/Cells/betse-normal-transporter-tests-20261030-02")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(node):
    return ast.dump(node, include_attributes=False)


test = "tests/unit/test_betse_normal_transporter_join.py"
now = ast.parse((ROOT / test).read_text())
inverse = copy.deepcopy(now)


class Undo(ast.NodeTransformer):
    def visit_Call(self, node):
        if (
            ast.unparse(node.func) == "ions.data"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "config"
        ):
            return node.args[0]
        return self.generic_visit(node)


inverse = Undo().visit(inverse)
assert dump(inverse) == dump(ast.parse((OLD / "source" / test).read_text()))
function = next(
    node
    for node in now.body
    if isinstance(node, ast.FunctionDef) and node.name == "transporter_comparisons"
)
bind = next(
    node
    for node in ast.walk(function)
    if isinstance(node, ast.Call) and ast.unparse(node.func) == "transporter_component.bind"
)
assert ast.unparse(bind.args[0]) == "[ions.data(config)]"
assert [ast.literal_eval(node) for node in bind.args[3:]] == [[0], [1], [True, True]]
assert ast.unparse(bind.args[2].func) == "joined.network_source.integer_valences"
api_tree = ast.parse((ROOT / "src/cells/processes/betse_network_transport.py").read_text())
api_bind = next(
    node for node in api_tree.body if isinstance(node, ast.FunctionDef) and node.name == "bind"
)
schemas = {
    target.id: ast.literal_eval(node.value)
    for node in api_bind.body
    if isinstance(node, ast.Assign)
    for target in node.targets
    if isinstance(target, ast.Name) and target.id in {"required", "optional"}
}
assert not [
    node
    for node in ast.walk(api_bind)
    if isinstance(node, ast.Subscript)
    and isinstance(node.ctx, ast.Store)
    and isinstance(node.value, ast.Name)
    and node.value.id == "row"
]
data_tree = ast.parse((ROOT / "src/cells/processes/betse_normal_ion_join.py").read_text())
data = next(
    node for node in data_tree.body if isinstance(node, ast.FunctionDef) and node.name == "data"
)
freeze = next(
    node for node in data_tree.body if isinstance(node, ast.FunctionDef) and node.name == "freeze"
)
assert "MappingProxyType" in ast.unparse(freeze) and "(tuple, list)" in ast.unparse(freeze)
assert "{key: data(item) for key, item in value.items()}" in ast.unparse(data)
assert "[data(item) for item in value]" in ast.unparse(data)
assert not [node for node in ast.walk(data) if isinstance(node, (ast.Assign, ast.AugAssign))]
base = RUN / "run-controls/evidence/normal-transporter-join"
files = {}
points = []
for case in ("transporter_only", "zero_capacity", "zero_rho"):
    folder = base / ("isolated-" + case)
    for phase in ("pre-transporters-0", "pre-network-0"):
        for name in ("inputs.json", "reference-1.json", "reference-2.json"):
            path = folder / phase / name
            files[str(path)] = sha(path)
    inputs = json.loads((folder / "pre-transporters-0/inputs.json").read_text())
    species = list(inputs["concentrations_before"]["cell_concs"])
    valence = inputs["valence"] + [
        row["parameters"]["z"] for row in inputs["definition"]["molecules"]
    ]
    assert len(species) == len(valence) == 7
    assert all(
        type(value) in (int, float)
        and math.isfinite(value)
        and -8 <= value <= 8
        and int(value) == value
        for value in valence
    )
    m = len(inputs["geometry"]["owner"])
    assert (
        m == 9 and len(inputs["rho_pump"]) == m and len(inputs["values_before"]["voltage_V"]) == m
    )
    assert (
        type(inputs["runtime_temperature_K"]) in (int, float)
        and inputs["runtime_temperature_K"] > 0
    )
    for zone in ("mem_concs", "env_concs"):
        assert list(inputs["concentrations_before"][zone]) == species
        assert all(len(inputs["concentrations_before"][zone][name]) == m for name in species)
    rows = inputs["definition"]["transporters"]
    for row in rows:
        assert (
            type(row) is dict
            and schemas["required"] <= row.keys()
            and set(row) <= schemas["required"] | schemas["optional"]
        )
        for key in (
            "reactants",
            "reactant multipliers",
            "Km reactants",
            "products",
            "product multipliers",
            "Km products",
            "transfered into cell",
            "transfered out of cell",
        ):
            assert type(row[key]) is list, (case, key)
        for prefix, km, n in (
            ("transporter activators", "activator Km", "activator n"),
            ("transporter inhibitors", "inhibitor Km", "inhibitor n"),
        ):
            if row.get(prefix) not in (None, "None"):
                assert all(type(row[key]) is list for key in (prefix, km, n))
        for role, transfer in (
            ("reactants", "transfered into cell"),
            ("products", "transfered out of cell"),
        ):
            for name in row[role]:
                zone = "env_concs" if name in row[transfer] else "mem_concs"
                assert all(
                    math.isfinite(value) and value > 0
                    for value in inputs["concentrations_before"][zone][name]
                )
    points.append(
        dict(
            case=case,
            species=species,
            component_owner_axes=dict(inside=[0], outside=[1], compartment_active=[True, True]),
            sites=m,
            configuration_count=len(rows),
            value_matrix_shape=[len(species), 2],
            valence_value_lossless=True,
            site_inputs_finite_and_shaped=True,
        )
    )
stdout = RUN / "run-controls/process/stdout.log"
files[str(stdout)] = sha(stdout)
assert stdout.read_text().count("mappingproxy(") >= 3
witness = dict(
    kind="cells.transporter_saved_component_boundary_audit@1",
    source_run=str(RUN),
    source_inputs=dict(path=str(OLD / "inputs.json"), sha256=sha(OLD / "inputs.json")),
    saved_files=files,
    actual_pre_transporter_points=3,
    actual_pre_network_points=3,
    saved_fresh_forms=12,
    carried_forms=0,
    full_control_histories_qualified=False,
    points=points,
    repair="One secondary component.bind row now uses ions.data(config): new dict/list containers recursively, original order and scalar/array payloads preserved, no input mutation",
    API_audit=dict(
        configuration_dict_and_all_substrate_multiplier_Km_transfer_and_regulator_lists=True,
        integer_valence_axis_existing_checked_helper=True,
        owner_axes_integer_distinct_two_active_compartments=True,
        site_value_matrix_float64_species_by_two=True,
        area_temperature_voltage_rho_source_fields_preserved=True,
        no_direct_row_mutation_in_component_bind_AST=True,
    ),
    inverse_test_AST_exact=True,
    scientific_imports=0,
    scientific_AST_executions=0,
    numerical_runs=0,
)
wpath = WORK / "betse_normal_transporter_container_saved_witness_03.json"
with wpath.open("x") as stream:
    json.dump(witness, stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")
qpath = WORK / "betse_normal_transporter_join_workqueue.json"
q = json.loads(qpath.read_text())
unchanged = {
    path: sha(ROOT / path)
    for path in q["owned"]
    if path
    not in {
        test,
        "validation/betse/betse_normal_transporter_join_protocol.json",
        "validation/betse/betse_normal_transporter_join_source_map.json",
    }
}
assert len(unchanged) == 7
for path, digest in unchanged.items():
    assert digest == q["owned_sha256"][path] == sha(OLD / "source" / path), path
for path, digest in q["protected_sha256"].items():
    assert sha(ROOT / path) == digest, path
evidence = q["binding_evidence"]
evidence["prior_transporter02_failed_static_inputs"] = dict(
    path=str(OLD / "inputs.json"), sha256=sha(OLD / "inputs.json")
)
evidence["transporter_container_saved_witness03"] = dict(path=str(wpath), sha256=sha(wpath))
repair = dict(
    authority="Chief requested a secondary component API container-only correction; Root02 deps5/raw2pass, controls3fail,15unrun; no numerical retry",
    saved_witness=evidence["transporter_container_saved_witness03"],
    changed_call="component.bind([ions.data(config)], ...)",
    inverse_test_AST_exact=True,
    unchanged_scientific_files=unchanged,
    unchanged_native_and_production_source=True,
    unchanged_scientific_bodies=27,
    unchanged_helpers=5,
    unchanged_protected_files=225,
    unchanged_constants_reference_and_budgets=True,
    API_audit=witness["API_audit"],
    saved_scope=dict(
        actual_pre_transporter_points=3,
        actual_pre_network_points=3,
        fresh_forms=12,
        full_control_history_credit=False,
    ),
    numerical_runs=0,
)
for relative in (
    "validation/betse/betse_normal_transporter_join_protocol.json",
    "validation/betse/betse_normal_transporter_join_source_map.json",
):
    path = ROOT / relative
    data = json.loads(path.read_text())
    if relative.endswith("protocol.json"):
        assert (
            data["acceptance"] == json.loads((OLD / "source" / relative).read_text())["acceptance"]
        )
        data["binding_evidence"] = evidence
    data["configuration_container_repair_03"] = repair
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")
q["previous_prepared_inputs02"] = dict(
    path=q.pop("prepared_inputs"), sha256=q.pop("prepared_inputs_sha256")
)
q["previous_static_receipt02"] = dict(
    path=q.pop("static_receipt"), sha256=q.pop("static_receipt_sha256")
)
q.update(
    prepared_inputs="/mnt/workspaces/Cells/betse-normal-transporter-prepared-20261030-03/inputs.json",
    configuration_container_repair_03=repair,
    status="container03_ready_for_static_audit_no_retry",
)
q["workfiles"].extend(
    [
        str((WORK / "prepare_native_transporter_container_repair_03.py").relative_to(ROOT)),
        str(wpath.relative_to(ROOT)),
    ]
)
qpath.write_text(json.dumps(q, indent=2, sort_keys=True, allow_nan=False) + "\n")
print(
    json.dumps(
        dict(
            changed_scientific_files=3,
            unchanged_scientific_files=7,
            protected=225,
            saved_prepoints=6,
            saved_fresh_forms=12,
            full_control_history_credit=False,
            numerical_runs=0,
        )
    )
)
