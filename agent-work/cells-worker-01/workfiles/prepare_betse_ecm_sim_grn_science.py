# ruff: noqa: E501
"""Reachability then literal standalone+ECM text assembly; no scientific imports."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
NEW = "betse_ecm_sim_grn"


def functions(text):
    return {
        n.name: ast.get_source_segment(text, n)
        for n in ast.parse(text).body
        if isinstance(n, ast.FunctionDef)
    }


def emit(path, text):
    with (ROOT / path).open("x") as stream:
        stream.write(text)


def replace(text, before, after):
    assert before in text, before
    return text.replace(before, after, 1)


# Check the actual caller/configuration first, before emitting scientific files.
gene = ast.parse((PIN / "science/chemistry/gene.py").read_text())
run = next(n for n in ast.walk(gene) if isinstance(n, ast.FunctionDef) and n.name == "run_core_sim")
calls = {ast.unparse(n.func) for n in ast.walk(run) if isinstance(n, ast.Call)}
assert {
    "self.reinitialize",
    "self.core.clear_cache",
    "self.core.run_loop",
    "self.core.write_data",
} <= calls
assert (
    not {"self.core.clear_run_loop", "self.core.run_loop_modulators", "self.core.run_loop_channels"}
    & calls
)
assert any(
    isinstance(n, ast.Assign) and ast.unparse(n) == "p.substances_affect_charge = False"
    for n in run.body
)
assert not any(
    isinstance(n, ast.Assign) and any(ast.unparse(t) == "p.is_ecm" for t in n.targets)
    for n in ast.walk(run)
)
runner = ast.parse((PIN / "science/simrunner.py").read_text())
branch = next(
    n
    for n in ast.walk(runner)
    if isinstance(n, ast.If) and ast.unparse(n.test) == "self._p.grn_unpickle_filename is None"
)
assert any(
    isinstance(n, ast.Expr) and ast.unparse(n) == "MoG.read_gene_config(phase)" for n in branch.body
)
receipt = dict(
    kind="cells.ecm_sim_grn_reachability@1",
    reachable=True,
    original_run_core_sim_lines=[run.lineno, run.end_lineno],
    new_owner_lines=[branch.lineno, branch.end_lineno],
    is_ecm_not_overridden=True,
    charge_publication_forced_off=True,
    real_reinitialize_cache_sampling_call=True,
    no_normal_clear_or_modulator_dispatch=True,
    source_sha256={
        str(p.relative_to(PIN.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (
            PIN / "science/chemistry/gene.py",
            PIN / "science/simrunner.py",
            PIN / "science/chemistry/networks.py",
        )
    },
    supplied_phase_boundary=True,
    scientific_execution=False,
)
emit(
    "agent-work/cells-worker-01/workfiles/" + NEW + "_reachability_01.json",
    json.dumps(receipt, indent=2, sort_keys=True) + "\n",
)

source = (ROOT / "src/cells/processes/betse_sim_grn.py").read_text().replace("betse_sim_grn", NEW)
source = replace(
    source,
    "from cells.processes import betse_normal_grn_source as base",
    "from cells.processes import betse_ecm_grn_source as base\n"
    "from cells.processes import betse_ecm_transport as material\n"
    "from cells.processes import betse_environment_field as field",
)
old_functions = functions(source)
common_make = (WORK / "ecm_sim_grn_context_template.txt").read_text().strip()
source = replace(source, old_functions["make_context"], common_make)
validate = old_functions["validate"]
validate = replace(
    validate,
    '    if inputs["ion_definition"]["parameters"]["is_ecm"] is not False:\n        raise ValueError("Standalone ECM requires a separate spatial phase")',
    '    if inputs.get("is_ecm") is not True:\n        raise ValueError("Require explicit ECM-enabled standalone phase")',
)
start = validate.index('    g = inputs["ion_definition"]["geometry"]')
validate = (
    validate[:start]
    + """    binding=material.bind(inputs["material_definition"])
    base_validate(inputs["network"],binding)
    cb=binding.geometry_binding.current_binding
    if not {"Na","K","Cl"}<=set(cb.ion_ids):
        raise ValueError("Standalone ECM reports require actual Na/K/Cl rows")
    if set(inputs["incoming_publication_fields"])!={"extra_rho_cells","extra_rho_env","extra_J_mem","extra_Jenv_x","extra_Jenv_y"}:
        raise ValueError("Require all five incoming ECM publications")
    n,m,e=len(cb.cell_ids),len(cb.membrane_ids),int(np.prod(binding.geometry_binding.geometry.shape))
    for key,size in (("extra_rho_cells",n),("extra_rho_env",e),("extra_J_mem",m),("extra_Jenv_x",e),("extra_Jenv_y",e)):
        array=np.asarray(inputs["incoming_publication_fields"][key],np.float64)
        if array.shape!=(size,) or not np.isfinite(array).all():
            raise ValueError("Require original cell/E-grid/M-membrane publication shapes")
    if inputs["material_definition"]["parameters"]["fluid_flow"] is not False:
        raise ValueError("Standalone fluid and cuts require separate phase dynamics")
