"""Authenticated private parent runtime with explicit standalone flow ownership.

Loading this module evaluates no scientific module. Parent execution and NumPy
imports occur only when an explicitly selected runtime is constructed.
"""

import copy
import hashlib
import itertools
import sys
import types
from contextlib import contextmanager
from pathlib import Path

INPUT_KIND = "cells.betse_standalone_grn_flow_join_inputs@1"
PARENTS = {
    "production": (
        "src/cells/processes/betse_ecm_sim_grn.py",
        "2a4d93becc61379a3bb68c3a2aef6bb9ac674d3be67e55a972e9e4fde8294a3c",
    ),
    "native": (
        "validation/betse/betse_ecm_sim_grn_native.py",
        "24c2ced2f626b881fbf2e8378cb661bbce28f8defc84d47269f6facf679111bd",
    ),
    "reference": (
        "validation/betse/betse_ecm_sim_grn_reference.py",
        "b00752ff2f39f0fe933918288479dcc1518a29e0dc53334106ef5deb91b273da",
    ),
}
EXTRA_FIELDS = (
    "P_cells",
    "PP",
    "E_cell_x",
    "E_cell_y",
    "J_cell_x",
    "J_cell_y",
    "rho_cells",
    "u_cells_x",
    "u_cells_y",
    "J_env_x",
    "J_env_y",
    "u_env_x",
    "u_env_y",
)
CONFIGURATION_KEYS = ("recalculate fluid flow", "recalculate fluid")
_SERIAL = itertools.count()


def parent_view(inputs):
    """Reuse only the parent's unchanged common admission, before execution."""
    view = copy.deepcopy(inputs)
    view["kind"] = "cells.betse_ecm_sim_grn_inputs@1"
    view.pop("flow_state")
    view.pop("presentation")
    view["scope"]["fluid"] = False
    view["network"]["scope"]["fluid"] = False
    view["network"]["scope"]["standalone"] = False
    for name in CONFIGURATION_KEYS:
        view["network"]["configuration"].pop(name)
    for call in view["calls"]:
        call.pop("flow_fault")
    return view


def nonfinite_arrays(value, path="snapshot"):
    """Retain all numeric source arrays before refusing a nonfinite candidate."""
    from collections.abc import Mapping

    import numpy as np

    if hasattr(value, "dtype") and hasattr(value, "shape"):
        return (
            [dict(path=path, shape=list(value.shape), dtype=value.dtype.str)]
            if value.dtype.kind in "f" and not np.isfinite(value).all()
            else []
        )
    if isinstance(value, Mapping):
        return [
            row
            for key, item in value.items()
            for row in nonfinite_arrays(item, path + "/" + str(key))
        ]
    if isinstance(value, (list, tuple)):
        return [
            row
            for index, item in enumerate(value)
            for row in nonfinite_arrays(item, path + "/" + str(index))
        ]
    return []


def warning_records(records):
    return [
        dict(
            category=item.category.__name__,
            message=str(item.message),
            filename=item.filename,
            lineno=item.lineno,
        )
        for item in records
    ]


@contextmanager
def observe_flow_execution(parent):
    """Observe actual returned/failed source locals without changing its code."""
    previous = sys.gettrace()

    def trace(frame, event, arg):
        ctx = parent._ACTIVE
        if (
            ctx is not None
            and frame.f_code.co_name == "run_core_sim"
            and (
                frame.f_locals.get("self") is ctx.owner and frame.f_locals.get("phase") is ctx.phase
            )
            and event in ("exception", "return")
        ):
            ctx.trace["flow_source_frames"].append(
                dict(
                    event=event,
                    method="MasterOfGenes.run_core_sim",
                    actual_mean_concentration=parent.clone(frame.f_locals.get("cc")),
                    actual_mean_valence=parent.clone(frame.f_locals.get("zz")),
                    actual_velocity_x=parent.clone(ctx.sim.u_env_x),
                    actual_velocity_y=parent.clone(ctx.sim.u_env_y),
                    current_x_present=hasattr(ctx.sim, "J_env_x"),
                    current_y_present=hasattr(ctx.sim, "J_env_y"),
                    fluid_flow=ctx.p.fluid_flow,
                    exception_type=arg[0].__name__ if event == "exception" else None,
                    exception_reason=str(arg[1]) if event == "exception" else None,
                    read_only_observation=True,
                )
            )
        return trace

    try:
        sys.settrace(trace)
        yield
    finally:
        sys.settrace(previous)


