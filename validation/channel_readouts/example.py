"""FR-34's maintained example: a membrane channel population's surface count, availability and
signed current, read from today's fields, with the halving control (README.md beside this file).

The world is FR-7's pump-free heredity cell in miniature
(validation/fr7/unit_turnover_fixtures.cell): one cell facing its held bath, with two gate-free K
populations on its one patch, declared in cells.operator.membrane_entity_state@1. Here they are made twins:
`leak_1` takes `kir_0`'s abundance, so the same count of units, and only their availabilities
differ, 1 for `kir_0` and 0.5 for `leak_1`. On one patch they share the voltage and both ends'
concentrations at every row, so the same driving force, and leak_1's current must be half of
kir_0's at every observed row. The world runs a few steps of 1 ms through the windowed runner,
observed at every step.

Per observed row it exports, for each population:
- the count: membrane state's readout `population_units` (units);
- the availability: @3's `channel_availability` (dimensionless), the value the population runs at
  before the routing door. In a composite it already holds the operators' factors (D265), so it is
  not multiplied by them again;
- the flux: @3's `channel_flux_fmol_s` per species (fmol/s, positive outward, from the cell of the
  population's patch to that patch's outside node);
- the current, derived: I = 1e-15 F sum_s z_s J_s (A, positive outward);
- the voltage it is at: @3's `membrane_voltage_V` on the patch (V, inside minus outside).

At a declared voltage. Passive routes and transporter populations have it (cells.kind.passive_routes@1's
clamped_flux, cells.kind.transporter@1's clamped_rates); @3's channel populations, read here, do not yet,
and that is the @3 owner's engine work (FR-34, D252). The first observed row, t = 0, is the declared
initial state: its voltage is the definition's charge anchor over the cell's capacitance, q0/C. So
row 0's current is the current at that declared voltage, and the output says so
(`first_row_at_declared_voltage`). Every later row is at the run's own, evolving voltage. In a
composite, a current at any declared voltage is the composition's own clamped_channel_flux
(cells.models.pump_composite; D265), never @3's helper given the stored controls.
"""

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from cells.laws.electrochemistry import F
from validation.fr7 import unit_turnover_fixtures as ufx

FULL, HALF = "kir_0", "leak_1"  # The twins: availability 1 and 0.5.
STEPS = 5
DT = 1e-3
DECLARED_V_ATOL = 1e-12  # V: row 0 against q0/C, rounding only.


def world(*, steps=STEPS):
    """The cell with its twin populations, observed at every step."""
    times = [k * DT for k in range(steps + 1)]
    raw = ufx.cell(end=steps * DT, dt=DT, observation_times=times)
    channels = {c["id"]: c for c in raw["model"]["channels"]}
    channels[HALF]["abundance"] = channels[FULL]["abundance"]  # The same count of units.
    for control in raw["experiment"]["channel_controls"]:
        if control["channel_id"] in (FULL, HALF):
            level = 1.0 if control["channel_id"] == FULL else 0.5
            control["schedule"] = [dict(time=0.0, availability=level)]
    return raw


def declared_voltage(spec, cell=ufx.CELL):
    """V at t = 0 as declared: the cell's charge anchor over its patches' capacitance (one cell
    facing a held bath at 0 V)."""
    owner = next(c for c in spec.model.cells if c.id == cell)
    capacitance = sum(m.capacitance_F for m in spec.model.membranes if m.inside == cell)
    return owner.initial_charge_C / capacitance


def readouts(*, steps=STEPS):
    """{times, species, declared_initial_voltage_V, and per population: units, availability,
    flux_fmol_s (per species), current_A, voltage_V}, at each observed row once (adjacent windows
    share an endpoint)."""
    spec = parse_spec(world(steps=steps))
    ids = [c.id for c in spec.model.channels]
    membranes = [m.id for m in spec.model.membranes]
    valence = np.asarray(spec.model.valence, dtype=float)
    out = dict(
        times=[],
        species=list(spec.model.species_ids),
        declared_initial_voltage_V=float(declared_voltage(spec)),
        populations={},
    )
    slots = {}
    for name in (FULL, HALF):
        patch = next(c.membrane_id for c in spec.model.channels if c.id == name)
        slots[name] = (ids.index(name), membranes.index(patch))
        out["populations"][name] = dict(
            units=[], availability=[], flux_fmol_s=[], current_A=[], voltage_V=[]
        )
    for window in iter_windows(spec, WindowPolicy(window_steps=steps, recording="observations")):
        obs = window.observations
        for i, t in enumerate(np.asarray(obs.times)):
            if out["times"] and float(t) <= out["times"][-1]:
                continue  # The shared endpoint of adjacent windows.
            out["times"].append(float(t))
            for name, (channel, membrane) in slots.items():
                rows = out["populations"][name]
                flux = np.asarray(obs.channel_flux_fmol_s)[i][:, channel]
                rows["units"].append(float(np.asarray(obs.population_units)[i][channel]))
                rows["availability"].append(float(np.asarray(obs.channel_availability)[i][channel]))
                rows["flux_fmol_s"].append([float(v) for v in flux])
                rows["current_A"].append(float(1e-15 * F * np.dot(valence, flux)))
                rows["voltage_V"].append(float(np.asarray(obs.membrane_voltage_V)[i][membrane]))
    v0 = out["populations"][FULL]["voltage_V"][0]
    out["first_row_at_declared_voltage"] = bool(
        abs(v0 - out["declared_initial_voltage_V"]) <= DECLARED_V_ATOL
    )
    return out


def halving_control(*, steps=STEPS):
    """The control at every observed row: the twins' current ratio (0.5 within rounding), their
    counts and voltages (equal) and availabilities (1 and 0.5)."""
    out = readouts(steps=steps)
    full, half = out["populations"][FULL], out["populations"][HALF]
    out["control"] = dict(
        current_ratio=[h / f for h, f in zip(half["current_A"], full["current_A"], strict=True)],
        same_units=full["units"] == half["units"],
        same_voltage=full["voltage_V"] == half["voltage_V"],
        availability=(full["availability"][0], half["availability"][0]),
    )
    return out


if __name__ == "__main__":
    import json

    result = halving_control()
    first = {k: v["current_A"][0] for k, v in result["populations"].items()}
    print(
        json.dumps(
            dict(
                control=result["control"],
                declared_initial_voltage_V=result["declared_initial_voltage_V"],
                first_row_at_declared_voltage=result["first_row_at_declared_voltage"],
                first_row_current_A=first,
            ),
            indent=1,
        )
    )
