# ruff: noqa: E501
"""Static construction: one event advance with one post-noise mechanics hook."""

import ast
import builtins
import copy
import symtable
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PREFIX = "betse_normal_ecm_event_mechanics"
old_path = ROOT / "src/cells/processes/betse_normal_ecm_event_join.py"
old_code = old_path.read_text()
tree = ast.parse(old_code)
function = copy.deepcopy(
    next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "advance")
)
function.name = "_advance_events"
function.args.kwonlyargs.append(ast.arg(arg="on_mechanics"))
function.args.kw_defaults.append(ast.Constant(value=None))
noise = next(
    n for n in ast.walk(function) if isinstance(n, ast.FunctionDef) and n.name == "on_noise"
)
noise.body += ast.parse("if on_mechanics is not None:\n on_mechanics(current)").body
symbols = next(
    t
    for t in symtable.symtable(old_code, str(old_path), "exec").get_children()
    if t.get_name() == "advance"
)
globals_used = sorted(
    s.get_name()
    for s in symbols.get_symbols()
    if s.is_global() and s.is_referenced() and s.get_name() not in vars(builtins)
)


# Nested scopes also read module globals.
def collect(scope):
    for symbol in scope.get_symbols():
        if (
            symbol.is_global()
            and symbol.is_referenced()
            and symbol.get_name() not in vars(builtins)
        ):
            globals_used.append(symbol.get_name())
    for child in scope.get_children():
        collect(child)


