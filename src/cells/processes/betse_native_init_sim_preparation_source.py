"""Original INIT-to-SIM caller/constructor catalog; no native body runs here.

The selected live route begins with an actually completed INIT and a separately
issued, fresh current Parameters owner. It never claims the original loadSim,
autoInit, saved-pickle or complete SimRunner.sim history.
"""

import ast
from types import CodeType

from cells.processes import betse_native_init_retained_world_source as original

NATIVE = original.NATIVE
PINS = {
    name: original.PINS[name]
    for name in (
        "betse/science/simrunner.py",
        "betse/science/phase/phasecls.py",
        "betse/science/sim.py",
    )
}
RUNNER = "betse/science/simrunner.py"
PHASE = "betse/science/phase/phasecls.py"
SIM = "betse/science/sim.py"
SITES = {
    "runner_constructor": (RUNNER, "SimRunner", "__init__"),
    "compatibility": (RUNNER, "SimRunner", "_die_if_seed_differs"),
    "caller": (RUNNER, "SimRunner", "sim"),
    "phase": (PHASE, "SimPhase", "__init__"),
    "phase_kludge": (PHASE, "SimPhase", "_init_kludge"),
    "phase_time": (PHASE, "SimPhase", "_init_kludge_time"),
    "setup": (SIM, "Simulator", "run_sim_core"),
}


def nodes():
    # Reuse the existing exact original-file reader/AST extractor. No original
    # module, decorator, constructor, property or numerical body is evaluated.
    trees = original._trees()
    return {
        name: original._method(trees[path], cls, method)
        for name, (path, cls, method) in SITES.items()
    }


def code(role):
    if role not in ("runner_constructor", "compatibility"):
        raise ValueError("Only the non-mutating runner prefix is selected")
    node = nodes()[role]
    # Compile, never execute, the complete original module. CPython can emit
    # different executable instructions for a method compiled out of class
    # context. Retain the original class context, annotations and decorators.
    unit = compile((NATIVE / RUNNER).read_bytes(), str(NATIVE / RUNNER), "exec", dont_inherit=True)
    cls = next(
        value
        for value in unit.co_consts
        if type(value) is CodeType and value.co_name == "SimRunner"
    )
    return next(
        value for value in cls.co_consts if type(value) is CodeType and value.co_name == node.name
    )


def source_plan():
    selected = nodes()
    caller = selected["caller"]
    constructor = next(
        node
        for node in ast.walk(caller)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "SimPhase"
    )
    keywords = tuple(key.arg for key in constructor.keywords)
    if keywords != ("kind", "cells", "p", "sim", "callbacks"):
        raise ValueError("Original SIM retains the actual Simulator optional argument")
    setup = selected["setup"]
    calls = [
        ast.unparse(node.func)
        for statement in setup.body
        for node in ast.walk(statement)
        if isinstance(node, ast.Call)
    ]
    prefix = (
        "phase.die_unless_kind_init_or_sim",
        "self.init_dynamics",
        "self.clear_storage",
        "self.update_V",
        "self._plot_loop",
    )
    if tuple(calls[:5]) != prefix:
        raise ValueError("Original SIM setup order changed")
    return dict(
        original_files=PINS,
        reused_reader_dependency_files=original.PINS,
        methods={name: (node.lineno, node.end_lineno) for name, node in selected.items()},
        caller_keyword_order=keywords,
        retained_from_INIT=("sim", "cells"),
        current_configuration="explicit separately issued fresh WorldReadyParametersOwner",
        compatibility="original general options/world options comparisons without normalization",
        selected_prefix=(
            "actual SimRunner(p=current_p,callbacks=retained_callbacks)",
            "actual runner._die_if_seed_differs(INIT_p,current_p)",
        ),
        phase_order=(
            "retain callbacks/cells/kind/p/sim",
            "fresh SimPhaseCaches",
            "fresh TissueHandler",
            "sim.dyna = phase.dyna",
            "p._run_sim = True",
            "dt = sim_time_step",
            "resample = sim_time_sampling",
            "total_time = sim_time_total",
            "t_resample = resample / dt",
            "export_dirname = sim_export_dirname",
        ),
        setup_order=prefix,
        later_setup=(
            "init_dynamics reinitializes profiles/events/network owners before clear_storage"
        ),
        stopped_before="SimPhase allocation or mutation of the retained Simulator",
        unavailable=(
            "native loadSim/pickle/autoInit history",
            "terminal-to-SIM forwarding claim",
            "fresh SIM cache/handler ownership on retained Simulator",
            "SIM init_dynamics/storage/electrical/calendar/event execution",
        ),
        original_source_body_execution=False,
    )
