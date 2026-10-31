"""Actual standalone GRN current-flow activation and held molecular advection."""

import traceback
import warnings

from validation.betse import betse_standalone_grn_flow_join_engine as engine

LAW_ID = "betse_standalone_GRN_current_flow_advection_v1_5_0@1"
_API = None


class FlowJoinRejected(RuntimeError):
    def __init__(self, code, *, stage, partial):
        super().__init__(code)
        self.code, self.stage, self.partial = code, stage, partial


def api():
    global _API
    if _API is None:
        _API = engine.install("production")
    return _API


def bind(inputs):
    return api().bind(inputs)


def initialize(binding):
    return api().initialize(binding)


def advance(binding, parent, *, before_step=None):
    runtime = api()
    if parent.binding_identity != binding.identity or parent.identity != runtime.ions.digest(
        (binding.identity, parent.invocation, parent.snapshot)
    ):
        raise ValueError("Changed complete standalone flow parent")
    if parent.invocation >= len(binding.inputs["calls"]):
        raise ValueError("No remaining standalone flow invocation")
    ctx = None
    stage = "prepared_context"
    caught = []
    try:
        ctx = runtime.make_context(runtime.ions.data(binding.inputs))
        stage = "restore_complete_parent"
        runtime.restore(ctx, runtime.ions.data(parent.snapshot))
        ctx.before_step = before_step
        runtime.configure_call(ctx, runtime.ions.data(binding.inputs["calls"][parent.invocation]))
        stage = "actual_run_core_sim"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with runtime.active(ctx), engine.observe_flow_execution(runtime):
                ctx.owner.run_core_sim(ctx.phase)
        returned = runtime.snapshot(ctx)
        ctx.trace["complete_source_return"] = runtime.clone(returned)
        stage = "complete_source_finiteness_gate"
        failures = engine.nonfinite_arrays(returned)
        ctx.trace["nonfinite_source_return_arrays"] = failures
        if failures:
            raise FlowJoinRejected(
                "standalone_source_returned_nonfinite",
                stage=stage,
                partial=dict(
                    snapshot=returned,
                    trace=runtime.clone(ctx.trace),
                    invocation=parent.invocation,
                    numerical_candidate_accepted=False,
                ),
            )
        candidate = runtime.state(binding, returned, parent.invocation + 1)
        ctx.trace["warnings"] = engine.warning_records(caught)
        return candidate, runtime.ions.freeze(ctx.trace)
    except Exception as error:
        partial = dict(
            parent=parent,
            invocation=parent.invocation,
            stage=stage,
            original_type=type(error).__name__,
            original_reason=str(error),
            original_partial=getattr(error, "partial", None),
            traceback=traceback.format_exc(),
            warnings=engine.warning_records(caught),
            numerical_candidate_accepted=False,
        )
        if ctx is not None:
            partial["snapshot"] = runtime.snapshot(ctx)
            partial["trace"] = runtime.clone(ctx.trace)
        code = getattr(error, "code", "standalone_source_exception")
        raise FlowJoinRejected(code, stage=stage, partial=runtime.ions.freeze(partial)) from error


def component_flow_readout(activation):
    """Existing standalone flow kernel at the actual archived activation input."""
    import numpy as np

    from cells.processes import betse_fluid_flow as flow

    state = activation["before"]["simulator"]
    grid = activation["before"]["grid_fields"]
    parameters = activation["before"]["parameters"]
    shape = np.asarray(grid["X"]).shape
    current = np.stack((state["J_env_x"], state["J_env_y"]))
    concentration = np.asarray(state["cc_env"]).reshape((-1, *shape))
    return flow.grn_current_flow(
        current, concentration, np.asarray(state["zs"]), parameters["F"], xp=np
    )
