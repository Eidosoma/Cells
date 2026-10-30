"""Pure array held-active coefficient projection and complete per-world rates.

No spec parsing, host transfer, Python data predicates, checkpoint admission,
random draw or mutation occurs in these numeric functions. Bad raw proposals
remain available alongside clearly labelled safety-substituted arithmetic.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.physiology_active_temperature_arrays import Certificate, NumericCohort
from cells.core.schedule import SurfaceCalciumControl, SurfaceKineticControl
from cells.core.surface_calcium_energy_spec import Control as FuelControl
from cells.models import physiology_active_temperature_view as host
from cells.models import surface_calcium as calcium
from cells.models import surface_calcium_energy as fuel
from cells.models.kinetic_finite_extracellular import pump_parameters
from cells.numerics import surface_transport
from cells.numerics.extracellular_field import scatter
from cells.processes import kinetic_pump
from cells.processes.electrochemistry import R

IMPLEMENTATIONS = {
    "resolved_tissue@12": host.ordinary.ionic,
    "resolved_calcium@11": host.ordinary.calcium,
    "resolved_calcium_energy@5": host.ordinary.fuel,
    "resolved_open_calcium@1": host.original.open_calcium,
    "resolved_open_calcium_energy@1": host.original.open_fuel,
}
REASONS = (
    "temperature_finite",
    "temperature_domain",
    "temperature_certified",
    "controls_domain",
    "step_domain",
    "step_certified",
    "stage_domain",
    "field_converged",
    "finite_complete_rates",
    "stage_energy",
    "dissipation",
    "passive_turnover",
    "fuel_turnover",
)


class Proposal(NamedTuple):
    temperature_K: object
    control: object
    step_s: object


class Values(NamedTuple):
    raw_proposal: Proposal
    raw_runtime_layout: object
    arithmetic_runtime_layout: object
    arithmetic_control: object
    readouts: object
    derivative: object
    passive_fraction: object
    fuel_fraction: object
    reason_validity: object
    reason_mask: object
    arithmetic_substitution: object
    valid: object


class NumericInputs(NamedTuple):
    """Light input/projection stage; raw and arithmetic buffers stay distinct."""

    raw_runtime_layout: object
    arithmetic_runtime_layout: object
    arithmetic_control: object
    arithmetic_step_s: object
    reason_validity: object
    arithmetic_substitution: object


class CompactPhysics(NamedTuple):
    """Complete physical outputs without nested parent/readout duplicates."""

    field: object
    derivative: object
    valid: object
    gross_hydrolysis_fmol_s: object
    gross_synthesis_fmol_s: object


class PhysicalChecks(NamedTuple):
    passive_fraction: object
    fuel_fraction: object
    reason_validity: object


class WorldStages(NamedTuple):
    """Three separately compiled family-bound functions, or pure equivalents."""

    family: str
    inputs: object
    physics: object
    checks: object


class CalciumPhysicsStages(NamedTuple):
    """Separate ionic and calcium/ER calls on the same complete world state."""

    ionic: object
    completion: object

    def __call__(self, state, layout, control):
        return self.completion(state, layout, control, self.ionic(state, layout, control))


class StagedValues(NamedTuple):
    raw_proposal: Proposal
    raw_runtime_layout: object
    arithmetic_runtime_layout: object
    arithmetic_control: object
    readouts: CompactPhysics
    passive_fraction: object
    fuel_fraction: object
    reason_validity: object
    reason_mask: object
    arithmetic_substitution: object
    valid: object

    @property
    def derivative(self):
        """Expose the complete derivative without another output-tree copy."""
        return self.readouts.derivative


def project(layout, temperature_K, *, xp=jnp):
    values = dict(
        temperature=temperature_K,
        pump_drive=xp.where(
            layout.pump_present,
            kinetic_pump.chemical_drive(pump_parameters(layout), temperature_K, xp=xp),
            0.0,
        ),
    )
    if hasattr(layout, "er_temperature"):
        mu = layout.er_standard_mu_RT * (298.15 / temperature_K)
        values.update(
            er_temperature=xp.ones_like(layout.er_temperature) * temperature_K,
            er_standard_mu_RT=mu,
            er_delta_mu_RT=xp.einsum("ns,nsr->nr", mu, layout.er_products - layout.er_reactants),
        )
    if hasattr(layout, "energy_delta_g0_J_mol"):
        values.update(
            pmca_dg=xp.where(
                layout.pmca_present,
                layout.energy_delta_g0_J_mol[layout.membrane_cell]
                - R * temperature_K * xp.log(1000.0),
                0.0,
            ),
            er_pump_dg0=xp.where(
                layout.er_pump_present,
                layout.energy_delta_g0_J_mol[: layout.er_pump_present.size]
                - R * temperature_K * xp.log(1000.0),
                0.0,
            ),
        )
    return layout._replace(**values)


def _amounts(state, p, *, xp):
    inside = (
        calcium.cytosol_amount(state, p, xp=xp)
        if hasattr(p, "er_initial_amount")
        else p.amount_reference + state.amount_increment
    )
    return inside, p.extracellular_amount_reference + state.extracellular_amount_increment


def _passive_fraction(state, control, p, field, step_s, *, xp):
    inside, outside = _amounts(state, p, xp=xp)
    ci = xp.where(p.active, inside / p.volume, 1.0)
    co = xp.where(p.outside_active, outside / p.extracellular_volume, 1.0)
    n = p.active.size
    topology = surface_transport.Layout(
        *(getattr(p, name) for name in surface_transport.Layout._fields)
    )
    rates = surface_transport.transport(
        ci,
        co,
        field.potential_V[:n],
        field.potential_V[n:],
        control.membrane,
        control.junction * state.junction_gate,
        topology,
        xp=xp,
    )
    gross = xp.abs(rates.membrane_flux_fmol_s)
    cell = scatter(gross, inside, (p.membrane_cell,), xp=xp)
    exterior = scatter(gross, outside, (p.membrane_outside,), xp=xp)
    finite = p.outside_active & ~p.reservoir
    cell_fraction = xp.where(p.active, cell / xp.where(p.active, inside, 1.0), 0.0)
    outside_fraction = xp.where(finite, exterior / xp.where(finite, outside, 1.0), 0.0)
    return step_s * xp.maximum(
        xp.max(cell_fraction, initial=0.0), xp.max(outside_fraction, initial=0.0)
    ), rates.valid


def _world_protocol(layout, certificate, proposal, family, *, xp):
    if family not in IMPLEMENTATIONS or type(proposal) is not Proposal:
        raise ValueError("Require a reviewed static family and complete numeric proposal")
    control_type = (
        FuelControl
        if hasattr(layout, "energy_initial_amount_fmol")
        else SurfaceCalciumControl
        if hasattr(layout, "er_temperature")
        else SurfaceKineticControl
    )
    shapes = dict(
        membrane=layout.membrane_active.shape,
        junction=layout.junction_active.shape,
        channel=layout.channel_active.shape,
        pump=layout.pump_present.shape,
    )
    if hasattr(layout, "er_temperature"):
        shapes.update(
            er_reactions=layout.er_forward_rate.shape,
            er_passive=layout.er_permeability.shape,
            **{name: layout.er_temperature.shape for name in ("er_pump", "er_release")},
            **{
                name: layout.membrane_active.shape
                for name in ("plasma_pump", "plasma_exchange", "calcium_channel")
            },
        )
    if hasattr(layout, "regeneration_active"):
        shapes["regeneration"] = layout.regeneration_active.shape
    if type(proposal.control) is not control_type or any(
        value.shape != shapes[name] for name, value in proposal.control._asdict().items()
    ):
        raise ValueError(
            "Control shape/type must match every exact physical owner axis; no broadcast"
        )
    for value in (
        proposal.temperature_K,
        proposal.step_s,
        certificate.temperature_K,
        certificate.maximum_step_s,
    ):
        if value.shape != () or value.dtype != xp.float64:
            raise ValueError("Array rate scalars require explicit scalar float64 values")
    for value in proposal.control:
        if value.dtype != xp.float64:
            raise ValueError("Array rate controls require explicit float64 values")


def evaluate_world(state, layout, certificate, proposal, *, family, xp=jnp):
    """Numeric values require original host-prepared state/layout/certificates.

    Proposal shape/dtype is static protocol; numerical invalidity returns bits.
    Uncertified T never inherits a step/loss proof from another point. Invalid
    input arithmetic uses the certified T and zero controls, while retaining the
    exact raw proposal and raw projected coefficients as failure evidence.
    """
    _world_protocol(layout, certificate, proposal, family, xp=xp)
    t, h = proposal.temperature_K, proposal.step_s
    temperature_finite = xp.isfinite(t)
    temperature_domain = (t >= 200.0) & (t <= 400.0)
    temperature_certified = t == certificate.temperature_K
    controls_domain = xp.all(
        xp.stack(
            [xp.all(xp.isfinite(value) & (value >= 0) & (value <= 1)) for value in proposal.control]
        )
    )
    step_domain = xp.isfinite(h) & (h > 0)
    step_certified = h <= certificate.maximum_step_s
    temperature_ok = temperature_finite & temperature_domain & temperature_certified
    safe_t = xp.where(temperature_ok, t, certificate.temperature_K)
    safe_h = xp.where(step_domain & step_certified, h, certificate.maximum_step_s)
    control = type(proposal.control)(
        *(xp.where(controls_domain, value, 0.0) for value in proposal.control)
    )
    raw_runtime = project(layout, t, xp=xp)
    runtime = project(layout, safe_t, xp=xp)
    implementation = IMPLEMENTATIONS[family]
    stage_domain = implementation.domain_valid(state, runtime, runtime.active, xp=xp)
    readouts = implementation.readouts(state, control, runtime, xp=xp)
    derivative, field = readouts.derivative, readouts.field
    finite = xp.all(xp.stack([xp.all(xp.isfinite(value)) for value in derivative]))
    energy = xp.isfinite(field.energy_balance_pJ_s) & (xp.abs(field.energy_balance_pJ_s) <= 1e-10)
    dissipated = xp.all(
        xp.stack(
            [
                xp.all(value >= -1e-12)
                for name, value in derivative._asdict().items()
                if name.endswith("_dissipated_energy_pJ")
            ]
        )
    )
    passive, transport_valid = _passive_fraction(state, control, runtime, field, safe_h, xp=xp)
    fuel_fraction = xp.asarray(0.0)
    if hasattr(runtime, "energy_initial_amount_fmol"):
        amount = fuel.energy_amounts(state, runtime)
        parent = readouts.parent if hasattr(readouts, "parent") else readouts
        gross = parent.exchange.gross_hydrolysis_fmol_s + parent.exchange.gross_synthesis_fmol_s
        fraction = xp.where(
            runtime.active, gross / xp.where(runtime.active, xp.min(amount, axis=0), 1.0), 0.0
        )
        fuel_fraction = safe_h * xp.max(fraction, initial=0.0)
    flags = xp.stack(
        (
            temperature_finite,
            temperature_domain,
            temperature_certified,
            controls_domain,
            step_domain,
            step_certified,
            stage_domain & readouts.valid,
            field.converged,
            finite,
            energy,
            dissipated,
            transport_valid & xp.isfinite(passive) & (passive <= 0.05),
            xp.isfinite(fuel_fraction) & (fuel_fraction <= 0.05),
        )
    )
    reason_mask = xp.sum(
        xp.where(
            flags,
            xp.uint32(0),
            xp.left_shift(xp.uint32(1), xp.arange(len(REASONS), dtype=xp.uint32)),
        ),
        dtype=xp.uint32,
    )
    return Values(
        proposal,
        raw_runtime,
        runtime,
        control,
        readouts,
        derivative,
        passive,
        fuel_fraction,
        flags,
        reason_mask,
        ~temperature_ok | ~controls_domain | ~step_domain | ~step_certified,
        reason_mask == 0,
    )


def prepare_numeric_world(layout, certificate, proposal, *, family, xp=jnp):
    """Pure numeric projection, separate from original host preparation.

    This stage can be compiled independently from the physical solve. It retains
    every raw proposed coefficient even when arithmetic uses the certified point.
    """
    _world_protocol(layout, certificate, proposal, family, xp=xp)
    t, h = proposal.temperature_K, proposal.step_s
    flags = xp.stack(
        (
            xp.isfinite(t),
            (t >= 200.0) & (t <= 400.0),
            t == certificate.temperature_K,
            xp.all(
                xp.stack(
                    [
                        xp.all(xp.isfinite(value) & (value >= 0) & (value <= 1))
                        for value in proposal.control
                    ]
                )
            ),
            xp.isfinite(h) & (h > 0),
            h <= certificate.maximum_step_s,
        )
    )
    safe_t = xp.where(xp.all(flags[:3]), t, certificate.temperature_K)
    safe_h = xp.where(xp.all(flags[4:]), h, certificate.maximum_step_s)
    control = type(proposal.control)(
        *(xp.where(flags[3], value, 0.0) for value in proposal.control)
    )
    return NumericInputs(
        project(layout, t, xp=xp),
        project(layout, safe_t, xp=xp),
        control,
        safe_h,
        flags,
        ~xp.all(flags),
    )


def compact_physics_world(state, runtime_layout, control, *, family, xp=jnp):
    """Complete unbatched RHS/field stage with one copy of each physical tree.

    All original rate laws and validity calculations execute. Nested readout
    parents are not compiler outputs; actual per-owner gross fuel flows remain
    available to the separate unchanged turnover checks.
    """
    if (
        family not in IMPLEMENTATIONS
        or type(state) is not IMPLEMENTATIONS[family].STATE_TYPE
        or type(runtime_layout) is not IMPLEMENTATIONS[family].LAYOUT_TYPE
    ):
        raise ValueError("Compact physical stage requires the exact reviewed family state/layout")
    result = IMPLEMENTATIONS[family].readouts(state, control, runtime_layout, xp=xp)
    hydrolysis = synthesis = xp.zeros_like(runtime_layout.active, dtype=xp.float64)
    if hasattr(runtime_layout, "energy_initial_amount_fmol"):
        parent = result.parent if hasattr(result, "parent") else result
        hydrolysis = parent.exchange.gross_hydrolysis_fmol_s
        synthesis = parent.exchange.gross_synthesis_fmol_s
    return CompactPhysics(result.field, result.derivative, result.valid, hydrolysis, synthesis)


def check_physics_world(state, runtime_layout, control, step_s, physics, *, family, xp=jnp):
    """Seven physical admission predicates, outside the complete RHS executable."""
    if family not in IMPLEMENTATIONS or type(physics) is not CompactPhysics:
        raise ValueError("Physical checks require a reviewed family and compact physical tree")
    implementation = IMPLEMENTATIONS[family]
    if (
        type(state) is not implementation.STATE_TYPE
        or type(runtime_layout) is not implementation.LAYOUT_TYPE
        or type(physics.derivative) is not implementation.STATE_TYPE
        or any(
            value.shape != getattr(state, name).shape
            for name, value in physics.derivative._asdict().items()
        )
        or getattr(physics.valid, "shape", None) != ()
        or getattr(physics.valid, "dtype", None) != xp.bool_
        or any(
            getattr(value, "shape", None) != runtime_layout.active.shape
            or getattr(value, "dtype", None) != xp.float64
            for value in (physics.gross_hydrolysis_fmol_s, physics.gross_synthesis_fmol_s)
        )
    ):
        raise ValueError(
            "Physical checks require exact family/derivative/gross-owner axes and dtypes"
        )
    if step_s.shape != () or step_s.dtype != xp.float64:
        raise ValueError("Physical checks require an explicit scalar float64 arithmetic step")
    derivative, field = physics.derivative, physics.field
    stage_domain = IMPLEMENTATIONS[family].domain_valid(
        state, runtime_layout, runtime_layout.active, xp=xp
    )
    finite = xp.all(xp.stack([xp.all(xp.isfinite(value)) for value in derivative]))
    energy = xp.isfinite(field.energy_balance_pJ_s) & (xp.abs(field.energy_balance_pJ_s) <= 1e-10)
    dissipated = xp.all(
        xp.stack(
            [
                xp.all(value >= -1e-12)
                for name, value in derivative._asdict().items()
                if name.endswith("_dissipated_energy_pJ")
            ]
        )
    )
    passive, transport_valid = _passive_fraction(
        state, control, runtime_layout, field, step_s, xp=xp
    )
    fuel_fraction = xp.asarray(0.0)
    if hasattr(runtime_layout, "energy_initial_amount_fmol"):
        amount = fuel.energy_amounts(state, runtime_layout)
        gross = physics.gross_hydrolysis_fmol_s + physics.gross_synthesis_fmol_s
        fraction = xp.where(
            runtime_layout.active,
            gross / xp.where(runtime_layout.active, xp.min(amount, axis=0), 1.0),
            0.0,
        )
        fuel_fraction = step_s * xp.max(fraction, initial=0.0)
    flags = xp.stack(
        (
            stage_domain & physics.valid,
            field.converged,
            finite,
            energy,
            dissipated,
            transport_valid & xp.isfinite(passive) & (passive <= 0.05),
            xp.isfinite(fuel_fraction) & (fuel_fraction <= 0.05),
        )
    )
    return PhysicalChecks(passive, fuel_fraction, flags)


def assemble_staged_values(proposal, inputs, physics, checks, *, xp=jnp):
    """Attach raw evidence and all thirteen reasons without repeating physics."""
    if (
        type(proposal) is not Proposal
        or type(inputs) is not NumericInputs
        or type(physics) is not CompactPhysics
        or type(checks) is not PhysicalChecks
        or inputs.reason_validity.shape != (6,)
        or checks.reason_validity.shape != (7,)
        or inputs.reason_validity.dtype != xp.bool_
        or checks.reason_validity.dtype != xp.bool_
    ):
        raise ValueError("Staged assembly requires the complete typed per-world stage outputs")
    flags = xp.concatenate((inputs.reason_validity, checks.reason_validity))
    reason_mask = xp.sum(
        xp.where(
            flags,
            xp.uint32(0),
            xp.left_shift(xp.uint32(1), xp.arange(len(REASONS), dtype=xp.uint32)),
        ),
        dtype=xp.uint32,
    )
    return StagedValues(
        proposal,
        inputs.raw_runtime_layout,
        inputs.arithmetic_runtime_layout,
        inputs.arithmetic_control,
        physics,
        checks.passive_fraction,
        checks.fuel_fraction,
        flags,
        reason_mask,
        inputs.arithmetic_substitution,
        reason_mask == 0,
    )


def evaluate_world_staged(state, layout, certificate, proposal, *, family, xp=jnp):
    """Convenience composition for parity; compile its three stages separately.

    Jitting this composition would recreate a fused graph. A bounded compiled
    caller instead executes prepare_numeric_world, compact_physics_world and
    check_physics_world as separate executables for each original world, then
    assembles the result. No new compiled-memory or execution claim is implied.
    """
    inputs = prepare_numeric_world(layout, certificate, proposal, family=family, xp=xp)
    physics = compact_physics_world(
        state, inputs.arithmetic_runtime_layout, inputs.arithmetic_control, family=family, xp=xp
    )
    checks = check_physics_world(
        state,
        inputs.arithmetic_runtime_layout,
        inputs.arithmetic_control,
        inputs.arithmetic_step_s,
        physics,
        family=family,
        xp=xp,
    )
    return assemble_staged_values(proposal, inputs, physics, checks, xp=xp)


def _batch_world_count(numeric, proposal, family):
    """Static complete-cohort protocol, identical for NumPy and JAX tracing."""
    if (
        family not in IMPLEMENTATIONS
        or type(numeric) is not NumericCohort
        or type(proposal) is not Proposal
    ):
        raise ValueError("Array batch requires a complete typed cohort/proposal and exact family")
    implementation = IMPLEMENTATIONS[family]
    if (
        type(numeric.state) is not implementation.STATE_TYPE
        or type(numeric.layout) is not implementation.LAYOUT_TYPE
        or type(numeric.certificate) is not Certificate
    ):
        raise ValueError(
            "Array batch state/layout/certificate types differ from its homogeneous family"
        )
    shape = getattr(numeric.layout.active, "shape", ())
    if len(shape) != 2 or shape[0] <= 0:
        raise ValueError("Array batch requires a nonempty explicit leading world axis")
    count = shape[0]
    for value in (
        numeric.certificate.temperature_K,
        numeric.certificate.maximum_step_s,
        proposal.temperature_K,
        proposal.step_s,
    ):
        if getattr(value, "shape", None) != (count,):
            raise ValueError(
                "Array batch temperature/step axes must cover every prepared world exactly"
            )
    for value in jax.tree.leaves((numeric, proposal)):
        shape = getattr(value, "shape", None)
        if shape is None or not shape or shape[0] != count:
            raise ValueError(
                "Every cohort state/layout/certificate/proposal/control leaf needs one world axis"
            )
    return count


def evaluate_batch(numeric, proposal, *, family, xp=jnp):
    """Leading world axis; each world owns independent T, controls and field solve."""
    count = _batch_world_count(numeric, proposal, family)
    if xp is np:
        rows = [
            evaluate_world(
                jax.tree.map(lambda value, i=i: value[i], numeric.state),
                jax.tree.map(lambda value, i=i: value[i], numeric.layout),
                jax.tree.map(lambda value, i=i: value[i], numeric.certificate),
                jax.tree.map(lambda value, i=i: value[i], proposal),
                family=family,
                xp=np,
            )
            for i in range(count)
        ]
        return jax.tree.map(lambda *values: np.stack(values), *rows)
    return jax.vmap(lambda s, p, c, raw: evaluate_world(s, p, c, raw, family=family, xp=xp))(
        numeric.state, numeric.layout, numeric.certificate, proposal
    )


def evaluate_batch_staged(numeric, proposal, *, family, xp=jnp, stages=None):
    """Map complete separately executed worlds after the full cohort protocol.

    Supply WorldStages with three independently compiled family-bound functions
    to keep executable boundaries between projection, physics and checks. The
    default calls their pure equivalents. Do not jit this orchestration wrapper:
    that would fuse the stages and unroll the full cohort into one compiler graph.
    """
    count = _batch_world_count(numeric, proposal, family)
    if stages is None:
        stages = WorldStages(
            family,
            lambda p, c, raw: prepare_numeric_world(p, c, raw, family=family, xp=xp),
            lambda s, p, u: compact_physics_world(s, p, u, family=family, xp=xp),
            lambda s, p, u, h, v: check_physics_world(s, p, u, h, v, family=family, xp=xp),
        )
    if (
        type(stages) is not WorldStages
        or stages.family != family
        or not all(callable(value) for value in stages[1:])
    ):
        raise ValueError("Staged cohort execution requires all three exact family-bound stages")
    rows = []
    for i in range(count):
        world = jax.tree.map(lambda value, i=i: value[i], numeric)
        raw = jax.tree.map(lambda value, i=i: value[i], proposal)
        inputs = stages.inputs(world.layout, world.certificate, raw)
        physics = stages.physics(
            world.state, inputs.arithmetic_runtime_layout, inputs.arithmetic_control
        )
        checks = stages.checks(
            world.state,
            inputs.arithmetic_runtime_layout,
            inputs.arithmetic_control,
            inputs.arithmetic_step_s,
            physics,
        )
        rows.append(assemble_staged_values(raw, inputs, physics, checks, xp=xp))
    return jax.tree.map(lambda *values: xp.stack(values), *rows)


def compiled_world_stages(family):
    """Build three reusable JAX executables without fusing complete worlds.

    Compilation is lazy on each stage's first call. Reuse the returned stages
    across homogeneous cohorts; ``evaluate_batch_staged`` remains the Python
    orchestrator. Jitting that wrapper would remove these executable boundaries.
    This changes execution only: every original rate, field and admission check
    still runs. Memory use and backend qualification require separate evidence.
    """
    if family not in IMPLEMENTATIONS:
        raise ValueError("Compiled stages require an exact reviewed active family")
    return WorldStages(
        family,
        jax.jit(lambda p, c, raw: prepare_numeric_world(p, c, raw, family=family)),
        jax.jit(lambda s, p, u: compact_physics_world(s, p, u, family=family)),
        jax.jit(lambda s, p, u, h, v: check_physics_world(s, p, u, h, v, family=family)),
    )


def compact_calcium_completion(state, layout, control, ionic, *, xp=jnp):
    """Complete maintained-fuel calcium physics after its original ionic stage."""
    family = IMPLEMENTATIONS["resolved_calcium@11"]
    if (
        type(state) is not family.STATE_TYPE
        or type(layout) is not family.LAYOUT_TYPE
        or type(ionic) is not calcium.IonicStage
    ):
        raise ValueError("Calcium completion requires its exact family and complete ionic stage")
    result = calcium.complete_ionic_stage(state, control, layout, ionic, xp=xp)
    zeros = xp.zeros_like(layout.active, dtype=xp.float64)
    return CompactPhysics(result.field, result.derivative, result.valid, zeros, zeros)


def compiled_calcium_world_stages():
    """Build four separate executables for the maintained-fuel calcium family.

    Use only through the unjitted ``evaluate_batch_staged`` orchestrator, which
    keeps each original world state/control/layout fixed between these calls.
    This candidate preserves all laws; its memory bound needs qualification.
    Finite-fuel and open-bath calcium families require their own composition.
    """
    stages = compiled_world_stages("resolved_calcium@11")
    return stages._replace(
        physics=CalciumPhysicsStages(
            jax.jit(lambda s, p, u: calcium.ionic_stage(s, u, p)),
            jax.jit(lambda s, p, u, ionic: compact_calcium_completion(s, p, u, ionic)),
        )
    )
