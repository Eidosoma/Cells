# ruff: noqa: E501
"""Emit tests from frozen ECM checks plus independent charged-cold accounting."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")
OLD, NEW = "betse_ecm_grn", "betse_ecm_charged_grn"
text = (ROOT / f"tests/unit/test_{OLD}_join.py").read_text().replace(OLD, NEW)
text = text.replace('"ecm-grn"', '"ecm-charged-grn"').replace(
    "CELLS_ECM_GRN_CPU", "CELLS_ECM_CHARGED_GRN_CPU"
)
text = text.replace("def test_ecm_grn_", "def test_ecm_charged_grn_")
text = text.replace(
    "from validation.betse import " + NEW + "_native as native",
    "from validation.betse import " + NEW + "_native as native\n"
    "from validation.betse import " + NEW + "_reference as reference",
)


def original(name):
    return next(
        ast.get_source_segment(text, n)
        for n in ast.parse(text).body
        if isinstance(n, ast.FunctionDef) and n.name == name
    )


configuration = original("compare_cold")
tree = ast.parse(configuration).body[0]
tree.name = "compare_configuration"
tree.body = [
    n
    for n in tree.body
    if not (isinstance(n, ast.For) and ast.unparse(n.iter) == "target['simulator_fields'].items()")
]
text = text.replace(configuration, ast.unparse(tree), 1)
helper = """

def compensation_comparisons(raw, inputs, lower, target):
    rows, add = comparisons()
    n, m, e = inputs["cells"], inputs["membranes"], inputs["environment_sites"]
    factor = 128 * np.finfo(float).eps * (len(inputs["ion_ids"]) + n + m + e + 64)
    assert raw["core_fields"]["charge_has_been_balanced"] is target["charge_has_been_balanced"]
    assert [(event["stage"], event["tag"]) for event in raw["balance_events"]] == [
        (event["stage"], event["tag"]) for event in target["balance_stages"]]
    for actual, expected in zip(raw["balance_events"], target["balance_stages"], strict=True):
        assert actual["Q"] == expected["Q"]
        assert actual["charge_has_been_balanced"] is False
        assert actual["substances_affect_charge"] is True
    for key, value in target["ionic_state"].items():
        before = np.asarray(inputs["ionic_state"][key])
        wanted = np.asarray(value)
        add("ionic/"+key, raw["ionic_state"][key], wanted, lower["ionic_state"][key],
            3e-13 + factor * (abs(before)+abs(wanted)), "mol/m3")
    np.testing.assert_array_equal(raw["ionic_state"]["cc_at_mem"], inputs["ionic_state"]["cc_at_mem"])
    wanted = np.asarray(target["ion_boundary_state"])
    add("ion_boundary", raw["ion_boundary_state"], wanted, lower["ion_boundary_state"],
        3e-13 + factor*(abs(wanted)+abs(np.asarray(inputs["network"]["initial_ion_boundary"]))), "mol/m3")
    assert set(raw["simulator_fields"]) == set(target["simulator_fields"])
    for key, wanted in target["simulator_fields"].items():
        rho = "rho" in key
        gross_q = max(target["source_Q_gross_mM"].values()) if rho else 0.0
        add("simulator/"+key, raw["simulator_fields"][key], wanted, lower["simulator_fields"][key],
            (1e-25 if rho else 1e-30) + factor * inputs["F"] * gross_q, "C/m3" if rho else "A/m2")
    declaration = inputs["material_declaration"]["environment_geometry_definition"]
    independent = reference.derive_geometry(declaration, precision=160)
    volumes = np.asarray(inputs["cell_volume_m3"])
    site_volume = declaration["parameters"]["cell_height_m"] * independent["delta_m"]**2
    true_volume = np.asarray(independent["true_environment_volume_m3"])
    for index, species in enumerate(inputs["ion_ids"]):
        def count(state, index=index):
            return dict(cell=np.sum(np.asarray(state["cc_cells"][index])*volumes),
                source_effective_environment=np.sum(state["cc_env"][index])*site_volume,
                native_true_volume_diagnostic=np.sum(np.asarray(state["cc_env"][index])*true_volume))
        first, last = count(inputs["ionic_state"]), count(raw["ionic_state"])
        for kind, value in last.items():
            measure = sum(volumes) if kind == "cell" else e*site_volume if kind == "source_effective_environment" else sum(abs(true_volume))
            budget = factor*target["ionic_count_gross_mol"][species][kind] + 3e-13*measure
            add("count/"+species+"/"+kind, value, target["ionic_count_after_mol"][species][kind],
                lower["ionic_count_after_mol"][species][kind], budget, "mol; source or diagnostic")
            add("count_change/"+species+"/"+kind, value-first[kind], target["ionic_count_change_mol"][species][kind],
                lower["ionic_count_change_mol"][species][kind], budget, "mol; counterion sink")
    for name, predicted in target["gene_count_mol"].items():
        fields = raw["molecule_fields"][name]
        actual = dict(cell=np.sum(np.asarray(fields["c_cells"])*volumes),
            source_effective_environment=np.sum(fields["c_env"])*site_volume,
            native_true_volume_diagnostic=np.sum(np.asarray(fields["c_env"])*true_volume))
        for kind, value in actual.items():
            measure = sum(volumes) if kind == "cell" else e*site_volume if kind == "source_effective_environment" else sum(abs(true_volume))
            add("gene_count/"+name+"/"+kind, value, predicted[kind], lower["gene_count_mol"][name][kind],
                2*factor*abs(predicted[kind]) + 3e-13*measure, "mol; raw amount, no scale factor")
    z = np.asarray(inputs["valence"])[:,None]
    for region, key in (("cell", "cc_cells"),("env", "cc_env")):
        before, actual = np.asarray(inputs["ionic_state"][key]), np.asarray(raw["ionic_state"][key])
        delta = inputs["F"]*np.sum(z*(actual-before), axis=0)
        # Predicted after-state and immutable before-state determine the gross.
        gross = inputs["F"]*np.sum(abs(z)*(abs(np.asarray(target["ionic_state"][key]))+abs(before)), axis=0)
        formal = inputs["F"]*target["formal_gene_charge_mM"][region]
        for suffix, value in (("_ionic_charge_change_C_m3", delta), ("_ionic_plus_formal_change_C_m3", delta+formal)):
            ledger_key = region+suffix
            add("charge/"+ledger_key, value, target["charge_ledger"][ledger_key], lower["charge_ledger"][ledger_key],
                factor*(gross+abs(formal))+1e-25, "C/m3; source compensation only")
    return rows