collect(symbols)
globals_used = sorted(set(globals_used))
imports = (
    "from cells.processes.betse_normal_ecm_event_join import (\n"
    + "".join("    " + name + ",\n" for name in globals_used)
    + ")\n"
)
header = '''"""One supplied-state ECM event/noise/steady-mechanics call in native order.

Sampling eligibility is carried; display output is explicitly refused within
this inherited <=16-cell field domain. No physical seed or whole solver claim.
"""

from dataclasses import dataclass

from cells.processes import betse_mechanics_join as mechanics
from cells.processes import betse_normal_ecm_event_join as event

'''
wrapper = """
LAW_ID = "betse_normal_ecm_event_steady_mechanics_v1_5_0@1"
INPUT_KIND = "cells.normal_ecm_event_mechanics_inputs@1"


@dataclass(frozen=True)
class Binding:
    events: object
    mechanics: object
    inputs: object
    identity: str


@dataclass(frozen=True)
class State:
    binding_identity: str
    events: object
    mechanics: object
    sample_state: object
    identity: str


class CompositionRejected(RuntimeError):
    def __init__(self, reason, partial):
        super().__init__(str(reason))
        self.partial = ions.freeze(partial)


def state(binding, events_parent, mechanical, sample_state):
    return State(binding.identity, events_parent, mechanical, ions.freeze(sample_state),
                 ions.digest((binding.identity, events_parent, mechanical, sample_state)))


def bind(inputs):
    raw = ions.data(inputs)
    if set(raw) != {"kind", "case_id", "event_inputs", "mechanics_definition", "mechanics_initial", "sample_policy"} or raw["kind"] != INPUT_KIND:
        raise ValueError("Require a complete separately declared event/mechanics supplied state")
    if raw["sample_policy"] != "calendar_eligibility_only_explicit_display_refusal":
        raise ValueError("Field domain<=16 and quartic display requires>=25; sampling stays held")
    eb = event.bind(raw["event_inputs"])
    policy = raw["mechanics_definition"]["policy"]
    if policy["display_regime"] != "none":
        raise ValueError("Field domain<=16 and quartic display requires>=25; no display widening")
    mb = mechanics.bind(raw["mechanics_definition"])
    if not policy["is_ecm"] or policy["molecules_enabled"] or not policy["grn_enabled"]:
        raise ValueError("Require actual ECM GRN owner and no separate molecule handler")
    fb = eb
    definition = mb.definition
"""
# Reuse the established complete shared-geometry comparisons, without a second
# field binding or any second material/field advance.
mech = ast.parse((ROOT / "src/cells/processes/betse_normal_ecm_mechanics_join.py").read_text())
old_bind = next(n for n in mech.body if isinstance(n, ast.FunctionDef) and n.name == "bind")
start = next(
    i
    for i, n in enumerate(old_bind.body)
    if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "cg"
)
stop = next(
    i
    for i, n in enumerate(old_bind.body)
    if i > start and isinstance(n, ast.If) and "pressure_drives" in ast.unparse(n.test)
)
shared = ast.unparse(ast.Module(body=copy.deepcopy(old_bind.body[start:stop]), type_ignores=[]))
wrapper += "\n".join("    " + line for line in shared.splitlines()) + "\n"
wrapper += '''    for packet in eb.inputs["steps"]:
        if packet["material"]["dt_s"] != p["dt_s"] or p["dt_s"] != eb.calendar.dt_s:
            raise ValueError("Require the same native phase dt for events, material and mechanics")
        for drive, cached in (("velocity_x_m_s", "u_env_x"), ("velocity_y_m_s", "u_env_y")):
            values = np.asarray(packet["material"][drive])
            if np.any(values != 0) or not np.array_equal(values, np.asarray(raw["mechanics_initial"][cached])):
                raise ValueError("Disabled fluid needs shared held-zero velocity stores")
    mechanics.state(mb, raw["mechanics_initial"])
    return Binding(eb, mb, ions.freeze(raw), ions.digest((LAW_ID, eb.identity, mb.identity, raw)))


def verify(binding, parent):
    if type(parent) is not State or parent.binding_identity != binding.identity or parent.identity != ions.digest((binding.identity, parent.events, parent.mechanics, parent.sample_state)):
        raise ValueError("Require the complete unchanged event/mechanics parent")
    mechanics._verify(binding.mechanics, parent.mechanics)
    if parent.events.clock.call_index != parent.mechanics.step_index:
        raise ValueError("Event/material/mechanics counters must name the same source call")


def sample_state(binding, index):
    eligible = bool(calendars.dense(binding.events.calendar).sampled[index])
    return dict(source_call=index, source_time_s=float(calendars.dense(binding.events.calendar).event_label_s[index]),
                native_calendar_eligible=eligible, display_attempted=False, display_completed=False,
                display_status="held_separate_display_domain_required" if eligible else "not_eligible",
                maximum_field_cells=16, minimum_quartic_display_cells=25)


def initialize(binding, *, after_cold=None, before_field=None):
    mechanical = mechanics.state(binding.mechanics, ions.data(binding.inputs["mechanics_initial"]))
    try:
        initialized = event.initialize(binding.events, after_cold=after_cold, before_field=before_field)
        return state(binding, initialized, mechanical,
                     dict(source_call=None, source_time_s=None, native_calendar_eligible=False,
                          display_attempted=False, display_completed=False, display_status="before_first_call",
                          maximum_field_cells=16, minimum_quartic_display_cells=25))
    except Exception as error:
        raise CompositionRejected(error, dict(stage="cold_or_bootstrap", mechanics_parent=mechanical,
                                              inputs=binding.inputs, event_partial=getattr(error,"partial",None))) from error


def mechanics_input(binding, parent, ctx, index):
    geometry = binding.mechanics.definition["geometry"]
    previous = parent.events.field
    molecules = ctx.sim.grn.core.molecules
    names = list(molecules)
    return dict(
        receipt=dict(stage=mechanics.FIELD_STAGE,
                     geometry_epoch=binding.mechanics.definition["provenance"]["geometry_epoch"],
                     cell_ids=geometry["cell_ids"], environment_ids=geometry["environment_ids"],
                     source_step=index, deferred_material_voltage_commit_done=False),
        clock_s=float(parent.events.clock.source_times_s[index]), dt_s=binding.events.calendar.dt_s,
        temperature_K=float(ctx.sim.T), pressure_Pa=np.array(ctx.sim.P_cells, copy=True),
        electric_field_V_m=np.asarray(previous.voltage.values.cell_field_xy_V_m).T,
        current_density_A_m2=np.asarray(previous.current.values.cell_current_xy_A_m2).T,
        charge_density_C_m3=previous.current.values.charge_density_C_m3,
        conductivity_S_m=binding.events.material_binding.geometry_binding.cache.sigma_S_m,
        primary_ids=list(binding.events.material_binding.geometry_binding.current_binding.ion_ids),
        primary_cell_mM=np.array(ctx.sim.cc_cells,copy=True), primary_env_mM=np.array(ctx.sim.cc_env,copy=True),
        molecule_ids=[], molecule_cell_mM=[], molecule_env_mM=[], grn_ids=names,
        grn_cell_mM=[np.array(molecules[name].c_cells,copy=True) for name in names],
        grn_env_mM=[np.array(molecules[name].c_env,copy=True) for name in names], sample=False)


def advance(binding, parent, *, before_mechanics=None, after_mechanics=None, **callbacks):
    holder = {}
    try:
        verify(binding,parent)
        index = parent.events.clock.call_index

        def on_mechanics(ctx):
            incoming = mechanics_input(binding,parent,ctx,index)
            holder["mechanics_input"] = ions.freeze(incoming)
            holder["actual_event_pressure"] = ions.freeze(event.events.event_snapshot(ctx.sim))
            if before_mechanics is not None:
                before_mechanics(dict(mode="mechanics", definition=binding.mechanics.definition,
                                      initial=ions.data(parent.mechanics.cache), steps=[incoming]))
            try:
                trial = mechanics.step(binding.mechanics,parent.mechanics,incoming)
            except Exception as error:
                holder["mechanics_failure"] = getattr(error,"trial",None)
                raise
            holder["mechanics_trial"] = trial
            if after_mechanics is not None:
                after_mechanics(trial)

        returned = _advance_events(binding.events,parent.events,on_mechanics=on_mechanics,**callbacks)
        holder["complete_event_return"] = returned
        candidate = state(binding,returned[0],holder["mechanics_trial"].candidate,sample_state(binding,index))
        verify(binding,candidate)
        return candidate, dict(event_return=returned, **holder, sample_state=candidate.sample_state)
    except Exception as error:
        raise CompositionRejected(error, dict(stage="event_noise_mechanics_material_field",parent=parent,
            available=holder,event_partial=getattr(error,"partial",None),reason=str(error))) from error


def sample(binding,parent):
    """Preserve the reached post-field state before explicit display refusal."""
    verify(binding,parent)
    stage = "sample_display_domain" if parent.sample_state["native_calendar_eligible"] else "sample_clock"
    raise CompositionRejected(ValueError("Field domain<=16 and quartic display requires>=25; display refused"),
        dict(stage=stage,parent=parent,sample_state=parent.sample_state,available_field=parent.events.field,
             available_mechanics=parent.mechanics,display_completed=False,physical_geometry_rebuilt=False))
'''
source = (
    header + imports + "\n" + ast.unparse(ast.fix_missing_locations(function)) + "\n\n" + wrapper
)
p = ROOT / "src/cells/processes" / (PREFIX + ".py")
with p.open("x") as stream:
    stream.write(source)
print(p)
