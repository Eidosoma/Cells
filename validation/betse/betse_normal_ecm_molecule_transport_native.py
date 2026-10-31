# ruff: noqa: E501, F841, B007, B905
"""Native FULL setup/dispatch on actual incoming two-owner conditional buffers."""

import argparse
import builtins
import json
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_normal_ecm_catalog_join_native_network as network
from validation.betse import betse_normal_ecm_init_phase_capture as failure_evidence
from validation.betse import betse_normal_ecm_molecule_transport_native_source as source
from validation.betse import betse_normal_grn_join_native as archives
from validation.betse.betse_normal_ecm_init_phase_native import _failure_readers

ROLES = ("molecules", "grn")
PUBLICATIONS = ("extra_rho_cells", "extra_rho_env", "extra_J_mem", "extra_Jenv_x", "extra_Jenv_y")
SHARED = (
    *PUBLICATIONS,
    "c_env_bound",
    "gj_block",
    "NaKATP_block",
    "rho_channel",
    "D_env_weight",
    "D_env_weight_base",
    "TJ_targets",
    "rho_pump",
)


def decode(value):
    if isinstance(value, list):
        return [decode(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"__native_buffer__", "dtype", "shape"}:
            array = np.asarray(value["__native_buffer__"], dtype=value["dtype"])
            if array.dtype.kind not in "biuf" or list(array.shape) != value["shape"]:
                raise ValueError("Changed complete conditional array dtype/shape")
            return array.copy()
        return {key: decode(item) for key, item in value.items()}
    return value


def snapshot(ctx, views):
    owners = {}
    for role in ROLES:
        owner = getattr(ctx.sim, role, None)
        owners[role] = (
            None
            if owner is None or not hasattr(owner, "core")
            else source.cache_general(views[role])
            if role == "molecules"
            else network.cache(views[role])
        )
    return dict(
        material=network.material_values(ctx.sim),
        handlers=owners,
        shared={key: network.clone(getattr(ctx.sim, key)) for key in SHARED},
        owner_classes={role: type(getattr(ctx.sim, role)).__name__ for role in ROLES},
    )


def evaluate(inputs):
    ctx = None
    views = {}
    failure = None
    capture = None
    stage = "conditional_inputs"
    order = []
    rows = []
    try:
        if inputs["kind"] != "cells.actual_ECM_general_GRN_conditional_inputs@1" or inputs[
            "mode"
        ] not in ("initialize", "dispatch"):
            raise ValueError("Require actual original two-owner conditional inputs")
        source.prepare_native_namespace()
        raw = inputs["raw"]
        sim = SimpleNamespace(**decode(inputs["simulator_fields"]))
        cells = SimpleNamespace(**decode(inputs["cell_fields"]))
        p = SimpleNamespace(**decode(inputs["parameter_fields"]))
        stage = "conditional_geometry_and_owner_bindings"
        ctx = network.augment(
            sim, cells, p, network.clone(raw["handlers"]["grn"]["network"]), inputs["ion_ids"]
        )
        for role in ROLES:
            view = SimpleNamespace(**vars(ctx))
            view.definition = network.clone(raw["handlers"][role]["network"])
            view.trace = network.new_trace()
            view.initial_transporter_fields = {}
            network.configure(view, network.clone(raw["handlers"][role]["catalog"]))
            views[role] = view
        p.grn = SimpleNamespace(conf=network.clone(views["grn"].definition["configuration"]))
        p.network_config = network.clone(raw["configuration"]["general network"])
        p.molecules_enabled = p.network_config["implement network"]
        p.grn_enabled = raw["configuration"]["gene regulatory network settings"][
            "gene regulatory network simulated"
        ]
        p.substances_affect_charge = inputs["publication"]
        p._run_sim = True
        ctx.phase.kind = "SIM"
        sim.molecules = sim.grn = None
        if inputs["mode"] == "dispatch":
            saved = decode(inputs["incoming_owners"])
            for role in ROLES:
                record = saved["handlers"][role]
                if record is not None:
                    if role == "molecules":
                        source.restore_general(views[role], record["cache"])
                    else:
                        network.restore(views[role], record["cache"])
        for key, value in decode(inputs["simulator_fields"]).items():
            setattr(sim, key, value)
        stage = "native_" + inputs["mode"]

        def hook(role, event, actual, phase):
            view = views[role]
            order.append(dict(role=role, stage=event))
            if event in ("before_setup", "before_dispatch"):
                if role == "molecules":
                    source.install_channel_observer_general(view)
                else:
                    network.install_channel_observer(view)
                if event == "before_dispatch":
                    view.net = getattr(actual, role).core
                    if role == "molecules":
                        source.attach_general(view, inputs["material_definition"])
                    else:
                        network.attach(view, inputs["material_definition"])
            elif event == "after_setup":
                view.net = getattr(actual, role).core
                view.initial_channel_fields = network.channel_fields(view.net)
                if role == "molecules":
                    view.initial_transporter_fields = source.transporter_fields(view.net)
            else:
                view.net._observe_dispatch(event, actual, phase)
            rows.append(dict(role=role, stage=event, buffers=snapshot(ctx, views)))

        if inputs["mode"] == "initialize":
            source.initialize_both(sim, 0.0, ctx.phase, cells, p, hook=hook)
        else:
            source.dispatch_both(sim, inputs["source_time_s"], ctx.phase, cells, p, hook=hook)
    except Exception as error:
        failure = dict(
            type=type(error).__name__,
            message=str(error),
            stage=stage,
            traceback=traceback.format_exc(),
        )
        readers = _failure_readers(locals(), error)
        readers["actual_conditional_inputs"] = lambda: inputs
        capture = failure_evidence.record_failure(error, stage=stage, readers=readers, retain=None)
    returned = None
    capture_errors = []
    if ctx is not None:
        try:
            returned = snapshot(ctx, views)
        except Exception as error:
            capture_errors.append(dict(type=type(error).__name__, message=str(error)))
    return dict(
        status="source_refused" if failure else "source_completed",
        mode=inputs.get("mode"),
        returned=returned,
        order=order,
        rows=rows,
        traces={role: network.clone(view.trace) for role, view in views.items()},
        failure=failure,
        failure_capture=capture,
        capture_errors=capture_errors,
        independently_carried_trajectory=False,
        native_whole_initializer=False,
        native_ER_enabled=False,
        production_scientific_implementation_used=False,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *values, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Native two-owner production import denied: " + name)
        return original(name, *values, **kwargs)

    builtins.__import__ = guarded
    try:
        result = evaluate(json.loads(args.inputs.read_text()))
    except Exception as error:
        failure_evidence.record_failure(
            error,
            stage="native_CLI_preparation",
            readers=dict(
                input_path=lambda: str(args.inputs), input_text=lambda: args.inputs.read_text()
            ),
            retain=lambda value: archives.write_archive(
                args.output.parent / (args.output.name + "-failure-before-reraise"), value
            ),
        )
        raise
    archives.write_archive(args.output.parent / (args.output.name + "-raw-before-runtime"), result)
    from validation.betse.betse_normal_channel_join_runtime import inventory

    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    if loaded:
        raise ImportError("Forbidden production module loaded")
    result.update(
        production_imports_denied=True, loaded_production_modules=loaded, runtime=inventory()
    )
    archives.write_archive(args.output, result)


if __name__ == "__main__":
    main()
