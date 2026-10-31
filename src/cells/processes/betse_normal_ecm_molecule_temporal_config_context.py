# ruff: noqa: E501
"""Pinned existing ECM context with an early selected parameter constructor.

Only the constructor call and explicit keyword parameter differ from the
existing factory. The original factory remains the default. No completed p is
patched or replaced, and the existing augment creates the actual phase.
"""

import ast
import copy
import dis
import hashlib
import math
import sys
from pathlib import Path
from types import CodeType, FunctionType, SimpleNamespace

import numpy as np

from cells.processes import betse_ecm_grn_join as network

source, Values = network.source, network.Values
ORIGINAL = network.make_context
ORIGINAL_CODE = ORIGINAL.__code__
ORIGINAL_AST = "866a35777f8eeba17d8d69d9af36591837053449136598109c98f754c1d301d7"


def check_original():
    check_live_bindings()
    if network.make_context is not ORIGINAL or ORIGINAL.__code__ is not ORIGINAL_CODE:
        raise ValueError("Changed original ECM context factory")
    node = next(
        n
        for n in ast.parse(Path(network.__file__).read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "make_context"
    )
    if (
        hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
        != ORIGINAL_AST
    ):
        raise ValueError("Upstream context AST changed; selected constructor requires review")
    if construct_context is not CONSTRUCT or CONSTRUCT.__code__ is not CONSTRUCT_CODE:
        raise ValueError("Selected context constructor replaced")
    selected = next(
        n
        for n in ast.parse(Path(__file__).read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "construct_context"
    )
    selected = copy.deepcopy(selected)
    selected.name = "make_context"
    if (
        len(selected.args.kwonlyargs) != 1
        or selected.args.kwonlyargs[0].arg != "parameter_constructor"
        or selected.args.kw_defaults != [None]
    ):
        raise ValueError("Selected context constructor signature drift")
    selected.args.kwonlyargs, selected.args.kw_defaults = [], []
    assignments = [
        n
        for n in selected.body
        if isinstance(n, ast.Assign)
        and len(n.targets) == 1
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id == "p"
    ]
    if (
        len(assignments) != 1
        or not isinstance(assignments[0].value, ast.Call)
        or not isinstance(assignments[0].value.func, ast.Name)
        or assignments[0].value.func.id != "parameter_constructor"
    ):
        raise ValueError("Selected parameter construction drift")
    assignments[0].value.func.id = "SimpleNamespace"
    if ast.dump(selected, include_attributes=False) != ast.dump(node, include_attributes=False):
        raise ValueError("Selected context differs beyond the early constructor hook")


def construct_context(binding, values, definition, packet=None, *, parameter_constructor):
    mb = binding.material_binding
    gb, k = mb.geometry_binding, mb.kernel
    cb, g = gb.current_binding, gb.geometry
    external = gb.definition
    ep = external["parameters"]
    arrays = [np.asarray(value, np.float64) for value in values]
    sim = SimpleNamespace(
        **{attr: arrays[Values._fields.index(key)] for key, attr in source.MATERIAL_PAIRS},
        mdl=len(cb.membrane_ids),
        edl=math.prod(g.shape),
        zs=cb.kernel.valence,
        Dm_cells=k.membrane_diffusion_m2_s,
        D_gj=k.gap_diffusion_m2_s,
        D_env=k.environment_diffusion_m2_s,
        TJ_modulator=k.tight_junction_modulator,
    )
    sim.E_gj_x, sim.E_gj_y = arrays[10][:, 0], arrays[10][:, 1]
    owner = cb.kernel.owner
    cells = SimpleNamespace(
        cell_i=np.arange(len(cb.cell_ids)),
        mem_i=np.arange(len(cb.membrane_ids)),
        mem_to_cells=owner,
        nn_i=k.partner,
        bflags_mems=k.boundary,
        gj_len=k.gap_length_m,
        mem_sa=cb.kernel.membrane_area_m2,
        cell_sa=cb.kernel.cell_area_m2,
        cell_vol=np.asarray(external["geometry"]["cell_volume_m3"], np.float64),
        cell_centres=np.asarray(external["geometry"]["cell_centres_m"], np.float64),
        mem_mids_flat=np.asarray(external["geometry"]["membrane_midpoints_m"], np.float64),
        X=g.X_m,
        Y=g.Y_m,
        xypts=g.grid_points_m,
        delta=g.delta_m,
        map_mem2ecm=g.membrane_to_grid,
        M_sum_mems=cb.kernel.owner_sum,
        memSa_per_envSquare=g.membrane_area_per_site_m2,
        M_divmap_mem2ecm=g.membrane_divergence_map_m2,
        ecm_vol=ep["cell_height_m"] * g.delta_m**2,
    )
    p = parameter_constructor(
        is_ecm=True,
        F=cb.kernel.F_C_mol,
        R=k.R_J_mol_K,
        T=ep["configured_temperature_K"],
        q=ep["q_C"],
        kb=ep["kb_J_K"],
        cell_height=ep["cell_height_m"],
        tm=k.membrane_thickness_m,
        cluster_open=k.cluster_open,
        fast_update_ecm=k.fast_update_ecm,
        sharpness=k.sharpness,
        fluid_flow=False,
        dt=0.0,
    )
    m, e = len(cb.membrane_ids), math.prod(g.shape)
    sim.T = p.T
    sim.rho_channel = np.ones(m)
    sim.gj_block = np.asarray(definition["initial_controls"]["gj_block"], np.float64).copy()
    sim.NaKATP_block = np.asarray(definition["initial_controls"]["NaKATP_block"], np.float64).copy()
    sim.c_env_bound = np.asarray(definition["initial_ion_boundary"], np.float64).copy()
    for key, size in (
        ("extra_rho_cells", len(cb.cell_ids)),
        ("extra_rho_env", e),
        ("extra_J_mem", m),
        ("extra_Jenv_x", e),
        ("extra_Jenv_y", e),
    ):
        setattr(sim, key, np.zeros(size))
    sim.E_env_x, sim.E_env_y = np.zeros(g.shape), np.zeros(g.shape)
    if packet is not None:
        p.dt, sim.T = packet.dt_s, packet.runtime_temperature_K
        sim.rho_channel = packet.channel_multiplier
        sim.c_env_bound = packet.boundary_mol_m3.copy()
        sim.E_env_x, sim.E_env_y = packet.electric_x_source, packet.electric_y_source
    return source.augment(sim, cells, p, definition, list(cb.ion_ids))


CONSTRUCT = construct_context
CONSTRUCT_CODE = CONSTRUCT.__code__
PARAMETER_NAMESPACE = SimpleNamespace

# Live import-time references stay here, never in a checkpoint. The copied
# function has its own globals dictionary; its eight resolved global names
# must still point to the same original objects. No factory is invoked here.
_NETWORK = network
_GLOBAL_BINDINGS = (
    ("np", np),
    ("math", math),
    ("source", source),
    ("Values", Values),
    ("SimpleNamespace", SimpleNamespace),
    ("len", len),
    ("list", list),
    ("setattr", setattr),
)
_FACTORY_NAMESPACES = ((ORIGINAL, vars(network)), (CONSTRUCT, globals()))
_ATTRIBUTE_BINDINGS = (
    ("np.asarray", np, "asarray", np.asarray),
    ("np.arange", np, "arange", np.arange),
    ("np.ones", np, "ones", np.ones),
    ("np.zeros", np, "zeros", np.zeros),
    ("np.float64", np, "float64", np.float64),
    ("math.prod", math, "prod", math.prod),
    ("source.augment", source, "augment", source.augment),
    ("source.MATERIAL_PAIRS", source, "MATERIAL_PAIRS", source.MATERIAL_PAIRS),
    ("Values._fields", Values, "_fields", Values._fields),
)
_PYTHON_BINDINGS = tuple(
    (
        label,
        value,
        value.__code__,
        value.__globals__,
        value.__defaults__,
        value.__kwdefaults__,
        None if value.__kwdefaults__ is None else tuple(value.__kwdefaults__.items()),
        value.__closure__,
    )
    for label, value in (
        ("original", ORIGINAL),
        ("selected", CONSTRUCT),
        ("source.augment", source.augment),
        ("np.ones", np.ones),
    )
)
_MODULE_BINDINGS = (
    ("original", network),
    ("selected", __file__),
    ("source", source),
    ("numpy", np),
    ("math", math),
)


def _loaded_globals(code):
    names = {entry.argval for entry in dis.get_instructions(code) if entry.opname == "LOAD_GLOBAL"}
    for value in code.co_consts:
        if type(value) is CodeType:
            names.update(_loaded_globals(value))
    return names


def check_live_bindings():
    """Refuse changed factory lookups/callables before their first invocation.

    This pins the direct factory lookup surface and its augment boundary, not
    every transitive NumPy/source operation. Full producer/runtime pins and the
    separate actual qualification still apply. External Python defaults and
    globals/code/closure identities are inspected without evaluating them.
    """
    if network is not _NETWORK:
        raise ValueError("Changed context module binding: original factory owner")
    for function, namespace in _FACTORY_NAMESPACES:
        if function.__globals__ is not namespace:
            raise ValueError("Changed context factory globals dictionary binding")
        for name, expected in _GLOBAL_BINDINGS:
            actual = namespace.get(name, function.__builtins__.get(name))
            if actual is not expected:
                raise ValueError("Changed context factory global binding: " + name)
        if _loaded_globals(function.__code__) != {name for name, _ in _GLOBAL_BINDINGS}:
            raise ValueError("Changed context factory global lookup surface")
    for label, owner, name, expected in _ATTRIBUTE_BINDINGS:
        if getattr(owner, name, None) is not expected:
            raise ValueError("Changed context attribute binding: " + label)
    for label, function, code, namespace, defaults, keyword, items, closure in _PYTHON_BINDINGS:
        if (
            type(function) is not FunctionType
            or function.__code__ is not code
            or function.__globals__ is not namespace
            or function.__defaults__ is not defaults
            or function.__kwdefaults__ is not keyword
            or function.__closure__ is not closure
        ):
            raise ValueError("Changed context Python callable binding: " + label)
        if items is not None and (
            set(keyword) != {key for key, _ in items}
            or any(keyword[key] is not expected for key, expected in items)
        ):
            raise ValueError("Changed context callable keyword default binding: " + label)


def binding_record():
    """Closed descriptions of checked bindings; no executable objects or IDs."""
    check_original()
    return dict(
        kind="cells.original_and_selected_ECM_context_runtime_bindings@1",
        globals=tuple(name for name, _ in _GLOBAL_BINDINGS),
        attributes=tuple(label for label, _, _, _ in _ATTRIBUTE_BINDINGS),
        modules={label: _module_record(label, module) for label, module in _MODULE_BINDINGS},
        python_callables={
            label: dict(
                module=function.__module__,
                qualname=function.__qualname__,
                bytecode_sha256=hashlib.sha256(code.co_code).hexdigest(),
                globals_module=namespace["__name__"],
                defaults_and_closure_identity_checked=True,
            )
            for label, function, code, namespace, _, _, _, _ in _PYTHON_BINDINGS
        },
        material_pairs=source.MATERIAL_PAIRS,
        value_fields=Values._fields,
        actual_factory_calls=0,
        scope="direct factory globals/attributes and augment callable boundary; "
        "not transitive native/numerical admission",
    )


def _module_record(label, module):
    if not any(label == name and module is expected for name, expected in _MODULE_BINDINGS):
        raise ValueError("Unbound context module cannot supply provenance")
    path = module if label == "selected" else getattr(module, "__file__", None)
    name = __name__ if label == "selected" else module.__name__
    if path is not None:
        return dict(
            name=name,
            kind="module_file",
            sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        )
    spec = getattr(module, "__spec__", None)
    if name not in sys.builtin_module_names or getattr(spec, "origin", None) != "built-in":
        raise ValueError("Missing source file for a non-builtin context module: " + name)
    return dict(
        name=name,
        kind="interpreter_builtin_module",
        origin="built-in",
        executable_sha256=hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest(),
    )
