"""Independent scalar schedule arithmetic; no production/JAX imports."""

from decimal import Decimal, localcontext

import numpy as np

from validation.perturbations import physiology_calendar_reference as calendars
from validation.perturbations import spatial_modulation_reference as spatial
from validation.perturbations import time_modulation_reference as modulators


def stage(plan, binding, initial, current, loop_index):
    if current["controls"]["phase"] != "SIM":
        return current
    modifier = np.array(initial["diffusion"]["scheduled_m2_s"], dtype=float, copy=True)
    for row in plan["changes"]:
        if row["loop_index"] <= loop_index:
            modifier = np.array(row["scheduled_m2_s"], dtype=float, copy=True)
    time = loop_index * plan["physiological_dt_s"]
    if "native_calendar" in plan:
        time = calendars.event_label(plan["native_calendar"], loop_index)
    ions, membranes = binding["inputs"]["ion_ids"], binding["inputs"]["membrane_ids"]
    with localcontext() as context:
        context.prec = 100

        def d(v):
            return Decimal.from_float(float(v))

        for row in plan["pulses"]:
            factors = row["spatial_scalar"]
            if "spatial_modulator" in row:
                factors = spatial.evaluate(row["spatial_modulator"])["factor"]
            dynamic = d(row["dynamic_scale"])
            if "time_modulator" in row:
                dynamic *= d(modulators.evaluate(row["time_modulator"], time)["factor"])
            gain = 10 / d(row["change_s"])
            first = 1 / (1 + (-gain * (d(time) - d(row["on_s"]))).exp())
            last = 1 / (1 + (-gain * (d(time) - d(row["off_s"]))).exp())
            for name, scale in zip(row["membrane_ids"], factors, strict=True):
                modifier[ions.index(row["ion_id"]), membranes.index(name)] = float(
                    d(row["multiplier"])
                    * d(scale)
                    * dynamic
                    * (first - last)
                    * d(row["default_diffusion_m2_s"])
                )
    return current | dict(diffusion=current["diffusion"] | dict(scheduled_m2_s=modifier))
