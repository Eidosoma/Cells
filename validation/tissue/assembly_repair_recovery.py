"""Two-ms one-way assembly/injury controls with matched event histories."""

import numpy as np

from cells.models import surface_repair as model
from validation.tissue import surface_repair_fixtures as short
from validation.tissue import surface_repair_recovery as ordinary

ARMS, STEPS = ordinary.ARMS, ordinary.STEPS
BANDS, UNCERTAINTY, READOUT_ATOL = ordinary.BANDS, ordinary.UNCERTAINTY, ordinary.READOUT_ATOL
SETTINGS, assess = ordinary.SETTINGS, ordinary.assess


def definition(arm="resealing", *, backend="cpu", dt=STEPS[0]):
    raw = short.assembly_definition(arm, backend=backend)
    raw["ionic"] = ordinary.definition(arm, backend=backend, dt=dt)
    # Snapshots stay on nominal ticks; the kernel still splits at exact controls.
    indices = sorted({8, 9, 24, 25, *(i * 40 for i in range(81))})
    raw["ionic"]["experiment"]["observation_times"] = [i * STEPS[0] for i in indices]
    raw["window_ticks"] = 40
    for binding in raw["pools"]:
        binding["pool"]["end_time_s"] = 0.002
    return raw


def normalized(raw):
    from copy import deepcopy

    result = deepcopy(raw)
    result["ionic"]["execution"]["backend"] = "cpu"
    return result


def segments(spec, events):
    """Availability from independently reconstructed scalar assembly events."""
    times = sorted({0.0, *(float(e[0]) for rows in events.values() for e in rows)})
    result = []
    for time in times:
        levels = []
        for binding in spec.pools:
            past = [e for e in events[binding.cell_id] if e[0] <= time]
            mask, bonds = (
                past[-1][1:3] if past else (binding.pool.initial_mask, binding.pool.initial_bonds)
            )
            levels.append(
                binding.active_availability
                if int(bonds).bit_count() >= int(mask).bit_count()
                else binding.inactive_availability
            )
        result.append((time, levels))
    return result


def exposure(times, channel_segments):
    """Independent integral of each cell's piecewise constant availability."""
    rows = []
    for end in times:
        total = np.zeros(len(channel_segments[0][1]))
        for i, (start, opening) in enumerate(channel_segments):
            stop = channel_segments[i + 1][0] if i + 1 < len(channel_segments) else end
            total += max(0.0, min(end, stop) - start) * np.asarray(opening)
        rows.append(total)
    return np.stack(rows)


def measurements(spec, observed, world):
    """Read complete coupled snapshots without replaying or resetting ionic state."""
    _, p = model.initial_values(spec.ionic)
    nc = len(spec.pools)
    no = len(spec.ionic.model.extracellular)
    voltage, inside, outside = [], [], []
    for i, time in enumerate(observed["pool_time_s"][:, world, 0]):
        state = model.STATE_TYPE(
            *(observed["ionic_" + k][i, world] for k in model.STATE_TYPE._fields)
        )
        voltage.append(model.ensemble_voltage(state, p, spec.ionic, time))
        inside.append(model.cytosol_amount(state, p, xp=np)[:, :nc] / p.volume[:nc])
        outside.append(
            (p.extracellular_amount_reference + state.extracellular_amount_increment)[:, :no]
            / p.extracellular_volume[:no]
        )
    return dict(
        membrane_voltage_V=np.stack(voltage),
        cytosol_free_mM=np.stack(inside),
        exterior_free_mM=np.stack(outside),
    )
