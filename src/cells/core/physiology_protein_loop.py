"""Atomic repeated charged loops with an unchanged origin and explicit work.

The numeric state is never republished as an ordinary/held checkpoint. Each
loop prepares permeability, evolves ions on the original grid, then calls the
protein component once. Declared drive is an energetic consistency model, not
a measured driving law. Compact accumulated ledgers retain exact float-input
sums; returned proposals/receipts belong in the caller's durable run journal.
"""

import math
from dataclasses import dataclass, fields, replace
from decimal import Context, Decimal, localcontext
from numbers import Real
from types import SimpleNamespace

import numpy as np

from cells.core import physiology_permeability_schedule as schedules
from cells.core import physiology_perturbation_phases as phases
from cells.core import physiology_perturbation_step as component_step
from cells.core import physiology_protein_charge_interval as held
from cells.core import physiology_protein_charge_step as step
from cells.core import physiology_protein_interval_accounting as accounting
from cells.core import physiology_protein_thermodynamics as thermo
from cells.core import physiology_protein_transition as transition
from cells.core import physiology_tissue_loop as seals
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.schedule import event_index
from cells.models import compartment_reactions as chemistry
from cells.models import physiology_permeability_view as view
from cells.models import physiology_protein_charge_rhs as charged
from cells.numerics import surface_field as field
from cells.processes import betse_perturbations as perturb
from cells.processes.electrochemistry import R

KIND = "cells.charged_protein_loop@1"


@dataclass(frozen=True, slots=True)
class ProteinLoopLedger:
    external_work_pJ: str
    dissipated_free_energy_pJ: str
    clamp_work_pJ: str
    electrode_charge_C: tuple


@dataclass(frozen=True, slots=True)
class ProteinLoopCheckpoint:
    origin: held.HeldProteinCheckpoint
    initial_component: object
    origin_loop_index: int
    standard_concentration_mol_m3: float
    state: object
    component: object
    time: float
    step_index: int
    event_index: int
    loop_index: int
    ledger: ProteinLoopLedger
    history_identity: str
    identity: str
    schedule: object = None

    @property
    def layout(self):
        return self.origin.layout


@dataclass(frozen=True, slots=True)
class IonicInterval:
    start_s: float
    end_s: float
    step_index: int
    trial: object
    accounting: object


@dataclass(frozen=True, slots=True)
class ProteinLoopProposal:
    source_identity: str
    preparation: object
    intervals: tuple
    component_transition: object
    before_rates: object
    after_rates: object
    thermodynamics: object
    electrical: object
    conditional_work: object
    identity: str
    permeability_staging: object = None


@dataclass(frozen=True, slots=True)
class ProteinLoopReceipt:
    checkpoint: ProteinLoopCheckpoint
    proposal: ProteinLoopProposal
    budget: transition.DrivingBudget
    local_energy_residual_pJ: float
    cumulative_accounting: object
    identity: str


class ProteinLoopRejected(NumericalError):
    """Uncommitted attempt, including completed ions and any proposed RNG tape."""

    def __init__(
        self,
        reason,
        *,
        source,
        stage,
        proposal=None,
        intervals=(),
        preparation=None,
        component_transition=None,
        trial=None,
        budget=None,
        report=None,
        failure=None,
    ):
        super().__init__("Charged protein loop refused at " + stage + ": " + str(reason))
        self.source, self.stage, self.proposal = source, stage, proposal
        self.intervals, self.preparation = tuple(intervals), preparation
        self.component_transition, self.trial = component_transition, trial
        self.budget, self.report, self.failure = budget, report, failure
        self.packet = (
            component_transition.packet
            if component_transition is not None
            else getattr(failure, "packet", None)
        )
        self.stream = (
            component_transition.state.stream
            if component_transition is not None
            else getattr(failure, "stream", None)
        )


def _hash_record(value, kind):
    payload = dict(
        kind=kind,
        **{
            f.name: transition._record(getattr(value, f.name))
            for f in fields(value)
            if f.name != "identity"
        },
    )
    return payload | dict(identity=seals._digest(payload))


