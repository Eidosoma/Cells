"""Independent conditional retained-owner SIM reinitialization.

Only the source reinitialization boundary is compared here. Input owners are
archived actual incoming buffers; this does not establish an independently
carried INIT/SIM trajectory, native loader or whole-phase equivalence.
"""

import argparse
import builtins
import copy
import json
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_normal_ecm_catalog_join_native_network as network
from validation.betse import betse_normal_ecm_init_phase_capture as capture_evidence
from validation.betse import betse_normal_grn_join_native as archives
from validation.betse.betse_normal_ecm_init_phase_native import _failure_readers


def reinitialize(self, phase):
    cells = phase.cells
    p = phase.p
    sim = phase.sim
    config_dic = p.grn.conf
    self.core.time_dila = float(config_dic.get("time dilation factor", 1.0))
    self.reset_MT = config_dic.get("reset microtubules", False)
    self.recalc_fluid = config_dic.get("recalculate fluid flow", False)
    substances_config = config_dic["biomolecules"]
    reactions_config = config_dic.get("reactions", None)
    transporters_config = config_dic.get("transporters", None)
    channels_config = config_dic.get("channels", None)
    modulators_config = config_dic.get("modulators", None)
    self.core.tissue_init(phase, substances_config)
    if reactions_config is not None:
        self.core.read_reactions(reactions_config, sim, cells, p)
        self.core.write_reactions()
        self.core.create_reaction_matrix()
        self.core.write_reactions_env()
        self.core.create_reaction_matrix_env()
        self.reactions = True
    else:
        self.core.create_reaction_matrix()
        self.core.create_reaction_matrix_env()
        self.reactions = False
    if transporters_config is not None:
        self.core.read_transporters(transporters_config, phase)
        self.core.write_transporters(sim, cells, p)
        self.transporters = True
    else:
        self.transporters = False
    if channels_config is not None:
        self.core.read_channels(channels_config, phase)
        self.channels = True
    else:
        self.channels = False
    if modulators_config is not None:
        self.core.read_modulators(modulators_config, sim, cells, p)
        self.modulators = True
    else:
        self.modulators = False


def arrays(value):
    if isinstance(value, list):
        return [arrays(v) for v in value]
    if isinstance(value, dict):
        if set(value) == {"__transition_ndarray__", "dtype", "shape"}:
            result = np.asarray(value["__transition_ndarray__"], dtype=value["dtype"])
            if list(result.shape) != value["shape"] or result.dtype.kind not in "biuf":
                raise ValueError("Changed complete typed conditional input array")
            return result.copy()
        return {key: arrays(v) for key, v in value.items()}
    return value


def evaluate(inputs):
    ctx = None
    failure = None
    stage = "conditional_input"
    before = None
    failure_capture = None
    try:
        if (
            inputs["kind"] != "cells.actual_SIM_reinitialize_conditional_inputs@1"
            or inputs["source_phase"] != "SIM"
            or inputs["legacy_run_sim"] is not True
        ):
            raise ValueError("Require complete actual incoming SIM reinitialization buffers")
        sim = SimpleNamespace(**arrays(inputs["simulator_fields"]))
        cells = SimpleNamespace(**arrays(inputs["cells_fields"]))
        p = SimpleNamespace(**arrays(inputs["parameter_fields"]))
        stage = "retained_owner_restore"
        ctx = network.augment(
            sim, cells, p, copy.deepcopy(inputs["definition"]), list(inputs["ion_ids"])
        )
        network.configure(ctx, copy.deepcopy(inputs["old_catalog"]))
        network.restore(ctx, arrays(inputs["incoming_cache"]))
        # Restore actual incoming arrays after generic context construction;
        # no constructor output is used as the transition's reference input.
        for key, value in arrays(inputs["simulator_fields"]).items():
            setattr(sim, key, value)
        network.configure(ctx, copy.deepcopy(inputs["catalog"]))
        dyna = SimpleNamespace(**arrays(inputs["maps"]))
        sim.dyna = ctx.phase.dyna = dyna
        ctx.phase.kind = "SIM"
        p._run_sim = True
        owner, core = sim.grn, sim.grn.core
        molecules = dict(core.molecules)
        channels = dict(core.channels)
        before = dict(material=network.material_values(sim), cache=network.cache(ctx))
        stage = "source_reinitialize"
        reinitialize(owner, ctx.phase)
        ctx.initial_channel_fields = network.channel_fields(sim.grn.core)
        ctx.channel_calls = {name: 0 for name in sim.grn.core.channels}
        identity = dict(
            owner_retained=sim.grn is owner,
            core_retained=sim.grn.core is core,
            molecule_objects_retained={
                name: sim.grn.core.molecules.get(name) is obj for name, obj in molecules.items()
            },
            channel_objects_reconstructed={
                name: obj is not channels.get(name) for name, obj in sim.grn.core.channels.items()
            },
            read_substances_called=False,
            fresh_cold_owner_created=False,
        )
    except Exception as error:
        failure = dict(
            stage=stage,
            type=type(error).__name__,
            message=str(error),
            traceback=traceback.format_exc(),
        )
        readers = _failure_readers(locals(), error)
        readers["conditional_inputs"] = lambda: inputs
        failure_capture = capture_evidence.record_failure(
            error,
            stage=stage,
            readers=readers,
            retain=None,
        )
    capture_errors = []
    returned = {}
    # Full reached buffers are captured before any correspondence assertion or
    # runtime receipt, including bootstrap/pre-loop failures in future callers.
    if ctx is not None:
        for key, producer in (
            ("material", lambda: network.material_values(ctx.sim)),
            ("cache", lambda: network.cache(ctx)),
        ):
            try:
                returned[key] = producer()
            except Exception as error:
                capture_errors.append(
                    dict(section=key, type=type(error).__name__, message=str(error))
                )
    return dict(
        status="source_refused" if failure else "source_completed",
        mode="reinitialize",
        before=before,
        returned=returned,
        owner_identity=locals().get("identity"),
        failure=failure,
        failure_capture=failure_capture,
        capture_errors=capture_errors,
        source_phase="SIM",
        legacy_run_sim=True,
        source_cold_recapture=False,
        independent_trajectory=False,
        whole_native_phase_completed=False,
        physical_initializer_credit=False,
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
            raise ImportError("Independent transition native import denied: " + name)
        return original(name, *values, **kwargs)

    builtins.__import__ = guarded
    result = evaluate(json.loads(args.inputs.read_text()))
    archives.write_archive(args.output.parent / (args.output.name + "-raw-before-runtime"), result)
    from validation.betse.betse_normal_channel_join_runtime import inventory

    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    if loaded:
        raise ImportError("Forbidden loaded transition modules: " + repr(loaded))
    result.update(
        production_imports_denied=True, loaded_production_modules=loaded, runtime=inventory()
    )
    archives.write_archive(args.output, result)


if __name__ == "__main__":
    main()
