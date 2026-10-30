# ruff: noqa: E501 -- source templates are formatted in their outputs.
"""Build protocol, workqueue and runner without evaluating a scientific packet."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = "agent-work/cells-worker-01/workfiles/"
OLD, NEW = "betse_normal_molecule", "betse_normal_transporter"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with (ROOT / path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


previous = json.loads((ROOT / (WORK + OLD + "_join_workqueue.json")).read_text())
protocol = json.loads((ROOT / ("validation/betse/" + OLD + "_join_protocol.json")).read_text())
protocol.update(
    kind="cells.native_configured_transporter_execution_static_contract@1",
    law_id="betse_normal_configured_transporter_execution_v1_5_0@1",
    purpose="Actual configured active-transporter execution coupled to ion/network/molecule state, before channels/modulators/chemistry",
    status="static_unqualified_no_transporter_numerics",
    source_map="validation/betse/" + NEW + "_join_source_map.json",
)
for name in ("molecules.py", "gene.py"):
    relative = "betse/science/chemistry/" + name
    protocol["native_source"]["source_sha256"][relative] = sha(
        Path(protocol["native_source"]["checkout"]) / relative
    )
protocol["planned"] = dict(
    checks=25,
    positive_three_call_histories=18,
    new_coupled_cases=15,
    component_control_histories=3,
    raw_partial_failures=2,
    dependency_controls=5,
    native_captures=20,
    positive_native_outer_calls=54,
    actual_pre_transporter_points=54,
    actual_pre_network_points=54,
    fresh_Decimal_reference_forms=216,
    carried_reference_forms=0,
    positive_completed_mover_calls_per_implementation=108,
    biological_cases=0,
)
protocol["scope"]["transporters"] = (
    "One to three genuine native Transporter instances; literal read_transporters/init_reaction/write_transporters/run_loop_transporters; positive all-target cell/no-ECM histories and separately retained supplied-subset failures"
)
protocol["scope"]["initial_state"] += (
    "; explicit membrane wedge volumes and cold/carried transporter flux caches; supplied named profile indices only in negative cases"
)
protocol["scope"]["excluded"] += [
    "Express-map initialization and generated tissue-profile targeting",
    "Mitochondrial/ECM transporter commits",
    "Physical conservation or full lifecycle credit for the native transporter buffers/bath",
]
protocol["input_versus_execution"]["executed"] += (
    "; original Transporter constructor/init_reaction and read/write/ordered run_loop_transporters"
)
protocol["input_versus_execution"]["observations"] += (
    "; actual immutable pre-transporter input before production execution; copied before/flux/current/per-term/after states with all partial writes"
)
protocol["input_versus_execution"]["phase"] += (
    "; wrapper transporter activation and normal dispatch audited but wrappers not executed"
)
protocol["owned_state"]["transporter_dynamic"] = (
    "Literal flux=None before first call and actual float64[M] thereafter, separately owned for every configured transporter; carried through network_cache/parent identity; missing or mutable state refused"
)
protocol["owned_state"]["transporter_geometry"] = (
    "Explicit membrane_volume_m3 equals source 0.5*radius*area; supplied cell_vol is preserved and is not claimed to be produced by the native wedge mesh initializer"
)
protocol["owned_state"]["transporter_controls"] = (
    "Actual live NaK packet rho_pump supplies the sole outer density multiplier; no extra availability gate or source-absent boundary mask"
)
protocol["source_order"].insert(
    2,
    "After network clear, configured transporters run in insertion order: evaluate full flux once, add full-membrane current, then sequential reactant/product bulk/membrane/environment writes. Next transporter sees preceding writes; channels and chemistry sample resulting state.",
)
protocol["source_order"][1] = "Ordinary NaK/ions/GJ/intra, then CaATP and network clear"
protocol["source_order"][3] = (
    "Late catalog channels run after configured transporters; original ion-driven GJ/NaK modulators overwrite controls in order, feeding molecules now and ordinary transport next call"
)
protocol["accounting"]["molecule_mover"] = {
    key: protocol["accounting"][key]
    for key in ("source_effective", "declared_single_bath", "directed_GJ")
}
protocol["accounting"]["transporter_source_effective"] = (
    "For all targets, use w_j=cell_vol[owner_j]/membrane_count(owner_j) for the per-membrane env aliases. sum(w_j*delta_env_j) cancels the configured bulk transfer for pure transport. This algebraic ledger does not redefine physical bath geometry or volume."
)
protocol["accounting"]["transporter_physical_bath"] = (
    "Keep original vol_env*mean(c_env). For each external term of signed coefficient sigma*nu, predict bath change sigma*nu*dt*vol_env/M*sum_i(n_i*sum_{owner=j=i}(f_j*A_j)/V_i), and bulk change from internal terms sigma*nu*dt*sum_j(f_j*A_j). Compare observed defect to predicted defect, not to zero."
)
protocol["accounting"]["transporter_buffer"] = (
    "For each internal term, literal membrane delta is sigma*f_j*A_j/mem_vol_j*dt, whereas stoichiometric delta is sigma*nu*f_j*A_j/mem_vol_j*dt. Preserve discrepancy sigma*(1-nu)*f_j*A_j/mem_vol_j*dt and compare it separately from the source-effective/physical amount ledgers. Membrane buffers are samples/caches, never added as a second independent bulk inventory."
)
protocol["accounting"]["transporter_current"] = (
    "Unconditional source extra_J_mem += net_z*flux*F precedes target commits, remains separate from ordinary flux storage, and may survive source failure. No closed electrical/energy/ATP/heat accounting claim."
)
protocol["acceptance"]["primary"] += (
    "; actual transporter generated metadata, full pre/partial/after flux/current/concentration arrays and target ordering"
)
protocol["acceptance"]["transporter_rates"] = json.loads(
    (ROOT / "validation/transport/betse_network_transport_protocol.json").read_text()
)["tolerances"]
protocol["acceptance"]["transporter_material"] = (
    "Unchanged molecule/B24 a priori 128*eps*(species+cells+membranes+64) local gross plus matching concentration floors; all physical/effective amount and buffer defects use old/new weighted gross and unchanged physical volumes"
)
protocol["acceptance"]["transporter_current"] = (
    "Unchanged standalone current_atol_A_m2 plus the a priori material factor times local current gross"
)
protocol["acceptance"]["conditional_pre_transporter_only"] = True
protocol["acceptance"]["independent"] = (
    "Fresh Decimal90/140 actual pre-transporter block and separate actual pre-chemistry forms; original generated strings/output metadata never feed reference algebra; no independently carried trajectory"
)
for relative in (
    "validation/transport/betse_network_transport_protocol.json",
    "validation/betse/betse_normal_molecule_join_protocol.json",
):
    protocol["acceptance"]["inherited_budget_source_sha256"][relative] = sha(ROOT / relative)
protocol["component_controls"] = dict(
    new_caller_controls=["transporter_only", "zero_capacity", "zero_rho"],
    legacy_source_laws=protocol["component_controls"]["legacy_source_laws"],
    distinction="Standalone transporter checks qualify the rate law and a conservative generic accumulator, not the actual native bulk/membrane/environment commits. Secondary component rates here use each actual incoming transporter state, while independent Decimal references own the native ordered commits. No legacy pass is counted as new coupled execution.",
)
protocol["failures"].update(
    raw=["first_subset_partial", "second_subset_partial"],
    partial="Preserve source IndexError caused by subset cell deltas indexed with global mem_to_cells: full current already added, internal bulk cell1 and membrane3:6 already changed, environment unchanged; preceding all-target transporter remains committed in second case",
    positive_credit=False,
)
evidence = dict(previous["binding_evidence"])
evidence["prior_molecule_static_inputs"] = dict(
    path=previous["prepared_inputs"], sha256=previous["prepared_inputs_sha256"]
)
receipt = ROOT / (WORK + OLD + "_join_static_receipt_01.json")
evidence["prior_molecule_static_receipt"] = dict(path=str(receipt), sha256=sha(receipt))
protocol["binding_evidence"] = evidence
write("validation/betse/" + NEW + "_join_protocol.json", protocol)

spec = importlib.util.spec_from_file_location(
    "transporter_AST_audit", ROOT / (WORK + NEW + "_join_ast_audit.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
proof = module.audit()
mapping = json.loads(
    (ROOT / "validation/betse/betse_normal_molecule_join_source_map.json").read_text()
)
mapping.update(proof)
mapping.update(
    kind="cells.native_configured_transporter_execution_source_map@1",
    law_id=protocol["law_id"],
    status="static_unqualified_no_transporter_numerics",
    scientific_AST_executions=0,
)
mapping["source_sha256"] = protocol["native_source"]["source_sha256"]
mapping["wrapper_reachability"] = dict(
    source_files=["betse/science/chemistry/molecules.py", "betse/science/chemistry/gene.py"],
    configuration="Non-None transporters config calls read_transporters/write_transporters and sets wrapper .transporters=True",
    normal_source="betse/science/sim.py:1287-1320",
    transported_before=["channels", "modulators", "core chemistry"],
    actual_wrapper_lifecycle_executed=False,
)
mapping["transporters"] = dict(
    executed=[
        "Transporter.__init__",
        "Transporter.init_reaction",
        "MasterOfNetworks.read_transporters",
        "MasterOfNetworks.write_transporters",
        "MasterOfNetworks.run_loop_transporters",
    ],
    literal_source_defects=[
        "cell-volume-based no-ECM environment update",
        "stoichiometric coefficient omitted in internal membrane buffer update",
        "subset cell-delta reindex by global mem_to_cells after current/material writes",
    ],
    repair=False,
    physical_conservation_credit=False,
)
write("validation/betse/" + NEW + "_join_source_map.json", mapping)

queue = {
    key: value
    for key, value in previous.items()
    if key
    not in {
        "owned",
        "owned_sha256",
        "protected_sha256",
        "prepared_inputs",
        "prepared_inputs_sha256",
        "static_receipt",
        "static_receipt_sha256",
        "static_checks",
        "reference_closure",
        "workfiles",
    }
}
queue.update(
    kind="cells.native_configured_transporter_execution_workqueue@1",
    status="implementation_ready_for_static_audits_no_transporter_numerics",
    notes=WORK + "BETSE_NORMAL_TRANSPORTER_JOIN_NOTES.md",
    runner=WORK + NEW + "_join_checks.py",
    binding_evidence=evidence,
    base_prior_protected_files=225,
    owned=[name.replace(OLD, NEW) for name in previous["owned"]],
    protected_sha256=previous["protected_sha256"] | previous["owned_sha256"],
    scientific_imports=0,
    numerical_runs=0,
    pytest_collection_runs=0,
    workfiles=[
        WORK + name
        for name in (
            NEW + "_join_checks.py",
            NEW + "_join_ast_audit.py",
            NEW + "_join_static_audit.py",
            "prepare_native_transporter_package.py",
            "prepare_native_transporter_checks.py",
            "prepare_native_transporter_evidence.py",
            "BETSE_NORMAL_TRANSPORTER_JOIN_NOTES.md",
        )
    ],
)
queue["owned_sha256"] = {name: sha(ROOT / name) for name in queue["owned"]}
write(WORK + NEW + "_join_workqueue.json", queue)

runner = (
    (ROOT / (WORK + OLD + "_join_checks.py"))
    .read_text()
    .replace(OLD, NEW)
    .replace("normal-molecule-join", "normal-transporter-join")
    .replace("CELLS_MOLECULE_JOIN_CPU", "CELLS_TRANSPORTER_JOIN_CPU")
)
runner = runner.replace(
    "cells.native_molecule_chemistry_transport_prepared@1",
    "cells.native_configured_transporter_execution_prepared@1",
)
runner = (
    runner.replace(
        "test_native_chemical_transport_and_conditional_reference",
        "test_native_configured_transporters_and_conditional_reference",
    )
    .replace("test_native_molecule_partial_failure", "test_native_transporter_partial_failure")
    .replace("test_complete_molecule_dependencies", "test_complete_transporter_dependencies")
)
runner = runner.replace('case != "transport_only"', 'case != "transporter_only"')
start = runner.index("        core = {")
end = runner.index('        for case in constants["CASES"]:', start)
runner = (
    runner[:start]
    + """        core = {"electrogenic_import", "electrogenic_export", "nkcc_multiplier_two", "ncx_multiplier_three", "ordered", "neutral_molecule"}
