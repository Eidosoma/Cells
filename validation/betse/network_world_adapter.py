#!/usr/bin/env python3
"""BETSE's default world with general-network ion channels, run by the BETSE-order emulator.

Extends ``default_world_adapter`` to plain-BETSE cases whose general network holds only
ion channels (no biomolecules, reactions, transporters or modulators): currently Kv1p5
and KLeak on every membrane, with no inhibitors or activators. ``network_world`` reads
the case with ``default_world_adapter.betse_world``, the only relaxation being that the
network is on (``molecules_enabled``); every other adapter requirement and check
applies. It adds the channel list from the case's ``network_config``.

The emulator step is ``emulator/network.py``; the run writes the comparison layout of
``default_world_adapter.run_emulator`` plus the channel gates. Channel gates start at
their steady state for Vm = 0 in INIT (BETSE creates the network before the first
voltage update) and, in SIM, for the Vm of the SIM start state (BETSE re-reads the
network at SIM start with the INIT-end Vm). Validation tooling; no Cells engine model.

``run-resolved`` runs Cells' own physics, resolved_pump_tissue@3: default_world_adapter's
resolved_pump_tissue@2 definition (``run_resolved``, blind) plus one channel population per
membrane patch and network channel (Kv1p5 -> kv1p5_mh@1, KLeak -> kleak_always_open@1),
max_permeability = max Dm / tm, abundance 1, permeant K. Its gates start as BETSE's do: the
steady state at 0 V in INIT and, at the SIM handoff, the steady state at the membrane
voltage of Cells' own INIT end. Channels with ``init active: false`` get availability 0 in
INIT. It is default_world_adapter.run_resolved with the backend NETWORK_RESOLVED
(default_world_adapter.ResolvedBackend): this module's world, definition, handoff and model
identity.

    PYTHONPATH=SRC/src:SRC python3 validation/betse/network_world_adapter.py run \\
        --case CASE --protocol P.json --out DIR [--dt-factor F --sim-start chained]
    ... difference-budget --case CASE --pair NAME BASE OTHER ... --out FILE.json
    ... run-resolved --case CASE --device cpu --dt-init 1e-3 --out DIR [--protocol P.json]
"""

