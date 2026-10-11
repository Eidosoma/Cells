"""Real CPU model evaluations at saved states; never advance or reset those states."""

import copy
import importlib
import sys

import release_design as design

sys.path.insert(0, str(design.HERE.parent / "channel_history_preflight"))
independent = importlib.import_module("history_math")
c, io = design.c, design.io


def saved_record(history):
    c.require(history in ("a", "b"), "Unknown saved probe history")
    name = history + "/cells/active_channel/jax_jit/dt_5e-05/result.json.gz"
    path = design.audit.CAPTURE / name
    expected = c.read(design.audit.CAPTURE / "completion.json")["files_sha256"][name]
    c.require(c.sha(path) == expected, "Saved probe state changed")
    return io.read_compressed(path)


def oracle(plan, history, definition, state, value):
    """Use D094's separately audited 80-digit RHS, not a production kernel."""
    c.require(value in plan["probe_availabilities"], "Unknown probe availability")
    p = copy.deepcopy(design.view(history)["reference_parameters"]["active_channel"])
    p["Pmax_m_per_s"] = [maximum * value for maximum in p["Pmax_m_per_s"]]
    n = len(p["volume_pL"])
    result = independent.ready.vector_field(
        p,
        state["amount_increment"][1][:n],
        state["gate"][0][:n],
        state["gate"][1][:n],
    )
    _, full_rate = independent.expected_arrays(definition, result)
    return full_rate, result


def cells_probes(plan, backends=None):
    import hashlib

    import jax
    import jax.numpy as jnp
    import numpy as np

    from cells.core.schedule import PhysicalIonicGraphControl, control_values
    from cells.core.specs import parse_spec
    from cells.io import runtime_identity
    from cells.models import finite_extracellular as model

    design.validate_plan(plan)
    c.require(
        jax.default_backend() == "cpu"
        and jax.config.x64_enabled
        and not jax.config.jax_disable_jit,
        "Require CPU float64, enabled JIT",
    )
    runtime = design.view("a")["preparation_registration"]["cells_runtime"]
    c.require(runtime_identity() == runtime, "Accepted Cells runtime changed")
    selected = plan["backends"] if backends is None else backends
    c.require(selected and len(set(selected)) == len(selected), "Missing or duplicated backends")
    c.require(all(b in plan["backends"] for b in selected), "Unregistered backend")

    def evaluate(state, control, layout, xp):
        return (
            model.rhs(state, control, layout, layout.active, xp=xp),
            model.channel_readouts(state, control.channel, layout, xp=xp),
            model.cell_voltage(state.amount_increment, layout, xp=xp),
        )

    compiled = jax.jit(lambda s, u, p: evaluate(s, u, p, jnp))
    rows = {}
    for history in plan["histories"]:
        definition = design.definition(plan, history, "baseline", plan["cells_steps_s"][0])
        spec = parse_spec(definition)
        _, layout = model.initial_values(spec)
        record = saved_record(history)
        c.require(set(record["history"]) == set(model.STATE_TYPE._fields), "Incomplete saved state")
        base = PhysicalIonicGraphControl(*(u[0] for u in control_values(spec, [0.0])))
        for time in plan["probe_times_s"]:
            index = record["times"]["values"].index(time)
            arrays = {}
            for name in model.STATE_TYPE._fields:
                saved = record["history"][name]
                values = np.asarray(saved["values"], dtype=np.float64)
                c.require(
                    saved["dtype"] == values.dtype.str
                    and saved["shape"] == list(values.shape)
                    and saved["bytes_sha256"] == hashlib.sha256(values.tobytes()).hexdigest(),
                    "Saved state array bytes changed",
                )
                arrays[name] = np.array(values[index], copy=True)
            state = model.STATE_TYPE(**arrays)
            model.check_values(state, spec)
            for value in plan["probe_availabilities"]:
                u = np.zeros_like(base.channel)
                u[: len(spec.model.channels)] = value
                control = base._replace(channel=u)
                for backend in selected:
                    before = [np.asarray(v).tobytes() for v in (*state, *layout, *control)]
                    if backend == "jax_jit":
                        rate, channels, voltage = compiled(state, control, layout)
                    else:
                        rate, channels, voltage = evaluate(
                            state, control, layout, np if backend == "numpy" else jnp
                        )
                    c.require(
                        before == [np.asarray(v).tobytes() for v in (*state, *layout, *control)],
                        "Control/RHS evaluation mutated complete state, layout or input",
                    )
                    rows[f"{history}/{time:.8g}/{value:g}/{backend}"] = {
                        "history": history,
                        "saved_time_s": time,
                        "availability": value,
                        "backend": backend,
                        "state": {k: np.asarray(v).tolist() for k, v in state._asdict().items()},
                        "rhs": {k: np.asarray(v).tolist() for k, v in rate._asdict().items()},
                        "voltage_V": np.asarray(voltage).tolist(),
                        "permeability_m_per_s": np.asarray(
                            channels.effective_permeability_m_per_s
                        ).tolist(),
                        "flux_fmol_per_s": np.asarray(channels.flux_fmol_per_s).tolist(),
                        "power_pJ_per_s": np.asarray(channels.dissipation_rate_pJ_per_s).tolist(),
                        "state_layout_control_unchanged": True,
                    }
    return {
        "rows": rows,
        "backends": selected,
        "saved_state_origins": "D100-audited D099 active histories; not release trajectories",
        "accepted_runtime": runtime,
        "new_trajectory_executed": False,
        "reference_integration_executed": False,
        "native_dispatch_executed": False,
    }


