"""CPU composition of the existing current readout and declared field law.

Only Jmem contributes to extracellular injection: membrane_current_A_m2 times
the same membrane's area. Positive current enters the environment. The native
I_mem readout instead contains junction current and smoothing, so it is not an
environmental source. Complete current diagnostics remain available separately.

The rectangular medium and every membrane-to-grid assignment are explicit.
This is a selected component composition, not native field correspondence,
live tissue/phase authority, ion evolution or an ionic energy balance.
"""

from typing import NamedTuple

import numpy as np

from cells.processes import betse_normal_current as current
from cells.processes import rectangular_current_coupling as coupling
from cells.processes import rectangular_current_transfer as transfer
from cells.processes import rectangular_environment_conduction as conduction

LAW_ID = "cells.declared_membrane_current_rectangle_coupling@1"


class MembraneCoupledResult(NamedTuple):
    current: current.CurrentReadout
    membrane_area_m2: object
    outward_current_A: object
    area_conversion_ok: object
    field: coupling.CoupledResult

    @property
    def usable(self):
        return self.area_conversion_ok & self.field.usable


class MembraneCouplingRejected(ValueError):
    """Retain the completed current readout when downstream metadata refuses."""

    def __init__(
        self,
        error,
        *,
        stage,
        readout,
        membrane_area_m2,
        outward_current_A,
        area_conversion_ok,
        field,
    ):
        super().__init__("Declared membrane field coupling refused: " + str(error))
        self.source_error = error
        self.stage = stage
        self.current = readout
        self.membrane_area_m2 = membrane_area_m2
        self.outward_current_A = outward_current_A
        self.area_conversion_ok = area_conversion_ok
        self.field = field


def solve(
    binding,
    source,
    mapping,
    grid,
    *,
    conductivity_S_m,
    depth_m,
    max_iterations,
    field_rtol,
    transfer_rtol,
    field_atol_A_m3=0.0,
    transfer_atol_A=0.0,
    initial_potential_V=None,
):
    """Evaluate once, convert the membrane component, then use the field API.

    All membrane IDs must match the declared map in order. The original current
    evaluator authenticates its complete binding and immutable input buffers;
    its own rejection and partial trial propagate unchanged. A failed area
    conversion remains unusable even if a lost-to-zero source solves. Returned
    candidates are never balanced, clipped or retried. This host composition
    uses the existing unbatched current readout; no compiled/GPU path is claimed.
    """
    if type(binding) is not current.CurrentBinding:
        raise ValueError("Require a complete typed normal-current binding")
    transfer._mapping(mapping, grid)
    if mapping.source_ids != binding.membrane_ids:
        raise ValueError("Current map must name every membrane in its exact source order")

    readout = current.evaluate(binding, source)
    area = outward = representable = solved = None
    stage = "conversion"
    try:
        density = readout.values.membrane_current_A_m2
        area = binding.kernel.membrane_area_m2
        with np.errstate(all="ignore"):
            outward = density * area
            representable = (
                np.all(conduction._portable(density, np))
                & np.all(conduction._portable(area, np))
                & np.all(conduction._portable(outward, np))
                & np.all(
                    (conduction._bits(density, np) == 0) | (conduction._bits(outward, np) != 0)
                )
            )
            stage = "field"
            solved = coupling.solve(
                outward,
                mapping,
                grid,
                conductivity_S_m=conductivity_S_m,
                depth_m=depth_m,
                max_iterations=max_iterations,
                field_rtol=field_rtol,
                transfer_rtol=transfer_rtol,
                field_atol_A_m3=field_atol_A_m3,
                transfer_atol_A=transfer_atol_A,
                initial_potential_V=initial_potential_V,
            )
        stage = "result"
        return MembraneCoupledResult(readout, area, outward, representable, solved)
    except Exception as error:
        raise MembraneCouplingRejected(
            error,
            stage=stage,
            readout=readout,
            membrane_area_m2=area,
            outward_current_A=outward,
            area_conversion_ok=representable,
            field=solved,
        ) from error
