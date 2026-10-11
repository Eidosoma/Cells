"""Separate actual native gates and production initial-state/RHS probes; no rollout."""

import copy
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import history_context as ctx

c = ctx.c


def native(data, plan):
    import betse
    import numpy as np
    from betse.science.channels.vg_k import Kv1p5

    package = Path(betse.__file__).resolve().parent
    c.require(package.is_relative_to(c.REFERENCE_PYTHON.parent.parent), "Wrong native origin")
    installed = {f"betse/{p.relative_to(package)}": c.sha(p) for p in package.rglob("*.py")}
    expected = {
        n: h
        for n, h in data["upstream"]["files_sha256"].items()
        if n.startswith("betse/") and n.endswith(".py")
    }
    c.require(installed == expected, "Native installed sources differ")
    c.require(c.environment()["packages"] == c.locked_reference_packages(), "Native lock differs")
    rows = {}
    voltage = np.asarray(data["native_voltage_V"], dtype=np.float64)
    for name, gates in plan["histories"].items():
        for step in plan["native_steps_s"]:
            original = voltage.copy()
            channel = Kv1p5()
            channel.init(voltage, None, SimpleNamespace(dt=0.0))
            equilibrium = [channel.m.tolist(), channel.h.tolist()]
            channel.m = np.full(voltage.shape, gates[0], dtype=np.float64)
            channel.h = np.full(voltage.shape, gates[1], dtype=np.float64)
            before = [channel.m.tolist(), channel.h.tolist()]
            opened = (channel.m * channel.h).tolist()
            channel.run(voltage, SimpleNamespace(dt=step))
            c.require(np.array_equal(voltage, original), "Native gate mutated voltage input")
            rows[name + f"/dt_{step:.8g}"] = {
                "voltage_V": voltage.tolist(),
                "equilibrium_gate": equilibrium,
                "before": before,
                "initial_open_derived": opened,
                "after": [channel.m.tolist(), channel.h.tolist()],
                "open_after_native": channel.P.tolist(),
                "target": [channel._mInf.tolist(), channel._hInf.tolist()],
                "tau_s": [(channel._mTau / 1000).tolist(), (channel._hTau / 1000).tolist()],
                "dt_s": step,
                "input_unchanged": True,
            }
    c.require(not any(k.split(".")[0] in {"cells", "jax"} for k in sys.modules), "Mixed engines")
    return {
        "rows": rows,
        "installed_python_sha256": installed,
        "engine": "unmodified_betse_Kv1p5_init_run",
        "input_carrier": "targets=None; cells=None; SimpleNamespace(dt); no native world",
        "fixture_origin": "explicit prescribed m/h after recorded native equilibrium init",
        "native_gate_batch_updates": len(rows),
        "native_scalar_gate_updates": len(rows) * len(voltage),
        "native_world_preparations": 0,
        "native_transport_updates": 0,
    }


def cells(data, plan, backends=None):
    import jax
    import jax.numpy as jnp
    import numpy as np

    from cells.core.resources import trace_bytes
    from cells.core.runner import timeline
    from cells.core.schedule import PhysicalIonicGraphControl, control_values
    from cells.core.specs import parse_spec
    from cells.io import runtime_identity
    from cells.models import finite_extracellular as model

    c.require(
        jax.default_backend() == "cpu"
        and jax.config.x64_enabled
        and not jax.config.jax_disable_jit,
        "Require CPU float64 with enabled JIT",
    )
    c.require(runtime_identity() == data["cells_runtime"], "Accepted Cells runtime differs")
    c.require(
        Path(model.__file__).resolve() == ctx.ROOT / "src/cells/models/finite_extracellular.py",
        "Wrong Cells source origin",
    )
    array = ctx.prior.pilot.audit.preparation.array_record

    def evaluate(state, control, layout, xp):
        return (
            model.rhs(state, control, layout, layout.active, xp=xp),
            model.channel_readouts(state, control.channel, layout, xp=xp),
            model.cell_voltage(state.amount_increment, layout, xp=xp),
        )

    compiled = jax.jit(lambda s, u, p: evaluate(s, u, p, jnp))
    rows, candidates = {}, {}
    for identifier, definition in data["definitions"].items():
        spec = parse_spec(definition)
        state, layout = model.initial_values(spec)
        balances = model.check_values(state, spec)
        control = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0])))
        candidates[identifier] = []
        for step in plan["candidate_cells_steps_s"]:
            candidate = copy.deepcopy(definition)
            candidate["execution"]["dt"] = step
            candidate_spec = parse_spec(candidate)
            grid = timeline(candidate_spec)
            candidates[identifier].append(
                {
                    "dt_s": step,
                    "grid_s": grid.tolist(),
                    "steps": len(grid) - 1,
                    "estimated_trace_bytes": trace_bytes(candidate_spec, len(grid) - 1),
                    "max_trace_bytes": candidate["execution"]["max_trace_bytes"],
                }
            )
        for backend in plan["backends"] if backends is None else backends:
            before = [np.asarray(v).tobytes() for v in (*state, *layout, *control)]
            if backend == "numpy":
                rate, channel, voltage = evaluate(state, control, layout, np)
            elif backend == "jax_eager":
                rate, channel, voltage = evaluate(state, control, layout, jnp)
            else:
                c.require(backend == "jax_jit", "Unknown backend")
                rate, channel, voltage = compiled(state, control, layout)
            record = {
                "state": {n: array(v) for n, v in state._asdict().items()},
                "rhs": {n: array(v) for n, v in rate._asdict().items()},
                "channel": {
                    n: array(getattr(channel, n))
                    for n in (
                        "open_probability",
                        "effective_permeability_m_per_s",
                        "flux_fmol_per_s",
                        "dissipation_rate_pJ_per_s",
                    )
                },
                "voltage": array(voltage),
                "layout_sha256": {
                    n: hashlib.sha256(np.asarray(v).tobytes()).hexdigest()
                    for n, v in layout._asdict().items()
                },
                "initial_balances": balances,
                "integration_executed": False,
            }
            c.require(
                before == [np.asarray(v).tobytes() for v in (*state, *layout, *control)],
                "Initial probe mutated state, layout or controls",
            )
            rows[identifier + "/" + backend] = record
    c.require(not any(k.split(".")[0] == "betse" for k in sys.modules), "Mixed engines")
    return {
        "rows": rows,
        "candidates": candidates,
        "accepted_runtime": runtime_identity(),
        "initial_rhs_evaluations": len(rows),
        "cells_trajectory_runs": 0,
        "engine": "unchanged_cells_initial_values_and_rhs",
    }
