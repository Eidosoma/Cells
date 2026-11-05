"""Pinned original SIM caller selection; compile never executes a native body."""

import ast
import copy
import hashlib
import sys
from functools import lru_cache
from types import CodeType, FunctionType, ModuleType

from validation.betse import native_init_terminal_reference as initial

RUNNER = "betse/science/simrunner.py"
ENTRY = "_retained_init_sim_reference"
EPOCH = "original_full_SIM_body_end_before_next_FOR_ITER"
OBSERVATION_KIND = "cells.original_SIM_iteration_observation@2"
ELECTRIC_FIELDS = ("E_cell_x", "E_cell_y", "E_env_x", "E_env_y", "Emc", "Eme", "v_env", "Phi_b")
GJ_FIELDS = ("gjopen", "gj_block", "vgj")
GJ_CORE_FIELDS = ("alpha", "beta", "gjopen")
EVENT_METHODS = {
    "betse.science.tissue.tishandler": (
        "fire_events",
        "_fire_events_global",
        "_fire_events_tissue",
    ),
    "betse.science.tissue.event.tiseveabc": ("fire",),
    "betse.science.tissue.event.tisevevolt": ("fire",),
}
OBSERVATION_PINS = {
    "betse/science/sim.py": ("02a9a049b5daa5cf6bc543332aa89437f58a4700ed31310abc3ee13697f22d43"),
    "betse/science/channels/gap_junction.py": (
        "17b4bd95ea8801c0907a8363d71a194d14292df5f25509f9f353397f91d39bbd"
    ),
    "betse/science/chemistry/networks.py": (
        "e32741a04c08812342461d18c80676153a6316bbd6bb958861defb23cb321177"
    ),
    "betse/science/physics/ion_current.py": (
        "a9a82ef377853c3e83466c312e508fdb33cae28237c5310a00fb50df3f56bc9f"
    ),
    "betse/science/tissue/tishandler.py": (
        "057ddab87be773e5d338d0681bd503b12aee02861be0902d6ef46e1133d42f54"
    ),
    "betse/science/tissue/event/tiseveabc.py": (
        "490e9e10f3ff713878145bc332a79a3b11bf0d7650238d31d7ff1032e85205a6"
    ),
    "betse/science/tissue/event/tisevevolt.py": (
        "28e1124a729bfbea9a3c4ce6821a93f419a0b82fadc6342d4ce9ab648d02b29b"
    ),
    "betse/science/tissue/event/tisevecut.py": (
        "95056b3486323f025b9a8ac2777073911b6303b930f23efaf12ec4937cf5c1a6"
    ),
}
CONTEXTS = "betse/util/type/contexts.py"
CONTEXT_SHA256 = "66fad70e4b3458f3d24e66c93c741628112be7ba591d745e034529caaa8da8ef"
TERMINAL_METHODS = {
    "phase": ("betse/science/phase/phasecls.py", "SimPhase.__init__"),
    "report": ("betse/science/sim.py", "Simulator.sim_info_report"),
    "core": ("betse/science/sim.py", "Simulator.run_sim_core"),
    "calendar": ("betse/science/sim.py", "Simulator._plot_loop"),
    "loop": ("betse/science/sim.py", "Simulator._run_sim_core_loop"),
    "context": (CONTEXTS, "noop_context"),
}


@lru_cache(maxsize=12)
def _terminal_compiled(raw, relative, mode):
    tree, _ = initial.selected_tree(relative, raw, mode)
    unit = compile(tree, str(initial.NATIVE_ROOT / relative), "exec", dont_inherit=True)
    pending = [unit]
    codes = {}
    while pending:
        code = pending.pop()
        codes[code.co_qualname] = code
        pending.extend(v for v in code.co_consts if type(v) is CodeType)
    return tuple(codes.items())


def terminal_code(role, mode):
    relative, qualified = TERMINAL_METHODS[role]
    raw, _ = initial._read(initial.NATIVE_ROOT / relative, initial.MAX_FILE_BYTES)
    expected = CONTEXT_SHA256 if relative == CONTEXTS else initial.CRITICAL[relative]
    initial._require(
        initial._sha(raw) == expected, "Original terminal witness source changed", "source"
    )
    return dict(_terminal_compiled(raw, relative, mode))[qualified]


def terminal_plan():
    return dict(
        kind="cells.original_SIM_terminal_observation@1",
        epoch=EPOCH,
        methods={name: list(value) for name, value in TERMINAL_METHODS.items()},
        context_source=dict(path=CONTEXTS, sha256=CONTEXT_SHA256),
        required_order=[
            "phase",
            "report",
            "core",
            "calendar",
            "context_yield",
            "loop_return",
            "context_return",
            "core_return",
            "caller_return",
        ],
        required_events=[
            [role, boundary]
            for role, boundary in (
                ("caller", "enter"),
                ("phase", "enter"),
                ("phase", "return"),
                ("report", "enter"),
                ("report", "return"),
                ("core", "enter"),
                ("calendar", "enter"),
                ("calendar", "return"),
                ("context", "enter"),
                ("context", "yield"),
                ("loop", "enter"),
                ("loop", "return"),
                ("context", "enter"),
                ("context", "return"),
                ("core", "return"),
                ("caller", "return"),
            )
        ],
        full_original_calendar=True,
        no_animation_context_only=True,
        FAST_unsupported=True,
        native_pickle_entered=False,
        normal_selected_core_prefix_return=True,
        ordinary_saved_caller_or_checkpoint_admission=False,
    )


