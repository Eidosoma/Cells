# ruff: noqa: E501
"""Emit ECM standalone state/sampling tests without collecting or evaluating them."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")
NEW = "betse_ecm_sim_grn"
text = (ROOT / "tests/unit/test_betse_sim_grn.py").read_text().replace("betse_sim_grn", NEW)
text = text.replace('"sim-grn"', '"ecm-sim-grn"').replace(
    "CELLS_SIM_GRN_CPU", "CELLS_ECM_SIM_GRN_CPU"
)
text = text.replace("test_standalone_grn_", "test_ecm_standalone_grn_")
text = text.replace("(90 if level == 1 else 140)", "(100 if level == 1 else 160)")


def functions(source):
    return {
        n.name: ast.get_source_segment(source, n)
        for n in ast.parse(source).body
        if isinstance(n, ast.FunctionDef)
    }


old = functions(text)
cold = """def cold_inputs(inputs):
    declaration=inputs["material_definition"]
    ids=declaration["environment_geometry_definition"]["current_definition"]["ions"]["ids"]
    return dict(mode="cold_initialization",network=inputs["network"],
        material_declaration=declaration,ion_ids=ids,cells=len(inputs["initial"]["cell_mol_m3"][0]),
        membranes=len(inputs["initial"]["voltage_V"]),environment_sites=len(inputs["initial"]["environment_mol_m3"][0]),
        incoming_publication_fields=inputs["incoming_publication_fields"])
"""
text = text.replace(old["cold_inputs"], cold, 1)
ecm = (ROOT / "tests/unit/test_betse_ecm_grn_join.py").read_text()
ecmf = functions(ecm)
compare = ast.parse(ecmf["compare_local"]).body[0]
compare.name = "compare_ecm_local"
compare.body = [
    node
    for node in compare.body
    if not (isinstance(node, ast.For) and ast.unparse(node.target) == "(key, gross_key, unit)")
]
transport = ast.unparse(ast.fix_missing_locations(compare))
new_local = """def compare_local(step,lower,target):
    before,after=step["before"],step["after"]
    sim=after["simulator"]
    feedback=dict(before=before,cache_after=dict(wire=after["wire"]),rhs=step["rhs"],
        controls_after={key:sim[key] for key in ("gj_block","NaKATP_block")},
        values_after=dict(voltage_V=sim["vm"],junction_voltage_V=sim["vgj"]))
    rows=compare_ecm_local(feedback,lower,target)
    for key,input_key in (("cc_cells","cell_mol_m3"),("cc_at_mem","membrane_mol_m3"),("cc_env","environment_mol_m3")):
        np.testing.assert_array_equal(sim[key],before["values_before"][input_key])
    for key in ("gj_block","NaKATP_block"):
        np.testing.assert_array_equal(sim[key],before["controls_before"][key])
    assert after["parameters"]["substances_affect_charge"] is before["substances_affect_charge"] is False
    for key,value in before["simulator_fields_before"].items():
        np.testing.assert_array_equal(after["wire"]["simulator_fields"][key],value)
    present={key:after["wire"]["core_fields"][key] for key in before["core_publication_fields_before"]}
    old.exact_nested(present,before["core_publication_fields_before"])
    assert not {"extra_rho_cells","extra_rho_env"}&after["wire"]["core_fields"].keys()
    return rows
"""
text = text.replace(
    old["compare_local"], ecmf["comparisons"] + "\n\n" + transport + "\n\n" + new_local, 1
)
text = text.replace(
    'for key in ("extra_rho_cells", "extra_J_mem", "c_env_bound"):',
    'for key in ("extra_rho_cells","extra_rho_env","extra_J_mem","extra_Jenv_x","extra_Jenv_y","c_env_bound","D_env_weight","D_env_weight_base","TJ_targets"):',
)
text = text.replace(
    "                standalone_sim_grn=True,",
    "                standalone_sim_grn=True,\n                standalone_ECM=True,\n"
    '                inherited_scalar_control=inputs["inherited_scalar_control"],\n'
    "                full_grid_E_buffers_and_publication_carry=True,",
)
text = text.replace(
    'if case in ("first_negative", "second_negative"):',
    'if case in ("first_negative","second_negative","first_environment_negative","second_environment_negative"):',
)
text = text.replace('0 if case == "first_negative" else 1', '0 if case.startswith("first_") else 1')
start = text.index('@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)')
end = text.index("\n\n@pytest.fixture", start)
text = (
    text[:start]
    + """@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_ecm_standalone_grn_dependencies(tmp_path,dependency):
    inputs=fixtures.fixture()
    try:
        binding=model.bind(inputs)
        parent=model.initialize(binding)
    except Exception as error:
        archive(tmp_path,dependency+"-unexpected-valid-constructor",dict(error=str(error),traceback=traceback.format_exc(),partial=getattr(error,"partial",None)))
        raise
    archive(tmp_path,dependency+"-valid-admission",dict(binding=binding,parent=parent))
    messages=dict(ECM_disabled="Require explicit ECM-enabled standalone phase",
        mitochondria="Standalone mitochondria require separate organelle state",
        fluid="Standalone fluid and cuts require separate phase dynamics",
        unsafe_sampling="Sampling below dt stalls the source sampling-index loop",
        missing_owner_state="Require complete standalone owner state",
        missing_boundary_state="Require standalone boundary state",
        missing_grid_state="Require complete generated standalone ECM grid state",
        missing_coefficient_state="Require standalone ECM coefficient state",
        file_restart="File restart requires a separate persistence boundary",
        prepared_mapping="Require owned in-grid TJ indices")
    if dependency in ("missing_owner_state","missing_boundary_state","missing_grid_state","missing_coefficient_state"):
        raw=ions.data(parent.snapshot)
        if dependency=="missing_owner_state":del raw["wire"]["owner_fields"]
        elif dependency=="missing_boundary_state":del raw["wire"]["ion_boundary_state"]
        elif dependency=="missing_grid_state":del raw["grid_fields"]
        else:del raw["simulator"]["D_env_weight"]
        changed=model.state(binding,raw,0)
        archive(tmp_path,dependency+"-malformed-parent-before-call",dict(parent=changed,inputs=inputs))
        with pytest.raises(ValueError) as caught:model.advance(binding,changed)
    else:
        changed=copy.deepcopy(inputs)
        if dependency=="ECM_disabled":changed["is_ecm"]=False
        elif dependency in ("mitochondria","fluid"):changed["scope"][dependency]=True
        elif dependency=="unsafe_sampling":changed["calls"][0]["sample_s"]=0.001
        elif dependency=="file_restart":changed["scope"]["grn_unpickle_filename"]="/uncaptured/restart.pickle"
        else:changed["network"]["grid_index_groups"]["all_bound_mem_inds"]=[999]
        archive(tmp_path,dependency+"-inputs",changed)
        with pytest.raises(ValueError) as caught:model.bind(changed)
    archive(tmp_path,dependency+"-refusal",dict(message=str(caught.value),type=type(caught.value).__name__))
    assert type(caught.value) is ValueError and str(caught.value)==messages[dependency]
    (root(tmp_path)/("dependency-"+dependency+".json")).write_text(json.dumps(dict(
        baseline_admitted=True,intended_failure_reached=True,actual_leaf_type="ValueError",
        expected_message=messages[dependency],actual_message=str(caught.value),source_failure_credit=False),indent=2)+"\\n")
"""
    + text[end:]
)
with (ROOT / ("tests/unit/test_" + NEW + ".py")).open("x") as stream:
    stream.write(text)
print("Standalone ECM tests emitted:18 histories,7 raw failures,10 dependencies; not collected")
