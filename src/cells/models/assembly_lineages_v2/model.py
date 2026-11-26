"""Version 2's entry in the model registry (models/registry.get_model), and its host-side tables.

The family's runner shape is its own (an event-driven world, not the fixed-step runner's), so it
offers none of that runner's interface. What it offers, resolved when the model is built (no
value enters a program):

- structure(spec): the value-free structure that selects the compiled program (the compile key);
- layout(spec): the world's values as host arrays, one lane's (kernel.Layout);
- founder(spec): the founder's counts, padded to the place capacity;
- tables(spec): the host tables of the exact free energy (kernel.Tables);
- components(spec): the registered IDs the definition uses;
- run(spec) (runner.py) and write_run (records.py); RUNNER names the entry.
"""

import math

import numpy as np

from cells.models.assembly_lineages import ledger as v1_ledger
from cells.models.assembly_lineages_v2 import (
    MODEL_ID,
    SHEAR_FISSION,
    SIZE_THRESHOLD_DIVISION,
    TENSION_HOLD,
    streams,
)
from cells.models.assembly_lineages_v2 import world as world_rules
from cells.models.assembly_lineages_v2.kernel import ENTRIES, Layout, Structure, Tables
from cells.registry import laws as law_registry

OBSERVER_ID = None  # No fixed-step observer: records come from the run itself (records.py).
RUNNER = "cells.models.assembly_lineages_v2.runner:run"


def _excess(world):
    return tuple(law_id for law_id, _ in world.terms[1:])