import argparse
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    for entry in (ROOT / "src", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

from validation.betse import betse_reference_run as reference_run  # noqa: E402
from validation.betse import default_world_adapter as adapter  # noqa: E402

PHASES = adapter.PHASES
# BETSE channel type (vg_k.py) -> emulator kind; both are K channels.
CHANNEL_TYPES = {"Kv1p5": "kv1p5", "KLeak": "kleak"}
CHANNEL_KEYS = {"name", "channel class", "channel type", "max Dm", "apply to", "init active"}
EXECUTED = (
    "validation/betse/network_world_adapter.py",
    "validation/betse/emulator/network.py",
)
RESOLVED_CHANNEL_MODEL_ID = "resolved_pump_tissue@3"
RESOLVED_LAWS = {"kv1p5": "kv1p5_mh@1", "kleak": "kleak_always_open@1"}
# default_world_adapter's requirements with the general network on (its only relaxation).
NETWORK_REQUIRED = adapter.REQUIRED_PARAMS | {"molecules_enabled": True}


class NetworkError(adapter.AdapterError):
    """The general network holds something this runner does not map; nothing is run."""


def network_channels(params):
    """[(name, kind, max Dm m^2/s, init active)] of an ion-channel-only network config."""
    config = params.get("network_config") or {}
    if not config.get("implement network"):
        raise NetworkError("the general network is off")
    if config.get("biomolecules") or any(
        config.get(k) for k in ("reactions", "transporters", "modulators")
    ):
        raise NetworkError("network has biomolecules, reactions, transporters or modulators")
    channels = []
    for c in config.get("channels") or []:
        if extra := sorted(set(c) - CHANNEL_KEYS):
            raise NetworkError(f"channel {c.get('name')}: unmapped keys {extra}")
        if c.get("channel class") != "K" or c.get("channel type") not in CHANNEL_TYPES:
            raise NetworkError(f"channel {c.get('name')}: only K Kv1p5 and KLeak are mapped")
        if c.get("apply to") != "all":
            raise NetworkError(f"channel {c.get('name')}: only 'apply to: all' is mapped")
        dm = float(c["max Dm"])
        if not np.isfinite(dm) or dm < 0:
            raise NetworkError(f"channel {c.get('name')}: max Dm must be finite and >= 0")
        channels.append((c["name"], CHANNEL_TYPES[c["channel type"]], dm, bool(c["init active"])))
    if not channels:
        raise NetworkError("network has no channels")
    return channels


def network_world(case, *, blind=False):
    """default_world_adapter.betse_world with the network on, plus its channel list."""
    world = adapter.betse_world(case, blind=blind, required=NETWORK_REQUIRED)
    _, manifest = adapter._blind_case(case) if blind else adapter.load_case(case)
    params = {phase: adapter.betse_parameters(manifest, phase) for phase in PHASES}
    channels = {phase: network_channels(params[phase]) for phase in PHASES}
    if channels["init"] != channels["sim"]:
        raise NetworkError("network channels differ between INIT and SIM")
    if "K" not in world["species"]:
        raise NetworkError("K channels need a K ion")
    world["network_channels"] = channels["init"]
    world["membrane_thickness_m"] = float(params["init"]["tm"])
    return world


# ............................................................ resolved backend (@3)


def steady_mh(vm):
    """Kv1p5 (m, h) steady state at each membrane voltage: [2, membrane]."""
    from cells.processes import voltage_gates

    return voltage_gates.kinetics(np.asarray(vm, dtype=np.float64).reshape(-1), xp=np)[0]


def resolved_channel_definition(world, phase, start, **kwargs):
    """The adapter's @2 definition of the phase plus the network's channel populations."""
    definition = adapter.resolved_definition(world, phase, start, **kwargs)
    model, experiment = definition["model"], definition["experiment"]
    if world["calcium_pump"] is None:
        raise NetworkError("resolved_pump_tissue@3 extends @2: the world needs its Ca-ATPase")
    mh = steady_mh(start.get("channel_vm_V", np.zeros(len(model["membranes"]))))
    channels, controls = [], []
    for name, kind, dm, init_active in world["network_channels"]:
        available = 1.0 if phase == "sim" or init_active else 0.0
        for j, row in enumerate(model["membranes"]):
            cid = f"chan-{name}-{j}"
            channels.append(
                {
                    "id": cid,
                    "membrane_id": row["id"],
                    "kinetic_law": RESOLVED_LAWS[kind],
                    "max_permeability_m_per_s": dm / world["membrane_thickness_m"],
                    "abundance": 1.0,
                    "initial_gate": [float(mh[0, j]), float(mh[1, j])] if kind == "kv1p5" else [],
                    "permeant_ions": [{"species_id": "K", "relative_permeability": 1.0}],
                }
            )
            controls.append(
                {"channel_id": cid, "schedule": [{"time": 0.0, "availability": available}]}
            )
    model["id"] = RESOLVED_CHANNEL_MODEL_ID
    model["channels"] = channels
    experiment["channel_controls"] = controls
    definition["execution"]["channel_capacity"] = len(channels)
    return definition


def resolved_channel_handoff(definition, checkpoint):
    """The adapter's handoff plus the patch voltages at the INIT end (SIM gates start there)."""
    from cells.core.schedule import control_values
    from cells.core.specs import parse_spec
    from cells.models.registry import get_model

    start = adapter.resolved_handoff(definition, checkpoint)
    spec = parse_spec(definition)
    controls = control_values(spec, [float(checkpoint.time)])
    control = type(controls)(*(np.asarray(v[0]) for v in controls))
    state = type(checkpoint.state)(*(np.asarray(v) for v in checkpoint.state))
    layout = type(checkpoint.layout)(*(np.asarray(v) for v in checkpoint.layout))
    values = get_model(spec.model).readouts(state, control, layout, xp=np)
    m = len(definition["model"]["membranes"])
    start["channel_vm_V"] = np.asarray(values.field.rates.membrane_voltage_V)[:m]
    return start


NETWORK_RESOLVED = adapter.ResolvedBackend(
    network_world,
    resolved_channel_definition,
    resolved_channel_handoff,
    lambda world: RESOLVED_CHANNEL_MODEL_ID,
    adapter.EXECUTED + EXECUTED,
)


def run_network_resolved(case, out, **kwargs):
    """default_world_adapter.run_resolved (blind) with the network's channel populations."""
    return adapter.run_resolved(case, out, backend=NETWORK_RESOLVED, **kwargs)


def network_inputs(world, phase, start, variant):
    from validation.betse.emulator import network, spatial

    state, layout, ko = adapter.emulator_inputs(world, phase, start, variant)
    channels, m = world["network_channels"], world["membrane_area_m2"].size
    kinds = tuple(kind for _, kind, _, _ in channels)
    k = world["species"].index("K")
    p = network.validate_layout(
        network.Layout(
            layout,
            kinds,
            tuple(k for _ in channels),
            np.stack([np.full(m, dm / world["membrane_thickness_m"]) for _, _, dm, _ in channels]),
            np.asarray([1.0 if phase == "sim" or active else 0.0 for _, _, _, active in channels]),
        ),
        variant=variant,
    )
    if phase == "init":
        vm = np.zeros(m)
    else:
        vm = np.asarray(
            spatial.field(
                state.active.tissue, layout.active.tissue, xp=np, variant=variant
            ).membrane_voltage_V
        )
    gates = start.get("channel_gates")
    if gates is None or phase == "sim":  # BETSE re-reads the network at SIM start
        gates = network.steady_gates(kinds, vm)
    return network.State(state, np.asarray(gates, dtype=np.float64)), p, ko, vm


def network_phase(state, layout, dt, steps, variant, device, substeps=1):
    """default_world_adapter.emulator_phase with the network step."""
    import jax
    import jax.numpy as jnp

    from validation.betse.emulator import junction, network, spatial

    m = layout.junction.junction_block.size
    control = junction.Control(*(np.ones(m) for _ in junction.Control._fields))
    static = {"kinds": layout.kinds, "ion": layout.ion}  # strings and indices: not traced

    def run(state, layout, dt, control):
        layout = layout._replace(**static)

        def update(carry):
            old, ok = carry
            new, _, valid = network.step(old, layout, dt, control, variant=variant)
            ok = ok & valid
            return jax.tree.map(lambda a, b: jnp.where(ok, a, b), new, old), ok

        def one(carry, _):
            if substeps == 1:
                new, ok = update(carry)
            else:
                new, ok = jax.lax.fori_loop(0, substeps, lambda _, c: update(c), carry)
            t = new.junction.active.tissue
            f = spatial.field(t, layout.junction.active.tissue, variant=variant)
            record = (
                f.membrane_voltage_V,
                t.cell_concentration,
                t.outside_concentration,
                f.outside_potential_V.reshape(-1),
                new.junction.junction_open,
                new.gates,
                ok,
            )
            return (new, ok), record

        return jax.lax.scan(one, (state, jnp.asarray(True)), None, length=steps)

    compiled = jax.jit(run)
    traced = layout._replace(kinds=None, ion=None)
    args = jax.device_put((state, traced, jnp.asarray(dt), control), device)
    start = time.perf_counter()
    (final, ok), history = jax.block_until_ready(compiled(*args))
    wall = time.perf_counter() - start
    history = [np.asarray(v) for v in history]
    accepted = history[-1]
    tissue = final.junction.active.tissue
    return {
        "valid": bool(ok),
        "accepted_samples": int(accepted.sum()),
        "first_rejected_sample": None if accepted.all() else int(np.argmin(accepted)) + 1,
        "wall_s_including_compile": wall,
        "vm": history[0],
        "cell_mM": history[1],
        "env_mM": history[2],
        "v_env": history[3],
        "gate_open": history[4],
        "channel_gates": history[5],
        "end": {
            "cell_mM": np.asarray(tissue.cell_concentration),
            "membrane_mM": np.asarray(tissue.membrane_concentration),
            "env_mM": np.asarray(tissue.outside_concentration),
            "gate_open": np.asarray(final.junction.junction_open),
            "channel_gates": np.asarray(final.gates),
        },
        "accounting": {
            k: float(np.abs(v).max())
            for k, v in spatial.accounting(
                state.junction.active.tissue, tissue, layout.junction.active.tissue
            ).items()
        },
    }


def run_network_emulator(
    case, protocol_path, out, *, constants, device_kind, sim_start, dt_factor=1, differences=()
):
    import jax

    jax.config.update("jax_enable_x64", True)
    from validation.betse.emulator import laws

    protocol, protocol_sha = adapter.compare.load_protocol(protocol_path)
    world = network_world(case)
    variant = laws.default_world(constants, differences)
    device = jax.devices(device_kind)[0]
    phases, records, chained = {}, {}, None
    for phase in PHASES:
        start = adapter.phase_start(world, phase, sim_start, chained)
        state, layout, ko, vm0 = network_inputs(world, phase, start, variant)
        dt, steps = world["dt_s"][phase], world["steps"][phase]
        result = network_phase(state, layout, dt / dt_factor, steps, variant, device, dt_factor)
        chained = result["end"]
        gates = result["channel_gates"]
        records[phase] = {
            "dt_s": dt / dt_factor,
            "dt_factor": dt_factor,
            "updates": steps * dt_factor,
            "valid": result["valid"],
            "accepted_samples": result["accepted_samples"],
            "first_rejected_sample": result["first_rejected_sample"],
            "wall_s_including_compile": result["wall_s_including_compile"],
            "start": "configured cell/env concentrations, gates 1"
            if phase == "init"
            else sim_start,
            "channel_gate_start": "steady state at Vm = 0"
            if phase == "init"
            else "steady state at the SIM start state's Vm",
            "channel_gate_start_vm_range_V": [float(vm0.min()), float(vm0.max())],
            "channels": [
                {
                    "name": name,
                    "kind": kind,
                    "max_Dm_m2_s": dm,
                    "permeability_m_s": dm / world["membrane_thickness_m"],
                    "active": bool(layout.active[c] > 0),
                    "open_fraction_end_range": [
                        float((gates[-1, c, 0] * gates[-1, c, 1]).min()),
                        float((gates[-1, c, 0] * gates[-1, c, 1]).max()),
                    ],
                }
                for c, (name, kind, dm, _) in enumerate(world["network_channels"])
            ],
            "accounting_max_abs_fmol": result["accounting"],
            "ko_env_per_m": ko,
            "betse_ko_env_per_m": world["betse_ko_env"][phase],
            "ko_env_relative_difference": ko / world["betse_ko_env"][phase] - 1,
            "gate_open_range": [float(result["gate_open"].min()), float(result["gate_open"].max())],
        }
        elapsed = [(k + 1) * dt for k in range(steps)]
        phases[phase] = adapter.layout_phase(
            world, elapsed, result["vm"], result["cell_mM"], result["env_mM"], result["v_env"]
        )
        if not result["valid"]:
            break
    record = {
        "kind": "cells.network_world_adapter_run@1",
        "created_utc": reference_run.utc_now(),
        "backend": "emulator",
        "model": "validation/betse/emulator/network.py (BETSE-order kernel, not an engine model)",
        "variant": variant._asdict(),
        "constants": constants,
        "model_differences": list(differences),
        "dt_factor": dt_factor,
        "device": str(device),
        "jax": jax.__version__,
        "sim_start": sim_start,
        "case": world["case"],
        "betse_extract": world["extract"],
        "network_channels": world["network_channels"],
        "protocol": {
            "path": str(Path(protocol_path).resolve()),
            "sha256": protocol_sha,
            "id": protocol.get("id"),
        },
        "phases": records,
        "valid": all(r["valid"] for r in records.values()) and len(records) == len(PHASES),
        "max_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    }
    record = adapter.provenance(record, adapter.EXECUTED + EXECUTED)
    out = reference_run.resolve_out(out)
    if record["valid"]:
        adapter.compare.write_layout(
            out,
            phases,
            protocol_sha256=protocol_sha,
            betse_geometry_sha256=world["geometry_sha256"],
            provenance=record,
        )
    else:
        out.mkdir(parents=True, exist_ok=False)
    reference_run.write_json(out / "run.json", adapter.compare.json_safe(record))
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="emulator run of a network-channel case")
    run.add_argument("--case", required=True)
    run.add_argument("--protocol", required=True)
    run.add_argument("--constants", choices=("betse", "codata"), default="betse")
    run.add_argument("--device", choices=("cpu", "gpu"), default="cpu")
    run.add_argument("--sim-start", choices=("betse", "chained"), default="betse")
    run.add_argument("--dt-factor", type=int, default=1)
    run.add_argument("--model-difference", action="append", default=[])
    run.add_argument("--out", required=True)
    budget = sub.add_parser("difference-budget", help="default_world_adapter's, network on")
    budget.add_argument("--case", required=True, help="BETSE case (inputs only)")
    budget.add_argument(
        "--pair", nargs=3, action="append", required=True, metavar=("NAME", "BASE", "OTHER")
    )
    budget.add_argument("--out", required=True, help="fresh JSON file")
    blind = sub.add_parser("run-resolved", help="blind resolved_pump_tissue@3 INIT then SIM")
    blind.add_argument("--case", required=True)
    blind.add_argument("--device", choices=("cpu", "gpu"), default="cpu")
    blind.add_argument("--dt-init", type=float, default=1e-3)
    blind.add_argument("--dt-sim", type=float, default=1e-4)
    blind.add_argument("--window-steps", type=int, default=250)
    blind.add_argument("--protocol", help="pre-registered protocol (judged run); omit for blind")
    blind.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "run-resolved":
        record = run_network_resolved(
            args.case,
            args.out,
            device_kind=args.device,
            dt_init=args.dt_init,
            dt_sim=args.dt_sim,
            window_steps=args.window_steps,
            protocol_path=args.protocol,
        )
        print(json.dumps({"valid": record["valid"], "device": record["device"]}, indent=2))
        return 0 if record["valid"] else 1
    if args.command == "difference-budget":
        world = network_world(args.case, blind=True)
        result = adapter.difference_budget(world, args.pair, adapter.EXECUTED + EXECUTED)
        out = reference_run.resolve_out(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        reference_run.write_json(out, adapter.compare.json_safe(result))
        print(json.dumps({"out": str(out), "pairs": list(result["pairs"])}, indent=2))
        return 0
    record = run_network_emulator(
        args.case,
        args.protocol,
        args.out,
        constants=args.constants,
        device_kind=args.device,
        sim_start=args.sim_start,
        dt_factor=args.dt_factor,
        differences=tuple(args.model_difference),
    )
    summary = {k: record[k] for k in ("valid", "constants", "dt_factor", "sim_start")}
    summary["phases"] = {
        p: {
            k: r[k]
            for k in ("valid", "wall_s_including_compile", "accounting_max_abs_fmol", "channels")
        }
        for p, r in record["phases"].items()
    }
    print(json.dumps(adapter.compare.json_safe(summary), indent=2))
    return 0 if record["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
