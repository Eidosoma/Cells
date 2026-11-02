"""Steady field coupling for explicitly assigned current sites.

Compose conservative deposition, the existing homogeneous rectangular solve,
and its transpose voltage readout. Positive site current enters the environment;
the original source must satisfy the existing closed-boundary compatibility
test. No current is centred, no failed solve is retried, and neither stage's
refusal can be hidden by the other stage succeeding.

Assignments and medium are declared inputs, not native tissue/phase authority.
Power pairing is a raw diagnostic, not an ionic energy balance. This does not
advance concentrations, gates or a membrane voltage state.
"""

from typing import NamedTuple

import numpy as np

from cells.processes import rectangular_current_transfer as transfer
from cells.processes import rectangular_environment_conduction as conduction

LAW_ID = "cells.declared_site_current_steady_field_coupling@1"


class CoupledResult(NamedTuple):
    deposition: transfer.DepositResult
    field: conduction.SolveResult
    site_potential_V: object
    site_power_W: object
    deposited_power_W: object
    transfer_power_defect_W: object
    finite_readout: object

    @property
    def usable(self):
        return self.deposition.usable & self.field.usable & self.finite_readout


def _finish(deposition, solution, mapping, grid, xp):
    potential = solution.fields.potential_V
    sites = transfer.gather_potential(potential, mapping, grid, xp=xp)
    site_power = xp.sum(deposition.site_current_A * sites, axis=-1)
    deposited_power = xp.sum(deposition.cell_current_A * potential, axis=-1)
    defect = site_power - deposited_power
    finite = (
        xp.all(xp.isfinite(sites), axis=-1)
        & xp.isfinite(site_power)
        & xp.isfinite(deposited_power)
        & xp.isfinite(defect)
    )
    return CoupledResult(deposition, solution, sites, site_power, deposited_power, defect, finite)


def solve(
    site_current_A,
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
    xp=np,
    iteration_loop=None,
):
    """Return both complete stage results and one voltage per declared site.

    Transfer tolerances measure aggregate amperes; field tolerances measure
    continuity residual in A/m^3. Both must pass independently. Invalid array
    values remain in returned candidates/diagnostics; invalid metadata raises.
    Leading batch axes remain independent. A usable result is a steady declared
    field calculation, not an accepted native tissue or a time step.
    """
    deposited = transfer.deposit(
        site_current_A,
        mapping,
        grid,
        depth_m=depth_m,
        rtol=transfer_rtol,
        atol_A=transfer_atol_A,
        xp=xp,
    )
    solution = conduction.solve(
        deposited.source_A_m3,
        grid,
        conductivity_S_m=conductivity_S_m,
        depth_m=depth_m,
        max_iterations=max_iterations,
        rtol=field_rtol,
        atol_A_m3=field_atol_A_m3,
        initial_potential_V=initial_potential_V,
        xp=xp,
        iteration_loop=iteration_loop,
    )
    return _finish(deposited, solution, mapping, grid, xp)


def compile_jax_solver(
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
):
    """Compile the same composition with the existing binary64 JAX solver.

    Grid, assignments, medium and budgets are static; currents and optional warm
    potentials are arrays. Device placement remains caller-controlled. Factory
    construction alone is neither execution nor GPU evidence.
    """
    transfer._mapping(mapping, grid)
    field_solver = conduction.compile_jax_solver(
        grid,
        conductivity_S_m=conductivity_S_m,
        depth_m=depth_m,
        max_iterations=max_iterations,
        rtol=field_rtol,
        atol_A_m3=field_atol_A_m3,
    )
    import jax
    import jax.numpy as jnp

    def run(site_current_A, initial_potential_V=None):
        deposited = transfer.deposit(
            site_current_A,
            mapping,
            grid,
            depth_m=depth_m,
            rtol=transfer_rtol,
            atol_A=transfer_atol_A,
            xp=jnp,
        )
        solution = field_solver(deposited.source_A_m3, initial_potential_V)
        return _finish(deposited, solution, mapping, grid, jnp)

    return jax.jit(run)