def checkpoint_record(point):
    if type(point) is not ProteinLoopCheckpoint:
        raise ValueError("Require a separate complete charged-loop checkpoint")
    # Keep full origin/component identities, not recursively growing receipts.
    payload = dict(
        kind=KIND,
        origin_identity=point.origin.identity,
        initial_component_identity=seals._component_identity(point.initial_component),
        state_identity=seals._arrays_identity(point.state),
        component_identity=seals._component_identity(point.component),
        **{
            name: transition._record(getattr(point, name))
            for name in (
                "origin_loop_index",
                "standard_concentration_mol_m3",
                "time",
                "step_index",
                "event_index",
                "loop_index",
                "ledger",
                "history_identity",
            )
        },
    )
    if point.schedule is not None:
        payload["schedule_identity"] = point.schedule.identity
    return payload | dict(identity=seals._digest(payload))


def _seal(point):
    return replace(point, identity=checkpoint_record(point)["identity"])


def proposal_record(proposal):
    if type(proposal) is not ProteinLoopProposal:
        raise ValueError("Require a complete charged-loop proposal")
    return _hash_record(proposal, KIND + "/proposal")


def _decimal(value):
    if type(value) is not str:
        raise ValueError("Accumulated ledgers require exact decimal strings")
    answer = Decimal(value)
    if not answer.is_finite() or str(answer) != value:
        raise ValueError("Noncanonical/nonfinite accumulated ledger")
    accounting._number(answer)
    return answer


def _budget(budget):
    if (
        type(budget) is not transition.DrivingBudget
        or type(budget.provenance) is not str
        or not budget.provenance.strip()
    ):
        raise ValueError("Declare external work, dissipation and their provenance")
    for value in (budget.external_work_pJ, budget.dissipated_free_energy_pJ):
        if (
            isinstance(value, (bool, np.bool_))
            or not isinstance(value, Real)
            or not math.isfinite(value)
        ):
            raise ValueError("Declare finite real work and dissipation")
    if budget.dissipated_free_energy_pJ < 0:
        raise ValueError("Declared free-energy dissipation must be nonnegative")