def check(plan, result):
    """Independent full-state RHS checks, with strict coverage and exact blocked zeros."""
    design.validate_plan(plan)
    c.require(
        all(
            result[k] is False
            for k in (
                "new_trajectory_executed",
                "reference_integration_executed",
                "native_dispatch_executed",
            )
        ),
        "Unexpected execution scope",
    )
    backends = result["backends"]
    c.require(
        backends
        and len(set(backends)) == len(backends)
        and all(b in plan["backends"] for b in backends),
        "Invalid probe backend coverage",
    )
    ledger = io.Ledger(plan["absolute_tolerances"], relative=plan["relative_tolerance"])
    expected_keys = set()
    for history in plan["histories"]:
        definition = design.definition(plan, history, "baseline", plan["cells_steps_s"][0])
        saved = saved_record(history)
        n = len(definition["model"]["cells"])
        for time in plan["probe_times_s"]:
            index = saved["times"]["values"].index(time)
            expected_state = {k: v["values"][index] for k, v in saved["history"].items()}
            for value in plan["probe_availabilities"]:
                rate, target = oracle(plan, history, definition, expected_state, value)
                for backend in backends:
                    key = f"{history}/{time:.8g}/{value:g}/{backend}"
                    expected_keys.add(key)
                    row = result["rows"][key]
                    c.require(
                        row["history"] == history
                        and row["saved_time_s"] == time
                        and row["availability"] == value
                        and row["backend"] == backend
                        and row["state"] == expected_state
                        and row["state_layout_control_unchanged"] is True
                        and set(row["rhs"]) == set(rate),
                        "Probe state, identity or mutation flag changed",
                    )
                    for name, expected in rate.items():
                        units = (
                            "gate_rate_per_s"
                            if name == "gate"
                            else ("power_pJ_per_s" if "energy" in name else "flux_fmol_per_s")
                        )
                        ledger.compare(key + "/" + name, row["rhs"][name], expected, units)
                        if value == 0 and name != "gate":
                            c.require(
                                row["rhs"][name] == expected,
                                "Blocked physical rate not exactly zero",
                            )
                    for name, values, width in (
                        ("voltage_V", target["voltage_V"], definition["execution"]["capacity"]),
                        (
                            "permeability_m_per_s",
                            target["permeability_m_per_s"],
                            definition["execution"]["channel_capacity"],
                        ),
                        (
                            "flux_fmol_per_s",
                            target["inward_K_fmol_per_s"],
                            definition["execution"]["channel_capacity"],
                        ),
                        (
                            "power_pJ_per_s",
                            target["dissipation_pJ_per_s"],
                            definition["execution"]["channel_capacity"],
                        ),
                    ):
                        ledger.compare(
                            key + "/" + name, row[name], values + [0.0] * (width - n), name
                        )
    c.require(set(result["rows"]) == expected_keys, "Omitted, extra or duplicate probe identity")
    return ledger.summary() | {
        "failures": ledger.failures,
        "rhs_evaluations": len(expected_keys),
        "new_trajectory_executed": False,
        "release_response_qualified": False,
    }
