# ruff: noqa: E501 -- emitted source templates; final files are formatted separately.
"""Emit static charged checks, retaining the established normal-call comparisons."""

from pathlib import Path

ROOT = Path("/home/robert/Cells")
old = (ROOT / "tests/unit/test_betse_normal_grn_join.py").read_text()
text = old.replace("betse_normal_grn", "betse_normal_charged_grn")
text = text.replace("normal-grn-join", "normal-charged-grn-join")
text = text.replace("CELLS_GRN_JOIN_CPU", "CELLS_CHARGED_GRN_JOIN_CPU")
text = text.replace(
    "test_genuine_grn_owner_and_conditional_reference",
    "test_charged_grn_owner_and_conditional_reference",
)
text = text.replace("test_genuine_grn_partial_failure", "test_charged_grn_partial_failure")
text = text.replace("test_complete_grn_dependencies", "test_complete_charged_grn_dependencies")
start, end = (
    text.index("def cold_comparisons("),
    text.index('@pytest.mark.parametrize("case", fixtures.CASES)'),
)
text = (
    text[:start]
    + """def cold_inputs(inputs):
    ion = inputs["ion_definition"]
    initial = inputs["initial"]
    return dict(
        mode="cold_initialization", network=inputs["channel_definition"]["network"],
        ion_ids=ion["ions"]["ids"], valence=ion["ions"]["valence"],
        cells=len(initial["cell_mol_m3"][0]), membranes=len(initial["voltage_V"]),
        ionic_state={target: initial[source] for target, source in (
            ("cc_cells", "cell_mol_m3"), ("cc_at_mem", "membrane_mol_m3"),
            ("cc_env", "bath_mol_m3"))},
        F=ion["parameters"]["F_C_mol"],
        cell_volume_m3=ion["geometry"]["cell_volume_m3"],
        bath_volume_m3=ion["parameters"]["bath_volume_m3"],
    )


def cold_comparisons(raw, inputs, lower, target):
    rows, errors, budgets = {}, {}, {}
    eps = np.finfo(float).eps
    factor = 128 * eps * (len(inputs["ion_ids"]) + inputs["cells"] + inputs["membranes"] + 64)

    def add(name, actual, expected, less, budget, unit):
        a, b = np.asarray(actual, np.float64), np.asarray(expected, np.float64)
        budget = np.broadcast_to(budget, a.shape)
        rows[name] = old.metric(a, b, budget) | dict(unit=unit)
        rows["reference/" + name] = old.metric(less, b, budget) | dict(unit=unit)
        errors[name], budgets[name] = abs(a - b), budget

    assert raw["core_fields"]["charge_has_been_balanced"] is target["charge_has_been_balanced"]
    assert [(e["stage"], e["tag"]) for e in raw["balance_events"]] == [(e["stage"], e["tag"]) for e in target["balance_stages"]]
    for actual, expected in zip(raw["balance_events"], target["balance_stages"], strict=True):
        assert actual["Q"] == expected["Q"]
        assert actual["charge_has_been_balanced"] is False
        assert actual["substances_affect_charge"] is True
    if target["failure_case"] is None:
        assert dict(raw["owner_fields"]) == target["owner_fields"]
        for name, fields in target["molecule_fields"].items():
            actual = raw["molecule_fields"][name]
            for key, wanted in fields.items():
                if wanted is None or type(wanted) is bool:
                    assert actual[key] is wanted
                else:
                    np.testing.assert_array_equal(actual[key], wanted)
                    np.testing.assert_array_equal(lower["molecule_fields"][name][key], wanted)
                    add(name + "/" + key, actual[key], wanted, lower["molecule_fields"][name][key], FLOORS["cell_mol_m3"], "source field")
        wanted = np.asarray(target["reaction_matrix"])
        add("reaction_matrix", raw["core_fields"]["reaction_matrix"], wanted, lower["reaction_matrix"], 1e-25, "stoichiometry")
    for key, wanted in target["ionic_state"].items():
        initial = np.asarray(inputs["ionic_state"][key])
        expected = np.asarray(wanted)
        add("ionic/" + key, raw["ionic_state"][key], expected, lower["ionic_state"][key], FLOORS["cell_mol_m3"] + factor * (abs(initial) + abs(expected)), "mol/m3")
    np.testing.assert_array_equal(raw["ionic_state"]["cc_at_mem"], inputs["ionic_state"]["cc_at_mem"])
    wanted = np.asarray(target["ion_boundary_state"])
    add("ion_boundary", raw["ion_boundary_state"], wanted, lower["ion_boundary_state"], FLOORS["bath_mol_m3"] + factor * (abs(wanted) + abs(np.asarray(inputs["network"]["ion_boundary_mM"]))), "mol/m3")
    assert set(raw["simulator_fields"]) == set(target["simulator_fields"])
    gross_q = max(target["source_Q_gross_mM"].values())
    for key, wanted in target["simulator_fields"].items():
        budget = 1e-25 + factor * inputs["F"] * gross_q
        add("simulator/" + key, raw["simulator_fields"][key], wanted, lower["simulator_fields"][key], budget, "C/m3" if "rho" in key else "A/m2")
    volumes = np.asarray(inputs["cell_volume_m3"])
    bath_volume, m = inputs["bath_volume_m3"], inputs["membranes"]
    actual_counts, actual_changes = {}, {}
    for i, species in enumerate(inputs["ion_ids"]):
        initial, after = inputs["ionic_state"], raw["ionic_state"]
        def count(state):
            env = np.mean(state["cc_env"][i]) * bath_volume
            return dict(cell=np.sum(np.asarray(state["cc_cells"][i]) * volumes), declared_single_bath=env, source_effective_bath=m * env)
        before_count, after_count = count(initial), count(after)
        actual_counts[species], actual_changes[species] = after_count, {}
        for kind, value in after_count.items():
            delta = value - before_count[kind]
            actual_changes[species][kind] = delta
            budget = factor * target["ionic_count_gross_mol"][species][kind] + 1e-40
            add("count/" + species + "/" + kind, value, target["ionic_count_after_mol"][species][kind], lower["ionic_count_after_mol"][species][kind], budget, "mol")
            add("count_change/" + species + "/" + kind, delta, target["ionic_count_change_mol"][species][kind], lower["ionic_count_change_mol"][species][kind], budget, "mol")
    z = np.asarray(inputs["valence"])[:, None]
    charge = {}
    for tag, key in (("cell", "cc_cells"), ("env", "cc_env")):
        before, after = np.asarray(inputs["ionic_state"][key]), np.asarray(raw["ionic_state"][key])
        delta = inputs["F"] * np.sum(z * (after - before), axis=0)
        gross = inputs["F"] * np.sum(abs(z) * (abs(after) + abs(before)), axis=0)
        formal = inputs["F"] * target["formal_gene_charge_mM"][tag]
        for name, value in ((tag + "_ionic_charge_change_C_m3", delta), (tag + "_ionic_plus_formal_change_C_m3", delta + formal)):
            budget = factor * (gross + abs(formal)) + 1e-25
            add("charge/" + name, value, target["charge_ledger"][name], lower["charge_ledger"][name], budget, "C/m3")
            charge[name] = value
    ledger = dict(actual_counts_mol=actual_counts, actual_changes_mol=actual_changes,
                  actual_charge=charge, independent=target,
                  source_compensation_only=True, physical_conservation_credit=False,
                  energetic_conservation_credit=False, counterion_removal_is_material_sink=True)
    return rows, errors, budgets, ledger


"""
    + text[end:]
)
start = text.index("    cold_inputs = dict(", text.index("def test_charged_grn_owner"))
end = text.index("    try:", start)
text = (
    text[:start]
    + "    before_cold = cold_inputs(inputs)\n    cold_answers = references(cold_folder, before_cold)\n"
    + text[end:]
)
text = text.replace(
    "cold_rows, cold_errors, cold_budgets = cold_comparisons(\n        parent.network_cache, cold_answers[0], cold_answers[1]\n    )",
    'cold_rows, cold_errors, cold_budgets, cold_ledger = cold_comparisons(\n        parent.network_cache["wire"], before_cold, cold_answers[0], cold_answers[1]\n    )',
)
text = text.replace(
    "exact_initial_assignments=True,",
    "exact_initial_assignments=True,\n            charge_and_count_ledger=cold_ledger,",
)
text = text.replace(
    "    exact_nested(parent.network_cache, native_cold)\n",
    """    exact_nested(parent.network_cache, native_cold)
    for source_key, parent_key in (("cc_cells", "cell_mol_m3"), ("cc_at_mem", "membrane_mol_m3"), ("cc_env", "bath_mol_m3")):
        np.testing.assert_array_equal(getattr(parent.pump.gated.material.values, parent_key), native_cold["wire"]["ionic_state"][source_key])
    assert parent.pump.gated.material.step_index == 0
    np.testing.assert_array_equal(parent.pump.gated.material.values.voltage_V, inputs["initial"]["voltage_V"])
""",
)
needle = "        count = len(binding.pump_binding.gated_binding.material_binding.ion_ids)"
text = text.replace(
    needle,
    """        # Source publishes no molecular environment charge in no-ECM mode.
        # With runtime publication disabled, its prior cold environment write persists.
        env_rho = feedback["cache_after"]["wire"]["simulator_fields"]["extra_rho_env"]
        if inputs["drives"][index]["channels"]["substances_affect_charge"]:
            np.testing.assert_array_equal(env_rho, np.zeros(len(inputs["initial"]["voltage_V"])))
        else:
            np.testing.assert_array_equal(env_rho, parent.network_cache["wire"]["simulator_fields"]["extra_rho_env"])
"""
    + needle,
)
text = text.replace(
    "genuine_grn_owner_dispatch=True,",
    "genuine_grn_owner_dispatch=True,\n                charged_cold_compensation_checked=True,\n                compensated_parent_handoff_exact=True,\n                source_compensation_is_not_physical_conservation=True,",
)
start = text.index('@pytest.mark.parametrize("case", fixtures.RAW_CASES)')
end = text.index('@pytest.fixture(scope="module", autouse=True)', start)
text = (
    text[:start]
    + """@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_charged_grn_partial_failure(tmp_path, case):
    inputs = fixtures.raw_fixture(case)
    preparation = root(tmp_path) / ("preparation-" + case)
    preparation.mkdir(parents=True, exist_ok=False)
    (preparation / "inputs-before-constructor.json").write_text(json.dumps(inputs, indent=2, allow_nan=False) + "\\n")
    cold_folder = preparation / "cold-initialization"
    cold_folder.mkdir()
    before = cold_inputs(inputs)
    answers = references(cold_folder, before)
    folder, captured = isolated(tmp_path, case, inputs)
    assert captured["status"] == "source_refused" and len(captured["history"]) == 1
    try:
        seed(inputs)
    except joined.ChannelJoinRejected as error:
        caught = error
        archive_refusal(tmp_path, case, inputs, error)
    except Exception as error:
        archive_refusal(tmp_path, case + "-unexpected-constructor", inputs, error)
        raise
    else:
        raise AssertionError("Source capacity refusal was not reached")
    source = captured["channel_initialization_failure"]
    exact_nested(caught.initialization, source)
    assert source["source_exception"] == "BetseSimConfException"
    assert source["stage"] == caught.stage == "grn_initialization"
    leaf = caught
    while leaf.__cause__ is not None:
        leaf = leaf.__cause__
    assert type(leaf).__name__ == "BetseSimConfException"
    assert str(leaf) == source["source_message"]
    assert source["actual_grn_enabled"] and not source["actual_molecules_enabled"]
    assert answers[1]["failure_case"] == case
    rows, errors, budgets, ledger = cold_comparisons(source["owner_snapshot"], before, answers[0], answers[1])
    archive(tmp_path, case + "-cold-errors", dict(fields=rows, errors=errors, budgets=budgets, ledger=ledger, actual=source, lower=answers[0], target=answers[1]))
    (cold_folder / "comparison.json").write_text(json.dumps(dict(fields=rows, actual_cold_configuration_only=True, physical_conservation_credit=False), indent=2) + "\\n")
    assert max(row["normalized_max_error"] for row in rows.values()) <= 1
    assert max(row["normalized_max_error"] for name, row in rows.items() if name.startswith("reference/")) <= 0.1
    failure = dict(source_refused=True, source_type="BetseSimConfException", cold_initialization_failure=True,
                   partial_owner_fields_preserved=True, completed_transports=0,
                   cell_compensation_completed=case.startswith("env_"),
                   preserved_source_charge_balanced_flag=False,
                   cold_reference_forms=2, intended_capacity_failure=case,
                   positive_grn_credit=False, physical_conservation_credit=False)
    (folder / "raw-retention.json").write_text(json.dumps(failure, indent=2) + "\\n")


@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_complete_charged_grn_dependencies(tmp_path, dependency):
    inputs = copy.deepcopy(fixtures.fixture())
    try:
        valid_binding, valid_parent = seed(inputs)
    except Exception as error:
        archive_refusal(tmp_path, dependency + "-unexpected-valid-constructor", inputs, error)
        raise
    archive(tmp_path, dependency + "-valid-admission", dict(binding=valid_binding, parent=valid_parent, baseline_admitted=True, genuine_grn_owner=True))
    expected_messages = dict(
        wrong_owner="Require an actual configured GRN owner and complete initialization context",
        missing_M="Charged GRN needs actual Na(+1), K(+1) and M(-1) counterion rows",
        wrong_M_valence="Charged GRN needs actual Na(+1), K(+1) and M(-1) counterion rows",
        missing_ionic_cache="Require complete charged GRN ionic snapshot",
        missing_balance_events="Require charged GRN compensation observations",
        missing_source_default="Missing source-initialized GRN molecule fields",
    )
    net = inputs["channel_definition"]["network"]
    if dependency == "wrong_owner":
        net["owner"] = "molecules"
    if dependency == "missing_M":
        for definition in (inputs["ion_definition"], inputs["current_definition"]):
            definition["ions"]["ids"] = ["missing_counterion" if name == "M" else name for name in definition["ions"]["ids"]]
    if dependency == "wrong_M_valence":
        for definition in (inputs["ion_definition"], inputs["current_definition"]):
            definition["ions"]["valence"][definition["ions"]["ids"].index("M")] = -2.0
    archive(tmp_path, dependency + "-inputs", inputs)
    if dependency in ("missing_ionic_cache", "missing_balance_events", "missing_source_default"):
        binding, parent = valid_binding, valid_parent
        cache = ions.data(parent.network_cache)
        if dependency == "missing_ionic_cache":
            del cache["wire"]["ionic_state"]
        elif dependency == "missing_balance_events":
            del cache["wire"]["balance_events"]
        else:
            del cache["wire"]["molecule_fields"]["X"]["ignore_ECM_pump"]
        changed = joined._state(binding, parent.pump, parent.channel_caches, parent.channel_calls,
                                parent.initialization, parent.calcium_rate_proxy_mol_m2_s,
                                parent.network_controls, cache)
        with pytest.raises(joined.ChannelJoinRejected) as caught:
            advance(inputs, binding, changed, 0, inputs["elapsed_start_s"])
    else:
        with pytest.raises(ValueError) as caught:
            seed(inputs)
    leaf = caught.value
    while leaf.__cause__ is not None:
        leaf = leaf.__cause__
    assert type(leaf) is ValueError and str(leaf) == expected_messages[dependency]
    witness = dict(baseline_admitted=True, dependency=dependency, genuine_grn_owner=True,
                   expected_message=expected_messages[dependency], actual_message=str(leaf),
                   actual_leaf_type=type(leaf).__name__, intended_failure_reached=True, source_failure_credit=False)
    (root(tmp_path) / ("dependency-" + dependency + ".json")).write_text(json.dumps(witness, indent=2) + "\\n")
    archive(tmp_path, dependency + "-expected-refusal", dict(type=type(caught.value).__name__, message=str(caught.value), source_failure_credit=False))


"""
    + text[end:]
)
with (ROOT / "tests/unit/test_betse_normal_charged_grn_join.py").open("x") as stream:
    stream.write(text)
print({"emitted_checks_without_import_or_collection": 1})
