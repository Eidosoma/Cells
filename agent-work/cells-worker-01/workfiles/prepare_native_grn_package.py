# ruff: noqa: E501 -- literal source templates are formatted in their outputs.
"""Emit original GRN lifecycle/dispatch bodies and separate outer/native files."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
OLD, NEW = "betse_normal_molecule", "betse_normal_grn"


def write(path, text):
    with (ROOT / path).open("x") as stream:
        stream.write(text)


def statement(text):
    return ast.parse(text).body[0]


class Clean(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.decorator_list = []
        node.returns = None
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
        return self.generic_visit(node)


def original_nodes(root):
    network = ast.parse((root / "science/chemistry/networks.py").read_text())
    core = next(
        node
        for node in network.body
        if isinstance(node, ast.ClassDef) and node.name == "MasterOfNetworks"
    )
    core = Clean().visit(copy.deepcopy(core))
    core.body = [
        node
        for node in core.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        in {
            "__init__",
            "read_substances",
            "tissue_init",
            "write_reactions_env",
            "create_reaction_matrix_env",
            "bal_charge",
        }
    ]
    core.bases = [ast.parse("molecule_source._Network", mode="eval").body]
    gene = ast.parse((root / "science/chemistry/gene.py").read_text())
    owner = Clean().visit(
        copy.deepcopy(
            next(
                node
                for node in gene.body
                if isinstance(node, ast.ClassDef) and node.name == "MasterOfGenes"
            )
        )
    )
    owner.body = [
        node
        for node in owner.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"__init__", "read_gene_config", "reinitialize"}
    ]
    mapping = ast.parse((root / "util/type/iterable/mapping/mapcls.py").read_text())
    mappings = [
        Clean().visit(copy.deepcopy(node))
        for node in mapping.body
        if isinstance(node, ast.ClassDef) and node.name in {"DynamicValue", "DynamicValueDict"}
    ]
    plot = Clean().visit(
        copy.deepcopy(
            next(
                node
                for node in ast.parse((root / "science/chemistry/netplot.py").read_text()).body
                if isinstance(node, ast.FunctionDef) and node.name == "set_net_opts"
            )
        )
    )
    sim = ast.parse((root / "science/sim.py").read_text())
    init = copy.deepcopy(
        next(node for node in ast.walk(sim) if isinstance(node, ast.If) and node.lineno == 884)
    )
    dispatch = copy.deepcopy(
        next(node for node in ast.walk(sim) if isinstance(node, ast.If) and node.lineno == 1306)
    )

    class Observe(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call):
                name = ast.unparse(node.value.func)
                if name.startswith("self.grn.core."):
                    stage = name.rsplit(".", 1)[-1]
                    return [
                        node,
                        statement(
                            "self.grn.core._observe_dispatch(" + repr(stage) + ",self,phase)"
                        ),
                    ]
            return node

    dispatch = Observe().visit(dispatch)
    wrappers = []
    for name, body in (("initialize_owner", init), ("dispatch", dispatch)):
        function = ast.parse("def " + name + "(self,t,phase,cells,p):\n    pass\n").body[0]
        function.body = [body]
        wrappers.append(function)
    return mappings + [plot, core, owner] + wrappers


header = '''# ruff: noqa: B007, B905, E501
"""Genuine configured MasterOfGenes initialization and normal GRN dispatch.

Scientific bodies are literal; neutral all-target no-ECM scope is explicit.
Hot state hydration preserves every public owner/core/molecule field.
"""
import copy
from collections import OrderedDict
from collections.abc import MutableMapping
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_molecule_source as molecule_source
from cells.processes import betse_normal_network_join_source as feedback_source

logs = SimpleNamespace(log_info=lambda *_: None, log_warning=lambda *_: None)
tex_val = str
types = SimpleNamespace(trim=repr)
MappingMutableType = MutableMapping
BetseMethodUnimplementedException = NotImplementedError
BetseSimConfException = ValueError
controls = molecule_source.controls
snapshot = molecule_source.snapshot
stb = molecule_source.stb

def _outside_scope(*args, **kwargs):
    raise ValueError("Separate mitochondria, asymmetry, optimizer or profile state is required")

Mito = _outside_scope
mods = SimpleNamespace()

class Molecule(molecule_source._Molecule):
    pass

'''
write(
    "src/cells/processes/" + NEW + "_source.py",
    header
    + ast.unparse(ast.fix_missing_locations(ast.Module(body=original_nodes(PIN), type_ignores=[])))
    + "\n",
)
outer = (ROOT / ("src/cells/processes/" + OLD + "_join.py")).read_text().replace(OLD, NEW)
outer = outer.replace(
    "betse_normal_native_molecule_chemistry_transport_v1_5_0@1",
    "betse_normal_native_grn_owner_dispatch_v1_5_0@1",
)
needle = '        network_source.initial_cache(binding.definition["network"]),'
assert outer.count(needle) == 1
outer = outer.replace(needle, "        grn_cache,", 1)
needle = "    return _state(\n        binding,\n        parent,\n        caches,"
assert outer.count(needle) == 1
outer = outer.replace(
    needle,
    """    try:
        grn_cache = network_source.initialize_cache(binding.definition["network"], binding.pump_binding.gated_binding.material_binding, parent.gated.material.values)
    except network_source.GRNInitializationRefused as error:
        raise ChannelJoinRejected(error, stage="grn_initialization", parent=parent, initialization=error.partial) from error
