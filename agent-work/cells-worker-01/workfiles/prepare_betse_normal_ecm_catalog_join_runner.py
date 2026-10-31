# ruff: noqa: E501
"""Adapt the existing durable bounded runner; no launch or test collection."""

from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
text = (WORK / "betse_normal_ecm_calcium_join_checks.py").read_text()
text = text.replace("betse_normal_ecm_calcium_join", "betse_normal_ecm_catalog_join")
text = text.replace("normal-ecm-calcium-join", "normal-ecm-catalog-join")
text = text.replace("CELLS_ECM_CALCIUM_CPU", "CELLS_ECM_CATALOG_CPU")
text = text.replace(
    '{"CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES"}',
    '{"CASES", "CLASSES", "FAMILIES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES"}',
)
text = text.replace(
    '("core", "context", "controls", "raw", "dependencies")',
    '("catalog_Na","catalog_K","catalog_Cl","catalog_Ca","catalog_Fun","catalog_Cat","catalog_ML","core", "context", "controls", "raw", "dependencies")',
)
text = text.replace(
    'core = {"active", "polarized", "negative_genes", "fast_duplicate", "rectangular"}',
    'core = {"mixed_forward", "mixed_reverse", "fast_duplicate", "rectangular", "profile_duplicate"}',
)
mark = (
    """            groups[group].append(TEST + "::test_ecm_calcium_field_history[" + case + "]")"""
)
assert mark in text
text = text.replace(
    mark,
    """            if case in constants["CLASSES"]:
                group="catalog_"+constants["FAMILIES"][case]
            groups[group].append(TEST + "::test_ecm_catalog_history[" + case + "]")""",
)
text = text.replace(
    "complete_native_ECM_CaATP=True,",
    'complete_native_ECM_modern_catalog=True,\n                complete_calls=1 if case in constants["CLASSES"] else 3,',
)
text = text.replace('"new_ECM_CaATP_field_case"', '"new_ECM_modern_catalog_composition"')
text = text.replace("test_ecm_calcium_raw_partial[", "test_ecm_catalog_raw_partial[").replace(
    "test_ecm_calcium_dependencies[", "test_ecm_catalog_dependencies["
)
text = text.replace("== 34", "== 94").replace("== 22", "== 78")
text = text.replace(
    "native_source_copies=44,", 'native_source_copies=2*len(native["source_sha256"]),'
)
text = text.replace(
    '("field", "material", "calcium")', '("field", "material", "calcium", "channels")'
)
text = text.replace(
    'row["complete_calls"] == 3',
    'row["complete_calls"] == required["positive"][name]["complete_calls"]',
)
text = text.replace(
    'row["conditional_" + name + "_reference_forms"] == 6',
    'row["conditional_" + name + "_reference_forms"] == 2*row["complete_calls"]',
)
text = text.replace(
    '("material", "calcium", "network", "field")',
    '("material", "calcium", "channels", "network", "field")',
)
text = text.replace(
    "        for index in range(3):", '        for index in range(row["complete_calls"]):'
)
text = text.replace(
    '(case not in ("first_gene_negative", "second_gene_negative"))',
    '("literal_pole" in case or "overflow" in case)',
)
text = text.replace('(2 if case == "late_CaATP_underflow" else 0)', "0")
# Preserve strict source/live hashes, exact ID sets, frozen reports, pre/post guards,
# full BaseException failure records and no automatic retry from the existing runner.
(WORK / "betse_normal_ecm_catalog_join_checks.py").write_text(text)
receipt = (WORK / "betse_normal_ecm_calcium_join_receipt.py").read_text()
receipt = receipt.replace("ecm_calcium", "ecm_catalog").replace(
    "betse_normal_ecm_calcium_join", "betse_normal_ecm_catalog_join"
)
(WORK / "betse_normal_ecm_catalog_join_receipt.py").write_text(receipt)
print("Prepared twelve bounded groups and separate receipt script; no run action invoked")
