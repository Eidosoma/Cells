"""Original native entry-control/event/dual-owner local conditionals only."""

import argparse
import ast
import builtins
import copy
import hashlib
import json
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_normal_ecm_event_join_native_events as native_events
from validation.betse import betse_normal_ecm_init_phase_capture as failure_evidence
from validation.betse import betse_normal_ecm_molecule_lifecycle_native as molecule
from validation.betse import betse_normal_grn_join_native as archives


def evaluate(inputs):
    if inputs.get("mode") not in ("events", "entry_controls"):
        return molecule.evaluate(inputs)
    ctx, owner, capture, failure, reset, result = (None, None, None, None, None, None)
    stage = "actual_conditional_inputs"
    try:
        incoming = inputs["native"]
        if incoming["source_phase"] != "SIM" or incoming["legacy_run_sim"] is not True:
            raise ValueError("Require actual SIM conditional phase")
        sim = SimpleNamespace(**molecule.decode(incoming["simulator_fields"]))
        cells = SimpleNamespace(**molecule.decode(incoming["cell_fields"]))
        p = SimpleNamespace(**molecule.decode(incoming["parameter_fields"]))
        ctx = SimpleNamespace(sim=sim, cells=cells, p=p, ion_ids=incoming["ion_ids"])
        ctx.phase = SimpleNamespace(sim=sim, cells=cells, p=p, kind="SIM")
        if inputs["mode"] == "entry_controls":
            pins = json.loads(native_events.PROTOCOL.read_text())["native_source"]
            path = Path(pins["checkout"]) / "betse/science/sim.py"
            expected = pins["source_sha256"]["betse/science/sim.py"]
            if (
                hashlib.sha256(path.read_bytes()).hexdigest() != expected
                or path.read_bytes()
                != (Path(pins["installed_package"]).parent / "betse/science/sim.py").read_bytes()
            ):
                raise ValueError("Pinned native SIM control source changed")
            tree = ast.parse(path.read_text())
            cls = next(
                n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Simulator"
            )
            method = next(
                n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "init_dynamics"
            )
            nodes = [
                copy.deepcopy(n)
                for n in method.body
                if isinstance(n, ast.If)
                and ast.unparse(n.test)
                in {"p.global_options['gj_block'] != 0", "p.global_options['NaKATP_block'] != 0"}
            ]
            if len(nodes) != 2:
                raise ValueError("Two actual native control source branches required")
            fn = ast.parse("def original(self,cells,p): pass").body[0]
            fn.body = nodes
            namespace = dict(np=np)
            exec(
                compile(
                    ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                    "<original native SIM event control entry>",
                    "exec",
                ),
                namespace,
            )
            stage = "actual_entry_control_branches"
            p.global_options = copy.deepcopy(inputs["global_options"])
            namespace["original"](sim, cells, p)
            result = dict(
                controls={
                    key: copy.deepcopy(getattr(sim, key)) for key in ("gj_block", "NaKATP_block")
                }
            )
        else:
            declared = dict(
                event_owner=inputs["owner"],
                entry_event_state=inputs["before"],
                prepared_rng=dict(manifest=inputs["prepared_rng"]),
                noise=dict(enabled=0, level_mol_m2_s=0.0),
                noise_cache=dict(present=False, value=None),
            )
            owner = native_events.Owner(ctx, declared)
            ctx.phase.kind = owner.api["SimPhaseKind"].SIM
            stage = "actual_native_flux_reset"
            owner.api["reset_fluxes"](sim, p)
            reset = molecule.network.material_values(sim)
            stage = "actual_native_events"
            result = owner.fire(inputs["source_time_s"])
    except Exception as error:
        failure = dict(
            type=type(error).__name__,
            message=str(error),
            stage=stage,
            traceback=traceback.format_exc(),
        )
        capture = failure_evidence.record_failure(
            error,
            stage=stage,
            readers=dict(
                actual_conditional_inputs=lambda: inputs,
                actual_event_partial=lambda: None if owner is None else owner.last_event,
                material=lambda: None if ctx is None else molecule.network.material_values(ctx.sim),
                event_stores=lambda: None if ctx is None else native_events.snapshot(ctx.sim),
            ),
            retain=None,
        )
    return dict(
        mode=inputs.get("mode"),
        status="source_refused" if failure else "source_completed",
        returned=result,
        events=None if owner is None else owner.last_event,
        reset_return=reset,
        failure=failure,
        failure_capture=capture,
        capture_errors=[] if capture is None else capture["capture_errors"],
        production_scientific_implementation_used=False,
        independently_carried_trajectory=False,
        native_whole_initializer=False,
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