"""
    + needle,
    1,
)
needle = (
    "                    cluster_open=ib.kernel.cluster_open,\n                    geometry=dict("
)
assert outer.count(needle) == 1
outer = outer.replace(
    needle,
    "                    cluster_open=ib.kernel.cluster_open,\n                    ion_Dm=ib.kernel.membrane_diffusion_m2_s,\n                    geometry=dict(",
    1,
)
# New scope has no late channels/transporters; execute the actual GRN guarded
# block in their place, including its own clear and real owner flags.
start = outer.index("            extra = core.extra_J_mem\n")
end = outer.index("        material = _pump_material_step(", start)
replacement = """            writes = []
            core._observe_control = lambda name, value, actual: writes.append(ions.freeze(dict(rule_id=name,target=core.modulators[name].target_label,value=np.array(value,copy=True),gj_block=np.array(actual.gj_block,copy=True),NaKATP_block=np.array(actual.NaKATP_block,copy=True))))
            dispatch_stages = []

            def dispatched(stage, actual, actual_phase):
                dispatch_stages.append(stage)
                observe("grn_" + stage)
                if stage == "clear_run_loop":
                    feedback.update(
                        values_before=ions.data(_values(arrays)), controls_before=effective_controls,
                        molecule_states_before=network_source.snapshot(core.molecules),
                        molecular_geometry=dict(owner=ib.kernel.owner,partner=ib.kernel.partner,boundary=ib.kernel.boundary,membrane_area_m2=ib.kernel.area_m2,cell_volume_m3=ib.kernel.cell_volume_m3,owner_sum=ib.kernel.owner_sum,gap_length_m=ib.kernel.gap_length_m,radius_m=binding.definition["network"]["radius_m"]),
                        configured_temperature_K=ib.kernel.configured_temperature_K,
                        membrane_thickness_m=ib.kernel.membrane_thickness_m,bath_volume_m3=ib.kernel.bath_volume_m3,cluster_open=ib.kernel.cluster_open,gap_open=opening.copy(),
                        cache_before=parent.network_cache, scheduled_control_outputs_supplied=scheduled_controls is not None,
                        definition=binding.definition["network"], ion_ids=ib.ion_ids,valence=ib.kernel.valence,
                        runtime_temperature_K=forcing.runtime_temperature_K,F=ib.kernel.F_C_mol,R=ib.kernel.R_J_mol_K,dt_s=forcing.dt_s,
                        incoming_channel_current_A_m2=core.extra_J_mem.copy(),phase_kind=live.phase_kind,substances_affect_charge=live.substances_affect_charge,
                        conditioned_before_model_network=True, executed_chemistry=False,control_writes=writes,source_completed=False,
                        grn_owner=network_source.owner_evidence(actual), cold_initialization=False,
                    )
                    if before_network is not None:
                        before_network(ions.freeze(feedback))
            core._observe_dispatch = dispatched
            try:
                with np.errstate(all="ignore"):
                    network_source.dispatch(sim,0.0,phase,geometry,p)
                feedback.update(source_completed=True, configured_chemistry_run_loop_completed=True)
            finally:
                feedback.update(cache_after=network_source.cache(core),rhs=core.rhs,molecule_frames=tuple(core.molecule_frames),mover_frames=tuple(core.mover_frames),molecule_states_after=network_source.snapshot(core.molecules),
                    chemical_rhs_evaluated=any(row["stage"]=="rhs_ready" for row in core.molecule_frames),
                    executed_chemistry=any(row["stage"]=="rhs_ready" for row in core.molecule_frames) and (bool(binding.definition["network"]["reactions"]) or any(row["growth"]["enabled"] for row in binding.definition["network"]["molecules"])),
                    molecular_transports_completed=sum(row["stage"]=="transport_after" for row in core.molecule_frames), values_after=ions.data(_values(arrays)),
                    controls_after=dict(gj_block=np.array(sim.gj_block,copy=True),NaKATP_block=np.array(sim.NaKATP_block,copy=True)),
                    grn_dispatch_stages=tuple(dispatch_stages), grn_owner_after=network_source.owner_evidence(sim))
            feedback["controls_after"] = network_source.controls(ions.data(feedback["controls_after"]),len(vm))
            feedback["cache_after"] = network_source.checked_cache(feedback["cache_after"],binding.definition["network"])
            network.update(values_before=network_values_before,values_after=_values(arrays),extra_current_A_m2=ions.freeze(core.extra_J_mem),extra_charge_C_m3=ions.freeze(core.extra_rho_cells),substances_affect_charge=live.substances_affect_charge,
                current_publication="replace" if live.substances_affect_charge else "retain incoming",aliases_follow_live_rows=True,user_molecules=len(core.molecules),reactions=len(core.reactions),energy_charge=ions.freeze(core.chi),ordinary_Dm_unchanged=True,channel_flux_added_to_ordinary_storage=False,source_channel_flux_boundary_mask=False)
            observe("network_publish")

"""
outer = outer[:start] + replacement + outer[end:]
write("src/cells/processes/" + NEW + "_join.py", outer)
for suffix in ("native.py", "native_helpers.py"):
    text = (ROOT / ("validation/betse/" + OLD + "_join_" + suffix)).read_text().replace(OLD, NEW)
    write("validation/betse/" + NEW + "_join_" + suffix, text)
print("Created separate original GRN lifecycle/dispatch and outer/native skeletons; stdlib only")
