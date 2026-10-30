# ruff: noqa: E501 -- source templates are formatted in their outputs.
"""Emit genuine GRN checks from the established material/chemistry harness."""

from pathlib import Path

ROOT = Path("/home/robert/Cells")
text = (
    (ROOT / "tests/unit/test_betse_normal_molecule_join.py")
    .read_text()
    .replace("betse_normal_molecule", "betse_normal_grn")
    .replace("normal-molecule-join", "normal-grn-join")
    .replace("CELLS_MOLECULE_JOIN_CPU", "CELLS_GRN_JOIN_CPU")
)
text = text.replace(
    "test_native_chemical_transport_and_conditional_reference",
    "test_genuine_grn_owner_and_conditional_reference",
)
text = text.replace(
    "    try:\n        binding, parent = seed(inputs)",
    """    cold_folder=preparation/"cold-initialization"
    cold_folder.mkdir()
    cold_inputs=dict(mode="cold_initialization",network=inputs["channel_definition"]["network"],ion_ids=inputs["ion_definition"]["ions"]["ids"],cells=len(inputs["initial"]["cell_mol_m3"][0]),membranes=len(inputs["initial"]["voltage_V"]))
    cold_answers=references(cold_folder,cold_inputs)
    try:
        binding, parent = seed(inputs)""",
    1,
)
needle = '    assert captured["status"] == "source_completed" and len(captured["history"]) == 3'
text = text.replace(
    needle,
    needle
    + """
    native_cold=captured["history"][0]["material"]["channel_capture"]["network_feedback"]["cache_before"]
    exact_nested(parent.network_cache,native_cold)
    cold_rows=cold_comparisons(parent.network_cache,cold_answers[0],cold_answers[1])
    (cold_folder/"comparison.json").write_text(json.dumps(dict(fields=cold_rows,actual_cold_configuration_only=True,physical_conservation_credit=False),indent=2)+"\\n")
    assert max(row["normalized_max_error"] for row in cold_rows.values())<=1
""",
    1,
)
needle = '        compare_feedback(feedback, material["channel_capture"]["network_feedback"], completed=True)'
text = text.replace(
    needle,
    needle
    + """
        exact_nested(feedback["grn_owner"],material["channel_capture"]["network_feedback"]["grn_owner"])
        exact_nested(feedback["grn_owner_after"],material["channel_capture"]["network_feedback"]["grn_owner_after"])
        assert feedback["grn_owner"]["owner_class"]=="MasterOfGenes" and feedback["grn_owner"]["core_class"]=="MasterOfNetworks"
        assert feedback["grn_owner"]["actual_core_identity"] and feedback["grn_owner"]["grn_enabled"] and not feedback["grn_owner"]["molecules_enabled"]
        expected=("clear_run_loop",)+( ("run_loop_modulators",) if inputs["channel_definition"]["network"]["modulators"] else () )+("run_loop",)
        assert tuple(feedback["grn_dispatch_stages"])==tuple(material["channel_capture"]["network_feedback"]["grn_dispatch_stages"])==expected
        assert material["channel_capture"]["network_feedback"]["cold_initialization"]==(index==0)
""",
    1,
)
text = text.replace(
    '        if case in ("reaction_only", "growth_only", "zero_Dm_GJ"):\n            for mol in feedback["molecule_states_after"].values():\n                np.testing.assert_array_equal(mol["f_mem"], np.zeros(9))\n',
    "",
)
text = text.replace(
    'executed_chemistry=case != "transport_only",',
    'executed_chemistry=True,\n                genuine_grn_owner_dispatch=True,\n                cold_initialization_checks=1,\n                cold_reference_forms=2,\n                cold_phase="constructor; native before first ordinary call",',
)
start = text.index('@pytest.mark.parametrize("case", fixtures.RAW_CASES)')
end = text.index('@pytest.fixture(scope="module", autouse=True)', start)
text = (
    text[:start]
    + """@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_genuine_grn_partial_failure(tmp_path,case):
    inputs=fixtures.raw_fixture(case)
    archive(tmp_path,case+"-inputs",inputs)
    folder,captured=isolated(tmp_path,case,inputs)
    assert captured["status"]=="source_refused" and len(captured["history"])==1
    if case.startswith("cold_"):
        with pytest.raises(joined.ChannelJoinRejected) as caught:
            seed(inputs)
        archive_refusal(tmp_path,case,inputs,caught.value)
        source=captured["channel_initialization_failure"]
        exact_nested(caught.value.initialization,source)
        assert source["source_exception"]=="KeyError" and source["stage"]==caught.value.stage=="grn_initialization"
        assert source["actual_grn_enabled"] and not source["actual_molecules_enabled"]
        fields=source["owner_snapshot"]["molecule_fields"]
        assert fields["X"]["c_cells"].shape==(3,) and fields["Y"]["c_cells"].shape==(3,)
        assert (fields["X"]["Dm"] is not None)==("second" in case)
        assert fields["Y"]["Dm"] is None
        failure=dict(source_refused=True,source_type="KeyError",cold_initialization_failure=True,partial_owner_fields_preserved=True,completed_transports=0,positive_grn_credit=False,physical_conservation_credit=False)
    else:
        binding,parent=seed(inputs)
        digest=ions.digest(parent)
        with pytest.raises(joined.ChannelJoinRejected) as caught:
            advance(inputs,binding,parent,0,inputs["elapsed_start_s"],lambda before:archive(tmp_path,case+"-pre-network",before))
        archive_refusal(tmp_path,case,dict(inputs=inputs,parent=parent),caught.value)
        assert digest==ions.digest(parent)
        feedback=caught.value.network["network_feedback"]
        material=captured["history"][0]["material"]
        compare_feedback(feedback,material["channel_capture"]["network_feedback"],completed=False)
        exact_nested(feedback["grn_owner_after"],material["channel_capture"]["network_feedback"]["grn_owner_after"])
        assert material["failure"]["type"]=="BetseSimUnstableException"
        expected=0 if "first" in case else 1
        assert feedback["molecular_transports_completed"]==expected
        failure=dict(source_refused=True,source_type="BetseSimUnstableException",cold_initialization_failure=False,partial_owner_fields_preserved=True,completed_transports=expected,positive_grn_credit=False,physical_conservation_credit=False)
    (folder/"raw-retention.json").write_text(json.dumps(failure,indent=2)+"\\n")


@pytest.mark.parametrize("dependency",fixtures.DEPENDENCIES)
def test_complete_grn_dependencies(tmp_path,dependency):
    inputs=copy.deepcopy(fixtures.fixture())
    net=inputs["channel_definition"]["network"]
    if dependency=="wrong_owner":
        net["owner"]="molecules"
    if dependency=="intracellular_field":
        net["grn_configuration"]["biomolecules"][0]["update intracellular"]=True
    if dependency=="charged_gene":
        net["grn_configuration"]["biomolecules"][0]["z"]=1.0
    archive(tmp_path,dependency+"-inputs",inputs)
    if dependency in ("missing_owner_cache","missing_source_default"):
        binding,parent=seed(inputs)
        cache=ions.data(parent.network_cache)
        if dependency=="missing_owner_cache":
            del cache["wire"]["owner_fields"]
        else:
            del cache["wire"]["molecule_fields"]["X"]["ignore_ECM_pump"]
        changed=joined._state(binding,parent.pump,parent.channel_caches,parent.channel_calls,parent.initialization,parent.calcium_rate_proxy_mol_m2_s,parent.network_controls,cache)
        with pytest.raises(joined.ChannelJoinRejected) as caught:
            advance(inputs,binding,changed,0,inputs["elapsed_start_s"])
    else:
        with pytest.raises(ValueError) as caught:
            seed(inputs)
    archive(tmp_path,dependency+"-expected-refusal",dict(type=type(caught.value).__name__,message=str(caught.value),source_failure_credit=False))


"""
    + text[end:]
)
position = text.index('@pytest.mark.parametrize("case", fixtures.CASES)')
text = (
    text[:position]
    + """def cold_comparisons(cache,lower,target):
    rows={}
    raw=cache["wire"]
    assert dict(raw["owner_fields"])==target["owner_fields"]
    assert raw["core_fields"]["charge_has_been_balanced"] is target["charge_has_been_balanced"] is True
    for name,fields in target["molecule_fields"].items():
        actual=raw["molecule_fields"][name]
        for key,wanted in fields.items():
            value=actual[key]
            if wanted is None or type(wanted) is bool:
                assert value is wanted
                continue
            a,b,less=np.asarray(value,np.float64),np.asarray(wanted,np.float64),np.asarray(lower["molecule_fields"][name][key],np.float64)
            budget=FLOORS["cell_mol_m3"]+128*np.finfo(float).eps*(abs(a)+abs(b)+1)
            rows[name+"/"+key]=old.metric(a,b,budget)
            rows["reference/"+name+"/"+key]=old.metric(less,b,budget)
    matrix=np.asarray(target["reaction_matrix"])
    rows["reaction_matrix"]=old.metric(raw["core_fields"]["reaction_matrix"],matrix,np.full(matrix.shape,1e-25))
    return rows


"""
    + text[position:]
)
with (ROOT / "tests/unit/test_betse_normal_grn_join.py").open("x") as stream:
    stream.write(text)
print("Created19 planned genuine GRN checks without collection or scientific import")