def compare_cold(binding, parent, inputs, lower, target):
    rows = compare_configuration(binding, parent, lower, target)
    rows.update(compensation_comparisons(parent.network_cache["wire"], inputs, lower, target))
    return rows

"""
point = text.index("\ndef compare_local(")
text = text[:point] + helper + text[point:]
start = text.index('    ids = inputs["definition"]', text.index("def test_ecm_charged_grn_history"))
end = text.index("    cold = references(", start)
text = text[:start] + "    cold_inputs = reference.cold_inputs(inputs)\n" + text[end:]
text = text.replace(
    "compare_cold(binding, parent, cold[0], cold[1])",
    "compare_cold(binding, parent, cold_inputs, cold[0], cold[1])",
    1,
)
text = text.replace(
    '    old.exact_nested(parent.network_cache, captured["cold_cache"])',
    """    old.exact_nested(parent.network_cache, captured["cold_cache"])
    old.exact_nested(parent.material.values._asdict(), captured["compensated_parent"])
    assert parent.material.step_index == 0
    for key, value in parent.material.values._asdict().items():
        if key not in {"cell_mol_m3", "environment_mol_m3"}:
            np.testing.assert_array_equal(value, inputs["initial"][key])
    if case == "negative_threshold_gap":
        assert cold[1]["actions"]["cell"]["action"] == "negative_threshold_gap"
    if case == "scheduled_boundary":
        assert [step["boundary_override"] for step in inputs["steps"]] == [False,True,False]""",
    1,
)
text = text.replace(
    "                genuine_ecm_grn=True,",
    """                genuine_ecm_grn=True,
                charged_cold_compensation_checked=True,
                compensated_parent_handoff_exact=True,
                original_E_grid_and_M_membrane_shapes=True,
                boundary_carry_and_explicit_override=True,
                independent_cold_counts_and_charge=True,
                source_compensation_is_not_physical_conservation=True,""",
    1,
)

# Add independent ionic alias checks to the established molecular warm budgets.
text = text.replace(
    "def compare_local(feedback, lower, target):",
    "def compare_molecular_local(feedback, lower, target):",
    1,
)
point = text.index('\n\n@pytest.mark.parametrize("case", fixtures.CASES)')
text = (
    text[:point]
    + """

