# ruff: noqa: E501
"""Exclusive source-only runner adaptation; no scientific imports or evaluation."""

import ast
from pathlib import Path

root = Path("/home/robert/Cells")
old = (
    root / "agent-work/cells-worker-01/workfiles/betse_normal_ecm_catalog_join_checks_02.py"
).read_text()
old = old.replace("normal ECM field composition", "normal ECM event/noise composition")
old = old.replace("betse_normal_ecm_catalog_join", "betse_normal_ecm_event_join")
old = old.replace("normal-ecm-catalog-join", "normal-ecm-event-join")
old = old.replace("CELLS_ECM_CATALOG_CPU", "CELLS_ECM_EVENT_CPU")
old = old.replace(
    "cells.normal_ecm_calcium_join_prepared@1", "cells.normal_ecm_event_join_prepared@1"
)
start = old.index("        groups = {")
end = old.index('        stage = "final_snapshot_hashes"', start)
old = (
    old[:start]
    + """        groups = {name: [] for name in ("core", "global", "tissue", "controls", "raw", "dependencies")}
        required = {group: dict(positive={}, raw=[]) for group in groups}
        global_cases = {"salt_order", "temperature", "GJ_override", "NaK_shape"}
        tissue_cases = {"membrane_four", "ecmJ", "periodic", "sweep", "voltage_same_edge"}
        for case in constants["CASES"]:
            group = ("controls" if case in constants["COMPONENT_CONTROLS"] else
                     "global" if case in global_cases else "tissue" if case in tissue_cases else "core")
            groups[group].append(TEST + "::test_ecm_event_history[" + case + "]")
            required[group]["positive"]["isolated-" + case + "/comparison.json"] = dict(
                complete_native_ECM_events=True, complete_native_ECM_protein_noise=True,
                complete_calls=3, case_role="component_control" if group == "controls"
                else "new_ECM_event_catalog_noise_composition")
        for case in constants["RAW_CASES"]:
            groups["raw"].append(TEST + "::test_ecm_event_raw_partial[" + case + "]")
            required["raw"]["raw"].append("isolated-" + case + "/raw-retention.json")
        for case in constants["DEPENDENCIES"]:
            groups["dependencies"].append(TEST + "::test_ecm_event_dependencies[" + case + "]")
        ids = [node for group in groups.values() for node in group]
        assert len(ids) == len(set(ids)) == protocol["planned"]["checks"] == 42
        assert sum(len(row["positive"]) + len(row["raw"]) for row in required.values()) == 26
"""
    + old[end:]
)
start = old.index('        if not (\n            row["completed"] is True')
end = old.index('        case = path.parent.name.removeprefix("isolated-")', start)
old = (
    old[:start]
    + """        if not (
            row["completed"] is True and row["exact_native"] is True
            and row["complete_calls"] == 3
            and row["cold_reference_forms"] == row["bootstrap_reference_forms"] == 2
            and all(row["conditional_" + ("event" if name == "events" else "channel" if name == "channels" else name) + "_reference_forms"] == 6
                    for name in ("events", "material", "calcium", "channels", "network", "noise", "field"))
            and row["carried_reference_forms"] == 0
            and row["complete_native_ECM_events"] is True
            and row["complete_native_ECM_protein_noise"] is True
            and row["actual_persistent_coefficient_owner"] is True
            and row["actual_normal_source_clock"] is True
            and row["source_ER_disabled"] is True
            and row["retained_material_panel_accepted"] is False
            and row["retained_material_checks_passed"] == 39
            and row["retained_material_checks_total"] == 40
            and row["physical_global_conservation_credit"] is False
            and row["native_initializer_or_mesh_claim"] is False
            and row["independent_trajectory"] is False
            and all(row[k] == v for k,v in required["positive"][name].items())
        ):
            raise ValueError("Invalid full normal ECM event/noise history report")
"""
    + old[end:]
)
old = old.replace(
    'for mode in ("material", "calcium", "channels", "network", "field"):',
    'for mode in ("events", "material", "calcium", "channels", "network", "noise", "field"):',
)
old = old.replace(
    'if mode in ("field", "material", "calcium", "channels")',
    'if mode in ("events", "field", "material", "calcium", "channels", "noise")',
)
start = old.index('            and row["strict_finite_guard_distinct_from_native_exception"]')
end = old.index(
    '        ):\n            raise ValueError("Invalid field-join raw limit report")', start
)
old = (
    old[:start]
    + """            and row["strict_port_guard_distinct_from_native_exception"]
            == (case in ("negative_Dm_source_return", "protein_noise_large_limit", "late_negative_temperature"))
            and 0 <= row["completed_calls"] < 3
            and row["port_stage"] == "event_material_network_noise_field"
"""
    + old[end:]
)
old = old.replace(
    "conditional_material_calcium_network_field_only=True,",
    "conditional_event_material_calcium_network_noise_field_only=True,",
)
old = old.replace(
    "native_ECM_CaATP_executed=True,",
    "native_ECM_CaATP_executed=True,\n                native_events_and_protein_noise_executed=True,",
)
with (root / "agent-work/cells-worker-01/workfiles/betse_normal_ecm_event_join_checks.py").open(
    "x"
) as stream:
    stream.write(ast.unparse(ast.parse(old)) + "\n")