"""
)
source = replace(source, old_functions["validate"], validate)
bind = old_functions["bind"]
start = bind.index("    ib = ions.bind(")
end = bind.index("    return Binding(", start)
bind = bind[:start] + bind[end:]
source = replace(source, old_functions["bind"], bind)
source = (
    replace(
        source,
        '        "directories": clone(ctx.directories),',
        '        "directories": clone(ctx.directories),',
    )
    if '        "directories": clone(ctx.directories),' in source
    else source
)
snapshot = old_functions["snapshot"]
snapshot = replace(
    snapshot,
    "        wire=wire(ctx.owner, ctx.sim),",
    "        wire=wire(ctx.owner, ctx.sim),\n        grid_fields={name:clone(getattr(ctx.cells,name)) for name in GRID_FIELDS},",
)
source = replace(source, old_functions["snapshot"], snapshot)
restore = old_functions["restore"]
restore = replace(
    restore,
    '    raw = incoming["wire"]',
    '    if "grid_fields" not in incoming or set(incoming["grid_fields"])!=set(GRID_FIELDS):\n'
    '        raise ValueError("Require complete generated standalone ECM grid state")\n'
    '    if not {"D_env_weight","D_env_weight_base","TJ_targets"}<=incoming["simulator"].keys():\n'
    '        raise ValueError("Require standalone ECM coefficient state")\n'
    '    vars(ctx.cells).update(clone(incoming["grid_fields"]))\n'
    '    raw = incoming["wire"]',
)
restore = replace(
    restore,
    "        for name in ctx.p.ions_dict:\n            i = ctx.sim.get_ion(name)",
    "        for name,enabled in ctx.p.ions_dict.items():\n            if enabled!=1: continue\n            i = ctx.sim.get_ion(name)",
)
source = replace(source, old_functions["restore"], restore)
# Original literal owner/Core methods stay byte-identical to standalone01.
source = replace(
    source,
    "        DynamicValueDict=base.DynamicValueDict,",
    "        DynamicValueDict=base.DynamicValueDict,\n        derive_context=base.derive_context,",
)
ecm_context = (ROOT / "src/cells/processes/betse_ecm_grn_source.py").read_text()
before = functions(ecm_context)["before"]
start = before.index("    return dict(")
local = before[:start] + before[start:]
local = local.replace("def before(ctx, material_declaration):", "def local_inputs(ctx,t):")
local = local.replace(
    "sim, p, cells, net = ctx.sim, ctx.p, ctx.cells, ctx.net",
    "sim, p, cells, net = ctx.sim, ctx.p, ctx.cells, ctx.owner.core",
)
local = local.replace(
    "material_declaration=clone(material_declaration)",
    'material_declaration=clone(ctx.inputs["material_definition"])',
)
local = local.replace(
    "cache_before=cache(ctx)",
    "core_publication_fields_before={key:clone(getattr(net,key)) for key in PUBLICATIONS if hasattr(net,key)}",
)
local = local.replace("values_before=material_values(sim)", "values_before=material_values(sim)")
local = local.replace(
    "ion_ids=list(ctx.ion_ids)",
    "ion_ids=[name for name,enabled in p.ions_dict.items() if enabled==1]",
)
local = local.replace(
    'grid_index_groups=clone(ctx.definition["grid_index_groups"])',
    'grid_index_groups=clone(ctx.inputs["network"]["grid_index_groups"])',
)
local = local.replace(
    'simulator_fields_before=wire(sim.grn, sim)["simulator_fields"]',
    'simulator_fields_before=wire(ctx.owner, sim)["simulator_fields"]',
)
local = local.replace("owner=owner_evidence(ctx)", "standalone_dispatch=True,source_time_s=t")
source = replace(source, old_functions["local_inputs"], local)
source = replace(
    source,
    'for k in ("f_X_ED", "fgj_X", "cX_cells", "cX_env_o", "cX_mems")',
    'for k in ("f_X_ED","fgj_X","cX_cells","cX_env_o","cX_mems","fenvx","fenvy","cenv","gcx","gcy","fx","fy","div_fa")',
)
source += """