def _context(spec, point):
    if (
        type(point) is not ProteinLoopCheckpoint
        or point.identity != checkpoint_record(point)["identity"]
    ):
        raise ValueError("Changed or incomplete charged-loop checkpoint")
    origin = point.origin
    held.validate(spec, origin)
    if origin.time != origin.seed.time or origin.step_index != origin.seed.step_index:
        raise ValueError("Loop origin must be its conditioned initial state")
    if point.schedule is not None:
        schedules.validate(
            point.schedule, spec, origin.binding, point.initial_component, point.origin_loop_index
        )
    initial_staged = schedules.stage(
        point.schedule,
        point.initial_component,
        point.initial_component,
        origin.binding,
        point.origin_loop_index,
    )
    prep = phases.prepare(initial_staged, origin.binding.component)
    if seals._component_identity(prep.held_state) != seals._component_identity(origin.component):
        raise ValueError("Original charged conditioning differs from its initial component")
    seals._index(point.origin_loop_index)
    seals._index(point.loop_index)
    count = point.loop_index - point.origin_loop_index
    if count < 0:
        raise ValueError("Cannot move behind the declared loop origin")
    dt = float(point.initial_component.controls.dt_s)
    grid = EventGrid(spec)
    if (
        type(point.time) is not float
        or not math.isfinite(point.time)
        or point.time != point.loop_index * dt
        or origin.time != point.origin_loop_index * dt
        or type(point.step_index) is not int
        or point.step_index != grid.exact_index(point.time)
        or type(point.event_index) is not int
        or point.event_index != event_index(spec, point.time)
    ):
        raise ValueError("Require exact original-grid nominal boundaries")
    standard = point.standard_concentration_mol_m3
    if type(standard) is not float or not math.isfinite(standard) or standard <= 0:
        raise ValueError("Require a fixed positive protein standard concentration")
    component_step.validate_state(point.component, origin.binding.component)
    initial, current = point.initial_component, point.component
    if (
        current.controls != initial.controls
        or current.loop_calls != initial.loop_calls + count
        or current.stream.next_tick
        != initial.stream.next_tick + count * int(perturb.dynamic_active(initial.controls))
        or type(current.stream.rng) is not type(initial.stream.rng)
    ):
        raise ValueError("Component controls/call count/random ownership differ from loop history")
    for name in ("stream_id", "world_id", "layout_identity"):
        if getattr(current.stream, name) != getattr(initial.stream, name):
            raise ValueError("Changed random-stream ownership")
    if (
        type(initial.stream.rng) is perturb.StableCoordinates
        and initial.stream.rng != current.stream.rng
    ):
        raise ValueError("Changed stable random coordinates")
    if count == 0:
        expected_diffusion = initial.diffusion
    else:
        previous = schedules.stage(
            point.schedule, initial, initial, origin.binding, point.loop_index - 1
        )
        expected_diffusion = phases.prepare(previous, origin.binding.component).held_state.diffusion
    if any(
        not np.array_equal(a, b) for a, b in zip(current.diffusion, expected_diffusion, strict=True)
    ):
        raise ValueError("Component buffers differ from the last accepted scheduled loop")
    if (
        type(point.ledger) is not ProteinLoopLedger
        or type(point.ledger.electrode_charge_C) is not tuple
    ):
        raise ValueError("Incomplete accumulated protein ledger")
    ledgers = tuple(
        _decimal(getattr(point.ledger, n))
        for n in ("external_work_pJ", "dissipated_free_energy_pJ", "clamp_work_pJ")
    )
    if ledgers[1] < 0 or len(point.ledger.electrode_charge_C) != point.layout.outside_active.size:
        raise ValueError("Invalid accumulated dissipation or electrode axis")
    for value in point.ledger.electrode_charge_C:
        _decimal(value)
    if (
        type(point.history_identity) is not str
        or len(point.history_identity) != 64
        or any(c not in "0123456789abcdef" for c in point.history_identity)
    ):
        raise ValueError("Invalid receipt-chain association")
    if count == 0:
        if (
            seals._component_identity(initial) != seals._component_identity(current)
            or seals._arrays_identity(origin.state) != seals._arrays_identity(point.state)
            or any(ledgers)
            or any(_decimal(x) for x in point.ledger.electrode_charge_C)
            or point.history_identity != origin.identity
        ):
            raise ValueError("Initial loop state differs from its declared zero-work origin")
    else:
        with localcontext(Context(prec=4096)):
            count_eps = Decimal(count) * accounting._d(np.finfo(float).eps)
            if count_eps >= 1:
                raise ValueError("Component elapsed clock has no resolvable accumulated bound")
            exact = accounting._d(initial.time_s) + Decimal(count) * accounting._d(dt)
            bound = (
                count_eps
                / (1 - count_eps)
                * (abs(accounting._d(initial.time_s)) + Decimal(count) * abs(accounting._d(dt)))
            )
            if (
                not current.time_s > initial.time_s
                or abs(accounting._d(current.time_s) - exact) > bound
            ):
                raise ValueError("Component elapsed clock differs from its accumulated duration")
    return grid, accounting._prepare(
        spec,
        point.state,
        point.state,
        point.layout,
        origin.binding,
        origin.charge_reference,
        current,
        origin.protein_species_id,
        origin.valence,
    )


def _actual(spec, point, state, component, time):
    origin = point.origin
    implementation, _, _, runtime, delta = accounting._prepare(
        spec,
        state,
        state,
        point.layout,
        origin.binding,
        origin.charge_reference,
        component,
        origin.protein_species_id,
        origin.valence,
    )
    control = held._control(spec, time)
    local = accounting.evaluate(
        spec,
        state,
        state,
        point.layout,
        origin.binding,
        origin.charge_reference,
        component,
        protein_species_id=origin.protein_species_id,
        valence=origin.valence,
        before_control=control,
        after_control=control,
    )
    rates = charged.array_readouts(
        state, control, runtime, delta, implementation=implementation, xp=np
    )
    if (
        not bool(rates.valid)
        or not np.isfinite(rates.field.energy_balance_pJ_s)
        or abs(float(rates.field.energy_balance_pJ_s)) > held.ENERGY_RATE_ATOL_PJ_S
    ):
        raise ValueError("Invalid actual charged endpoint rates/energy")
    return runtime, rates, local


