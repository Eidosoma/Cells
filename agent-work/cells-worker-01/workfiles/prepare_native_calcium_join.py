# ruff: noqa: E501
"""Static rectangular-bath source adaptation; leaves all old laws untouched."""

import ast
import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def prepare():
    target = ROOT / "src/cells/processes/betse_normal_calcium_join.py"
    if target.exists():
        raise FileExistsError(target)
    source = (ROOT / "src/cells/processes/betse_normal_catalog_join.py").read_text()
    source = source.replace(
        "from cells.processes import betse_channel_catalog_source as catalog",
        "from cells.processes import betse_channel_catalog_source as catalog\nfrom cells.processes import betse_calcium_atp_source as calcium_source",
    )
    source = source.replace(
        "betse_normal_late_catalog_join_v1_5_0@1",
        "betse_normal_rectangular_bath_calcium_join_v1_5_0@1",
    )
    source = source.replace(
        "cells.betse_normal_catalog_join_inputs@1", "cells.betse_normal_calcium_join_inputs@1"
    )
    source = source.replace(
        "    pump: pump.MaterialTrial\n",
        "    pump: pump.MaterialTrial\n    calcium_handler: object\n",
    )
    start = source.index('    if "Ca" in ib.ion_ids:')
    end = source.index("    result = Binding(", start)
    source = (
        source[:start]
        + """    if "Ca" not in ib.ion_ids or ib.kernel.valence[ib.ion_ids.index("Ca")] != 2:
        raise ValueError("Active CaATP requires an explicitly owned +2 Ca row")
    policy=raw["calcium_handler"]
    if (type(policy) is not dict or set(policy)!={"Ca_dyn","maintained","kinetics","provenance"}
        or type(policy["Ca_dyn"]) is not int or policy["Ca_dyn"]!=0):
        raise MissingCoupledState("ER/buffer handling requires separate complete owned state; Ca_dyn must be explicit0")
    if (type(policy["maintained"]) is not dict or set(policy["maintained"])!={"cATP","cADP","cPi"}
        or type(policy["kinetics"]) is not dict or set(policy["kinetics"])!={"KmCa_Ca","KmCa_ATP","deltaGATP"}
        or not isinstance(policy["provenance"],str) or not policy["provenance"].strip()):
        raise ValueError("Require complete native CaATP maintained pools and kinetics")
    for key,value in (policy["maintained"]|policy["kinetics"]).items():
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError("Require finite original calcium parameter: "+key)
        if key.startswith("Km") and value<=0:raise ValueError("Require positive native calcium Km")
    if (policy["maintained"] != ions.data(pump_binding.definition["maintained"])
        or policy["kinetics"]["deltaGATP"] != pump_binding.kernel.delta_g_J_mol):
        raise ValueError("NaK and CaATP must share the actual source maintained pools/deltaGATP")
"""
        + source[end:]
    )
    # All shape validation is explicit in this new law, never reinterpreted by
    # the frozen scalar-bath state constructor.
    source = source.replace("ions.state(", "vector_state(")
    source = source.replace(
        "def material_step(binding, parent, forcing, live_pump, live):",
        "def material_step(binding, parent, forcing, live_pump, live, live_calcium, *, before_calcium=None):",
    )
    source = source.replace("    network = {}\n", "    network = {}\n    calcium_phase = {}\n", 1)
    marker = "        ib = binding.pump_binding.gated_binding.material_binding\n        caches, calls = list(parent.channel_caches), list(parent.channel_calls)"
    source = source.replace(
        marker,
        """        if type(live_calcium) is not CalciumPacket or ions.record(calcium_packet(binding,**live_calcium._asdict()))!=ions.record(live_calcium) or live_calcium.block.flags.writeable:
            raise ValueError("Require immutable explicit live CaATP alpha/block packet")
"""
        + marker,
    )
    start = source.index(
        '            if binding.definition["calcium_handler"] is not None:\n                observe("calcium_handler_disabled")'
    )
    end = start + len(
        '            if binding.definition["calcium_handler"] is not None:\n                observe("calcium_handler_disabled")'
    )
    source = (
        source[:start]
        + """            i=ib.ion_ids.index("Ca")
            policy=binding.definition["calcium_handler"]
            parameters=dict(policy["maintained"])|dict(policy["kinetics"])|dict(
                alpha_Ca=live_calcium.alpha_Ca,F=ib.kernel.F_C_mol,R=ib.kernel.R_J_mol_K)
            calcium_phase.update(values_before=ions.data(_values(arrays)),
                alpha_Ca=live_calcium.alpha_Ca,parameters=parameters,
                rate_before=parent.calcium_rate_proxy_mol_m2_s,
                rate_after=parent.calcium_rate_proxy_mol_m2_s,
                rho_pump=live_pump.rho_pump,block_unused=live_calcium.block,met_unused=live_pump.met_concs,
                dt_s=forcing.dt_s,runtime_temperature_K=forcing.runtime_temperature_K,
                membrane_before_mM=ions.freeze(membrane[i]),bath_before_mM=ions.freeze(bath[i]),
                voltage_V=ions.freeze(vm),stored_before=ions.freeze(fm),arithmetic=None,
                source_rate_aliases_masked_flux=True,Ca_dyn=0,ER_executed=False)
            if before_calcium is not None:
                before_calcium(ions.freeze(calcium_phase))
            if live_calcium.alpha_Ca>0:
                core=None
                try:
                    core=calcium_source.evaluate(membrane_mM=membrane[i],bath_mM=bath[i],voltage_V=vm,
                        runtime_temperature_K=forcing.runtime_temperature_K,parameters=parameters,
                        block=live_calcium.block,met=live_pump.met_concs)
                except calcium_source.CalciumSourceRefused as error:
                    core=error.partial
                    membrane[i]=core.membrane_after_mM
                    bath[i]=core.bath_after_mM
                    calcium_phase.update(arithmetic=core,source_failure=core.failure,
                        values_after=ions.data(_values(arrays)))
                    observe("calcium_handler_failure",i)
                    raise
                membrane[i]=core.membrane_after_mM
                bath[i]=core.bath_after_mM
                masked=core.flux_mol_m2_s.copy()
                if not ib.kernel.cluster_open:masked[ib.kernel.boundary]=0
                # Source rate is the SAME array as raw flux, masked in place,
                # before the single no-ECM rho multiplication in storage.
                applied=live_pump.rho_pump*masked
                fm[i]+=applied
                calcium_phase.update(arithmetic=core,rate_after=ions.freeze(masked),
                    applied_flux_mol_m2_s=ions.freeze(applied))
            calcium_phase.update(stored_after=ions.freeze(fm),values_after=ions.data(_values(arrays)),
                cache_retained=live_calcium.alpha_Ca<=0,source_completed=True)
            observe("calcium_handler",i)
"""
        + source[end:]
    )
    source = source.replace(
        "            parent.calcium_rate_proxy_mol_m2_s,\n        )\n        trial = MaterialTrial(",
        '            calcium_phase["rate_after"],\n        )\n        trial = MaterialTrial(',
        1,
    )
    source = source.replace(
        'parent, material, tuple(phases), ions.freeze(network), candidate, ""',
        'parent, material, ions.freeze(calcium_phase), tuple(phases), ions.freeze(network), candidate, ""',
    )
    # A finite source result can still contain unused invalid arithmetic; retain
    # it before the strict publication guard, exactly as in the NaK lane.
    source = source.replace(
        "        if any(\n            not np.isfinite(value).all()",
        '        if (calcium_phase.get("arithmetic") is not None and not calcium_phase["arithmetic"].finite) or any(\n            not np.isfinite(value).all()',
        1,
    )
    source = source.replace(
        "            network=ions.freeze(network),\n        ) from error",
        "            network=ions.freeze(dict(network,calcium_handler=calcium_phase)),\n        ) from error",
        1,
    )
    # Advance uses candidate Ca cache and the same exact current/voltage kernel.
    source = source.replace(
        "    live,\n    *,\n    boundary_V,",
        "    live,\n    live_calcium,\n    *,\n    before_calcium=None,\n    boundary_V,",
    )
    source = source.replace(
        "material = material_step(binding, parent, forcing, live_pump, live)",
        "material = material_step(binding, parent, forcing, live_pump, live, live_calcium, before_calcium=before_calcium)",
    )
    source = source.replace(
        "            parent.calcium_rate_proxy_mol_m2_s,\n        )\n        clock =",
        "            material.candidate.calcium_rate_proxy_mol_m2_s,\n        )\n        clock =",
        1,
    )
    # Scalar-returning source update_Co assignments broadcast into rectangular
    # bath rows. Only layout-specific diagnostics need different reduction axes.
    source = source.replace(
        "bath_change = (bath - parent.values.bath_mol_m3) * k.bath_volume_m3",
        "bath_site_change = (bath - parent.values.bath_mol_m3) * k.bath_volume_m3\n            bath_change = np.sum(bath_site_change,axis=1)",
    )
    source = source.replace(
        "source_mixed_bath_residual_mol=bath_change + membrane_transfer / len(vm)",
        "bath_site_change_mol=bath_site_change,\n                    source_mixed_bath_residual_mol=bath_change + membrane_transfer",
    )
    # New state constructor uses the exact same immutable typed values with a
    # separately authenticated rectangular environment shape.
    ion_tree = ast.parse((ROOT / "src/cells/processes/betse_normal_ion_join.py").read_text())
    state = copy.deepcopy(
        next(n for n in ion_tree.body if isinstance(n, ast.FunctionDef) and n.name == "state")
    )
    state.name = "vector_state"

    class Qualify(ast.NodeTransformer):
        def visit_Name(self, n):
            if isinstance(n.ctx, ast.Load) and n.id in ("Values", "State", "digest"):
                return ast.Attribute(
                    value=ast.Name(id="ions", ctx=ast.Load()), attr=n.id, ctx=n.ctx
                )
            if isinstance(n.ctx, ast.Load) and n.id == "_array":
                return ast.Attribute(
                    value=ast.Name(id="current", ctx=ast.Load()), attr="_array", ctx=n.ctx
                )
            return n

    state = Qualify().visit(state)
    for n in ast.walk(state):
        if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "shapes" for t in n.targets
        ):
            n.value.elts[2] = ast.Tuple(
                elts=[ast.Name(id="i", ctx=ast.Load()), ast.Name(id="m", ctx=ast.Load())],
                ctx=ast.Load(),
            )
    # Gate construction is unchanged numerically, with only the state checker
    # redirected to the new vector-bath validator.
    gate_tree = ast.parse((ROOT / "src/cells/processes/betse_normal_gated_join.py").read_text())
    gate = copy.deepcopy(
        next(n for n in gate_tree.body if isinstance(n, ast.FunctionDef) and n.name == "initialize")
    )
    gate.name = "_initialize_gate"
    names = {
        "Binding",
        "binding_record",
        "bind",
        "_rates",
        "Memory",
        "Initialization",
        "GatedJoinRejected",
        "_state",
    }

    class GateQualify(ast.NodeTransformer):
        def visit_Name(self, n):
            if isinstance(n.ctx, ast.Load) and n.id in names:
                return ast.Attribute(
                    value=ast.Name(id="gated", ctx=ast.Load()), attr=n.id, ctx=n.ctx
                )
            return n

        def visit_Attribute(self, n):
            if ast.unparse(n) == "ions.state":
                return ast.Name(id="vector_state", ctx=ast.Load())
            return self.generic_visit(n)

    gate = GateQualify().visit(gate)
    extra = """
class CalciumPacket(NamedTuple):
    alpha_Ca: float
    block: object


def calcium_packet(binding,*,alpha_Ca,block):
    if type(alpha_Ca) not in (int,float) or not math.isfinite(alpha_Ca):
        raise ValueError("Require explicit finite signed native alpha_Ca")
    m=len(binding.pump_binding.gated_binding.material_binding.membrane_ids)
    return CalciumPacket(float(alpha_Ca),current._array(block,(m,),"source-unused CaATP block"))


def initialize_values(binding,values,*,initial_gate_block,initial_NaK_rate,initial_CaATP_rate):
    pb=binding.pump_binding
    material=vector_state(pb.gated_binding.material_binding,values)
    active=_initialize_gate(pb.gated_binding,material,initial_block=initial_gate_block)
    proxy=current._array(initial_NaK_rate,(len(material.values.voltage_V),),"explicit initial NaK cache")
    parent=pump._state(pb,active,proxy)
    return initialize(binding,parent,initial_calcium_rate_proxy_mol_m2_s=initial_CaATP_rate)
"""
    target.write_text(
        source
        + "\n\n"
        + ast.unparse(ast.fix_missing_locations(state))
        + "\n\n"
        + ast.unparse(ast.fix_missing_locations(gate))
        + "\n"
        + extra
    )


if __name__ == "__main__":
    prepare()