def observation_plan():
    """Pinned read roster, not a normalized solver or native owner issuer."""
    attrs = set()
    for name, expected in OBSERVATION_PINS.items():
        raw, _ = initial._read(initial.NATIVE_ROOT / name, initial.MAX_FILE_BYTES)
        initial._require(
            hashlib.sha256(raw).hexdigest() == expected,
            "Original SIM observation source changed",
            "source",
        )
        attrs.update(
            node.attr for node in ast.walk(ast.parse(raw)) if isinstance(node, ast.Attribute)
        )
    initial._require(
        set((*ELECTRIC_FIELDS, *GJ_FIELDS, *GJ_CORE_FIELDS)) <= attrs,
        "Original native observation roster changed",
        "source",
    )
    return dict(
        kind=OBSERVATION_KIND,
        epoch=EPOCH,
        native_sources=dict(OBSERVATION_PINS),
        electric_fields=list(ELECTRIC_FIELDS),
        gap_junction_fields=list(GJ_FIELDS),
        gap_junction_core_fields=list(GJ_CORE_FIELDS),
        event_methods={name: list(methods) for name, methods in EVENT_METHODS.items()},
        channels=(
            "actual molecules/grn core.channels roster and each actual channel_core dictionary"
        ),
        events="actual body entry/return/unwind and current two event-object dictionaries",
        missing="explicit present=False; never zero-filled or inferred from parameter values",
        identity="separate process-local forensics; never a cross-process equality key",
        actual_body_or_RNG_execution=False,
    )


def selected():
    path = initial.NATIVE_ROOT / RUNNER
    raw, _ = initial._read(path, initial.MAX_FILE_BYTES)
    initial._require(
        hashlib.sha256(raw).hexdigest() == initial.CRITICAL[RUNNER],
        "Original SIM caller source changed",
        "source",
    )
    node = copy.deepcopy(initial._method(ast.parse(raw), "SimRunner", "sim"))
    initial._require(
        len(node.body) == 10 and ast.get_docstring(node) is not None,
        "Exact original SIM caller roster required",
        "source",
    )
    initial._require(
        ast.unparse(node.body[4].value) == "fh.loadSim(self._p.init_pickle_filename)"
        and ast.unparse(node.body[5].value) == "self._die_if_seed_differs(p_old, self._p)"
        and ast.unparse(node.body[7].value) == "sim.sim_info_report(phase)"
        and ast.unparse(node.body[8].value) == "sim.run_sim_core(phase)",
        "Original SIM data/compatibility/body boundary changed",
        "source",
    )
    retained = [copy.deepcopy(node.body[i]) for i in (1, 2, 5, 6, 7, 8, 9)]
    declaration = dict(
        original_file=RUNNER,
        original_sha256=initial.CRITICAL[RUNNER],
        original_method="SimRunner.sim",
        entry=ENTRY,
        omitted_statements=[dict(index=i, line=node.body[i].lineno) for i in (0, 3, 4)],
        omitted="docstring, file/autoInit branch and loadSim assignment only",
        retained_statement_sha256=hashlib.sha256(
            ast.dump(ast.Module(body=retained, type_ignores=[]), include_attributes=False).encode()
        ).hexdigest(),
        current_parameters="fresh original Parameters.make from unchanged execution config",
        retained_data="actual same-process successful INIT sim/cells/old_p only",
        full_loadSim_autoInit_pickle_or_checkpoint_history=False,
    )
    node.name, node.decorator_list, node.body = ENTRY, [], retained
    node.args.args.extend(ast.arg(arg=name) for name in ("sim", "cells", "p_old"))
    unit = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    code = compile(unit, str(path), "exec", dont_inherit=True)
    body = next(
        value for value in code.co_consts if type(value) is CodeType and value.co_name == ENTRY
    )
    return body, declaration


def bind(module):
    """Use the actual imported original globals, never inspection dictionaries."""
    initial._require(
        type(module) is ModuleType
        and sys.modules.get("betse.science.simrunner") is module
        and type(module.__loader__) is initial.OriginalPackage,
        "Actual original SimRunner module namespace required",
        "source",
    )
    module.__loader__.verify()
    code, _ = selected()
    return FunctionType(code, vars(module))


def source_plan():
    _, declaration = selected()
    return dict(
        caller=declaration,
        epoch=EPOCH,
        phase_kind="genuine original SimPhaseKind.SIM",
        phase_constructor=(
            "original SimPhase(...,sim=actual_INIT_sim,cells=actual_INIT_cells,p=fresh_p)"
        ),
        phase_helpers_unchanged=["_init_kludge", "_init_kludge_time"],
        core="original parent-loader run_sim_core prefix, before its native pickle",
        normal_calendar_and_transport_bodies_unchanged=True,
        missing_new_original_imports_refuse=True,
        original_files={
            name: initial.CRITICAL[name]
            for name in (RUNNER, "betse/science/phase/phasecls.py", "betse/science/sim.py")
        },
        numerical_solver_or_flux_repair=False,
        observation=observation_plan(),
        terminal_observation=terminal_plan(),
    )