def compare_local(feedback, lower, target):
    rows = compare_molecular_local(feedback, lower, target)
    before = feedback["before"]
    actual = feedback["cache_after"]["wire"]
    source = before["values_before"]
    owner = np.asarray(before["molecular_geometry"]["owner"], np.int64)
    ionic = dict(cc_cells=np.asarray(source["cell_mol_m3"]),
        cc_at_mem=np.asarray(source["cell_mol_m3"])[:,owner],
        cc_env=np.asarray(source["environment_mol_m3"]))
    extra, add = comparisons()
    for key, wanted in ionic.items():
        add("ionic_alias/"+key, actual["ionic_state"][key], wanted, wanted,
            3e-13+6e-12*abs(wanted), "mol/m3; actual pre-network conditional")
    # Warm dispatch never repeats tissue_init or compensation.
    old.exact_nested(actual["balance_events"], before["cache_before"]["wire"]["balance_events"])
    assert actual["core_fields"]["charge_has_been_balanced"] is before["cache_before"]["wire"]["core_fields"]["charge_has_been_balanced"]
    rows.update(extra)
    return rows
"""
    + text[point:]
)

raw = original("test_ecm_charged_grn_partial_failure")
start = text.index('@pytest.mark.parametrize("case", fixtures.RAW_CASES)')
end = text.index('\n\n@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)', start)
text = (
    text[:start]
    + """@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_ecm_charged_grn_partial_failure(tmp_path, case):
    inputs = fixtures.raw_fixture(case)
    archive(tmp_path, case+"-inputs", inputs)
    prep = root(tmp_path)/("preparation-"+case)
    prep.mkdir(parents=True, exist_ok=False)
    before = reference.cold_inputs(inputs)
    answers = references(prep/"cold", before)
    folder, captured = isolated(tmp_path, inputs)
    assert captured["status"] == "source_refused" and not captured["history"]
    assert captured["failure"]["type"] == "BetseSimConfException"
    assert answers[1]["failure_case"] == case
    try:
        binding = joined.bind(inputs)
        joined.initialize(binding)
    except joined.ECMNetworkRejected as error:
        archive(tmp_path, case+"-partial", dict(partial=error.partial, error=str(error), traceback=traceback.format_exc()))
        leaf = error
        while leaf.__cause__ is not None:
            leaf = leaf.__cause__
        assert type(leaf).__name__ == "BetseSimConfException" and str(leaf) == captured["failure"]["message"]
        assert error.partial["stage"] == "cold"
        old.exact_nested(error.partial["cache"], captured["cold_failure"])
        old.exact_nested(error.partial["partial_material"], captured["cold_partial_material"])
        check(tmp_path, case+"-cold-errors", prep/"cold",
            compensation_comparisons(error.partial["cache"]["wire"], before, answers[0], answers[1]))
        if case.startswith("env_"):
            assert [(event["stage"],event["tag"]) for event in captured["cold_failure"]["wire"]["balance_events"]] == [("before","cell"),("after","cell"),("before","env")]
            assert len(captured["cold_failure"]["wire"]["ionic_state"]["cc_env"][0]) == 12
            assert len(captured["cold_failure"]["wire"]["ionic_state"]["cc_at_mem"][0]) == 9
    except Exception as error:
        archive(tmp_path, case+"-unexpected-refusal", dict(error=str(error),traceback=traceback.format_exc()))
        raise
    else:
        raise AssertionError("Intended source cold capacity refusal was not reached")
    (folder/"raw-retention.json").write_text(json.dumps(dict(source_refused=True,
        source_type="BetseSimConfException", cold_initialization_failure=True,
        exact_native_partial=True, complete_ionic_boundary_cache_and_publication=True,
        cell_before_environment=True, independent_cold_reference_forms=2,
        source_compensation_is_not_physical_conservation=True,
        positive_credit=False, physical_conservation_credit=False), indent=2)+"\\n")