def validate(spec, point):
    """Recompute endpoint/global conservation; do not replay historical RK stages.

    Ledger/lineage seals establish association, not authorship or a physical
    drive law. Preserve per-loop receipts separately for historical replay.
    """
    _context(spec, point)
    origin, b, e = point.origin, point.origin.state, point.state
    p0, first, _ = _actual(spec, point, b, origin.component, origin.time)
    p, last, local = _actual(spec, point, e, point.component, point.time)
    protein = thermo.change(
        origin.component.protein,
        point.component.protein,
        origin.binding,
        temperature_K=spec.model.temperature_K,
        standard_concentration_mol_m3=point.standard_concentration_mol_m3,
        gas_constant_J_mol_K=R,
    )
    if not protein.strict_conservation_valid:
        raise ValueError("Cumulative protein material changed")
    with localcontext(Context(prec=4096)):
        chemical, er = accounting._chemical(b, e, p)
        plasma = sum(
            (
                Decimal("5e11")
                * accounting._d(c)
                * (accounting._d(y) - accounting._d(x))
                * (accounting._d(y) + accounting._d(x))
                for c, x, y in zip(
                    p.membrane_capacitance,
                    first.field.rates.membrane_voltage_V,
                    last.field.rates.membrane_voltage_V,
                    strict=True,
                )
            ),
            Decimal(0),
        )

        def diff(name):
            return accounting._difference_sum(getattr(b, name), getattr(e, name))

        heat = sum((diff(n) for n in b._fields if n.endswith("_dissipated_energy_pJ")), Decimal(0))
        pool = (
            accounting._sum(accounting._pool_change(b, e, p))
            if hasattr(b, "energy_amount_increment_fmol")
            else Decimal(0)
        )
        metabolic = (
            Decimal(0)
            if hasattr(b, "energy_amount_increment_fmol")
            else sum(
                (
                    diff(n)
                    for n in (
                        "metabolic_work_pJ",
                        "plasma_metabolic_work_pJ",
                        "er_metabolic_work_pJ",
                    )
                    if hasattr(b, n)
                ),
                Decimal(0),
            )
        )
        regeneration = (
            diff("regeneration_supplied_work_pJ")
            if hasattr(b, "energy_amount_increment_fmol")
            else Decimal(0)
        )
        terms = dict(
            chemical_change_pJ=chemical,
            er_capacitor_change_pJ=er,
            plasma_capacitor_change_pJ=plasma,
            fuel_chemical_change_pJ=pool,
            protein_chemical_change_pJ=accounting._d(protein.total_free_energy_change_pJ),
            dissipated_energy_pJ=heat,
            protein_dissipated_free_energy_pJ=_decimal(point.ledger.dissipated_free_energy_pJ),
            reservoir_work_pJ=diff("reservoir_work_pJ"),
            electrode_work_pJ=diff("electrode_work_pJ"),
            external_metabolic_work_pJ=metabolic,
            regeneration_supplied_work_pJ=regeneration,
            protein_external_work_pJ=_decimal(point.ledger.external_work_pJ),
            protein_clamp_work_pJ=_decimal(point.ledger.clamp_work_pJ),
        )
        residual = sum((v * (-1 if "work" in k else 1) for k, v in terms.items()), Decimal(0))
        qprotein = np.asarray(
            [accounting._number(_decimal(v)) for v in point.ledger.electrode_charge_C]
        )
        expected_work = sum(
            (
                Decimal("1e12") * accounting._d(v) * _decimal(q)
                for v, q in zip(p.boundary_V, point.ledger.electrode_charge_C, strict=True)
            ),
            Decimal(0),
        )
        work_error = accounting._number(expected_work - terms["protein_clamp_work_pJ"])
    qionic = e.electrode_charge_transferred_C - b.electrode_charge_transferred_C
    qactual = last.field.electrode_charge_C - first.field.electrode_charge_C
    qerror = np.where(p.reservoir, qactual - qionic - qprotein, 0.0)
    qlimit = 2 * field.CHARGE_ATOL_C + field.CHARGE_RTOL * (
        abs(first.actual_charge_C[p.active.size :]) + abs(last.actual_charge_C[p.active.size :])
    )
    limit = float(accounting._limits(spec, e, p)["energy"])
    checks = dict(
        endpoint=local.valid,
        energy=abs(residual) <= Decimal.from_float(limit),
        protein_electrode_owners=bool(np.all(np.where(p.reservoir, True, qprotein == 0))),
        electrode_charge=bool(np.all(abs(qerror) <= qlimit)),
        clamp_work=abs(work_error) <= 3e-12,
    )
    for name in b._fields:
        if name.endswith("_dissipated_energy_pJ"):
            checks["nondecreasing/" + name] = bool(
                np.all(
                    getattr(e, name) - getattr(b, name)
                    >= -(
                        chemistry.ROUND_ATOL
                        if type(spec.model) in view.IMPLEMENTATIONS
                        and view.IMPLEMENTATIONS[type(spec.model)] is view.calcium
                        else 1e-12
                    )
                )
            )
    report = accounting._freeze_tree(
        dict(
            valid=all(checks.values()),
            checks=checks,
            energy_terms={k: accounting._number(v) for k, v in terms.items()},
            exact_energy_terms={k: str(v) for k, v in terms.items()},
            energy_residual_pJ=accounting._number(residual),
            energy_limit_pJ=limit,
            electrode_charge_residual_C=qerror,
            electrode_charge_limit_C=qlimit,
            protein_clamp_work_residual_pJ=work_error,
            original_anchors_preserved=True,
        )
    )
    if not report["valid"]:
        raise ProteinLoopRejected(
            "Cumulative conservation: " + str([k for k, v in checks.items() if not v]),
            source=point,
            stage="cumulative_accounting",
            report=report,
        )
    return report


