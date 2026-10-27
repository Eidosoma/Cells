"""Declared 2-ms injury controls and engineering recovery bands, without fitted biology."""

import numpy as np

from cells.assays.recovery import sampled_recovery
from validation.tissue import surface_repair_fixtures as short

ARMS = short.ARMS
STEPS = (0.625e-6, 0.3125e-6, 0.15625e-6)
BANDS = dict(membrane_voltage_V=1e-5, cytosol_free_mM=1e-6, exterior_free_mM=1e-6)
UNCERTAINTY = dict(membrane_voltage_V=1e-7, cytosol_free_mM=1e-8, exterior_free_mM=1e-8)
READOUT_ATOL = dict(membrane_voltage_V=1e-8, cytosol_free_mM=1e-9, exterior_free_mM=1e-9)
SETTINGS = dict(intervention_s=5.3e-6, release_s=15.3e-6, hold_s=0.5e-3, max_gap_s=25e-6)


def definition(arm="resealing", *, backend="cpu", dt=STEPS[0]):
    raw = short.definition(arm, backend=backend)
    raw["experiment"].update(
        end_time=0.002,
        observation_times=sorted({5.3e-6, 15.3e-6, *(i * 40 * STEPS[0] for i in range(81))}),
    )
    raw["execution"].update(dt=dt, max_steps=16384, max_trace_bytes=2**33)
    return raw


def measurements(raw, observations):
    """Strip execution padding from the ordinary runner's owned free-ion readouts."""
    ion = raw["model"]["ionic"]
    nc, no, nm = (len(ion[k]) for k in ("cells", "extracellular", "membranes"))
    return dict(
        membrane_voltage_V=np.asarray(observations["membrane_voltage_V"])[:, :nm],
        cytosol_free_mM=np.asarray(observations["amount"])[:, :, :nc]
        / np.array([c["volume_pL"] for c in ion["cells"]]),
        exterior_free_mM=np.asarray(observations["extracellular_amount"])[:, :, :no]
        / np.array([c["volume_pL"] for c in ion["extracellular"]]),
    )


def assess(times, actual, baseline):
    return sampled_recovery(
        times, actual, baseline, bands=BANDS, uncertainty=UNCERTAINTY, **SETTINGS
    )
