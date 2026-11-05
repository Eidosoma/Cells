"""Original full SIM source metadata; compiling never imports or runs BETSE.

The run driver calls the actual retained native methods. This catalog supplies
their complete original code and exact loop/storage boundaries, not another
implementation of the equations, calendar, event laws or solvers.
"""

import ast
import dis
import hashlib
from functools import lru_cache
from types import CodeType

from cells.processes import betse_native_init_first_step_source as transport
from cells.processes import betse_native_init_molecule_channels_source as channels
from cells.processes import betse_native_init_molecule_network_source as network
from cells.processes import betse_native_init_sim_assembly_source as assembly
from cells.processes import betse_native_init_tissue_dynamics as tissue

NATIVE = assembly.NATIVE
# Exact original filenames plus SHA256 necessarily exceed the style width.
# ruff: noqa: E501
PINS = {
    **assembly.PINS,
    **transport.SOURCE_PINS,
    **network.PINS,
    **channels.PINS,
    **tissue.PINS,
    "betse/science/math/toolbox.py": "a2a63fe1f44303fe05d2b1fbcfe9250e4575992f688cbe4cbd7fd99ef99e60a3",
    "betse/util/type/text/string/strjoin.py": "ba85964d929a9080d7ca06e713042c07858c2dd8747e3e1206fbfa8ff2a852e7",
    "betse/util/type/text/string/strs.py": "351a1a8cd61d7942c83cf8c7bffcbf918de9dffab9d58764ffd38e88d88c841c",
}
SIM = "betse/science/sim.py"
METHODS = {
    "report": (SIM, "Simulator.sim_info_report"),
    "run_core": (SIM, "Simulator.run_sim_core"),
    "dynamics": (SIM, "Simulator.init_dynamics"),
    "storage": (SIM, "Simulator.clear_storage"),
    "voltage": (SIM, "Simulator.update_V"),
    "calendar": (SIM, "Simulator._plot_loop"),
    "loop": (SIM, "Simulator._run_sim_core_loop"),
    "sample": (SIM, "Simulator.write2storage"),
    "events": ("betse/science/tissue/tishandler.py", "TissueHandler.fire_events"),
    "global_events": ("betse/science/tissue/tishandler.py", "TissueHandler._fire_events_global"),
    "tissue_events": ("betse/science/tissue/tishandler.py", "TissueHandler._fire_events_tissue"),
    "make_changes": ("betse/science/tissue/tishandler.py", "TissueHandler.makeAllChanges"),
    "reload": ("betse/science/chemistry/molecules.py", "MasterOfMolecules.reinitialize"),
    "noop": ("betse/util/type/contexts.py", "noop_context"),
}


def payload(path):
    file = NATIVE / path
    raw = file.read_bytes()
    if file.is_symlink() or hashlib.sha256(raw).hexdigest() != PINS[path]:
        raise ValueError("Exact original SIM source required: " + path)
    return raw


@lru_cache(maxsize=64)
def _compiled(raw, filename):
    unit = compile(raw, filename, "exec", dont_inherit=True, optimize=0)
    result, pending = [], [unit]
    while pending:
        item = pending.pop()
        result.append((item.co_qualname, item))
        pending.extend(value for value in item.co_consts if type(value) is CodeType)
    return tuple(result)


def codes(path):
    return dict(_compiled(payload(path), str(NATIVE / path)))


def code(role):
    path, qualified = METHODS[role]
    return codes(path)[qualified]


def sites():
    """Source-declared top-level functions/methods, without invoking decorators."""
    result = {}
    for path in PINS:
        tree = ast.parse(payload(path))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                result[(None, node.name)] = path
            elif isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, ast.FunctionDef):
                        key = (node.name, method.name)
                        if key in result and result[key] != path:
                            raise ValueError("Ambiguous original runtime method")
                        result[key] = path
    return result


def import_code(owner, method):
    path = sites()[(owner, method)]
    return codes(path)[method if owner is None else owner + "." + method]


import_sites = sites


def boundaries():
    tree = ast.parse(payload(SIM))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Simulator")
    nodes = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    core, loop = nodes["run_sim_core"], nodes["_run_sim_core_loop"]
    pickles = [
        n
        for n in ast.walk(core)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "self"
        and n.func.attr == "_pickle_phase"
    ]
    loops = [n for n in loop.body if isinstance(n, ast.For)]
    if len(pickles) != 1 or len(loops) != 1 or ast.unparse(loops[0].target) != "t":
        raise ValueError("Original single loop and final pickle boundary required")
    instructions = tuple(dis.get_instructions(code("run_core")))
    stop = tuple(
        i.offset
        for i in instructions
        if i.opname in ("LOAD_ATTR", "LOAD_METHOD") and i.argval == "_pickle_phase"
    )
    sequence = tuple(dis.get_instructions(code("loop")))
    forward = tuple(i for i in sequence if i.opname == "FOR_ITER")
    # Nested native loops also use FOR_ITER; select the original outer calendar.
    outer = next(i for i in forward if i.positions.lineno == loops[0].lineno)
    store = next(
        index
        for index, i in enumerate(sequence)
        if i.offset > outer.offset and i.opname == "STORE_FAST" and i.argval == "t"
    )
    if len(stop) != 1:
        raise ValueError("One exact pre-pickle instruction required")
    return dict(
        stop=stop[0],
        for_iter=outer.offset,
        iteration=sequence[store + 1].offset,
        loop_lines=(loops[0].lineno, loops[0].end_lineno),
        before_pickle_line=pickles[0].lineno,
    )


def source_plan():
    return dict(
        kind="actual_native_FULL_SIM_report_complete_calendar_before_pickle@1",
        files=PINS,
        methods=METHODS,
        boundaries=boundaries(),
        order=(
            "sim_info_report",
            "run_sim_core",
            "init_dynamics",
            "clear_storage",
            "update_V",
            "_plot_loop",
            "original complete loop",
            "normal context exit",
        ),
        equations_and_native_context_unchanged=True,
        no_replacement_calendar_no_selected_stop=True,
        original_flux_inverse_and_explicit_omitted_inverse_are_separate=True,
        endpoint="after_original_loop_and_context_before_native_pickle",
        native_pickle_or_biological_or_checkpoint_admission=False,
    )