def initialise(
    spec,
    seed,
    binding,
    charge_reference,
    component,
    *,
    protein_species_id,
    valence,
    standard_concentration_mol_m3,
    loop_index=0,
    schedule=None,
):
    """Declare the starting conditioned field; no prior preparation work claimed."""
    seals._index(loop_index)
    if isinstance(standard_concentration_mol_m3, (bool, np.bool_)) or not isinstance(
        standard_concentration_mol_m3, Real
    ):
        raise ValueError("Require a positive protein standard concentration")
    if schedule is not None:
        schedules.validate(schedule, spec, binding, component, loop_index)
    staged = schedules.stage(schedule, component, component, binding, loop_index)
    preparation = phases.prepare(staged, binding.component)
    origin = held.initialise(
        spec,
        seed,
        binding,
        charge_reference,
        preparation.held_state,
        protein_species_id=protein_species_id,
        valence=valence,
    )
    ledger = ProteinLoopLedger("0", "0", "0", ("0",) * origin.layout.outside_active.size)
    point = _seal(
        ProteinLoopCheckpoint(
            origin,
            component,
            loop_index,
            float(standard_concentration_mol_m3),
            origin.state,
            component,
            origin.time,
            origin.step_index,
            origin.event_index,
            loop_index,
            ledger,
            origin.identity,
            "",
            schedule,
        )
    )
    validate(spec, point)
    return point


def _prepare_loop(spec, point):
    staged = schedules.stage(
        point.schedule,
        point.initial_component,
        point.component,
        point.origin.binding,
        point.loop_index,
    )
    preparation = phases.prepare(staged, point.origin.binding.component)
    if point.schedule is None:
        return staged, preparation, None
    # Conductance interventions alter rates. They must not silently change
    # stored ionic/protein/capacitor energy or require an electrode impulse.
    _, before, _ = _actual(spec, point, point.state, point.component, point.time)
    runtime, after, _ = _actual(spec, point, point.state, preparation.held_state, point.time)
    vb, va = before.field.rates.membrane_voltage_V, after.field.rates.membrane_voltage_V
    delta_energy = math.fsum(
        float(x) for x in 5e11 * runtime.membrane_capacitance * (va - vb) * (va + vb)
    )
    delta_electrode = after.field.electrode_charge_C - before.field.electrode_charge_C
    limit = 2 * field.CHARGE_ATOL_C + field.CHARGE_RTOL * (
        abs(before.actual_charge_C[runtime.active.size :])
        + abs(after.actual_charge_C[runtime.active.size :])
    )
    checks = dict(
        stored_energy=abs(delta_energy) <= accounting._limits(spec, point.state, runtime)["energy"],
        electrode_charge=bool(np.all(abs(delta_electrode) <= limit)),
    )
    timing = dict(sampled_time_s=point.time)
    if point.schedule.native_calendar is not None:
        timing.update(
            sampled_time_s=schedules.sample_time_s(point.schedule, point.loop_index),
            event_clock="betse_phase_event_label",
            native_calendar_identity=point.schedule.native_calendar.identity,
            nominal_start_s=point.time,
            nominal_duration_s=point.schedule.physiological_dt_s,
            events_applied=point.component.controls.phase == "SIM",
        )
    report = accounting._freeze_tree(
        dict(
            schedule_identity=point.schedule.identity,
            sampled_loop_index=point.loop_index,
            **timing,
            current_permeability_m_s=runtime.membrane_permeability,
            capacitor_energy_change_pJ=delta_energy,
            electrode_charge_change_C=delta_electrode,
            electrode_charge_limit_C=limit,
            checks=checks,
            parameter_actuation_cost_modelled=False,
        )
    )
    if not all(checks.values()):
        raise ProteinLoopRejected(
            "Scheduled conductance changed stored electrical state",
            source=point,
            stage="permeability_staging",
            preparation=preparation,
            report=report,
        )
    return staged, preparation, report