PUBLICATIONS=("extra_rho_cells","extra_rho_env","extra_J_mem","extra_Jenv_x","extra_Jenv_y")
GRID_FIELDS=("X","Y","xypts","delta","map_cell2ecm","map_mem2ecm","M_sum_mems",
             "memSa_per_envSquare","M_divmap_mem2ecm","true_ecm_vol","ecm_vol","rads","R_rads",
             "all_bound_mem_inds","interior_bound_mem_inds","ecm_inds_bound_cell")
material_values=base.material_values
base_validate=base.validate


def build_grid(cells,p,inputs):
    binding=field.bind(inputs["material_definition"]["environment_geometry_definition"])
    g=binding.geometry
    for target,attr in (("X","X_m"),("Y","Y_m"),("xypts","grid_points_m"),
        ("delta","delta_m"),("map_cell2ecm","cell_to_grid"),("map_mem2ecm","membrane_to_grid"),
        ("memSa_per_envSquare","membrane_area_per_site_m2"),("M_divmap_mem2ecm","membrane_divergence_map_m2"),
        ("true_ecm_vol","true_environment_volume_m3")):
        setattr(cells,target,clone(getattr(g,attr)))
"""
emit("src/cells/processes/" + NEW + ".py", source)

native = (
    (ROOT / "validation/betse/betse_sim_grn_native.py").read_text().replace("betse_sim_grn", NEW)
)
native = replace(
    native,
    "from validation.betse import betse_normal_grn_join_native_network as previous",
    "from validation.betse import betse_ecm_grn_native_network as previous\n"
    "from validation.betse import betse_environment_field_native as field_native",
)
# The original ECM factory already supplies literal mover/FD/context bodies.
native = replace(
    native,
    '        ns["stb"] = SimpleNamespace(',
    '        ns["fd"]=SimpleNamespace(**{name:ns[name] for name in ("gradient","divergence","integrator")})\n'
    '        ns["stb"] = SimpleNamespace(',
)
nf = functions(native)
sf = functions(source)
for name in ("validate", "make_context", "snapshot", "restore", "local_inputs", "attach"):
    native = replace(native, nf[name], sf[name])
native += """

PUBLICATIONS=("extra_rho_cells","extra_rho_env","extra_J_mem","extra_Jenv_x","extra_Jenv_y")
GRID_FIELDS=("X","Y","xypts","delta","map_cell2ecm","map_mem2ecm","M_sum_mems",
             "memSa_per_envSquare","M_divmap_mem2ecm","true_ecm_vol","ecm_vol","rads","R_rads",
             "all_bound_mem_inds","interior_bound_mem_inds","ecm_inds_bound_cell")
material_values=previous.material_values


def base_validate(definition,binding):
    pass  # Port admission is independently checked; native is bounded below.


def build_grid(cells,p,inputs):
    code,sites,pins=field_native.capture()
    code["grid"](cells,p)
    code["owner_matrices"](cells)
    code["environment"](cells,p)
"""
# Native admission must not import port material binding. Replace only that
# plumbing with bounded original declaration/shape checks, never source physics.
nv = functions(native)["validate"]
point = nv.index("    binding=material.bind(")
nv = (
    nv[:point]
    + """    definition=inputs["material_definition"]
    external=definition["environment_geometry_definition"]
    ids=external["current_definition"]["ions"]["ids"]
    n=len(external["current_definition"]["geometry"]["cell_ids"])
    m=len(external["current_definition"]["geometry"]["membrane_ids"])
    if not (1<=n<=16 and 1<=m<=128 and 1<=len(ids)<=32):
        raise ValueError("Refuse unbounded original standalone ECM context")
"""
)
native = replace(native, functions(native)["validate"], nv)
native = native.replace("        open=capture_open,", "        open=capture_open,")
# This binding check is not used after replacing native validation.
start = native.index("\ndef base_validate(definition,binding):")
stop = native.index("\ndef build_grid(", start)
native = native[:start] + native[stop:]
# Helpers appended after the main guard would otherwise be undefined during CLI.
main_guard = 'if __name__ == "__main__":\n    main()'
assert main_guard in native
native = native.replace(main_guard, "", 1) + "\n\n" + main_guard + "\n"
emit("validation/betse/" + NEW + "_native.py", native)
print("Reachable standalone ECM source/native emitted; no science executed")