"""
    + runner[end:]
)
runner = (
    runner.replace("== 21\n", "== 25\n")
    .replace("== 17\n", "== 20\n")
    .replace("native_source_copies=38", "native_source_copies=42")
)
runner = runner.replace(
    'and row["conditional_pre_network_checks"] == 3',
    'and row["conditional_pre_network_checks"] == 3\n            and row["conditional_pre_transporter_checks"] == 3\n            and row["native_configured_transporter_calls"] == 3\n            and row["source_buffer_discrepancy_preserved"] is True\n            and row["source_bath_update_preserved"] is True',
)
needle = "        reports.append(dict(path=name, **row))\n"
assert runner.count(needle) == 2
runner = runner.replace(
    needle,
    """        for index in range(3):
            local = path.parent / ("pre-transporters-" + str(index))
            comp = json.loads((local / "comparison.json").read_text())
            if not (comp["actual_pre_transporter_only"] is True and comp["physical_global_conservation_credit"] is False and comp["fields"] and all(0 <= value["normalized_max_error"] <= (0.1 if key.startswith("reference/") else 1) for key, value in comp["fields"].items())):
                raise ValueError("Conditional transporter report failed: " + name)
            for level in (1, 2):
                answer = json.loads((local / ("reference-" + str(level) + ".json")).read_text())
                if not (answer["production_imports_denied"] and not answer["loaded_production_modules"] and answer["carried_reference_forms"] == 0 and answer["decimal_precision"] == (90 if level == 1 else 140)):
                    raise ValueError("Missing independent transporter reference form")
"""
    + needle,
    1,
)
runner = (
    runner.replace(
        'row["source_failure"]["type"] == "BetseSimUnstableException"',
        'row["source_failure"]["type"] == "IndexError"',
    )
    .replace('row["positive_chemistry_credit"]', 'row["positive_transporter_credit"]')
    .replace(
        'row["completed_transports"] == (0 if "first_molecule" in name else 1)',
        'row["completed_transporters"] == (0 if "first_subset" in name else 1)\n            and row["partial_current_and_material_preserved"] is True',
    )
)
runner = runner.replace(
    "genuine_molecule_mover=True,",
    "genuine_molecule_mover=True,\n                genuine_native_configured_transporter_execution=True,",
)
with (ROOT / (WORK + NEW + "_join_checks.py")).open("x") as stream:
    stream.write(runner)
print(
    json.dumps(
        dict(
            owned=len(queue["owned"]),
            protected=len(queue["protected_sha256"]),
            native_files=len(protocol["native_source"]["source_sha256"]),
            planned=protocol["planned"],
            scientific_imports=0,
            numerical_runs=0,
        )
    )
)