def load_parent(role):
    relative, expected = PARENTS[role]
    root = Path(__file__).resolve().parents[2]
    path = root / relative
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != expected:
        raise ValueError("Changed authenticated standalone parent: " + relative)
    name = (
        "validation.betse.betse_standalone_grn_flow_join_inherited_"
        + role
        + "_"
        + str(next(_SERIAL))
    )
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    try:
        exec(compile(source, str(path), "exec", dont_inherit=True), vars(module))
    except BaseException:
        del sys.modules[name]
        raise
    module.__source_provenance__ = dict(
        role=role,
        source_file=str(path),
        source_relative_path=relative,
        source_sha256=expected,
        private_module_name=name,
        parent_compiled_verbatim=True,
        existing_namespace_patched=False,
    )
    return module


def install(role):
    """Keep parent equations/code intact; each runtime owns private globals."""
    if role not in {"production", "native"}:
        raise ValueError("Select only an explicitly constructed source runtime")
    import numpy as np

    parent = load_parent(role)
    original_validate = parent.validate
    original_make_context = parent.make_context
    original_observe = parent.observe
    original_local_inputs = parent.local_inputs
    original_attach = parent.attach
    original_new_trace = parent.new_trace
    original_configure_call = parent.configure_call

    def validate(inputs):
        if inputs.get("kind") != INPUT_KIND:
            raise ValueError("Require the complete standalone GRN flow declaration")
        if not {"flow_state", "presentation"} <= inputs.keys():
            raise ValueError("Require explicit prepared flow ownership and plot-input policy")
        if inputs["scope"] != dict(
            mitochondria=False, fluid=True, cuts=False, grn_unpickle_filename=None
        ):
            raise ValueError("Only the explicit standalone ECM flow capability is extended")
        if inputs["network"]["scope"] != dict(
            mitochondria=False, fluid=True, cuts=False, standalone=True
        ):
            raise ValueError("Declare standalone flow lifecycle ownership separately")
        if inputs["presentation"] != dict(
            autosave=False, turn_all_plots_off=True, capture_stream_inputs=True
        ):
            raise ValueError("Declare in-memory source plot-input capture without rendering")
        cfg = inputs["network"]["configuration"]
        if any(type(cfg.get(name)) is not bool for name in CONFIGURATION_KEYS):
            raise ValueError("Declare both genuine source configuration spellings as booleans")
        if any(
            "flow_fault" not in call or call["flow_fault"] not in (None, "missing_current_y")
            for call in inputs["calls"]
        ):
            raise ValueError("Use only declared standalone flow partial-write controls")
        declared = inputs["flow_state"]
        if set(declared) != {
            "cell_ids",
            "membrane_ids",
            "environment_ids",
            "shape",
            "initial_simulator_fields",
        }:
            raise ValueError("Require complete standalone flow input owners")
        current = inputs["material_definition"]["environment_geometry_definition"][
            "current_definition"
        ]
        geometry = current["geometry"]
        if (
            declared["cell_ids"] != geometry["cell_ids"]
            or declared["membrane_ids"] != geometry["membrane_ids"]
        ):
            raise ValueError("Bind actual declared cell and membrane owners without reordering")
        shape = tuple(declared["shape"])
        if len(shape) != 2 or any(type(v) is not int or not 2 <= v <= 7 for v in shape):
            raise ValueError("Retain the parent's bounded explicit ECM grid")
        n, e = len(declared["cell_ids"]), len(inputs["initial"]["environment_mol_m3"][0])
        names = declared["environment_ids"]
        if (
            len(names) != e
            or e != shape[0] * shape[1]
            or len(set(names)) != e
            or any(type(v) is not str or not v for v in names)
        ):
            raise ValueError("Declare every C-order ECM owner exactly once")
        fields = declared["initial_simulator_fields"]
        if set(fields) != set(EXTRA_FIELDS):
            raise ValueError("Require all current, electric, pressure and initial velocity stores")
        for key, value in fields.items():
            actual = np.asarray(value)
            expected = shape if key in {"J_env_x", "J_env_y", "u_env_x", "u_env_y"} else (n,)
            if (
                actual.shape != expected
                or actual.dtype.kind not in "fiu"
                or not np.isfinite(actual).all()
            ):
                raise ValueError("Incorrect finite prepared flow owner axis: " + key)
        original_validate(parent_view(inputs))

    def new_trace():
        return dict(
            original_new_trace(),
            flow_activations=[],
            flow_before_activation=None,
            stream_plot_calls=[],
            flow_source_frames=[],
        )

    def make_context(inputs):
        ctx = original_make_context(inputs)
        declared = inputs["flow_state"]
        if tuple(ctx.cells.X.shape) != tuple(declared["shape"]):
            raise ValueError("The source-generated grid differs from declared flow owners")
        for key, value in declared["initial_simulator_fields"].items():
            setattr(ctx.sim, key, np.array(value, dtype=np.float64, copy=True))
        ctx.p.autosave = inputs["presentation"]["autosave"]
        ctx.p.turn_all_plots_off = inputs["presentation"]["turn_all_plots_off"]
        return ctx

    def local_inputs(ctx, time):
        result = original_local_inputs(ctx, time)
        result.update(
            fluid_flow=ctx.p.fluid_flow,
            velocity_x_m_s=parent.clone(ctx.sim.u_env_x),
            velocity_y_m_s=parent.clone(ctx.sim.u_env_y),
            flow_ownership=parent.clone(ctx.inputs["flow_state"]),
            current_x_A_m2=parent.clone(ctx.sim.J_env_x),
            current_y_A_m2=parent.clone(ctx.sim.J_env_y),
        )
        return result

    def configure_call(ctx, call):
        original_configure_call(ctx, call)
        if call["flow_fault"] == "missing_current_y":
            ctx.trace["flow_fault_before"] = parent.snapshot(ctx)
            del ctx.sim.J_env_y
            ctx.trace["declared_flow_fault"] = dict(
                name="missing_current_y",
                stage="before_actual_run_core_sim",
                input_owner_was_complete=True,
                accuracy_credit=False,
            )

    def observe(stage, owner, phase, local):
        ctx = parent._ACTIVE
        if stage == "after_clear_cache":
            ctx.trace["flow_before_activation"] = parent.snapshot(ctx)
        if stage == "before_run_loop" and not ctx.trace["flow_activations"]:
            ctx.trace["flow_activations"].append(
                dict(
                    before=ctx.trace["flow_before_activation"],
                    after=parent.snapshot(ctx),
                    recalculate_fluid=owner.recalc_fluid,
                    source_returned_mean_concentration=parent.clone(local.get("cc")),
                    source_returned_mean_valence=parent.clone(local.get("zz")),
                    ordinary_getFlow_called=False,
                    static_for_entire_invocation=True,
                    computed_after_reinitialize_and_clear_cache=True,
                )
            )
        return original_observe(stage, owner, phase, local)

    def attach(ctx):
        original_attach(ctx)
        old_mover = ctx.p._mover_observe

        def mover(stage, name, local, actual):
            old_mover(stage, name, local, actual)
            ctx.trace["mover_frames"][-1]["flow_inputs"] = dict(
                fluid_flow=ctx.p.fluid_flow,
                ux=parent.clone(local.get("ux")),
                uy=parent.clone(local.get("uy")),
                held_velocity_x_m_s=parent.clone(ctx.sim.u_env_x),
                held_velocity_y_m_s=parent.clone(ctx.sim.u_env_y),
            )

        ctx.p._mover_observe = mover

    class PlotBoundary:
        def figure(self):
            parent._ACTIVE.trace["stream_plot_calls"].append(
                dict(operation="figure", rendered=False)
            )

        def subplot(self, index):
            parent._ACTIVE.trace["stream_plot_calls"].append(
                dict(operation="subplot", index=index, rendered=False)
            )
            return None

        def plotStreamField(self, x, y, cells, parameters, **options):
            ctx = parent._ACTIVE
            if cells is not ctx.cells or parameters is not ctx.p:
                raise ValueError("Retain actual source stream-plot owner objects")
            ctx.trace["stream_plot_calls"].append(
                dict(
                    operation="plotStreamField",
                    x_nm_per_s=parent.clone(x),
                    y_nm_per_s=parent.clone(y),
                    options=parent.clone(options),
                    source_scaling=1e9,
                    rendered=False,
                    geometry_moved=False,
                )
            )

    parent.validate = validate
    parent.make_context = make_context
    parent.new_trace = new_trace
    parent.observe = observe
    parent.local_inputs = local_inputs
    parent.attach = attach
    parent.configure_call = configure_call
    boundary = PlotBoundary()
    if role == "production":
        parent.plt = parent.viz = boundary
    else:
        namespace = parent.science()
        namespace["observe"] = observe
        namespace["plt"] = namespace["viz"] = boundary
    return parent
