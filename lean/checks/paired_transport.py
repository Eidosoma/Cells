"""Compare epithelial chloride reversal and recombinant SK2 measurements with Cells."""

import json
import math
from pathlib import Path

import charged_permeation
import chloride_channel
import jax
import numpy as np
import regulated_availability
from scipy.optimize import brentq

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.laws.junctions.selective import selective_flux
from cells.operators.species_regulated_availability import LAW_ID_V2
from validation.tissue import regulated_availability_fixtures as gates
from validation.tissue import secreted_species_fixtures as pools

DATA = Path(__file__).with_name("data") / "paired_transport_responses.json"


def chloride_shift(study):
    temperature = study["temperature_C"] + 273.15
    high, low = study["external_Cl_mM"]

    def zero_mV(outside):
        # Fixed internal chloride cancels from the predicted shift.
        def flux(volts):
            return selective_flux(50.0, outside, volts, -1, temperature, 1, 1, 0, 1, 1, xp=np)

        return 1000 * brentq(flux, -0.12, 0.06)

    return {"model_shift_mV": zero_mV(low) - zero_mV(high), "measured_shift_mV": study["shift_mV"]}


def rise_interval(version):
    """Locate both crossing times on a compiled rising trace with a nonzero starting state."""
    dt, end = 1 / 2048, 1 / 16
    times = np.asarray(pools.grid_times(end, dt, dt))
    raw = pools.world(
        nodes=(),
        contacts=(),
        faces=(),
        dt=dt,
        end=end,
        trace_mM=0.001,
        observation_times=times.tolist(),
    )
    # The held concentration equals the Hill midpoint, giving a = 16/s and b = 16/s.
    start, on, off = 0.125, 32.0, 16.0
    opening = on / 2
    plateau = opening / (opening + off)
    state = gates.state(
        "gate",
        ["cell_0"],
        [("hill_activation", pools.SPECIES, 0.001, 1.0)],
        on=on,
        off=off,
        initial=start,
    )
    raw = gates.with_coupling(raw, species=[pools.SPECIES], states=[state])
    if version == 2:
        raw["model"]["operators"][-1]["law"] = LAW_ID_V2
    result = run(parse_spec(raw))
    trace = np.asarray(result.observations.regulatory_state)[:, 0]
    assert trace[0] == start and np.all(np.diff(trace) > 0)
    brackets = []
    for fraction in (0.2, 0.8):
        index = int(np.searchsorted(trace, start + fraction * (plateau - start)))
        assert 0 < index < len(times)
        left, right = times[index - 1 : index + 1]
        assert left <= -math.log1p(-fraction) / (opening + off) <= right
        brackets.append((left, right))
    (lo20, hi20), (lo80, hi80) = brackets
    elapsed = math.log(4) / (opening + off)
    ceiling = math.log(4) / off
    assert lo80 - hi20 <= elapsed <= hi80 - lo20 <= ceiling
    return {
        "dt_ms": 1000 * dt,
        "rise_20_80_bracket_ms": [1000 * (lo80 - hi20), 1000 * (hi80 - lo20)],
        "exact_rise_20_80_ms": 1000 * elapsed,
        "washout_ceiling_ms": 1000 * ceiling,
    }


def sk2_comparisons(syme, oliver):
    fit = regulated_availability.sk2_comparison()
    half, hill = fit["apparent_half_uM"], fit["hill_exponent"]
    midpoint = syme["control_half_uM"]
    ceiling = math.log(4) * oliver["washout_tau_ms"]
    return {
        "cells_half_uM": half,
        "cells_hill": hill,
        "syme_control_half_uM": midpoint,
        "syme_control_hill": syme["control_hill"],
        "cells_fraction_of_ceiling_at_syme_midpoint": 1 / (1 + (half / midpoint) ** hill),
        "hirschberg_cells_activation_tau_ms": fit["charged_cell_clamps"]["rise_ms"],
        "hirschberg_measured_activation_tau_ms": fit["measured_rise_ms"],
        "oliver_high_dose_rise_20_80_ms": oliver["rise_20_80_ms"],
        "oliver_low_dose_rise_20_80_ms_approx": oliver["low_rise_20_80_ms_approx"],
        "oliver_ceiling_from_mean_washout_ms": ceiling,
    }


if __name__ == "__main__":
    if jax.default_backend() != "cpu" or not jax.config.x64_enabled:
        raise RuntimeError("Run with JAX_PLATFORMS=cpu and JAX_ENABLE_X64=1")
    data = json.loads(DATA.read_text())
    print(
        json.dumps(
            {
                "compiled_gate": {str(v): rise_interval(v) for v in (1, 2)},
                "sk2": sk2_comparisons(
                    data["syme2000_rsk2_calcium@1"], data["oliver2000_rsk2_calcium_jumps@1"]
                ),
                "bajnath_chloride": chloride_shift(data["bajnath1993_chloride_reversal@1"]),
                "ling_chloride": chloride_channel.paper_reversal_shift(),
                "constant_field": charged_permeation.biology(),
            },
            indent=2,
            allow_nan=False,
        )
    )