def _ions(spec, point, preparation, completed):
    grid = EventGrid(spec)
    if point.loop_index == seals.MAX_LOOP_INDEX:
        raise ValueError("Loop counter cannot advance")
    end = (point.loop_index + 1) * float(point.component.controls.dt_s)
    if not math.isfinite(end) or end <= point.time or end > grid.end:
        raise ValueError("Require one complete nominal interval within the source horizon")
    stop = grid.exact_index(end)
    origin = point.origin
    implementation, _, _, runtime, delta = accounting._prepare(
        spec,
        point.state,
        point.state,
        point.layout,
        origin.binding,
        origin.charge_reference,
        preparation.held_state,
        origin.protein_species_id,
        origin.valence,
    )
    state = point.state
    changed = view._admission_spec(spec, runtime.membrane_permeability)
    for index in range(point.step_index, stop):
        start, right = float(grid[index]), float(grid[index + 1])
        h = right - start
        control = held._control(spec, start)
        table = type(control)(*(value[None] for value in control))
        implementation.check_steps(changed, np.asarray([h]), table)
        trial = step.array_rk4_step(
            state, control, runtime, delta, h, implementation=implementation, xp=np
        )
        if not bool(trial.valid) or any(
            not np.isfinite(s.energy_rate_residual_pJ_s)
            or abs(float(s.energy_rate_residual_pJ_s)) > held.ENERGY_RATE_ATOL_PJ_S
            for s in trial.status
        ):
            raise ProteinLoopRejected(
                "Charged RK4 domain/rate/turnover/energy gate",
                source=point,
                stage="ionic_trial",
                preparation=preparation,
                intervals=completed,
                trial=view._immutable_tree(trial),
            )
        try:
            report = accounting.evaluate(
                spec,
                state,
                trial.proposed_state,
                point.layout,
                origin.binding,
                origin.charge_reference,
                preparation.held_state,
                protein_species_id=origin.protein_species_id,
                valence=origin.valence,
                before_control=control,
                after_control=control,
            )
            _actual(spec, point, trial.proposed_state, preparation.held_state, right)
        except Exception as error:
            raise ProteinLoopRejected(
                error,
                source=point,
                stage="ionic_accounting",
                preparation=preparation,
                intervals=completed,
                trial=view._immutable_tree(trial),
                report=getattr(error, "report", None),
                failure=error,
            ) from error
        trial = view._immutable_tree(trial)
        completed.append(IonicInterval(start, right, index + 1, trial, report))
        state = trial.proposed_state
    return state, end, stop, implementation, runtime, delta


def _endpoint_context(point, preparation, state, end):
    origin = point.origin
    return SimpleNamespace(
        component=preparation.held_state,
        binding=origin.binding,
        charge_reference=origin.charge_reference,
        valence=origin.valence,
        protein_species_id=origin.protein_species_id,
        layout=point.layout,
        state=state,
        time=end,
    )


def propose(spec, point):
    """Propose a full loop, drawing protein only after every ionic step succeeds."""
    stage, completed, preparation, component = "source_admission", [], None, None
    evidence = {}
    try:
        validate(spec, point)
        stage = "preparation"
        staged, preparation, staging = _prepare_loop(spec, point)
        stage = "ionic_intervals"
        state, end, _, implementation, runtime, delta = _ions(spec, point, preparation, completed)
        stage = "post_ion_component"
        component = phases.finish(staged, point.origin.binding.component, preparation)
        stage = "protein_endpoint_work"
        endpoints = transition._endpoints(
            spec,
            _endpoint_context(point, preparation, state, end),
            component.state,
            runtime,
            delta,
            implementation,
            point.standard_concentration_mol_m3,
            evidence,
        )
        proposal = ProteinLoopProposal(
            point.identity, preparation, tuple(completed), component, *endpoints, "", staging
        )
        return replace(proposal, identity=proposal_record(proposal)["identity"])
    except ProteinLoopRejected:
        raise
    except Exception as error:
        raise ProteinLoopRejected(
            error,
            source=point,
            stage=stage,
            preparation=preparation,
            intervals=completed,
            component_transition=component,
            report=accounting._freeze_tree(evidence),
            failure=error,
        ) from error