def structure(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    world = m.world
    return Structure(
        places=x.place_capacity,
        steps=x.step_capacity,
        molecules=x.molecule_capacity,
        offset=world.conventions.offset,
        last_molecule=world.conventions.last_molecule,
        reactions=tuple(sorted({step.law for step in world.steps})),
        factor=None if world.rate_factor is None else world.rate_factor[0],
        terms=_excess(world),
        chunk=x.chunk_events,
        unroll=x.unroll,
        uniforms=e.uniforms,
        geometry=None if world.geometry is None else world.geometry[0],
    )


def log_extent(world, phase):
    """ln X = ln(N_A V c0) of a dilute phase (V in litres, c0 in mol/L)."""
    c0 = world.units.standard_concentration_mM * 1e-3
    return math.log(world_rules.AVOGADRO * world.volume(phase) * c0)


def place_arrays(world, capacity):
    """(held, phase, mu0, log_X, log_activity, held_mu, finite, membrane), each [P]."""
    held = np.zeros(capacity, dtype=bool)
    phase = np.zeros(capacity, dtype=np.int32)
    mu0 = np.zeros(capacity, dtype=np.float64)
    log_X = np.zeros(capacity, dtype=np.float64)
    log_activity = np.zeros(capacity, dtype=np.float64)
    held_mu = np.zeros(capacity, dtype=np.float64)
    finite = np.zeros(capacity, dtype=bool)
    membrane = np.zeros(capacity, dtype=bool)
    c0 = world.units.standard_concentration_mM
    for i, place in enumerate(world.places):
        species = world.species_by_id(place.species)
        phase[i] = world_rules.PHASE_INDEX[place.phase]
        mu0[i] = species.mu(place.phase)
        if place.phase in world_rules.DILUTE and world.volume(place.phase) is not None:
            log_X[i] = log_extent(world, place.phase)  # An osmotic lumen's X is 1 (lumen.py).
        if place.held:
            held[i] = True
            log_activity[i] = math.log(place.held_mM / c0)
            held_mu[i] = mu0[i] + log_activity[i]
        else:
            finite[i] = True
            membrane[i] = place.phase == world_rules.MEMBRANE
    return held, phase, mu0, log_X, log_activity, held_mu, finite, membrane


def entries(world, steps):
    """(place [R, K] int32, alpha [R, K] int64, beta [R, K] int64): each step's distinct places in
    place order, padded with exact no-ops (place 0, α = β = 0)."""
    place = np.zeros((steps, ENTRIES), dtype=np.int32)
    alpha = np.zeros((steps, ENTRIES), dtype=np.int64)
    beta = np.zeros((steps, ENTRIES), dtype=np.int64)
    index = {p.name: i for i, p in enumerate(world.places)}
    for r, step in enumerate(world.steps):
        reactants, products = dict(step.reactants), dict(step.products)
        names = sorted(set(reactants) | set(products), key=index.__getitem__)
        for k, name in enumerate(names):
            place[r, k] = index[name]
            alpha[r, k] = reactants.get(name, 0)
            beta[r, k] = products.get(name, 0)
    return place, alpha, beta


def _fold(values):
    total = 0.0
    for v in values:
        total = total + float(v)
    return total


def layout(spec):
    """One lane's values (host NumPy arrays)."""
    m, e, x = spec.model, spec.experiment, spec.execution
    world = m.world
    P, R = x.place_capacity, x.step_capacity
    held, phase, mu0, log_X, log_activity, held_mu, _, _ = place_arrays(world, P)
    place, alpha, beta = entries(world, R)
    active = np.zeros(R, dtype=bool)
    step_law = np.zeros(R, dtype=np.int32)
    reactions = sorted({step.law for step in world.steps})
    kf = np.zeros(R, dtype=np.float64)
    log_ratio = np.zeros(R, dtype=np.float64)
    locus_membrane = np.zeros(R, dtype=bool)
    extent = np.zeros(R, dtype=np.float64)
    work = np.zeros(R, dtype=np.float64)
    moves = np.zeros(R, dtype=np.int64)
    for r, step in enumerate(world.steps):
        active[r] = True
        step_law[r] = reactions.index(step.law)
        kf[r] = step.forward_rate_per_s
        nu = beta[r] - alpha[r]
        real = (alpha[r] + beta[r]) > 0
        log_ratio[r] = _fold(nu[k] * mu0[place[r, k]] for k in range(ENTRIES) if real[k])
        locus_membrane[r] = step.locus == world_rules.MEMBRANE
        if not locus_membrane[r] and world.volume(step.locus) is not None:
            extent[r] = log_extent(world, step.locus)  # An osmotic lumen's: X(V(m))^0 = 1.
        work[r] = -_fold(
            nu[k] * held_mu[place[r, k]] for k in range(ENTRIES) if real[k] and held[place[r, k]]
        )
        moves[r] = sum(
            int(nu[k])
            for k in range(ENTRIES)
            if real[k] and phase[place[r, k]] == world_rules.PHASE_INDEX["membrane"]
        )
    registry = law_registry.active()
    factor = ()
    if world.rate_factor is not None:
        law_id, data = world.rate_factor
        factor = registry.lookup(law_id).layout(data, world, R, P)
    terms = tuple(
        registry.lookup(law_id).layout(data, world, P) for law_id, data in world.terms[1:]
    )
    return Layout(
        entry_place=place,
        entry_alpha=alpha,
        entry_beta=beta,
        entry_phase=phase[place],
        entry_held=held[place],
        entry_log_X=log_X[place],
        entry_log_activity=log_activity[place],
        entry_mu0=mu0[place],
        step_active=active,
        step_law=step_law,
        kf=kf,
        log_ratio=log_ratio,
        locus_membrane=locus_membrane,
        log_extent=extent,
        step_work=work,
        step_moves=moves,
        place_held=held,
        place_phase=phase,
        log_factorial=v1_ledger.log_factorials(x.molecule_capacity),
        factor=factor,
        terms=terms,
        base_key=streams.base_key_data(x.seed, x.environment, x.lineage, x.branch),
        horizon=np.float64(e.time_horizon_s),
        event_limit=np.int64(e.event_limit),
        geometry=geometry_layout(world, P, R, place) if world.geometry is not None else (),
    )


def geometry_layout(world, P, R, place):
    """OL2's geometry arrays, in kernel.GEOMETRY_FIELDS' order (geometry.py); FR-21's shell's in
    the same order (shell_layout)."""
    from cells.models.assembly_lineages_v2 import (
        MEMBRANE_PERMEATION,
        PHASE_EXCHANGE,
        PRESCRIBED_SHELL,
    )
    from cells.models.assembly_lineages_v2 import geometry as geometry_rules

    if world.geometry[0] == PRESCRIBED_SHELL:
        return shell_layout(world, P, R)

    quanta = geometry_rules.place_quanta(world, P)
    entry_quanta = quanta[place]
    _, alpha, beta = entries(world, R)
    step_quanta = np.sum(entry_quanta * (beta - alpha), axis=1).astype(np.int64)
    encounter = np.zeros(R, dtype=np.int32)
    radius = world.conventions.exchange_encounter == "diffusion_radius"
    for r, step in enumerate(world.steps):
        if step.law == PHASE_EXCHANGE:
            encounter[r] = 2 if radius else 1
        elif step.law == MEMBRANE_PERMEATION:
            encounter[r] = 1  # permeation_area, whatever the exchange token (§0.2b rule 6)
    c_area, c_radius = geometry_rules.log_constants(world)
    return (
        quanta,
        entry_quanta.astype(np.int64),
        step_quanta,
        encounter,
        np.float64(c_area),
        np.float64(c_radius),
        np.int64(geometry_rules.floor_quanta(world)),
        *lysis_layout(world, P),
    )


def shell_layout(world, P, R):
    """FR-21's prescribed shell in kernel.GEOMETRY_FIELDS' order: no quanta, no floor and no
    lysis; each cells.reaction.shell_permeation@1 step takes the constant extent ln(A_sh·ρ0) (code 3, in
    the log_area slot)."""
    from cells.models.assembly_lineages_v2 import SHELL_PERMEATION, prescribed_shell

    encounter = np.zeros(R, dtype=np.int32)
    for r, step in enumerate(world.steps):
        if step.law == SHELL_PERMEATION:
            encounter[r] = SHELL_ENCOUNTER
    return (
        np.zeros(P, dtype=np.int64),
        np.zeros((R, ENTRIES), dtype=np.int64),
        np.zeros(R, dtype=np.int64),
        encounter,
        np.float64(prescribed_shell.log_extent(world)),
        np.float64(0.0),
        np.int64(0),
        np.zeros(P, dtype=np.int64),
        np.zeros(4, dtype=np.float64),
        np.float64(np.inf),
        np.float64(world.units.kT_J),
        np.float64(0.0),
    )


SHELL_ENCOUNTER = 3  # kernel.GEOMETRY_FIELDS' step_encounter: a shell's constant extent


def lysis_layout(world, P):
    """OL2 milestone 2's lysis arrays (kernel.GEOMETRY_FIELDS after floor_quanta): the lumen
    mask, the tension's constants and sigma_max. A world without an osmotic lumen cannot lyse:
    sigma_max is +inf there, so no event lyses and OL2 milestone 1's worlds run as before."""
    from cells.models.assembly_lineages_v2 import lumen as lumen_rules

    mask = np.asarray([i < len(world.places) and world.places[i].phase == world_rules.LUMEN
                       for i in range(P)], dtype=np.int64)  # fmt: skip
    kT, q = np.float64(world.units.kT_J), np.float64(world.geometry[1]["area_quantum_m2"])
    if world.conventions.lumen_volume != "osmotic":
        return mask, np.zeros(4, dtype=np.float64), np.float64(np.inf), kT, q
    return (
        mask,
        np.asarray(lumen_rules.constants(world), dtype=np.float64),
        np.float64(world.geometry[1]["sigma_max_N_per_m"][0]),
        kT,
        q,
    )


def founder(spec):
    counts = np.zeros(spec.execution.place_capacity, dtype=np.int64)
    counts[: len(spec.model.world.founder)] = spec.model.world.founder
    return counts


def tables(spec):
    """The host tables of the exact free energy (kernel.Tables), per place."""
    world, x = spec.model.world, spec.execution
    _, _, mu0, log_X, _, _, finite, membrane = place_arrays(world, x.place_capacity)
    return Tables(
        mu0=mu0,
        log_X=log_X,
        finite=finite,
        membrane=membrane,
        log_factorial=v1_ledger.log_factorials(x.molecule_capacity),
        offset=world.conventions.offset,
    )


def components(spec):
    """The registered IDs the definition uses, by role."""
    world = spec.model.world
    laws = list(dict.fromkeys(step.law for step in world.steps))
    laws += [law_id for law_id, _ in world.terms]
    if world.rate_factor is not None:
        laws.append(world.rate_factor[0])
    if world.geometry is not None:
        laws.append(world.geometry[0])
    operators = [] if world.division is None else [SHEAR_FISSION]  # OL3 (division.py)
    if world.size_division is not None:  # OL6 S7 (size_division.py)
        operators.append(SIZE_THRESHOLD_DIVISION)
    if world.hazard is not None:  # FR-31: the hazard, and the holds it reads (written only then)
        laws.append(world.hazard[0])
    if spec.experiment.tension_holds:
        operators.append(TENSION_HOLD)
    return {"model": MODEL_ID, "laws": laws, "operators": operators}