"""
    + text[end:]
)
start = text.index('@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)')
end = text.index('\n\n@pytest.fixture(scope="module", autouse=True)', start)
text = (
    text[:start]
    + """@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_ecm_charged_grn_dependencies(tmp_path, dependency):
    inputs = fixtures.fixture("rectangular" if dependency == "wrong_environment_shape" else "positive")
    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(binding)
    except Exception as error:
        archive(tmp_path, dependency+"-unexpected-valid-admission", dict(error=str(error),
            traceback=traceback.format_exc(),partial=getattr(error,"partial",None)))
        raise
    archive(tmp_path, dependency+"-valid-admission", dict(binding=binding,parent=parent))
    messages = dict(
        wrong_owner="Require a complete genuine ECM GRN declaration",
        missing_M="Require actual Na(+1), K(+1), M(-1) counterion rows",
        wrong_M_valence="Require actual Na(+1), K(+1), M(-1) counterion rows",
        moving_M="Declare the compensation M row stationary",
        mitochondria="ECM GRN mitochondria/fluid/cuts/standalone require separate state",
        fluid="ECM network fluid coupling requires separate state",
        missing_cache="Require complete ECM GRN owner cache",
        missing_ionic_cache="Require complete ECM charged ionic snapshot",
        missing_balance_events="Require ECM charged compensation observations",
        wrong_environment_shape="Require original E-grid and M-membrane ionic cache shapes",
        missing_default="Missing source-initialized ECM gene fields",
        missing_coefficients="Require owned ECM molecular grid coefficients",
        prepared_mapping="Require owned in-grid TJ indices")
    cache_controls = {"missing_cache","missing_ionic_cache","missing_balance_events",
        "wrong_environment_shape","missing_default","missing_coefficients"}
    if dependency in cache_controls:
        raw = ions.data(parent.network_cache)
        if dependency == "missing_cache": raw["kind"] = "missing"
        elif dependency == "missing_ionic_cache": del raw["wire"]["ionic_state"]
        elif dependency == "missing_balance_events": del raw["wire"]["balance_events"]
        elif dependency == "wrong_environment_shape": raw["wire"]["ionic_state"]["cc_env"] = [row[:9] for row in raw["wire"]["ionic_state"]["cc_env"]]
        elif dependency == "missing_default": del raw["wire"]["molecule_fields"]["X"]["Dm"]
        else: del raw["coefficient_fields"]["D_env_weight"]
        changed = joined._state(binding,parent.material,raw,parent.controls)
        with pytest.raises(joined.ECMNetworkRejected) as caught:
            joined.advance(binding,changed)
    else:
        changed = copy.deepcopy(inputs)
        ions_definition = changed["definition"]["environment_geometry_definition"]["current_definition"]["ions"]
        if dependency == "wrong_owner": changed["network"]["owner"] = "molecules"
        elif dependency == "missing_M": ions_definition["ids"][-1] = "anion"
        elif dependency == "wrong_M_valence": ions_definition["valence"][-1] = 1.0
        elif dependency == "moving_M": changed["definition"]["ions"]["moving_ids"].append("M")
        elif dependency == "mitochondria": changed["network"]["scope"]["mitochondria"] = True
        elif dependency == "fluid": changed["definition"]["parameters"]["fluid_flow"] = True
        else: changed["network"]["grid_index_groups"]["all_bound_mem_inds"] = [999]
        archive(tmp_path,dependency+"-inputs",changed)
        with pytest.raises(ValueError) as caught:
            joined.bind(changed)
    leaf = caught.value
    while leaf.__cause__ is not None: leaf = leaf.__cause__
    archive(tmp_path,dependency+"-refusal",dict(type=type(leaf).__name__,message=str(leaf)))
    assert type(leaf) is ValueError and str(leaf) == messages[dependency]
    (root(tmp_path)/("dependency-"+dependency+".json")).write_text(json.dumps(dict(
        baseline_admitted=True,intended_failure_reached=True,actual_leaf_type="ValueError",
        expected_message=messages[dependency],actual_message=str(leaf),source_failure_credit=False),indent=2)+"\\n")
"""
    + text[end:]
)
with (ROOT / f"tests/unit/test_{NEW}_join.py").open("x") as stream:
    stream.write(text)
print(
    "Emitted18 three-call histories,4 raw capacity checks and13 precise dependency checks; not collected"
)