def accept(spec, point, proposal, budget):
    """Commit against this exact current source; deterministic checks never draw.

    Pure replay from an old immutable source is allowed. The caller replaces its
    current checkpoint only on success and journals returned receipts. Restart
    validates cumulative balances, not the authenticity of historical budgets.
    """
    stage = "proposal_association"
    try:
        validate(spec, point)
        if (
            type(proposal) is not ProteinLoopProposal
            or proposal.source_identity != point.identity
            or proposal.identity != proposal_record(proposal)["identity"]
        ):
            raise ValueError("Proposal belongs to another current source or its contents changed")
        staged, _, staging = _prepare_loop(spec, point)
        phases._validate_preparation(staged, point.origin.binding.component, proposal.preparation)
        if transition._record(staging) != transition._record(proposal.permeability_staging):
            raise ValueError("Scheduled preparation differs from actual source/field association")
        stage = "ionic_replay"
        completed = []
        state, end, stop, implementation, runtime, delta = _ions(
            spec, point, proposal.preparation, completed
        )
        if transition._record(tuple(completed)) != transition._record(proposal.intervals):
            raise ValueError("Ionic proposal differs from deterministic original-grid replay")
        stage = "protein_replay"
        transition._component_law(
            proposal.preparation, proposal.component_transition, point.origin.binding.component
        )
        actual = (
            proposal.before_rates,
            proposal.after_rates,
            proposal.thermodynamics,
            proposal.electrical,
            proposal.conditional_work,
        )
        expected = transition._endpoints(
            spec,
            _endpoint_context(point, proposal.preparation, state, end),
            proposal.component_transition.state,
            runtime,
            delta,
            implementation,
            point.standard_concentration_mol_m3,
        )
        if transition._record(actual) != transition._record(expected):
            raise ValueError("Changed proposed protein/field/work association")
        stage = "declared_work"
        _budget(budget)
        residual = math.fsum(
            (
                proposal.thermodynamics.total_free_energy_change_pJ,
                proposal.electrical.capacitor_energy_change_pJ,
                budget.dissipated_free_energy_pJ,
                -proposal.electrical.clamp_work_pJ,
                -budget.external_work_pJ,
            )
        )
        if (
            not math.isfinite(residual)
            or abs(residual) > accounting._limits(spec, state, runtime)["energy"]
        ):
            raise ValueError("Protein budget fails the original family energy limit")
        with localcontext(Context(prec=4096)):
            ledger = ProteinLoopLedger(
                str(
                    _decimal(point.ledger.external_work_pJ) + accounting._d(budget.external_work_pJ)
                ),
                str(
                    _decimal(point.ledger.dissipated_free_energy_pJ)
                    + accounting._d(budget.dissipated_free_energy_pJ)
                ),
                str(
                    _decimal(point.ledger.clamp_work_pJ)
                    + accounting._d(proposal.electrical.clamp_work_pJ)
                ),
                tuple(
                    str(_decimal(old) + accounting._d(new))
                    for old, new in zip(
                        point.ledger.electrode_charge_C,
                        proposal.electrical.electrode_charge_change_C,
                        strict=True,
                    )
                ),
            )
        history = seals._digest(
            dict(
                parent=point.history_identity,
                source_identity=point.identity,
                proposal_identity=proposal.identity,
                budget=transition._record(budget),
            )
        )
        checkpoint = _seal(
            replace(
                point,
                state=state,
                component=proposal.component_transition.state,
                time=end,
                step_index=stop,
                event_index=event_index(spec, end),
                loop_index=point.loop_index + 1,
                ledger=ledger,
                history_identity=history,
            )
        )
        stage = "cumulative_accounting"
        report = validate(spec, checkpoint)
        identity = seals._digest(
            dict(
                kind=KIND + "/receipt",
                checkpoint=checkpoint.identity,
                proposal=proposal.identity,
                budget=transition._record(budget),
                local_energy_residual_pJ=residual,
            )
        )
        return ProteinLoopReceipt(checkpoint, proposal, budget, residual, report, identity)
    except Exception as error:
        raise ProteinLoopRejected(
            error,
            source=point,
            stage=stage,
            proposal=proposal,
            intervals=getattr(proposal, "intervals", ()),
            preparation=getattr(proposal, "preparation", None),
            component_transition=getattr(proposal, "component_transition", None),
            budget=budget,
            report=getattr(error, "report", None),
            failure=error,
        ) from error
