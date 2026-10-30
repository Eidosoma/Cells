# ruff: noqa: E501 -- literal source templates are formatted in their outputs.
"""Create new-prefix checks from the frozen molecule harness, without importing it."""

from pathlib import Path

root = Path("/home/robert/Cells")
source = (root / "tests/unit/test_betse_normal_molecule_join.py").read_text()
source = source.replace("betse_normal_molecule", "betse_normal_transporter")
source = source.replace("normal-molecule-join", "normal-transporter-join")
source = source.replace("CELLS_MOLECULE_JOIN_CPU", "CELLS_TRANSPORTER_JOIN_CPU")
source = source.replace(
    "def advance(inputs, binding, parent, index, elapsed, observer=None):",
    "def advance(inputs, binding, parent, index, elapsed, observer=None, transporter_observer=None):",
)
source = source.replace(
    "        before_network=observer,",
    "        before_network=observer,\n        before_transporters=transporter_observer,",
)
source = source.replace(
    "test_native_chemical_transport_and_conditional_reference",
    "test_native_configured_transporters_and_conditional_reference",
)
source = source.replace(
    "        answers, reused = [], []",
    "        answers, reused, transporter_answers = [], [], []\n        transporter_local = folder / ('pre-transporters-' + str(index))\n        transporter_local.mkdir()",
)
needle = "        digest = ions.digest(parent)\n"
assert source.count(needle) == 1
source = source.replace(
    needle,
    """        def transporter_observer(before):
            archive(tmp_path, case + "-pre-transporters-" + str(index), before)
            transporter_answers.extend(references(transporter_local, before))

"""
    + needle,
)
source = source.replace(
    "trial = advance(inputs, binding, parent, index, elapsed, observer)",
    "trial = advance(inputs, binding, parent, index, elapsed, observer, transporter_observer)",
)
source = source.replace(
    "assert ions.digest(parent) == digest and len(answers) == 2",
    "assert ions.digest(parent) == digest and len(answers) == len(transporter_answers) == 2",
)
needle = '        compare_feedback(feedback, material["channel_capture"]["network_feedback"], completed=True)'
assert source.count(needle) == 1
source = source.replace(
    needle,
    needle
    + """
        execution = feedback["transporter_execution"]
        exact_nested(execution, material["channel_capture"]["network_feedback"]["transporter_execution"])
        assert execution["source_completed"]
        transporter_rows, transporter_errors, transporter_budgets, transporter_ledgers = transporter_comparisons(execution, transporter_answers[0], transporter_answers[1])
        archive(tmp_path, "transporter-errors-" + case + "-" + str(index), dict(fields=transporter_rows, errors=transporter_errors, budgets=transporter_budgets, ledgers=transporter_ledgers))
        (transporter_local / "comparison.json").write_text(json.dumps(dict(fields=transporter_rows, actual_pre_transporter_only=True, physical_global_conservation_credit=False), indent=2) + "\\n")
        assert max(row["normalized_max_error"] for row in transporter_rows.values()) <= 1
        assert max(row["normalized_max_error"] for key, row in transporter_rows.items() if key.startswith("reference/")) <= 0.1
        if case in ("zero_capacity", "zero_rho"):
            for value in execution["fluxes_after"].values():
                np.testing.assert_array_equal(value, np.zeros(9))
        if case in ("nkcc_multiplier_two", "ncx_multiplier_three"):
            assert max(np.max(abs(row["observed_buffer_discrepancy_mM"])) for row in transporter_ledgers) > 0
        if case == "closed_boundary":
            assert any(np.any(np.asarray(value)[[1, 5, 6]] != 0) for value in execution["fluxes_after"].values())
""",
)
source = source.replace(
    'if case in ("reaction_only", "growth_only", "zero_Dm_GJ"):', 'if case == "transporter_only":'
)
source = source.replace(
    "        reports.append(rows)",
    "        reports.append(rows | {'transporter/' + key: value for key, value in transporter_rows.items()})",
)
source = source.replace(
    "conditional_pre_network_checks=3,",
    "conditional_pre_network_checks=3,\n                conditional_pre_transporter_checks=3,\n                native_configured_transporter_calls=3,\n                source_buffer_discrepancy_preserved=True,\n                source_bath_update_preserved=True,",
)
source = source.replace('case != "transport_only"', 'case != "transporter_only"')
start = source.index('@pytest.mark.parametrize("case", fixtures.RAW_CASES)')
end = source.index('@pytest.fixture(scope="module", autouse=True)', start)
source = (
    source[:start]
    + """@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_native_transporter_partial_failure(tmp_path, case):
    inputs = fixtures.raw_fixture(case)
    archive(tmp_path, case + "-raw-inputs", inputs)
    binding, parent = seed(inputs)
    archive(tmp_path, case + "-constructor-return", dict(binding=binding, parent=parent))
    folder, captured = isolated(tmp_path, case, inputs)
    assert captured["status"] == "source_refused" and len(captured["history"]) == 1
    material = captured["history"][0]["material"]
    assert material["failure"]["type"] == "IndexError"
    digest = ions.digest(parent)
    with pytest.raises(joined.ChannelJoinRejected) as caught:
        advance(inputs, binding, parent, 0, inputs["elapsed_start_s"], transporter_observer=lambda before: archive(tmp_path, case + "-actual-pre-transporters", before))
    archive_refusal(tmp_path, case, dict(inputs=inputs, parent=parent), caught.value)
    assert ions.digest(parent) == digest
    actual = caught.value.network["network_feedback"]["transporter_execution"]
    source = material["channel_capture"]["network_feedback"]["transporter_execution"]
    exact_nested(actual, source)
    assert not actual["source_completed"]
    stages = [(row["stage"], row["name"]) for row in actual["frames"]]
    assert stages[-1] == ("reactant_commit", "subset_export")
    completed = sum(stage == "after" for stage, _ in stages)
    assert completed == (0 if case == "first_subset_partial" else 1)
    # The source adds current over ALL membranes before target writes. Its
    # internal reactant commits bulk cell1 and membrane3:6, then fails in env.
    before = next(row for row in actual["frames"] if row["stage"] == "before" and row["name"] == "subset_export")
    final = actual["concentrations_after"]
    assert np.any(actual["extra_current_after_A_m2"] != before["extra_current_A_m2"])
    assert final["cell_concs"]["Na"][1] != before["concentrations"]["cell_concs"]["Na"][1]
    assert np.any(final["mem_concs"]["Na"][[3,4,5]] != before["concentrations"]["mem_concs"]["Na"][[3,4,5]])
    np.testing.assert_array_equal(final["env_concs"]["Na"], before["concentrations"]["env_concs"]["Na"])
    causes, error = [], caught.value
    while error is not None:
        causes.append(type(error).__name__)
        error = error.__cause__
    assert "IndexError" in causes
    (folder / "raw-retention.json").write_text(json.dumps(dict(source_refused=True, source_failure=material["failure"], model_cause_types=causes, completed_transporters=completed, partial_current_and_material_preserved=True, positive_transporter_credit=False, physical_conservation_credit=False, equation_or_mover_bypass=False), indent=2) + "\\n")


@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_complete_transporter_dependencies(tmp_path, dependency):
    inputs = copy.deepcopy(fixtures.fixture())
    network = inputs["channel_definition"]["network"]
    if dependency == "missing_membrane_volume":
        del network["membrane_volume_m3"]
    if dependency == "missing_configuration":
        del network["transporters"][0]["reactants"]
    if dependency == "unknown_profile":
        network["transporters"][0]["apply to"] = ["missing"]
    if dependency == "mitochondrial_zone":
        network["transporters"][0]["reaction zone"] = "mit"
    archive(tmp_path, dependency + "-dependency-inputs", inputs)
    if dependency == "missing_flux_cache":
        binding, parent = seed(inputs)
        cache = ions.data(parent.network_cache)
        del cache["transporter_fluxes"]
        altered = joined._state(binding, parent.pump, parent.channel_caches, parent.channel_calls, parent.initialization, parent.calcium_rate_proxy_mol_m2_s, parent.network_controls, cache)
        with pytest.raises(joined.ChannelJoinRejected) as caught:
            advance(inputs, binding, altered, 0, inputs["elapsed_start_s"])
    else:
        with pytest.raises((ValueError, joined.MissingCoupledState)) as caught:
            seed(inputs)
    archive(tmp_path, dependency + "-expected-refusal", dict(type=type(caught.value).__name__, message=str(caught.value), native_refusal_or_physical_case_credit=False))


"""
    + source[end:]
)
with (root / "tests/unit/test_betse_normal_transporter_join.py").open("x") as stream:
    stream.write(source)
print("Created new-prefix tests without collection or scientific imports")
