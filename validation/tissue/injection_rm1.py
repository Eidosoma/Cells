"""First acceptance of electrode_current_injection@1: Rm1 on the uncleaved egg (PROPOSED; not run).

docs/PUMP_COMPOSITE_V2_DESIGN.md §4.1. The world is the uncleaved egg of
validation/tissue/egg_scale_smoke.py: resolved_pump_tissue@3, anchor "consistent", IMEX
ARS(2,2,2) at 1 ms, which ran 35 min cleanly in S0b. It becomes a composition with one
electrode driven by J1's registered pulse protocol (validation/division/
j1_declared_inputs.json, rm_definition): pulses of +/-3e-8 A lasting 1.2 s every 10 s,
alternating and starting positive at t = 0, carried by K 0.4912 and Cl 0.5088.

Observable (the rm_rule): Rm1 = (|dV_0| + |dV_1|) / (2 x 3e-8 A), with
dV_k = V(t_k + 1.0 s) - V(t_k).

Acceptance, registered before the run: |Rm1 - Rm1_reference| <= 3 x (engine step term +
reference term).
* The engine step term is |Rm1(1 ms) - Rm1(0.5 ms)|, from a development dt study.
* Rm1_reference is R-full's first pulse pair, 852 kOhm, pinned from its record at
  registration.

This module only builds and checks the definition. The lead approves the run before launch.

Usage: python -m validation.tissue.injection_rm1 --output DEFINITION.json [--dt S] [--check]
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    for entry in (ROOT / "src", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

LAW = "electrode_current_injection@1"
RM1_REFERENCE_OHM = 852e3  # R-full's first pulse pair (lead, 12 November); pinned at registration.
STATUS = "PROPOSED first acceptance of electrode_current_injection@1; not run."


def protocol():
    inputs = json.loads((ROOT / "validation/division/j1_declared_inputs.json").read_text())
    return inputs["rm_definition"]


def definition(dt=1e-3):
    """The composition: the uncleaved egg with one electrode and pulses 0 and 1."""
    from cells.core import pump_composite_spec as cs
    from validation.tissue import egg_scale_smoke as smoke

    rm = protocol()
    period, width = rm["pulse_period_s"], rm["pulse_duration_s"]
    amplitude, sign = rm["pulse_amplitude_A"], rm["first_pulse_sign"]

    def grid(t):  # Every scheduled time an exact multiple of dt.
        return round(t / dt) * dt

    end = grid(period + width + 0.8)  # Past pulse 1's sample at t_1 + 1.0 s.
    raw, _ = smoke.egg_definition(end_time=end, dt=dt, anchor="consistent", observe_every=1.0)
    raw["experiment"]["observation_times"] = [0.0, grid(1.0), grid(period), grid(period + 1.0)]
    out = cs.frozen_definition(raw)
    cell = out["model"]["cells"][0]["id"]
    carriers = rm["injected_carrier_fractions"]
    out["model"]["operators"] = [dict(law=LAW, electrodes=[dict(cell_id=cell, carriers=carriers)])]
    schedule = [
        dict(time=0.0, current_A=sign * amplitude),
        dict(time=grid(width), current_A=0.0),
        dict(time=grid(period), current_A=-sign * amplitude),
        dict(time=grid(period + width), current_A=0.0),
    ]
    out["experiment"]["injection_controls"] = [dict(cell_id=cell, schedule=schedule)]
    return out


def rm1(voltage_at):
    """Rm1 (Ohm) from V at t_0, t_0 + 1.0 s, t_1 and t_1 + 1.0 s (the rm_rule)."""
    rm = protocol()
    v0, v0b, v1, v1b = voltage_at
    return (abs(v0b - v0) + abs(v1b - v1)) / (2 * rm["pulse_amplitude_A"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dt", type=float, default=1e-3)
    parser.add_argument("--check", action="store_true", help="parse and check (no run)")
    args = parser.parse_args(argv)
    raw = definition(args.dt)
    if args.check:
        import jax

        jax.config.update("jax_enable_x64", True)
        from cells.core.specs import parse_spec
        from cells.models.registry import get_model

        spec = parse_spec(raw)
        get_model(spec.model).check_definition(spec)
    record = dict(status=STATUS, rm1_reference_ohm=RM1_REFERENCE_OHM, definition=raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=1) + "\n")
    print("written", args.output, "(checked)" if args.check else "")


if __name__ == "__main__":
    main()
