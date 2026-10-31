# ruff: noqa: E501
"""Build isolated domain04 orchestration from unchanged calcium03 stdlib driver."""

from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_calcium_domain04"
OLD = Path("/mnt/workspaces/Cells/betse-normal-ecm-calcium-join-prepared-20261031-03/driver.py")
text = OLD.read_text()
text = text.replace(
    '"""Freeze the static full normal ECM field composition package.\n\nRun bounded groups only in a newly requested round.\n"""',
    '"""Freeze exact-input calcium domain04; runs require a separate requested round."""',
)
text = text.replace("betse_normal_ecm_calcium_join_source_map.json", PREFIX + "_source_map.json")
text = text.replace("betse_normal_ecm_calcium_join_protocol.json", PREFIX + "_protocol.json")
text = text.replace("betse_normal_ecm_calcium_join_workqueue.json", PREFIX + "_workqueue.json")
text = text.replace("test_betse_normal_ecm_calcium_join.py", "test_" + PREFIX + ".py")
start = text.index("        tree = ast.parse(")
end = text.index('        stage = "final_snapshot_hashes"', start)
text = text[:start] + "        groups, required = plan(source, protocol)\n" + text[end:]
start = text.index("        for path, expected in hashes.items():")
end = text.index('        (out / "driver.py")', start)
text = (
    text[:start]
    + """        controlled = queue["owned_sha256"] | queue["protected_sha256"]
        for path, expected in controlled.items():
            if sha(ROOT / path) != expected or hashes[path] != expected:
                raise ValueError("Controlled dependency changed during freeze: " + path)
"""
    + text[end:]
)
text = text.replace(
    'kind="cells.normal_ecm_calcium_join_prepared@1"',
    'kind="cells.normal_ecm_calcium_domain04_prepared@1"',
)
text = text.replace(
    "                native_source_copies=44,",
    """                native_source_copies=2 * len(native["source_sha256"]),
                retained_failure_artifact_copies=len(queue["retained_failure_artifacts"]),
                retained_failure_artifacts=queue["retained_failure_artifacts"],
                snapshot_only_unloaded_paths=sorted(set(hashes) - set(controlled)),
                snapshot_only_unloaded_paths_are_not_adopted_dependencies=True,
                scientific_qualification_passes=0,
                qualification_scientific_passes_retained=0,
                original_campaign_still_failed=True,
                historical_negative_genes_owned_hot_credit=0,
                historical_generated_uncompared_constructor_forms=4,
                classification_only_no_scientific_core_changes=True,""",
)
marker = '        stage = "static_test_and_report_plan"'
assert text.count(marker) == 1
text = text.replace(
    marker,
    """        for relative, row in queue["retained_failure_artifacts"].items():
            data = Path(row["path"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise ValueError("Retained failure evidence changed: " + relative)
            target = out / "native-inputs/retained-failure" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            copies[str(target.relative_to(out))] = row["sha256"]
"""
    + marker,
)
text = text.replace(
    "    out.mkdir(exist_ok=False)",
    """    for row in queue["freeze_prerequisites"].values():
        if sha(row["path"]) != row["sha256"]:
            raise ValueError("Changed required source/failure review")
    out.mkdir(exist_ok=False)""",
    1,
)
marker = "\ndef prepare(out):"
plan = """
def plan(source, protocol):
    tree = ast.parse((source / "validation/betse/betse_normal_ecm_calcium_domain04_fixtures.py").read_text())
    keys = {"CASES", "COMPONENT_CONTROLS", "RAW_CASES", "RAW_DOMAIN_CASES", "DEPENDENCIES"}
    constants = {
        target.id: ast.literal_eval(node.value)
        for node in tree.body if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name) and target.id in keys
    }
    groups = {name: [] for name in ("core", "context", "controls", "raw", "raw_domain", "dependencies")}
    required = {group: dict(positive={}, raw=[], raw_domain=[]) for group in groups}
    core = {"active", "polarized", "fast_duplicate", "rectangular"}
    for case in constants["CASES"]:
        group = "controls" if case in constants["COMPONENT_CONTROLS"] else "core" if case in core else "context"
        groups[group].append(TEST + "::test_calcium_domain04_positive[" + case + "]")
        required[group]["positive"]["isolated-" + case + "/comparison.json"] = dict(
            complete_native_ECM_CaATP=True,
            case_role="component_control" if group == "controls" else "new_ECM_CaATP_field_case",
        )
    for case in constants["RAW_CASES"]:
        groups["raw"].append(TEST + "::test_calcium_domain04_raw[" + case + "]")
        required["raw"]["raw"].append("isolated-" + case + "/raw-retention.json")
    for case in constants["RAW_DOMAIN_CASES"]:
        groups["raw_domain"].append(TEST + "::test_calcium_domain04_observed_history[" + case + "]")
        required["raw_domain"]["raw_domain"].append("isolated-" + case + "/raw-domain-retention.json")
    for case in constants["DEPENDENCIES"]:
        groups["dependencies"].append(TEST + "::test_calcium_domain04_dependencies[" + case + "]")
    ids = [node for group in groups.values() for node in group]
    assert len(ids) == len(set(ids)) == protocol["planned"]["checks"] == 34
    assert sum(len(row["positive"]) + len(row["raw"]) + len(row["raw_domain"]) for row in required.values()) == 22
    assert {k: len(v) for k, v in groups.items()} == dict(core=4, context=7, controls=4, raw=6, raw_domain=1, dependencies=12)
    return groups, required

"""
text = text.replace(marker, "\n" + plan + marker, 1)
# The unchanged positive/raw/dependency reader is retained; add the distinct raw-history schema.
marker = '    if group == "dependencies":'
assert text.count(marker) == 1
text = text.replace(
    marker,
    """    domains = {str(p.relative_to(base)): p for p in base.glob("isolated-*/raw-domain-retention.json")}
    if set(domains) != set(required["raw_domain"]):
        raise ValueError("Exact observed raw-domain set differs")
    for name, path in sorted(domains.items()):
        row = json.loads(path.read_text())
        expected = dict(
            positive_credit=False, case_id="negative_genes",
            input_sha256="41d5da23526aac015a219e2c7d535998c7181fc40520d5ef1a967034af808606",
            input_retained_exactly=True, context="negatively_charged_gene_products",
            native_completed_calls=2, port_completed_calls=2, native_history_records=3,
            first_nonfinite_frame=4, first_nonfinite_stage="junction_flux", first_nonfinite_ion="Na",
            first_nonfinite_membrane_occurrences=[7, 8], native_stop="GRN_X_transport_no_negs_NaN",
            port_stop="existing_CaATP_finite_guard", distinct_native_port_stops=True,
            calcium_specific_cause_claim=False, cold_reference_forms=2, bootstrap_reference_forms=2,
            completed_prefix_reference_forms=16, failed_native_chemistry_reference_forms=2,
            total_fresh_reference_forms=22, carried_reference_forms=0,
            full_native_and_port_partials_retained=True, source_ER_disabled=True,
            native_full_history_accepted=False, physical_global_conservation_credit=False,
            dt_rates_coefficients_or_guards_changed=False,
        )
        if set(row) != set(expected) or any(type(row[k]) is not type(v) or row[k] != v for k, v in expected.items()):
            raise ValueError("Invalid observed raw-domain source/owned endpoints or credit")
        prep = base / "preparation-negative_genes"
        if sha(prep / "inputs-before-constructor.json") != expected["input_sha256"]:
            raise ValueError("Observed raw-domain input bytes changed")
        reference(prep / "cold", "cold")
        reference(prep / "bootstrap", "field")
        for index in range(2):
            for mode in ("material", "calcium", "network", "field"):
                reference(prep / ("point-" + str(index)) / mode, mode)
        folder = prep / "failed-third-chemistry"
        reference(folder, "network_chemistry_prefix")
        for level in (1, 2):
            form = json.loads((folder / ("reference-" + str(level) + ".json")).read_text())
            if not (form["mode"] == "network_chemistry_prefix" and form["transport_evaluations"] == 0
                    and form["complete_network_return_predicted"] is False):
                raise ValueError("Failed-step chemistry scope expanded")
        for relative in (
            "isolated-negative_genes/native", "negative_genes-domain-original-input",
            "negative_genes-domain-cold-return", "negative_genes-domain-bootstrap-return",
            "negative_genes-domain-complete-return-0", "negative_genes-domain-complete-return-1",
            "negative_genes-domain-native-before-failed-chemistry", "negative_genes-domain-complete-third-refusal",
        ):
            archive = base / relative
            manifest = json.loads((archive / "manifest.json").read_text())
            if not (manifest["kind"] == "cells.betse_normal_current_raw_evidence@1"
                    and manifest["complete"] is True and set(manifest["files"]) == {"arrays.npz", "data.json"}):
                raise ValueError("Incomplete typed raw-domain evidence")
            for filename, digest in manifest["files"].items():
                if sha(archive / filename) != digest:
                    raise ValueError("Typed raw-domain evidence changed")
        reports.append(dict(path=name, **row))
"""
    + marker,
    1,
)
text = text.replace("CELLS_ECM_CALCIUM_CPU=str(cpu)", "CELLS_ECM_CALCIUM_DOMAIN04_CPU=str(cpu)")
start = text.index("                conditional_material_calcium_network_field_only=True,")
end = text.index("                automatic_followup=False,", start)
text = (
    text[:start]
    + """                classification_only_no_scientific_core_changes=True,
                positive_history_credit=len(inputs["required_reports"][group]["positive"]),
                observed_raw_domain_credit=0,
                raw_domain_contract_passed=group == "raw_domain",
                original_campaign_still_failed=True,
                original_failed_negative_genes_hot_credit=0,
                carried_reference_forms=0,
                conditional_material_calcium_network_field_only=True,
                source_ER_disabled=True,
                retained_ECM_material_panel_accepted=False,
                full_native_normal_solver_executed=False,
                file_persistence_credit=False,
                native_full_initialization_parity=False,
                physical_global_conservation_credit=False,
"""
    + text[end:]
)
text = text.replace('name + ".json"', 'name + Path(row["path"]).suffix')
target = WORK / (PREFIX + "_checks.py")
with target.open("x") as stream:
    stream.write(text)
print(target)
