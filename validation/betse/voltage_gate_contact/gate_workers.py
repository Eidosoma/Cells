"""Separate-environment workers; no tissue simulator or production runner hooks."""

import importlib.metadata as metadata
import sys
from pathlib import Path
from types import SimpleNamespace

import gate_reference as ref

c = ref.c


def native_worker(registration):
    import betse
    import numpy as np
    from betse.science.channels import channelsabc, vg_k

    package = Path(betse.__file__).resolve().parent
    c.require(package.is_relative_to(c.REFERENCE_PYTHON.parent.parent), "Wrong BETSE origin")
    expected = {
        name: digest
        for name, digest in registration["upstream"]["files_sha256"].items()
        if name.startswith("betse/") and name.endswith(".py")
    }
    installed = {f"betse/{p.relative_to(package)}": c.sha(p) for p in package.rglob("*.py")}
    c.require(installed == expected and len(installed) == 332, "Installed BETSE source differs")
    c.require(metadata.version("betse") == "1.5.0", "Wrong native version")
    c.require(c.environment()["packages"] == c.locked_reference_packages(), "Native lock differs")
    p = registration["protocol"]
    voltage = np.asarray(p["voltages_V"], dtype=np.float64)
    before = voltage.copy()
    channel = vg_k.Kv1p5()
    # With targets=None these intact upstream entry points consume no cells
    # object and only p.dt. This is not a loaded BETSE simulation configuration.
    channel.init(voltage, None, SimpleNamespace(dt=0.0))
    initial = np.stack((channel.m.copy(), channel.h.copy()), axis=-1).tolist()
    channel.run(voltage, SimpleNamespace(dt=0.0))
    kinetics = {
        "target": np.stack((channel._mInf, channel._hInf), axis=-1).tolist(),
        "tau_s": (np.stack((channel._mTau, channel._hTau), axis=-1) / 1000).tolist(),
    }
    metadata_row = {
        "time_unit": channel.time_unit,
        "voltage_correction_mV": channel.v_corr,
        "powers": [channel._mpower, channel._hpower],
        "ions": channel.ions,
        "relative_permeability": channel.rel_perm,
        "targets": channel.targets,
        "declared_unused_reversal_mV": channel.vrev,
    }
    c.require(np.array_equal(voltage, before), "Native kinetics changed voltage input")
    trajectories = {}
    for case in p["cases"]:
        for dt in p["step_us"]:
            vm = np.asarray([case["segments"][0]["voltage_V"]], dtype=np.float64)
            model = vg_k.Kv1p5()
            model.init(vm, None, SimpleNamespace(dt=0.0))
            # Explicit non-equilibrium fixture installation; not native preparation.
            model.m = np.asarray([case["initial_gate"][0]], dtype=np.float64)
            model.h = np.asarray([case["initial_gate"][1]], dtype=np.float64)
            states = [[float(model.m[0]), float(model.h[0])]]
            # Native init does not create P. Do not call an artificial zero-time
            # update: even dt=0 multiply/divide can perturb the installed state.
            # Only this initial readout is derived; later P is native run output.
            opened = [float(model.m[0] * model.h[0])]
            valid, unchanged, steps = True, True, 0
            parameters = SimpleNamespace(dt=dt / 1_000_000)
            for segment in case["segments"]:
                vm = np.asarray([segment["voltage_V"]], dtype=np.float64)
                before = vm.copy()
                for index in range(segment["duration_us"] // dt):
                    model.run(vm, parameters)
                    values = np.asarray([model.m[0], model.h[0], model.P[0]])
                    valid &= bool(np.all(np.isfinite(values) & (values >= 0) & (values <= 1)))
                    unchanged &= bool(np.array_equal(vm, before))
                    steps += 1
                    if (index + 1) % (segment["sample_every_us"] // dt) == 0:
                        states.append([float(model.m[0]), float(model.h[0])])
                        opened.append(float(model.P[0]))
            times, volts = ref.grid(case)
            trajectories[f"{case['id']}/{dt}"] = {
                "time_us": times,
                "voltage_V": volts,
                "gate": states,
                "open_fraction": opened,
                "steps": steps,
                "all_steps_valid": valid,
                "input_unchanged": unchanged,
            }
    c.require(
        not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "Native worker imported Cells",
    )
    return {
        "engine": "unmodified_betse_Kv1p5_init_run",
        "environment": c.environment(),
        "installed_python_sha256": installed,
        "module_paths": [vg_k.__file__, channelsabc.__file__],
        "native_metadata": metadata_row,
        "input_carrier": "targets=None; cells=None; SimpleNamespace(dt); no native world",
        "state_preparation": "native equilibrium init recorded; then explicit m/h fixture",
        "initial_open_fraction_origin": "derived_m_times_h_before_first_native_update",
        "kinetics": kinetics,
        "equilibrium_initial_gate": initial,
        "trajectories": trajectories,
        "dtype": "float64",
        "kinetic_input_unchanged": True,
    }


def cells_worker(registration):
    import jax
    import jax.numpy as jnp
    import numpy as np

    from cells.io import runtime_identity
    from cells.numerics import fixed_step
    from cells.processes import voltage_gates

    c.require(jax.default_backend() == "cpu" and jax.config.x64_enabled, "Need CPU float64")
    c.require(not jax.config.jax_disable_jit, "JIT disabled")
    c.require(runtime_identity() == registration["cells_runtime"], "Cells runtime changed")
    c.require(voltage_gates.LAW_ID == registration["protocol"]["kinetic_law"], "Wrong law")
    c.require(voltage_gates.TEMPERATURE_K == 298.15, "Wrong temperature contract")
    modules = (voltage_gates, fixed_step)
    paths = ("src/cells/processes/voltage_gates.py", "src/cells/numerics/fixed_step.py")
    c.require(
        all(
            Path(m.__file__).resolve() == c.ROOT / name
            for m, name in zip(modules, paths, strict=True)
        ),
        "Wrong production origin",
    )

    def rhs(state, voltage, _parameters, _active):
        target, tau = voltage_gates.kinetics(voltage)
        return (target - state) / tau

    def valid(state, _parameters, _active):
        return jnp.all(jnp.isfinite(state) & (state >= 0) & (state <= 1))

    def step(state, voltage, dt):
        return fixed_step.rk4_checked_step(rhs, valid, state, dt, voltage, None, None)

    @jax.jit
    def rollout(state, voltages, dt):
        def advance(carry, voltage):
            old, all_ok = carry
            new, ok = step(old, voltage[None], dt)
            return (new, all_ok & ok), new

        (_, ok), states = jax.lax.scan(advance, (state, jnp.asarray(True)), voltages)
        return states, ok

    p = registration["protocol"]
    voltage = np.asarray(p["voltages_V"], dtype=np.float64)
    before = voltage.copy()
    jv = jnp.asarray(voltage)
    kinetics = {}
    values = {
        "numpy": voltage_gates.kinetics(voltage, xp=np),
        "jax_eager": voltage_gates.kinetics(jv),
        "jax_jit": jax.jit(voltage_gates.kinetics)(jv),
    }
    for backend, (target, tau) in values.items():
        arrays = [np.asarray(a) for a in (target, tau)]
        c.require(
            all(a.dtype == np.float64 and a.shape == (2, len(voltage)) for a in arrays),
            "Wrong kinetic shape/dtype",
        )
        kinetics[backend] = {"target": arrays[0].T.tolist(), "tau_s": arrays[1].T.tolist()}
    initial = np.tile(np.asarray(p["one_step_initial_gate"])[:, None], (1, len(voltage)))

    def numpy_rhs(state, vm):
        target, tau = voltage_gates.kinetics(vm, xp=np)
        return (target - state) / tau

    numpy_step = fixed_step.rk4_step(numpy_rhs, initial.copy(), 0.001, voltage)
    eager, eager_ok = step(jnp.asarray(initial), jv, 0.001)
    compiled, compiled_ok = jax.jit(step)(jnp.asarray(initial), jv, 0.001)
    c.require(bool(eager_ok) and bool(compiled_ok), "One-step stage refusal")
    one_step = {
        name: np.asarray(a).T.tolist()
        for name, a in zip(ref.BACKENDS, (numpy_step, eager, compiled), strict=True)
    }
    c.require(np.array_equal(voltage, before), "Cells changed voltage input")
    trajectories = {}
    for case in p["cases"]:
        for dt in p["step_us"]:
            schedule = np.concatenate(
                [
                    np.full(s["duration_us"] // dt, s["voltage_V"], dtype=np.float64)
                    for s in case["segments"]
                ]
            )
            original = schedule.copy()
            initial = jnp.asarray(case["initial_gate"], dtype=jnp.float64)[:, None]
            all_states, ok = rollout(initial, jnp.asarray(schedule), dt / 1_000_000)
            c.require(all_states.dtype == jnp.float64, "Trajectory not float64")
            times, volts = ref.grid(case)
            observed = np.asarray(all_states)[np.asarray(times[1:]) // dt - 1, :, 0]
            states = np.concatenate((np.asarray(initial).T, observed))
            trajectories[f"{case['id']}/{dt}"] = {
                "time_us": times,
                "voltage_V": volts,
                "gate": states.tolist(),
                "open_fraction": (states[:, 0] * states[:, 1]).tolist(),
                "steps": len(schedule),
                "all_steps_valid": bool(ok),
                "input_unchanged": bool(np.array_equal(schedule, original)),
            }
    c.require(
        not any(n == "betse" or n.startswith("betse.") for n in sys.modules),
        "Cells worker imported BETSE",
    )
    return {
        "engine": "unchanged_cells_kinetics_shared_rk4_isolated_harness",
        "environment": c.environment(),
        "accepted_runtime": runtime_identity(),
        "module_sha256": {name: c.sha(c.ROOT / name) for name in paths},
        "kinetics": kinetics,
        "one_step": one_step,
        "trajectories": trajectories,
        "kinetic_backends": list(ref.BACKENDS),
        "trajectory_backend": "jax_jit",
        "device": "cpu",
        "x64_enabled": True,
        "jit_disabled": False,
        "dtype": "float64",
        "kinetic_input_unchanged": True,
        "production_world_runner_executed": False,
    }
