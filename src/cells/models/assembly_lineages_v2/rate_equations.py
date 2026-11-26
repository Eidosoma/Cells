"""cells.assembly_representation.rate_equations@1: the deterministic representation of the family's laws (OL6, D304).

The design is docs/OL6_DETERMINISTIC_REPRESENTATION_DESIGN.md (tag ol6-design-note-2026-11-22).
A definition chooses it by `execution.representation`, over the same world as exact events: the
world id, its laws, terms and founder are the world's; the representation is the definition's
choice, made before the run and recorded with it. A definition that declares none runs as exact
events, as before.

**The flux** (the note's §1.3). Every step r keeps its exact pair's rule in the large-count limit:

    J_r(n) = s_r(n) θ⁺_r(n) (1 − e^{ΔF_r}),   ΔF_r = ν_r·μ(n) − w_r,   μ = ∇F_cont,

with s, θ⁺ from each law's declared limit (arithmetic A: ff(n, a) → n^a, ff(N − c, r) → (N − c)^r,
m → n; a geometric law's extent at the real footprint W(n)) and F_cont the terms' declared limits
(Stirling's form of the declared F; the osmotic lumen's closed form at real N_L and W). μ is
F_cont's gradient by differentiation; w_r is the held places' work, as the exact kernel's. So
−J_r ΔF_r ≥ 0 for every step at every state. J is evaluated in the factored form (i), with
−expm1, which has no cancellation near equilibrium; the limit's check compares it with the
products' law (ii).

**The state** (§1.6): y = [pool, vesicles, supplied, Q, W]. In a single lineage `pool` is the
world's every place and there is no vesicle block (S1's layout); in a population
(cells.population.shared_pool@1, at most 64 slots, §6.9) `pool` holds the pool's places and each slot holds
its vesicle's membrane and lumen places. `supplied` is each held place's net supply, Q the heat
and W the reservoir work (k_BT), all integrated by the same stages; the counts, Q and W under the
step control, the supplies not (a linear quadrature, kept exactly). Every slot's flux is the
single assembly's at its vesicle with the pool, the pool's own steps at the pool with an empty
vesicle (as population.py's rates).

**The integrator** is declared apart (cells.solver.rosenbrock_rodas4_dense@1, numerics/rosenbrock_dense.py),
with its Jacobian the forward derivative of this module's right-hand side, so linear invariants (the
moieties) are kept to rounding.

**Stops and crossings** (§3.1, §3.2). The integrator lands exactly on every observation time,
schedule time (declared or drawn) and the horizon; at a stop the schedule's operators act in
schedule-index order, and an observation at that time sees the state after them. A crossing is a
guard with a direction: an enveloped place's count − min_count (downward: the run stops
`outside_envelope`), a vesicle's footprint − W_floor (downward: the exact floor is a barrier the
rate equations do not carry, so the same stop), its tension − σ_max (upward: lysis, §3.3) and
ln V_osm − ln V_sph (either way: the lumen's kink, a restart, so the method keeps its order past
μ's kink). After each accepted step every guard is evaluated on the step's dense output at its ends
and 8 interior points; the earliest bracket's root is located by the Illinois method, the step is
re-taken from its start to the root, and the guard is evaluated again at the re-stepped state (a
secant on the step repeats it, at most 4 times, or the run stops `stalled`). Two crossings within
clock_instants.same_instant of each other, or a crossing at a stop, are refused (FR-20's rule).

**The operators** (§3.3, §3.4): a lysis is the release (the vesicle's molecules to their pool
places, a held place's reservoir taking them back with its work, the closure cost released), one
booking q = −(F_cont(after) − F_cont(before)) + w_r; a single lineage ends `lysed`, a population's
slot frees. Shear fission at its stops: the exact operator's admission on the continuous state,
then the mean split (each daughter n/k of every vesicle place, the last the complement), the floor
test (refused, the parent kept), keys and continuation as the exact operator's (domain 3), and the
booking Σ_j F_v(d_j) − F_v(parent). A serial transfer draws as the exact operator does (domain 6)
and books F_cont.

**The envelope** (§1.5, E1): every finite place a rate reads holds at least `min_count`, at the
founder (else refused at parse) and at every accepted step (else the run stops `outside_envelope`
at the located crossing). A step whose end state is below min_count/2 is rejected and retried.

**The ledger** (§2): at every row F_cont(n_t) − F_cont(n_0) = W − Q − S (W summed over payers, S
the sinks), to the integrator's tolerance; every moiety to rounding; and the second law per step,
−J_r ΔF_r ≥ 0, at every accepted state. A run whose books do not close is refused.

**The pore clock** (§3.5, S3; cells.assembly_hazard.pore_nucleation@1 and cells.operator.tension_hold@1). Each vesicle
draws E_v = −ln u from domain 7 (its key, counter 0) when the run first holds it: a founder at the
start, a daughter at its birth, with H_v = 0 then. H_v = ∫ k_v dt, k_v the law's rate at the
vesicle's real area A = q·W/2 and tension: the hold's over [start_s, end_s) (whose edges are stops),
or, with no hold, the osmotic lumen's σ(N_L, W) (σ from F; 0 while floppy). H is carried by each
step's own stages (rosenbrock_dense.quadrature), never appended to y, so it stays out of step
selection and a pore world takes exactly its pore-free twin's steps until its first opening; its
embedded error estimate U^H is monitored at every accepted step, per vesicle, and a run where
|U^H| passes 1e-10 + 2e-3·|ΔH| (ΔH the step's own clock increment; D309, which replaced the
absolute 1e-10) is refused. The opening is the crossing H_v = E_v (upward), located as every
guard is; Phase A's outcome follows, the rupture through the release (cause `pore`), booked as two
parts whose ΔF_open cancels: the opening q_open = −ΔF_open + w (under a hold w = σ_β/σ, paid by
source:tension_hold/<i>, ΔF_open = 2σ_β/σ − ln(A·n_s); with σ from F w = 0 and
ΔF_open = σ_β/σ − ln(A·n_s), the note's §2.1) and the release from the open state. The hazard and
σ_max both stand: whichever crosses first acts. Under a hold, a step that changes a membrane
place's count is refused (T2); with σ from F, σ_max ≤ σ_β/4 is required at parse.

**FR-47 (D323, D327): the prescribed shell, its washes and E2.**
- **The shell** (cells.assembly_geometry.prescribed_shell@1): each cells.reaction.shell_permeation@1 step's extent is the
  shell's constant A_sh·ρ0, dispatched by the geometry kind as the exact kernel does; a shell has
  no bilayer quantities, closure cost, floor, tension or lysis. Its permeation's limit is its exact
  form (one molecule a step), and cells.rate_factor.gate_factor@1's is g at m = n. A shell world's own check
  adds parity with the exact kernel's rates (the extent's dispatch).
- **The washes** (in a shell's world, version 1), host operators beside the transfer: a
  replacement is the same map (the sink F_cont of the old pool, the schedule's work column F_cont
  of the fresh one); a withdrawal is its mean, n → (1 − f)·n + b on the pool's finite places,
  booked as the exact operator books with F_cont (the sink F(n; V) − F((1 − f)n; (1 − f)V), the
  work F(b; fV), the mixing heat F((1 − f)n; (1 − f)V) + F(b; fV) − F(after; V)).
- **E2, true zeros at first-order places** (in a shell's world, version 1): a finite dilute place
  that every step reading it reads at first order (at most one finite molecule a side, by no excess
  term) and that some founder holds below min_count or a declared wash acts on. Such a place is
  outside E1's envelope; each step reading it takes the difference form J = a⁺ − a⁻, each
  direction its law's at the place's count 1 times that count: the first-order law's linear form,
  exact at any real count, with an exact derivative at 0 (the factored form gives J = −0 there).
  A step that starts with an E2 place at or below 0 books its heat by the closure identity, since
  μ = ln n diverges there (integrably); its heat leaves that step's error control. A step result
  with an E2 place below −10·atol_count is rejected and retried at h/4, or the run stops
  `stalled`. A world without E2 places traces its program as before.
- **Refused by name in version 1,** each until a qualification covers it: washes and the gate
  factor outside a shell's world, site binding in a shell's world, a gate driven by anything but
  its own forms (bound states included), and FR-46's inner face.
- **Status:** admitted, development-only until fr47-shell-exchange's verdict. The registered
  declaration's `qualified` says so, and each run that uses these paths records it
  (representation.qualification in run.json).

**Slices:** S1 (OL1's laws), S2 (vesicles: geometry, the osmotic lumen, lysis, the shared pool,
shear fission, serial transfer) and S3 (the pore clock and held tensions); FR-47 (the shell).
"""

import functools
import math
from dataclasses import dataclass, field
from time import perf_counter

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import ConfigError, SimulationSpec, bounded_integer, require_fields
from cells.models.assembly_lineages_v2 import (
    BILAYER_GEOMETRY,
    GATE_FACTOR,
    IDEAL_MIXING,
    MODE,
    MODEL_ID,
    POPULATION,
    PORE_NUCLEATION,
    PRESCRIBED_SHELL,
    RATE_EQUATIONS,
    SIZE_THRESHOLD_DIVISION,
    geometry,
    kernel,
    lumen,
    model,
    pore_clock,
    pore_nucleation,
    streams,
    tension_hold,
)
from cells.models.assembly_lineages_v2 import world as world_rules
from cells.models.assembly_lineages_v2.interfaces import AssemblyRepresentation
from cells.modules import Citation, CitedWork
from cells.numerics import rosenbrock_dense as rd
from cells.numerics.clock_instants import same_instant

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

TEST = "tests/unit/test_assembly_lineages_v2_rate_equations.py"
METHODS = (rd.METHOD_ID,)
STATUSES = ("complete", "lysed", "outside_envelope", "stalled", "step_limit", "slots_full")
READOUTS = (
    "the counts of every place, real, at the start, each observation time, each event and the end",
    "each held place's net supply",
    "the heat Q and the work W by payer (k_BT), the sinks, and F_cont at each row",
    "vesicle-level events with their times: lysis, division, transfer",
)
REFUSED_READOUTS = (
    "event traces and their uniforms (trace, uniforms)",
    "the diagnostic record of draws",
    "channel counts",
    "H similarity, F12, composomes and extinction statistics (they measure discreteness)",
)
NOT_APPLICABLE = ("event_limit", "row_every_events")  # the experiment's event-based keys
EXECUTION_KEYS = {"backend", "precision", "mode", "stream", "place_capacity", "step_capacity",
                  "representation"}  # fmt: skip
EXECUTION_REQUIRED = {"backend", "precision", "mode", "stream", "representation"}
EXACT_ONLY = ("molecule_capacity", "chunk_events", "unroll")
RTOL_RANGE = (1e-13, 1e-3)
EPS = float(np.finfo(np.float64).eps)
MAX_SLOTS = 64  # §6.9: a population's linear algebra is dense in version 1
WASHES = ("replacement", "withdrawal")  # FR-47: admitted in a prescribed shell's world only
BELOW_ZERO = 10.0  # FR-47's E2: a step result below −BELOW_ZERO·atol_count is retried at h/4
FR47_STATUS = "admitted, development-only until fr47-shell-exchange's verdict"  # the lead's words
FR47_PROTOCOL = "fr47-shell-exchange-registered-2026-11-24"  # FR-47's registered tag (D323)
H_ERROR = 1e-10  # §3.5: the pore clock's bound per accepted step, its absolute part
H_RELATIVE = 2e-3  # D309: its relative part, |U^H| <= H_ERROR + H_RELATIVE |dH| per vesicle

FORMULAS = {
    "flux": "J_r = s_r(n) theta+_r(n) (1 - exp(dF_r)), dF_r = nu_r . mu(n) - w_r, mu = grad F_cont",
    "limit": "arithmetic A: ff(n, a) -> n^a, ff(N - c, r) -> (N - c)^r, m -> n; F_cont is "
    "Stirling's form of the declared F (each law's and term's declared limit)",
    "state": "dn/dt = sum_r nu_r J_r; d supplied_p/dt = -sum_r nu_r,p J_r (held p); "
    "dQ/dt = -sum_r J_r dF_r >= 0; dW/dt = sum_r J_r w_r",
    "closure": "F_cont(n_t) - F_cont(n_0) = W - Q - S at every row, to the integrator's tolerance",
    "envelope": "every finite place a rate reads holds at least min_count",
    "geometry": "cells.assembly_geometry.bilayer_geometry@1 at real W = sum_i k_i n_i: the extents at W(n) (consumed "
    "0, so W(m) = W(n)); the closure cost once per living vesicle, in F_cont's value; the floor "
    "refuses a fission with a daughter below W_floor, and a vesicle reaching W_floor stops the run "
    "outside_envelope",
    "population": "F_cont = F(pool) + sum over living slots of [F(pool + slot) - F(pool) + C]; a "
    "slot's flux is the single assembly's at its vesicle with the pool, the pool's steps at the "
    "pool with an empty vesicle",
    "crossings": "guards on the dense output at a step's ends and 8 interior points; the earliest "
    "root by the Illinois method, the step re-taken to it, the guard checked again (a secant, at "
    "most 4 times)",
    "lysis": "the crossing sigma = sigma_max; the release, booked q = -(F_cont(after) - "
    "F_cont(before)) + w_r",
    "fission": "the mean split: each daughter n/k of every vesicle place, the last the complement; "
    "shear work sum_j F_v(d_j) - F_v(parent), F_v with the closure cost",
    "pores": "E_v = -ln u (domain 7, the vesicle's key, counter 0) at its founding or birth, "
    "H_v = 0 then; dH_v/dt = k_v(A_v, sigma_v, T), A_v = q W_v / 2 real, sigma_v the hold's "
    "over [start_s, end_s) or the osmotic lumen's sigma(N_L, W) (0 while floppy); H carried by "
    "the step's stages, out of step selection; the opening at H_v = E_v, upward; q_open = "
    "-dF_open + w, then the release from the open state, so dF_open cancels",
}
PORE_LIMIT = {  # the pore law in this representation: the same law at real counts (§1.4)
    "rule": "the same closed form at the vesicle's real area A = q W / 2 and tension (the hold's, "
    "or the osmotic lumen's sigma(N_L, W) at real N_L and W); its clock H integrated with the "
    "state",
}
FR47_FORMULAS = {  # FR-47 (D323): written into a run's record only where its world uses them
    "shell": "cells.assembly_geometry.prescribed_shell@1: each cells.reaction.shell_permeation@1 step's extent is the "
    "constant A_sh rho0, as the exact kernel's; no bilayer quantities, closure cost, floor, "
    "tension or lysis",
    "washes": "cells.operator.pool_replacement@1: the same map, the sink F_cont(old pool), the work "
    "F_cont(fresh pool); cells.operator.pool_withdrawal@1's mean, n -> (1 - f) n + b on the pool's "
    "finite "
    "places: the sink F(n; V) - F((1 - f) n; (1 - f) V), the work F(b; f V), the mixing heat "
    "F((1 - f) n; (1 - f) V) + F(b; f V) - F((1 - f) n + b; V), with F(c; g V) = F_cont(c) - "
    "F_cont(0) - (sum c) ln g",
    "e2": "at a first-order place that some founder holds below min_count or that a wash acts on: "
    "J_r = a+_r - a-_r, each direction its law's at the place's count 1 times that count, exact at "
    "any real count; a step from such a place at or below 0 books its heat by closure, Q1 = Q0 + "
    "(W1 - W0) - (F_cont(y1) - F_cont(y0)); a step result below -10 atol_count is retried at h/4",
}

REPRESENTATION = law_registry.BUILTIN.register(
    AssemblyRepresentation(
        RATE_EQUATIONS,
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "Kurtz (1972), J Chem Phys 57:2976 (the large-system limit of a chemical master "
            "equation), cited from memory in docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §1.2 (d); "
            "docs/OL6_DETERMINISTIC_REPRESENTATION_DESIGN.md §1",
            "the reaction-rate equations of the same declared laws, in their large-count limit",
            "no numbers taken",
            (
                "a declared representation over the same world, chosen at definition (D304)",
                "valid only inside its envelope: every count a rate reads is large",
            ),
            (
                CitedWork(
                    ("T. G. Kurtz",),
                    1972,
                    "The relationship between stochastic and deterministic models for chemical "
                    "reactions",
                    doi="10.1063/1.1678692",
                ),
            ),
        ),
        test=TEST,
        represents={
            "detailed": f"{MODEL_ID}'s exact events (the default representation)",
            "scope": "the whole world: one representation per run (refused when mixed)",
            "reduction": "the large-count limit of the same declared laws, term by term",
        },
        preserves={
            "exactly": (
                "the world id, its laws, terms, founder and units",
                "every moiety, to rounding",
                "F_cont's minima, and so every end state that is one",
            ),
            "to_tolerance": ("the ledger's closure, F_cont(n_t) - F_cont(n_0) = W - Q - S",),
        },  # fmt: skip
        supports={"readouts": READOUTS, "refused": REFUSED_READOUTS},
        qualified={
            "envelope": "execution.representation.envelope.min_count, declared with provenance",
            "error_budget": "Protocol D's criterion B: b = 2 on the mean, c_r = 5 per replica "
            "(docs/OL6_DETERMINISTIC_REPRESENTATION_DESIGN.md §5.1)",
            "record": "development: Protocol D's registered tag is pending (S5)",
            "fr47": FR47_STATUS + ": the prescribed shell, its washes, E2 and autonomous gates, "
            "in a prescribed shell's world only, registered for FR-47's protocol (tag "
            "fr47-shell-exchange-registered-2026-11-24); its independent checker's run is pending, "
            "and each run that uses them records this status (representation.qualification)",
            "checker": "an independent checker runs each protocol at its tag (D304)",
        },
        methods=METHODS,
        readouts=READOUTS,
        refused_readouts=REFUSED_READOUTS,
        statuses=STATUSES,
        pair={
            "world": "the same world id: one world, two representations",
            "interface": "the counts of every place, held supplies, heat and work by payer, "
            "vesicle-level events and their times, in the world's units",
            "streams": "what stays stochastic draws on the same domains and keys (pores 7, "
            "schedules 6, continuation 3); exact events alone draw domains 1, 2 and 5",
            "qualification": "a registered protocol, against exact events where both run",
        },
        formulas=FORMULAS,
    )
)
assert REPRESENTATION.law_id == RATE_EQUATIONS


# ------------------------------------------------------------------ the definition


@dataclass(frozen=True)
class RepresentationExecution:
    """A definition's execution in this representation. The last three fields are fixed: what the
    exact layout builders read, unused here (no log-factorial table, no chunks)."""

    backend: str
    precision: str
    mode: str
    seed: int
    environment: int
    lineage: int
    branch: int
    place_capacity: int
    step_capacity: int
    representation: str
    min_count: float
    envelope_provenance: str
    method: str
    rtol: float
    atol_count: float
    step_limit: int
    molecule_capacity: int = 1
    chunk_events: int = 1
    unroll: int = 1


def parse_execution(raw, model_spec):
    """`execution` with a `representation` block (spec.parse calls it before the exact parser)."""
    from cells.models.assembly_lineages_v2 import spec as spec_rules

    if not isinstance(raw, dict):
        raise ConfigError("execution is an object")
    present = sorted(set(raw) & set(EXACT_ONLY))
    if present:
        raise ConfigError(
            f"execution: {', '.join(present)} does not apply in {RATE_EQUATIONS}: it builds no "
            "log-factorial table and draws no event chunks"
        )
    spec_rules._keys(raw, EXECUTION_KEYS, EXECUTION_REQUIRED, "execution")
    if raw["backend"] not in ("cpu", "gpu") or raw["precision"] != "float64":
        raise ConfigError("execution: backend cpu or gpu, precision float64")
    if raw["mode"] not in (MODE, POPULATION):
        raise ConfigError(f"execution: {RATE_EQUATIONS} runs mode {MODE} or {POPULATION}")
    stream = raw["stream"]
    require_fields(stream, spec_rules.STREAM_KEYS, "execution: stream")
    words = {}
    for key in sorted(spec_rules.STREAM_KEYS):
        try:
            words[key] = streams.check_word(stream[key], f"execution: stream {key}")
        except ValueError as error:
            raise ConfigError(str(error)) from error
    world = model_spec.world
    places = bounded_integer(
        raw.get("place_capacity", spec_rules.bucket(len(world.places))),
        "execution: place_capacity",
        minimum=len(world.places),
        maximum=spec_rules.BUCKETS[-1],
    )
    steps = bounded_integer(
        raw.get("step_capacity", spec_rules.bucket(len(world.steps))),
        "execution: step_capacity",
        minimum=len(world.steps),
        maximum=spec_rules.BUCKETS[-1],
    )
    block = raw["representation"]
    require_fields(block, {"id", "envelope", "integrator"}, "execution: representation")
    if set(block) != {"id", "envelope", "integrator"}:
        raise ConfigError("execution: representation is {id, envelope, integrator}")
    if block["id"] != RATE_EQUATIONS:
        raise ConfigError(f"execution: representation's id is {RATE_EQUATIONS}")
    envelope = block["envelope"]
    if not isinstance(envelope, dict) or set(envelope) != {"min_count", "provenance"}:
        raise ConfigError("execution: representation: envelope is {min_count, provenance}")
    min_count = _number(envelope["min_count"], "envelope: min_count", low=1.0)
    if not isinstance(envelope["provenance"], str) or not envelope["provenance"]:
        raise ConfigError("execution: representation: envelope states its provenance")
    method = block["integrator"]
    keys = {"id", "rtol", "atol_count", "step_limit"}
    if not isinstance(method, dict) or set(method) != keys:
        raise ConfigError(f"execution: representation: integrator is {{{', '.join(sorted(keys))}}}")
    if method["id"] not in METHODS:
        raise ConfigError(f"execution: representation: integrator's id is one of {METHODS}")
    rtol = _number(method["rtol"], "integrator: rtol", low=RTOL_RANGE[0], high=RTOL_RANGE[1])
    atol = _number(method["atol_count"], "integrator: atol_count", low=1e-300)
    limit = bounded_integer(method["step_limit"], "integrator: step_limit", maximum=10**9)
    return RepresentationExecution(
        backend=raw["backend"],
        precision=raw["precision"],
        mode=raw["mode"],
        place_capacity=places,
        step_capacity=steps,
        representation=block["id"],
        min_count=min_count,
        envelope_provenance=envelope["provenance"],
        method=method["id"],
        rtol=rtol,
        atol_count=atol,
        step_limit=limit,
        **words,
    )


def _number(value, name, *, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ConfigError(f"execution: representation: {name} is a finite number")
    value = float(value)
    if (low is not None and value < low) or (high is not None and value > high):
        raise ConfigError(f"execution: representation: {name} is in [{low}, {high}]")
    return value


def execution_to_dict(x):
    return {
        "backend": x.backend,
        "precision": x.precision,
        "mode": x.mode,
        "stream": {"seed": x.seed, "environment": x.environment, "lineage": x.lineage,
                   "branch": x.branch},
        "place_capacity": x.place_capacity,
        "step_capacity": x.step_capacity,
        "representation": {
            "id": x.representation,
            "envelope": {"min_count": x.min_count, "provenance": x.envelope_provenance},
            "integrator": {"id": x.method, "rtol": x.rtol, "atol_count": x.atol_count,
                           "step_limit": x.step_limit},
        },
    }  # fmt: skip


def refusals(world, experiment, execution):
    """Version 1's refusals (the note's §4), each by name, after the world and the experiment
    parse as they do for exact events."""
    from cells.models.assembly_lineages_v2 import spec as spec_rules

    spec_rules._mode_refusals(world, execution.mode)
    if world.size_division is not None:  # OL6 S7
        raise ConfigError(
            f"{RATE_EQUATIONS}: {SIZE_THRESHOLD_DIVISION} is refused in version 1: its trigger is "
            "a count reaching a size, and the GARD limit's scale, its first use, lies outside the "
            "envelope (the note's §6.8)"
        )
    if world.hazard is not None or experiment.tension_holds:
        _pore_refusals(world, experiment.tension_holds)
    if world.inner_sites:  # FR-46 (D323): binding from the lumen, until a qualification covers it
        raise ConfigError(
            f"{RATE_EQUATIONS}: inner-face site binding is refused in version 1 (FR-46): with a "
            "finite lumen ligand it is bimolecular, and no qualification covers it yet"
        )
    shell = world.geometry is not None and world.geometry[0] == PRESCRIBED_SHELL
    if shell:  # FR-47 (D323, R9): site binding in a shell's world, until W3 or another covers it
        from cells.models.assembly_lineages_v2 import spec as spec_rules

        by_name = {p.name: p for p in world.places}
        for step in world.steps:
            if spec_rules._declared_binding(step, world, by_name):
                raise ConfigError(
                    f"{RATE_EQUATIONS}: site binding in a {PRESCRIBED_SHELL} world (step "
                    f"{step.id}) is refused in version 1 (FR-47, D323), until a qualification "
                    "covers it: it is bimolecular at the wall, and FR-47's does not cover it"
                )
    if world.rate_factor is not None and world.rate_factor[0] == GATE_FACTOR:
        if not shell:
            raise ConfigError(
                f"{RATE_EQUATIONS}: {GATE_FACTOR} is refused in version 1 outside a "
                f"{PRESCRIBED_SHELL} world, until a qualification covers it: FR-47's covers a "
                "gate in a shell's world only"
            )
        _gate_refusals(world)  # FR-47 (D323, R7): autonomous switching only
    if world.geometry is not None and world.geometry[0] not in (BILAYER_GEOMETRY, PRESCRIBED_SHELL):
        raise ConfigError(
            f"{RATE_EQUATIONS}: the geometry {world.geometry[0]} is refused in version 1: this "
            f"representation carries {BILAYER_GEOMETRY} and {PRESCRIBED_SHELL} only"
        )
    if world.population is not None and world.population["slots"] > MAX_SLOTS:
        raise ConfigError(
            f"{RATE_EQUATIONS}: a population of {world.population['slots']} slots is refused: at "
            f"most {MAX_SLOTS} in version 1 (dense linear algebra, the note's §6.9)"
        )
    for schedule in experiment.schedules:
        if schedule.kind in WASHES and not shell:
            raise ConfigError(
                f"{RATE_EQUATIONS}: a {schedule.kind} schedule is refused in version 1 outside a "
                f"{PRESCRIBED_SHELL} world, until a qualification covers it: FR-47's covers "
                "washes in a shell's world only"
            )
    if world.role is not None:
        raise ConfigError(
            f"{RATE_EQUATIONS}: a world with world_role {world.role!r} is refused: its singular "
            "rate is a statement about integer states"
        )
    for name in ("trace", "uniforms", "diagnostic"):
        if getattr(experiment, name):
            raise ConfigError(
                f"{RATE_EQUATIONS}: experiment.{name} is an event-level readout, refused here"
            )
    registry = law_registry.active()
    laws = [step.law for step in world.steps] + [law_id for law_id, _ in world.terms]
    if world.rate_factor is not None:
        laws.append(world.rate_factor[0])
    for law_id in dict.fromkeys(laws):
        if getattr(registry.lookup(law_id), "limit", None) is None:
            raise ConfigError(
                f"{RATE_EQUATIONS}: {law_id} declares no large-count limit, so it is refused "
                "in this representation"
            )
    envelope = enveloped(world, exempt=e2_places(world, experiment, execution.min_count))
    for label, counts in _founders(world):
        for i, place in enumerate(world.places):
            if envelope[i] and counts[i] < execution.min_count:
                raise ConfigError(
                    f"{RATE_EQUATIONS}: {label}'s {place.name} holds {counts[i]}, below the "
                    f"envelope's min_count {execution.min_count:g}: the representation is valid "
                    "only where every count a rate reads is large (a place rising from 0 is "
                    "refused in version 1, but at E2's first-order places in a shell's world, "
                    "until a qualification covers it elsewhere)"
                )


def _founders(world):
    """[(label, whole-world counts)]: the founder, or each population founder with the pool's."""
    if world.population is None:
        return [("the founder", world.founder)]
    pool = np.asarray(world.founder)
    return [(f"founder {i}", pool + np.asarray(v))
            for i, v in enumerate(world.population["founders"])]  # fmt: skip


def _gate_refusals(world):
    """FR-47 (D323, R7): a gate's forms switch autonomously, by steps among themselves. A step
    that changes a form's count and reads any other place (a bound state, a ligand, another wall
    species, the form in another phase) couples the gate to what it gates: refused by name, since
    FR-47 qualifies autonomous switching only."""
    forms = set(world.rate_factor[1]["forms"])
    by_name = {p.name: p for p in world.places}

    def form(name):
        return by_name[name].phase == world_rules.MEMBRANE and by_name[name].species in forms

    for step in world.steps:
        change = {}
        for name, k in step.reactants:
            change[name] = change.get(name, 0) - k
        for name, k in step.products:
            change[name] = change.get(name, 0) + k
        changed = sorted(n for n, c in change.items() if c != 0 and form(n))
        others = sorted(n for n in change if not form(n))
        if changed and others:
            raise ConfigError(
                f"{RATE_EQUATIONS}: step {step.id} changes the gate's form {changed[0]} and reads "
                f"{others[0]}: a gate driven by bound states, or by anything but its own forms, is "
                "refused in version 1 (FR-47, D323), until a qualification covers it: FR-47's "
                "covers autonomous switching only, forms interconverting by wall steps among "
                "themselves"
            )


def _pore_refusals(world, holds):
    """S3's rules for the pore law and held tensions (the note's §3.5; §4 items 6 and 7). The
    tension is a hold's or the osmotic lumen's: tension_hold's cross-checks stand as they are when
    a hold is declared (its reader, no osmotic lumen, σ ≤ σ_β/4), and under a hold a step that
    changes a membrane place's count is refused (T2); with no hold, the lumen is osmotic (σ from
    F) and σ_max ≤ σ_β/4, so the law's domain holds on every trajectory that has not lysed."""
    if world.hazard is not None and world.hazard[0] != PORE_NUCLEATION:
        raise ConfigError(f"{RATE_EQUATIONS}: the hazard {world.hazard[0]} is refused: this "
                          f"representation carries {PORE_NUCLEATION}'s clock only")  # fmt: skip
    if holds:
        tension_hold.cross_checks(world, holds)
        changed = pore_nucleation.membrane_changes(world)
        if changed:
            step, place = changed[0]
            raise ConfigError(
                f"{RATE_EQUATIONS}: step {step} changes {place}'s count under a held tension: the "
                "hold would do sigma dA of work on every such step, which the laws sheet books "
                "only at an opening, so area-changing steps are refused under a hold (T2, the "
                "note's §2.3 and §6.7)"
            )
        return
    if world.conventions.lumen_volume != "osmotic":
        raise ConfigError(
            f"{RATE_EQUATIONS}: {PORE_NUCLEATION} reads a tension: a held one (the experiment's "
            "tension_holds) or the osmotic lumen's (sigma from F, under lumen_volume osmotic)"
        )
    _, gamma, _, _ = pore_nucleation.parameters(world)
    beta = pore_nucleation.sigma_beta(gamma, world.units.temperature_K)
    sigma_max = world.geometry[1]["sigma_max_N_per_m"][0]
    if not sigma_max <= tension_hold.SIGMA_BETA_FRACTION * beta:
        raise ConfigError(
            f"{RATE_EQUATIONS}: with sigma from F the tension reaches sigma_max = "
            f"{sigma_max:g} N/m, beyond sigma_beta/4 = "
            f"{tension_hold.SIGMA_BETA_FRACTION * beta:.6g} N/m (sigma_beta = "
            "pi Gamma^2/(k_B T)): the law needs sigma_beta >> sigma on every trajectory that has "
            "not lysed (the note's §3.5)"
        )


def enveloped(world, exempt=None):
    """[places] bool: the finite places whose count some rate or the geometry reads (§1.5), less
    `exempt`'s places (E2's, FR-47), when given. Held places hold no count. A place is read:
    1. **as a step's reactant or product,** by its law's activity (mass_action.limit_log_direction,
       exchange.geometric_log_direction);
    2. **through the membrane total N, which sums every finite membrane place,** where a law reads
       N:
       - a step with a membrane place on either side: the reverse or forward direction's
         membrane normalisation 1/ff(N − c, r) (both laws), and ideal mixing's −ln(N − c) in that
         place's μ, which the step's ΔF reads;
       - a mass-action step at the membrane locus: its extent (N − c + 1)/(N − c)^r
         (mass_action.limit_log_direction). A geometric law's extent comes from the geometry
         instead (kernel.encounter_extent, kernel.shell_extent);
       - the transition-state factor: its fractions m_j/N over every membrane molecule
         (transition_state.log_factor);
    3. **by the gate factor, only its forms' places:** its fractions are over the gate's own forms
       (gate_factor.log_factor), so no other wall species dilutes or reads it;
    4. **by a bilayer's footprint W(n) = Σ k_i n_i,** which sums every membrane place: the
       extents, the floor, the lumen's tension and kink, and the pore law (kernel.encounter_extent,
       lumen.tension).

    **A prescribed shell reads no wall count.** Its extent is the constant A_sh·ρ0
    (kernel.shell_extent; prescribed_shell.py: the wall's counts set neither its area nor its
    lumen), and cells.reaction.shell_permeation@1 moves no membrane molecule. So a wall species that no step,
    factor or law reads (an inert marker) is outside the envelope (FR-47's inert-wall fix). Every
    other world's places are enveloped as before."""
    index = {p.name: i for i, p in enumerate(world.places)}
    membrane = [i for i, p in enumerate(world.places) if p.phase == world_rules.MEMBRANE]
    out = [False] * len(world.places)
    total_read = world.geometry is not None and world.geometry[0] == BILAYER_GEOMETRY  # rule 4
    for step in world.steps:
        names = [name for name, _ in (*step.reactants, *step.products)]
        for name in names:  # rule 1
            out[index[name]] = True
        if any(index[name] in membrane for name in names):  # rule 2: its normalisation and μ
            total_read = True
        elif step.locus == world_rules.MEMBRANE and not total_read:
            # rule 2: a law at the membrane locus reads N through its extent unless the extent is
            # the geometry's. Only this case reads the registry, so a world whose steps are on a
            # scoped (planted) law is read the same outside the scope.
            law = law_registry.active().lookup(step.law)
            total_read = getattr(law, "extent", "locus") != "geometric"
    if world.rate_factor is not None:
        if world.rate_factor[0] == GATE_FACTOR:  # rule 3
            forms = set(world.rate_factor[1]["forms"])
            for i in membrane:
                out[i] |= world.places[i].species in forms
        else:  # rule 2: a factor over the membrane's composition reads N
            total_read = True
    for i, place in enumerate(world.places):
        if place.phase == world_rules.MEMBRANE and total_read:
            out[i] = True
        if place.held:
            out[i] = False
    if exempt is not None:
        out = [on and not e for on, e in zip(out, exempt, strict=True)]
    return out


def first_order(world):
    """[places] bool (FR-47's E2, D323): a finite dilute place whose every reading step reads it at
    first order: each step that has it as a reactant or a product carries at most one finite
    molecule on each side (so the place at coefficient 1, on one side), it lies in no phase that
    an excess term reads, and a lumen place lies in a declared lumen. The family's laws read a
    dilute place through its activity n/X alone (a rate factor reads the membrane only, an extent
    the wall), so such a place's rates are linear in its count; each E2 world's own check confirms
    it (each direction's linear form equals its law's direction at positive states)."""
    registry = law_registry.active()
    excess = set()
    for law_id, _ in world.terms:
        term = registry.lookup(law_id)
        if term.part == "excess":
            excess |= set(term.phases)
    by_name = {p.name: p for p in world.places}
    read, out = set(), []
    unimolecular = {}
    for step in world.steps:
        sides = (step.reactants, step.products)
        finite = [sum(k for n, k in side if not by_name[n].held) for side in sides]
        both = {n for n, _ in step.reactants} & {n for n, _ in step.products}
        for name, _ in (*step.reactants, *step.products):
            read.add(name)
            unimolecular[name] = unimolecular.get(name, True) and max(finite) <= 1 and not both
    osmotic = world.conventions.lumen_volume == "osmotic"
    for place in world.places:
        out.append(
            place.name in read
            and unimolecular[place.name]
            and not place.held
            and place.phase in world_rules.DILUTE
            and place.phase not in excess
            and not (place.phase == world_rules.LUMEN and osmotic)
        )
    return out


def e2_places(world, experiment, min_count):
    """[places] bool: E2's places (FR-47, D323), in a prescribed shell's world (version 1): the
    first-order places that some founder holds below min_count and, when a wash is declared, the
    pool's first-order places. Every other place keeps E1's envelope, so a world without E2 places
    (every world before FR-47) traces its program as before. None (an exact spec) has none."""
    out = [False] * len(world.places)
    if min_count is None or world.geometry is None or world.geometry[0] != PRESCRIBED_SHELL:
        return out
    order = first_order(world)
    washed = any(s.kind in WASHES for s in experiment.schedules)
    founders = [np.asarray(counts) for _, counts in _founders(world)]
    for i, place in enumerate(world.places):
        low = any(counts[i] < min_count for counts in founders)
        out[i] = order[i] and (low or (washed and place.phase == world_rules.POOL))
    return out


# ------------------------------------------------------------------ the arithmetic


class Problem:
    """One assembly's arithmetic in this representation, at a whole-world state n [P]: its layout
    (the exact builders', reused), its laws' limits and the ODE's matrices. Built from any parsed
    spec of the world, exact or not (the limit's check uses exact specs too)."""

    def __init__(self, spec):
        world = spec.model.world
        self.spec, self.world = spec, world
        self.structure = model.structure(spec)
        self.layout = model.layout(spec)
        self.tables = model.tables(spec)
        self.P, self.R = self.structure.places, self.structure.steps
        self.offset = world.conventions.offset
        registry = law_registry.active()
        self.reactions = kernel.reactions(self.structure)
        self.factor, excess = kernel.laws(self.structure)
        self.terms = (registry.lookup(IDEAL_MIXING), *excess)
        self.term_layouts = ((), *self.layout.terms)
        lay = self.layout
        nu = np.zeros((self.R, self.P))
        for r in range(self.R):
            for k in range(kernel.ENTRIES):
                if lay.entry_alpha[r, k] + lay.entry_beta[r, k] > 0:
                    nu[r, lay.entry_place[r, k]] += lay.entry_beta[r, k] - lay.entry_alpha[r, k]
        held = np.asarray(lay.place_held, dtype=bool)
        self.nu_finite = np.where(held[None, :], 0.0, nu)
        self.nu_held = np.where(held[None, :], nu, 0.0)
        self.held = held
        self.held_mu = model.place_arrays(world, self.P)[5]
        self.membrane = np.asarray(self.tables.membrane, dtype=bool)
        self.finite = np.asarray(self.tables.finite, dtype=bool)
        # FR-47's E2 (D323): its places, out of E1's envelope, and per step its E2 reactant and
        # product ([R, P] one-hot rows); static, so a world without E2 places is as it was.
        e2 = np.zeros(self.P, dtype=bool)
        e2[: len(world.places)] = e2_places(
            world, spec.experiment, getattr(spec.execution, "min_count", None)
        )
        self.e2 = e2
        self.e2_in, self.e2_out = np.zeros((self.R, self.P)), np.zeros((self.R, self.P))
        index = {p.name: i for i, p in enumerate(world.places)}
        for r, step in enumerate(world.steps):
            for side, rows in ((step.reactants, self.e2_in), (step.products, self.e2_out)):
                for name, _ in side:
                    if e2[index[name]]:
                        rows[r, index[name]] = 1.0
        self.e2_step = (self.e2_in.sum(axis=1) + self.e2_out.sum(axis=1)) > 0
        mask = np.zeros(self.P, dtype=bool)
        mask[: len(world.places)] = enveloped(world, exempt=e2[: len(world.places)])
        self.enveloped = mask
        # Moieties: C = sum_finite m n - sum_held m supplied is conserved (§2.4).
        names = sorted({m for s in world.species for m in s.moiety_counts()})
        matrix = np.zeros((len(names), self.P))
        for i, place in enumerate(world.places):
            for name, count in world.species_by_id(place.species).moiety_counts().items():
                matrix[names.index(name), i] = count
        self.moiety_names, self.moieties = tuple(names), matrix
        # S2: a vesicle's places, its footprint, its lumen and its closure cost.
        vesicle = np.zeros(self.P, dtype=bool)
        pool_of = np.full(self.P, -1, dtype=np.int64)
        pools = {p.species: i for i, p in enumerate(world.places) if p.phase == world_rules.POOL}
        for i, place in enumerate(world.places):
            if place.phase in (world_rules.MEMBRANE, world_rules.LUMEN) and not place.held:
                vesicle[i] = True
                pool_of[i] = pools.get(place.species, -1)
        self.vesicle, self.pool_of = vesicle, pool_of
        self.bilayer = world.geometry is not None and world.geometry[0] == BILAYER_GEOMETRY
        self.shell = world.geometry is not None and world.geometry[0] == PRESCRIBED_SHELL
        self.osmotic = self.bilayer and world.conventions.lumen_volume == "osmotic"
        self.closure = geometry.closure_kT(world) if self.bilayer else 0.0
        if self.bilayer:
            g = lay.geometry
            self.quanta = np.asarray(g[0], dtype=np.float64)
            self.floor = float(g[6])
            self.lumen_mask = np.asarray(g[7], dtype=np.float64)
            self.lumen_c = np.asarray(g[8], dtype=np.float64)
            self.sigma_max, self.kT, self.q = float(g[9]), float(g[10]), float(g[11])
        # S3: the pore law's constants; a hold's tension, or the osmotic lumen's (σ from F).
        self.pores = world.hazard is not None and world.hazard[0] == PORE_NUCLEATION
        self.held_tension = bool(spec.experiment.tension_holds)
        if self.pores:
            self.pore_parameters = pore_nucleation.parameters(world)
            self.temperature = world.units.temperature_K

    # -- the terms and the forces
    def free_energy(self, n, xp=jnp, terms=None):
        """F_cont(n) (k_BT): the declared terms' limits (no closure cost); `terms` selects a
        subset by index."""
        chosen = range(len(self.terms)) if terms is None else terms
        total = 0.0
        for i in chosen:
            total = total + self.terms[i].limit(n, self.tables, self.term_layouts[i], xp)
        return total

    def potentials(self, n):
        """μ = ∇F_cont by reverse differentiation (traceable)."""
        return jax.grad(lambda m: self.free_energy(m))(n)

    def excess_potentials(self, n):
        if len(self.terms) == 1:
            return jnp.zeros_like(n)
        return jax.grad(lambda m: self.free_energy(m, terms=range(1, len(self.terms))))(n)

    def view(self, n, forward):
        """The laws' View at real counts n with the common state m = n (consumed 0), and, with a
        bilayer, each geometric law's extent at the real footprint W(n) = W(m)."""
        totals = jnp.stack([
            jnp.sum(jnp.where(self.finite & (np.asarray(self.layout.place_phase) == p), n, 0.0))
            for p in range(3)
        ])  # fmt: skip
        v = kernel.view(n, totals, self.layout, self.offset, forward, jnp)
        v = v._replace(consumed=jnp.zeros_like(v.consumed))
        if self.bilayer:
            footprint = jnp.sum(n * self.quanta)
            v = v._replace(log_encounter=kernel.encounter_extent(footprint, self.layout, v, jnp))
        elif self.shell:  # FR-47: the shell's constant extent, by the geometry kind, as exact's
            v = v._replace(log_encounter=kernel.shell_extent(self.layout, jnp))
        return v

    def log_direction(self, n, forward):
        """ln (a / k_f) of each step's direction at n, from each law's limit and the factor's."""
        lay = self.layout
        v = self.view(n, forward)
        log_a = jnp.full(self.R, -jnp.inf)
        for k, law in enumerate(self.reactions):
            log_k = law.limit(v, lay.locus_membrane, lay.log_extent, self.offset, jnp)
            log_a = jnp.where(np.asarray(lay.step_law) == k, log_k, log_a)
        if self.factor is not None:
            state = self.factor.state(n, lay.factor, jnp)
            log_a = log_a + self.factor.limit(state, lay.factor, v, jnp)
        return jnp.where(np.asarray(lay.step_active), log_a, -jnp.inf)

    def flux(self, n):
        """(J [R], ΔF [R]) at n: the factored form (i); at E2's steps the difference form."""
        lay = self.layout
        mu = self.potentials(n)
        d_f = jnp.asarray(self.nu_finite) @ mu - np.asarray(lay.step_work)
        log_a = self.log_direction(n, True)
        active = np.asarray(lay.step_active)
        safe = jnp.where(active, log_a, 0.0)
        rate = np.asarray(lay.kf) * jnp.exp(safe)
        j = jnp.where(active, rate * -jnp.expm1(d_f), 0.0)
        if self.e2_step.any():  # FR-47's E2, static: a world without E2 places is as it was
            forward, reverse = self.difference(n)
            j = jnp.where(self.e2_step, forward - reverse, j)
        return j, jnp.where(active, d_f, 0.0)

    def difference(self, n):
        """(a⁺ [R], a⁻ [R]) at n in E2's linear form (FR-47): each direction's law at the state
        with every E2 place at one molecule, times the count of the direction's E2 place where it
        has one. The directions are the factored form's own (log_direction, log_reverse), so the
        identity check and a planted law act on the rates the flux uses; no logarithm or
        feasibility test sees an E2 count, so the form holds at any real count and its derivative
        at an empty place is the first-order law's."""
        lay = self.layout
        active = np.asarray(lay.step_active)
        kf = np.asarray(lay.kf)
        unit = jnp.where(self.e2, 1.0, n)

        def rate(log_a, rows):
            count = jnp.asarray(rows) @ n + (1.0 - rows.sum(axis=1))
            return jnp.where(active, kf * jnp.exp(jnp.where(active, log_a, 0.0)) * count, 0.0)

        return (rate(self.log_direction(unit, True), self.e2_in),
                rate(self.log_reverse(unit), self.e2_out))  # fmt: skip

    def e2_margin(self, n, j, margin):
        """[R] the second law's margin at n (a sign, §2) with E2's steps read as the difference
        form needs: a step whose E2 place is at or below 0 holds (its potential is ∓inf there and
        the linear form's rates are not negative), and |J| within the difference's rounding,
        8 eps (a⁺ + a⁻), counts as equilibrium, 0."""
        forward, reverse = self.difference(n)
        empty = (jnp.asarray(self.e2_in + self.e2_out) @ (n <= 0).astype(n.dtype)) > 0
        level = jnp.abs(j) <= 8.0 * EPS * (jnp.abs(forward) + jnp.abs(reverse))
        margin = jnp.where(self.e2_step & level, 0.0, margin)
        return jnp.where(self.e2_step & empty, 1.0, margin)

    def log_reverse(self, n):
        """ln (a⁻ / k_f) of each step from the products' law (ii): the law's limit on the reverse
        view, k⁻ = k_f exp(Σ ν μ°), the same factor, and exp(ν·∇F_ex) for the excess terms."""
        log_a = self.log_direction(n, False) + np.asarray(self.layout.log_ratio)
        return log_a + jnp.asarray(self.nu_finite) @ self.excess_potentials(n)

    # -- a vesicle's derived quantities, on the host (numpy), of whole-world states [..., P]
    def footprint(self, n):
        return np.asarray(n) @ self.quanta

    def tension(self, n):
        n = np.asarray(n, dtype=np.float64)
        return lumen.tension(n @ self.lumen_mask, n @ self.quanta, self.kT, self.q, self.lumen_c,
                             np)  # fmt: skip

    def kink(self, n):
        """ln V_osm − ln V_sph: positive where tense, negative where floppy."""
        n = np.asarray(n, dtype=np.float64)
        log_osm, log_sph = lumen.log_branches(n @ self.lumen_mask, n @ self.quanta, self.lumen_c,
                                              np)  # fmt: skip
        return log_osm - log_sph

    def volume_L(self, n):
        n = np.asarray(n, dtype=np.float64)
        return float(np.exp(lumen.log_volume(n @ self.lumen_mask, n @ self.quanta, self.lumen_c,
                                             np)))  # fmt: skip

    # -- the pore law (S3), at whole-world states of one vesicle [..., P]
    def pore_tension(self, n, sigma_hold, xp=jnp):
        """σ (N/m): the hold's (`sigma_hold`, 0 outside a hold) or, with no hold, the lumen's."""
        if self.held_tension:
            return xp.broadcast_to(sigma_hold, n.shape[:-1])
        return lumen.tension(n @ self.lumen_mask, n @ self.quanta, self.kT, self.q, self.lumen_c,
                             xp)  # fmt: skip

    def pore_rate(self, n, sigma_hold, xp=jnp):
        """k_v (1/s) of one vesicle's whole-world state: the law at A = q·W(n)/2 and its σ."""
        log_nu, gamma, e_a, _ = self.pore_parameters
        area = self.q * (n @ self.quanta) / 2.0
        return pore_nucleation.rate_at(area, self.pore_tension(n, sigma_hold, xp),
                                       self.temperature, log_nu, gamma, e_a, xp)  # fmt: skip


# ------------------------------------------------------------------ the limit's check


CHECK_SEED = 20261123
CHECK_STATES = 16
IDENTITY_ATOL = 1e-9  # ln units, as the exact kernel's check (balance.ATOL)


def limit_check(problem, rng, states=CHECK_STATES, low=1e2, high=1e4, draw=None):
    """The limit's check (§1.4) on one problem: (1) the factored form equals the products' law,
    (2) μ equals central differences of F_cont, (3) −J_r ΔF_r ≥ 0. Returns the worst of each;
    raises ConfigError if one fails. Eager evaluation (no compile). `draw(rng)` gives a state [P]
    (default: every finite place uniform in [low, high])."""
    worst = {"identity": 0.0, "potential": 0.0, "dissipation_margin": math.inf, "states": 0}
    places = len(problem.world.places)
    finite = np.flatnonzero(problem.finite[:places])
    active = np.asarray(problem.layout.step_active)
    drawn = []
    for _ in range(states):
        if draw is None:
            n = np.zeros(problem.P)
            n[finite] = rng.uniform(low, high, finite.size)
        else:
            n = draw(rng)
        drawn.append(n)
    out = _check_program(problem, tuple(finite.tolist()))(jnp.asarray(np.stack(drawn)))
    j, d_f, forward, reverse, mu, numeric = (np.asarray(a) for a in out)
    both = active[None, :] & np.isfinite(forward) & np.isfinite(reverse)
    gap = np.abs(reverse[both] - forward[both] - d_f[both])  # masked first: no inf - inf
    worst["identity"] = float(gap.max(initial=0.0))
    mu = mu[:, finite]
    worst["potential"] = float(np.max(np.abs(mu - numeric) / (1 + np.abs(mu)), initial=0.0))
    product = -(j * d_f)
    worst["dissipation_margin"] = float(np.min(product / (np.abs(product) + 1e-300), initial=1.0))
    worst["states"] = len(drawn)
    failed = []
    if problem.e2_step.any():  # FR-47's E2: its linear form is each direction's law, at n > 0
        a_plus, a_minus = (
            np.asarray(a) for a in _e2_program(problem)(jnp.asarray(np.stack(drawn)))
        )
        kf = np.asarray(problem.layout.kf)
        gaps = [0.0]
        for rates, logs in ((a_plus, forward), (a_minus, reverse)):
            on = problem.e2_step[None, :] & (rates > 0) & np.isfinite(logs)
            with np.errstate(divide="ignore"):
                gap = np.abs(np.log(np.where(on, rates, 1.0)) - np.log(np.where(on, kf, 1.0))
                             - np.where(on, logs, 0.0))  # fmt: skip
            gaps.append(float(gap[on].max(initial=0.0)))
        worst["e2_linearity"] = max(gaps)
        if worst["e2_linearity"] > IDENTITY_ATOL:
            failed.append(f"E2's first-order form is not its law's direction (largest gap "
                          f"{worst['e2_linearity']:.3g} in ln units)")  # fmt: skip
    if worst["identity"] > IDENTITY_ATOL:
        failed.append(f"the factored flux is not the products' law (largest gap "
                      f"{worst['identity']:.3g} in ln units)")  # fmt: skip
    if worst["potential"] > 1e-6:
        failed.append(
            f"mu is not F_cont's gradient (largest relative gap {worst['potential']:.3g})"
        )
    if worst["dissipation_margin"] < -64 * EPS:
        failed.append("a step's -J dF is negative")
    if failed:
        raise ConfigError(f"{RATE_EQUATIONS}: the limit's check fails: {'; '.join(failed)}")
    return worst


def _check_program(problem, finite):
    """The check's arithmetic at a batch of states [S, P], compiled once per call (the planted
    tests change a problem's laws in place, so nothing is cached): the flux and ΔF, both forms'
    logarithms, μ by differentiation, and μ by central differences of F_cont's value at
    δ = 10⁻⁴ n at each finite place."""
    places = np.asarray(finite, dtype=np.int64)

    def one(n):
        j, d_f = problem.flux(n)
        forward = problem.log_direction(n, True)
        reverse = problem.log_reverse(n)
        mu = problem.potentials(n)
        delta = 1e-4 * n[places]
        shift = jnp.zeros((places.size, n.shape[0])).at[jnp.arange(places.size), places].set(delta)
        f_up = jax.vmap(problem.free_energy)(n[None, :] + shift)
        f_down = jax.vmap(problem.free_energy)(n[None, :] - shift)
        return j, d_f, forward, reverse, mu, (f_up - f_down) / (2.0 * delta)

    return jax.jit(jax.vmap(one))


def _e2_program(problem):
    """E2's two directions at a batch of states [S, P] (FR-47), compiled once per call, as the
    check's own program is."""
    return jax.jit(jax.vmap(problem.difference))


def shell_parity(spec, rng):
    """FR-47: a shell world's own parity (item 4) with the exact kernel's forward rates, on its
    exact twin (the same world and experiment as exact events): the shell's extent is dispatched
    by the geometry kind in both, and parity reads it, where the identity check does not (the
    extent cancels between the two directions)."""
    from cells.models.assembly_lineages_v2 import spec as spec_rules

    raw = spec_rules.to_dict(spec)
    x = raw["execution"]
    raw["execution"] = {"backend": x["backend"], "precision": x["precision"], "mode": x["mode"],
                        "stream": x["stream"], "molecule_capacity": 1 << 20}  # fmt: skip
    return parity(raw, rng)


def vesicle_draw(problem, low=1e3, high=1e5):
    """A state draw for a vesicle world's check: every finite place uniform in [low, high], then
    the lumen's solutes scaled so that ln V_osm − ln V_sph is uniform in [−1, 1], so the draws lie
    on both sides of the lumen's kink (the osmotic term's μ is checked on both branches)."""
    places = len(problem.world.places)
    finite = np.flatnonzero(problem.finite[:places])
    lumen_places = np.flatnonzero(problem.lumen_mask[:places] > 0) if problem.osmotic else []

    def draw(rng):
        n = np.zeros(problem.P)
        n[finite] = rng.uniform(low, high, finite.size)
        if len(lumen_places):
            n[lumen_places] *= math.exp(rng.uniform(-1.0, 1.0) - problem.kink(n))
        return n

    return draw


def parity(problem_spec, rng, scales=(1e2, 1e3, 1e4)):
    """Item 4 (§1.4): each law's limit against the exact kernel's forward rates at integer states
    scaled by λ: the largest gap in ln a⁺ falls as 1/λ (fitted order at least 0.9), or is
    rounding at every λ (identical forms). `problem_spec` is an exact spec's definition dict, parsed
    once at the largest state's molecule capacity (the forward rates take their logarithms
    directly, so the capacity selects no value)."""
    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages_v2 import balance

    raw = dict(problem_spec)
    raw["execution"] = dict(problem_spec["execution"])
    places = parse_spec(raw).model.world.places
    base = rng.integers(3, 13, len(places))
    states = [(base * scale).astype(np.int64) for scale in scales]
    membrane = max(sum(int(c) for c, p in zip(counts, places, strict=True) if p.phase == "membrane")
                   for counts in states)  # fmt: skip
    raw["execution"]["molecule_capacity"] = int(max(max(c.max() for c in states), membrane)) + 8
    problem = Problem(parse_spec(raw))
    kf = np.asarray(problem.layout.kf)
    active = np.asarray(problem.layout.step_active) & (kf > 0)
    fulls = np.zeros((len(states), problem.P), dtype=np.int64)
    fulls[:, : len(places)] = np.stack(states)
    fulls[:, problem.held] = 0
    limits = jax.jit(jax.vmap(lambda n: problem.log_direction(n, True)))(
        jnp.asarray(fulls.astype(np.float64))
    )
    gaps = []
    for full, log_a in zip(fulls, np.asarray(limits), strict=True):
        exact = balance.host_log_rates(full, problem.layout, problem.structure)[: problem.R]
        limit = np.log(np.where(active, kf, 1.0)) + log_a
        both = active & np.isfinite(exact) & np.isfinite(limit)
        gaps.append(float(np.max(np.abs(exact[both] - limit[both]), initial=0.0)))
    if max(gaps) <= 1e-12:
        return {"gaps": gaps, "order": None, "identical": True}
    order = math.log(gaps[0] / gaps[-1]) / math.log(scales[-1] / scales[0])
    if order < 0.9:
        raise ConfigError(
            f"{RATE_EQUATIONS}: a law's limit does not tend to its exact form (gaps {gaps}, "
            f"order {order:.3g} < 0.9)"
        )
    return {"gaps": gaps, "order": order, "identical": False}


def generic_probes():
    """The exact check's probe worlds (balance.PROBES) that differ in what a limit reads: both
    measures, with regular mixing and catalysis and without. The `last_molecule` token governs only
    an empty membrane, outside every envelope, so one value per measure covers it."""
    from cells.models.assembly_lineages_v2 import balance

    firsts, out = set(), []
    for measure, last, regular, catalysis in balance.PROBES:
        if regular != catalysis:
            continue
        if (measure, regular) in firsts:
            continue
        firsts.add((measure, regular))
        out.append((measure, last, regular, catalysis))
    return tuple(out)


OSMOTIC_PROBES = ("multinomial", "multinomial_less_one")  # with regular mixing and catalysis


@functools.cache
def _generic_verdict():
    """The limit's four items (§1.4) on generic probe worlds, before every run (cached per
    process): items 1-3 at real states and item 4, parity with the exact kernel at λ-scaled
    integer states, on generic_probes() (every order up to three, held species, both measures,
    regular mixing and catalysis) and on balance's osmotic probe in both measures (the geometric
    laws' extents, the lumen's mass action and the osmotic term, its check's states on both sides
    of the kink). Refuses (ConfigError) when an item fails."""
    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages_v2 import balance

    rng = np.random.default_rng(CHECK_SEED)
    out = {"identity": 0.0, "potential": 0.0, "dissipation_margin": math.inf, "worlds": 0,
           "parity_orders": [], "parity_identical": 0}  # fmt: skip
    worlds = [(balance.probe_world(rng, measure, last, regular=regular, catalysis=catalysis),
               False) for measure, last, regular, catalysis in generic_probes()]  # fmt: skip
    worlds += [(balance.osmotic_probe_world(rng, measure, "insertion_area", regular=True,
                                            catalysis=True), True)
               for measure in OSMOTIC_PROBES]  # fmt: skip
    for raw, vesicle in worlds:
        problem = Problem(parse_spec(raw))
        draw = vesicle_draw(problem) if vesicle else None
        worst = limit_check(problem, rng, states=4, draw=draw)
        out["identity"] = max(out["identity"], worst["identity"])
        out["potential"] = max(out["potential"], worst["potential"])
        out["dissipation_margin"] = min(out["dissipation_margin"], worst["dissipation_margin"])
        tends = parity(raw, rng)
        if tends["identical"]:
            out["parity_identical"] += 1
        else:
            out["parity_orders"].append(tends["order"])
        out["worlds"] += 1
    return out


def verdict():
    return dict(_generic_verdict())


# ------------------------------------------------------------------ the continuous state


class Shape:
    """The continuous state's layout over a Problem (the note's §1.6): y = [pool (P), slots (K × V),
    supplied (P), Q, W]. A single lineage has no slot block, and its `pool` is the whole world (S1's
    layout); a population's pool holds the pool's places and each slot its vesicle's V places."""

    def __init__(self, problem):
        p, world = problem, problem.world
        self.problem = p
        self.population = world.population is not None
        self.K = world.population["slots"] if self.population else 1
        self.places = np.flatnonzero(p.vesicle) if self.population else np.zeros(0, dtype=int)
        self.V = self.places.size
        P = p.P
        self.blocks = self.K * self.V if self.population else 0
        self.size = 2 * P + self.blocks + 2
        self.supply_at, self.heat_at = P + self.blocks, 2 * P + self.blocks
        pool_place = np.zeros(P, dtype=bool)
        pool_place[: len(world.places)] = [pl.phase == world_rules.POOL for pl in world.places]
        self.pool_place = pool_place if self.population else np.ones(P, dtype=bool)
        lay = p.layout
        vesicle_step = np.zeros(p.R, dtype=bool)
        for r, step in enumerate(world.steps):
            names = [name for name, _ in (*step.reactants, *step.products)]
            vesicle_step[r] = any(world.places[world.place_index(n)].phase != world_rules.POOL
                                  for n in names)  # fmt: skip
        self.vesicle_step = vesicle_step & np.asarray(lay.step_active)
        self.pool_step = ~vesicle_step & np.asarray(lay.step_active)
        self.nu_pool = np.where(self.pool_place[None, :], p.nu_finite, 0.0)
        self.nu_slot = p.nu_finite[:, self.places]
        founders = world.population["founders"] if self.population else ()
        self.safe = np.zeros(P)  # a dead slot's stand-in state (constant: no derivative)
        if founders:
            self.safe[: len(world.places)] = np.asarray(world.founder) + np.asarray(founders[0])

    def split(self, y):
        """(pool [P], slots [K, V], supplied [P], Q, W)."""
        P, b = self.problem.P, self.blocks
        slots = y[P : P + b].reshape((self.K, self.V)) if self.population else None
        return y[:P], slots, y[P + b : 2 * P + b], y[2 * P + b], y[2 * P + b + 1]

    def full(self, pool, slots, xp=jnp):
        """[K, P]: each slot's whole-world state, its vesicle with the pool."""
        out = xp.zeros((self.K, self.problem.P), dtype=pool.dtype) + pool[None, :]
        if xp is jnp:
            return out.at[:, self.places].add(slots)
        out[:, self.places] += slots
        return out

    def assemblies(self, y, alive):
        """[(slot, whole-world state [P])] of the living assemblies, on the host."""
        y = np.asarray(y)
        pool, slots = self.split(y)[:2]
        if not self.population:
            return [(0, pool)] if alive[0] else []
        full = self.full(pool, slots, np)
        return [(int(k), full[k]) for k in np.flatnonzero(alive)]

    def rhs(self, y, alive):
        p = self.problem
        pool, slots, _, _, _ = self.split(y)
        work = np.asarray(p.layout.step_work)
        if not self.population:
            j, d_f = p.flux(pool)
            dn = jnp.asarray(p.nu_finite).T @ j
            supplied = -(jnp.asarray(p.nu_held).T @ j)
            heat = -jnp.sum(j * d_f)
            return jnp.concatenate((dn, supplied, jnp.stack((heat, jnp.sum(j * work)))))
        full = self.full(pool, slots)
        safe = jnp.where(alive[:, None], full, jnp.asarray(self.safe)[None, :])
        j, d_f = jax.vmap(p.flux)(safe)
        on = alive[:, None] & self.vesicle_step[None, :]
        j, d_f = jnp.where(on, j, 0.0), jnp.where(on, d_f, 0.0)
        pool_only = jnp.where(jnp.asarray(self.pool_place), pool, 0.0)
        j0, d0 = p.flux(pool_only)
        j0, d0 = jnp.where(self.pool_step, j0, 0.0), jnp.where(self.pool_step, d0, 0.0)
        total = j0 + jnp.sum(j, axis=0)
        d_pool = jnp.asarray(self.nu_pool).T @ total
        d_slots = (j @ jnp.asarray(self.nu_slot)).reshape(-1)
        supplied = -(jnp.asarray(p.nu_held).T @ total)
        heat = -(jnp.sum(j0 * d0) + jnp.sum(j * d_f))
        books = jnp.stack((heat, jnp.sum(total * work)))
        return jnp.concatenate((d_pool, d_slots, supplied, books))

    def initial(self):
        """(y, alive): the founders."""
        p, world = self.problem, self.problem.world
        n = np.zeros(p.P)
        n[: len(world.places)] = np.asarray(world.founder, dtype=np.float64)
        n[p.held] = 0.0
        if not self.population:
            return np.concatenate((n, np.zeros(p.P), np.zeros(2))), np.ones(1, dtype=bool)
        founders = world.population["founders"]
        slots = np.zeros((self.K, self.V))
        for i, vesicle in enumerate(founders):
            full = np.zeros(p.P)
            full[: len(world.places)] = vesicle
            slots[i] = full[self.places]
        alive = np.arange(self.K) < len(founders)
        return np.concatenate((n, slots.reshape(-1), np.zeros(p.P), np.zeros(2))), alive

    def pore_rates(self, y, alive, sigma_hold):
        """[K] each slot's k_v (S3; 0 in an empty slot), traceable: what H's stages carry."""
        p = self.problem
        pool, slots = self.split(y)[:2]
        if not self.population:
            return jnp.where(alive, p.pore_rate(pool[None, :], sigma_hold), 0.0)
        full = jnp.where(alive[:, None], self.full(pool, slots), jnp.asarray(self.safe)[None, :])
        return jnp.where(alive, p.pore_rate(full, sigma_hold), 0.0)

    def weight(self, heat=True):
        """The step control's weights: the finite counts, Q and W; not the supplies. `heat`
        False leaves Q out (FR-47: a step from an E2 zero books its heat by closure)."""
        p = self.problem
        pool = (p.finite & self.pool_place).astype(np.float64)
        return np.concatenate((pool, np.ones(self.blocks), np.zeros(p.P),
                               np.asarray([1.0 if heat else 0.0, 1.0])))  # fmt: skip

    def e2_counts(self, y, alive):
        """FR-47: the E2 places' counts of the pool and of each living slot, on the host."""
        p = self.problem
        pool, slots = self.split(np.asarray(y, dtype=np.float64))[:2]
        if not self.population:
            return pool[p.e2] if alive[0] else pool[:0]
        living = slots[np.asarray(alive, dtype=bool)][:, p.e2[self.places]]
        return np.concatenate((pool[p.e2 & self.pool_place], living.ravel()))

    def free_energy(self, y, alive, f):
        """F_cont of a world state, with the closure cost per living vesicle (host floats); `f` is
        the compiled Problem.free_energy."""
        p = self.problem
        if not self.population:
            pool = np.asarray(self.split(y)[0])
            return float(f(pool)) + (p.closure if p.bilayer and alive[0] else 0.0)
        pool, slots = (np.asarray(a) for a in self.split(y)[:2])
        pool_only = np.where(self.pool_place, pool, 0.0)
        base = float(f(pool_only))
        full = self.full(pool, slots, np)
        parts = [base] + [float(f(full[k])) - base + p.closure for k in np.flatnonzero(alive)]
        return math.fsum(parts)


# ------------------------------------------------------------------ crossings


@dataclass(frozen=True)
class Crossing:
    """A located root of a guard (§3.2): its name, the slot, θ in the step and the time."""

    guard: str
    slot: int
    theta: float
    time: float


GUARDS = {  # name: (direction, the handler's kind)
    "envelope": ("down", "stop"),
    "floor": ("down", "stop"),
    "lysis": ("up", "lysis"),
    "kink": ("either", "restart"),
    "pore": ("up", "rupture"),  # S3: H_v − E_v, the opening (then the rupture)
}
EVENTS = ("lysis", "rupture")  # the handlers that are events (FR-20's rule refuses their ties)
THETAS = np.linspace(0.0, 1.0, 10)  # a step's ends and 8 interior points
RESTEPS = 4


def _crosses(direction, a, b):
    if direction == "down":
        return a >= 0 > b
    if direction == "up":
        return a <= 0 < b
    return (a > 0) != (b > 0)


def _dense_clock(start, carried, thetas):
    """[T, K] the carried clock's dense output (rosenbrock_dense.dense_carried), on the host."""
    theta = np.asarray(thetas, dtype=np.float64)[:, None]
    end = start + carried["increment"]
    return (1.0 - theta) * start + theta * (end + (1.0 - theta) * (carried["k1"]
                                                                   + theta * carried["k2"]))


def _locate(guard_at, theta_low, theta_high, g_low, g_high, tolerance=1e-13):
    """The Illinois method on θ in [theta_low, theta_high], where g_low and g_high have opposite
    sides: the root of a guard on the dense output (§3.2). Returns the θ on g_high's side."""
    side = 0
    for _ in range(200):
        theta = (theta_low * g_high - theta_high * g_low) / (g_high - g_low)
        g = guard_at(theta)
        if (g > 0) == (g_low > 0) and g != 0:
            theta_low, g_low = theta, g
            if side == -1:
                g_high /= 2.0
            side = -1
        else:
            theta_high, g_high = theta, g
            if side == 1:
                g_low /= 2.0
            side = 1
        if theta_high - theta_low <= tolerance:
            break
    return theta_high


# ------------------------------------------------------------------ the run


@dataclass
class RateEquationsRun:
    spec: object
    status: str
    rows: dict
    statistics: dict
    ledger: dict
    moieties: dict
    dissipation: dict
    check: dict
    events: list = field(default_factory=list)
    timings: dict = field(default_factory=dict)

    def check_books(self):
        """Raise if the books or the moieties did not close (a fault, never repaired)."""
        if not self.ledger["closes"]:
            raise ConfigError(f"{RATE_EQUATIONS}: the ledger did not close: {self.ledger}")
        if not self.moieties["closes"]:
            raise ConfigError(f"{RATE_EQUATIONS}: a moiety did not close: {self.moieties}")


_PROGRAMS = {}


def _program(spec):
    """The compiled pieces of one world at one execution's capacities and tolerances, kept by
    them (as the exact kernel keeps a program per structure; the experiment and the stream are the
    run's, read on the host), with the world's own limit check."""
    from cells.models.assembly_lineages_v2 import spec as spec_rules

    x = spec.execution
    world = spec.model.world
    e2 = tuple(e2_places(world, spec.experiment, x.min_count))  # FR-47: the mask, in the key
    key = (spec_rules.world_id(world), x.place_capacity, x.step_capacity, x.rtol,
           x.atol_count, e2)  # fmt: skip
    if key not in _PROGRAMS:
        problem = Problem(spec)
        shape = Shape(problem)
        x = spec.execution
        weight = jnp.asarray(shape.weight())
        rtol, atol = x.rtol, x.atol_count

        def one_step(y, h, alive):
            def f(z):
                return shape.rhs(z, alive)

            return rd.step(f, jax.jacfwd(f), y, h)

        def dissipation(y, alive):
            pool, slots = shape.split(y)[:2]
            if not shape.population:
                j, d_f = problem.flux(pool)
                on = jnp.ones_like(j, dtype=bool)
            else:
                full = jnp.where(alive[:, None], shape.full(pool, slots),
                                 jnp.asarray(shape.safe)[None, :])  # fmt: skip
                j, d_f = jax.vmap(problem.flux)(full)
                on = alive[:, None] & shape.vesicle_step[None, :]
            product = jnp.where(on, -(j * d_f), 0.0)
            margin = product / (jnp.abs(product) + 1e-300)
            if problem.e2_step.any():  # FR-47: E2's steps, as the difference form needs
                if shape.population:
                    margin = jax.vmap(problem.e2_margin)(full, j, margin)
                else:
                    margin = problem.e2_margin(pool, j, margin)
            return jnp.min(jnp.where(on, margin, 1.0))

        draw = vesicle_draw(problem) if problem.bilayer else None
        own = limit_check(problem, np.random.default_rng(CHECK_SEED), draw=draw)
        if problem.shell:  # FR-47: the shell's extent against the exact kernel's, in shells only
            own = {**own, "parity": shell_parity(spec, np.random.default_rng(CHECK_SEED))}
        carry = None
        if problem.pores:

            def carry(y, h, stages, alive, sigma_hold):
                def rate(z):
                    return shape.pore_rates(z, alive, sigma_hold)

                return rd.quadrature(rate, jax.jacrev(rate), y, h, stages)

            carry = jax.jit(carry)
            own = {**own, "pore": _pore_check(spec, problem)}
        _PROGRAMS[key] = {
            "problem": problem,
            "shape": shape,
            "step": jax.jit(one_step),
            "norm": jax.jit(lambda err, y0, y1: rd.error_norm(err, y0, y1, rtol, atol, weight)),
            "dense": jax.jit(jax.vmap(rd.dense, in_axes=(None, None, 0))),
            "free_energy": jax.jit(problem.free_energy),
            "dissipation": jax.jit(dissipation),
            "carry": carry,
            "check": own,
        }
        if problem.e2.any():  # FR-47: a step from an E2 zero keeps its heat out of the control
            opened = jnp.asarray(shape.weight(heat=False))
            _PROGRAMS[key]["norm_open"] = jax.jit(
                lambda err, y0, y1: rd.error_norm(err, y0, y1, rtol, atol, opened)
            )
    return _PROGRAMS[key]


def _pore_check(spec, problem):
    """The pore law's traced rate against its host form (pore_nucleation.log_rate) at each
    founder's area and tension (the hold's; with σ from F the lumen's where tense, σ_max/2 and
    σ_max): equal to 1e-12 in ln k_v, or the world is refused."""
    world = spec.model.world
    log_nu, gamma, e_a, _ = problem.pore_parameters
    founders = [np.asarray(world.founder, dtype=np.float64)]
    if world.population is not None:
        founders = [founders[0] + np.asarray(v, dtype=np.float64)
                    for v in world.population["founders"]]  # fmt: skip
    sigmas = [h.sigma for h in spec.experiment.tension_holds]
    worst, points = 0.0, 0
    for counts in founders:
        n = np.zeros(problem.P)
        n[: len(world.places)] = counts
        tensions = sigmas or [float(problem.tension(n)), problem.sigma_max / 2, problem.sigma_max]
        for sigma in tensions:
            if not sigma > 0:
                continue
            area = problem.q * float(n @ problem.quanta) / 2.0
            host = pore_nucleation.log_rate(area, sigma, problem.temperature, log_nu, gamma, e_a)
            traced = float(np.log(pore_nucleation.rate_at(
                jnp.asarray(area), jnp.asarray(sigma), problem.temperature, log_nu, gamma, e_a,
                jnp)))  # fmt: skip
            worst, points = max(worst, abs(traced - host) / max(1.0, abs(host))), points + 1
    if worst > 1e-12:
        raise ConfigError(f"{RATE_EQUATIONS}: the pore law's traced rate is not its host form "
                          f"(largest relative gap {worst:.3g} in ln k_v)")  # fmt: skip
    return {"largest_relative_gap": worst, "points": points}


class _Run:
    """One run's host loop (§3): stops, crossings, the operators and the books."""

    def __init__(self, spec):
        self.spec, self.x, self.e = spec, spec.execution, spec.experiment
        prog = _program(spec)
        self.prog, self.p, self.shape = prog, prog["problem"], prog["shape"]
        self.world = spec.model.world
        x = self.x
        self.base_key = streams.base_key_data(x.seed, x.environment, x.lineage, x.branch)
        self.y, self.alive = self.shape.initial()
        self.y = jnp.asarray(self.y)
        self.t, self.status, self.stop_reason = 0.0, None, None
        self.accepted = self.rejected = self.restarts = self.located = 0
        self.dissipation = math.inf
        self.horizon = float(self.e.time_horizon_s)
        # The host's bookings (k_BT): event heat, reservoir work at events, shear and transfer
        # work by schedule, and the sinks.
        self.booked = {"heat": 0.0, "reservoir": 0.0, "shear": {}, "transfer": {}, "sink": 0.0}
        self.moiety_out = np.zeros(len(self.p.moiety_names))  # what left with the sinks, net
        self.events, self.rows = [], []
        self.keys = np.where(self.alive, np.arange(self.shape.K, dtype=np.int64) << 32, -1)
        self.next_key = 1  # a single lineage's next carrier key (kernel.initial's)
        self.count = {i: 0 for i in range(int(self.alive.sum()))}  # sub-lineages' last counts
        self.lineage = np.where(self.alive, np.arange(self.shape.K), -1)
        self.next_sub = int(self.alive.sum())
        self.generation = np.zeros(self.shape.K, dtype=np.int64)
        self.transfer_counter = {}
        self.h = None
        self.just = set()  # guards crossed at the current time (no immediate re-crossing)
        self.tied = []  # crossings at the located one's instant
        # S3: each slot's pore clock (H, its threshold E; inf in an empty slot), the holds' work by
        # index, the tension of the segment in progress, and the clock's largest error estimate.
        self.holds = tuple(self.e.tension_holds)
        self.booked["hold"] = {h.index: 0.0 for h in self.holds}
        self.H = np.zeros(self.shape.K)
        self.E = np.full(self.shape.K, np.inf)
        self.draws = []  # (key, counter, u, E, time drawn)
        self.sigma_hold = 0.0
        self.clock_error = 0.0
        self.clock_fraction = 0.0  # the largest |U^H| / (H_ERROR + H_RELATIVE |dH|), D309
        self.carried = None  # the accepted step's carried clock (a crossing's dense H)
        # FR-47's E2: whether the world has E2 places, its steps from a zero (heat by closure)
        # and its step results rejected below zero.
        self.e2 = bool(self.p.e2.any())
        self.zero_starts = self.below_rejected = 0
        if self.p.pores:
            for slot in np.flatnonzero(self.alive):
                self.draw_threshold(int(slot))

    def draw_threshold(self, slot):
        """A vesicle's pore threshold E = −ln u (domain 7, its key, counter 0) when the run first
        holds it (a founder at the start, a daughter at its birth), with H = 0 then (§3.5)."""
        key = int(self.keys[slot])
        u, energy = pore_clock.threshold(self.base_key, key, 0)
        self.H[slot], self.E[slot] = 0.0, energy
        self.draws.append((key, 0, u, energy, self.t))

    def drop_clock(self, slot):
        self.H[slot], self.E[slot] = 0.0, np.inf

    # -- rows and books
    def row(self, kind):
        extra = {"H": self.H.copy(), "hold": [self.booked["hold"][h.index] for h in self.holds]}
        self.rows.append((kind, self.t, np.asarray(self.y, dtype=np.float64).copy(),
                          self.alive.copy(), self.keys.copy(), self._booked_total(),
                          self.moiety_out.copy(), extra))  # fmt: skip

    def _booked_total(self):
        """(event heat, reservoir work at events, shear, transfer, sink, the holds' work)."""
        b = self.booked
        return (b["heat"], b["reservoir"], math.fsum(b["shear"].values()),
                math.fsum(b["transfer"].values()), b["sink"],
                math.fsum(b["hold"].values()))  # fmt: skip

    def world_f(self, y=None, alive=None):
        y = self.y if y is None else y
        alive = self.alive if alive is None else alive
        return self.shape.free_energy(np.asarray(y), alive, self.prog["free_energy"])

    def vesicle_f(self, pool, vesicle):
        """F_v: a vesicle's own F_cont with the pool, less the pool's alone, plus its closure cost
        (whole-world vectors; the pool's places of `vesicle` are ignored)."""
        f = self.prog["free_energy"]
        pool_only = np.where(self.p.vesicle, 0.0, pool)
        with_vesicle = pool_only + np.where(self.p.vesicle, vesicle, 0.0)
        return float(f(with_vesicle)) - float(f(pool_only)) + self.p.closure

    # -- guards
    def guards(self, states, clocks=None):
        """{name: [T, C] values} of every guard at whole-world states [T, ...] of y; `clocks` [T, K]
        holds the pore clocks H at the same points (S3)."""
        T = states.shape[0]
        shape, p = self.shape, self.p
        out = {}
        pools, slots = [], []
        for y in states:
            pool, s = shape.split(y)[:2]
            pools.append(pool)
            slots.append(s)
        pools = np.stack(pools)
        living = np.flatnonzero(self.alive)
        if shape.population:
            full = np.stack([shape.full(pool, s, np) for pool, s in zip(pools, slots,
                                                                         strict=True)])  # fmt: skip
            full = full[:, living]  # [T, L, P]
        else:
            full = pools[:, None, :] if self.alive[0] else np.zeros((T, 0, p.P))
        margin = full - self.x.min_count
        env = np.where(p.enveloped[None, None, :], margin, np.inf)
        if shape.population:
            pool_env = np.where((p.enveloped & shape.pool_place)[None, :],
                                pools - self.x.min_count, np.inf)  # fmt: skip
            env = np.where(shape.pool_place[None, None, :], np.inf, env)
            columns = [pool_env.min(axis=1)] + [env[:, i].min(axis=1) for i in range(len(living))]
            out["envelope"] = (np.stack(columns, axis=1), [-1, *living.tolist()])
        else:
            out["envelope"] = (env.min(axis=2) if full.shape[1] else np.full((T, 0), np.inf),
                               [0] if full.shape[1] else [])  # fmt: skip
        if p.bilayer and full.shape[1]:
            slots_of = living.tolist() if shape.population else [0]
            out["floor"] = (full @ p.quanta - p.floor, slots_of)
            if p.osmotic:
                out["lysis"] = (p.tension(full) - p.sigma_max, slots_of)
                out["kink"] = (p.kink(full), slots_of)
            if clocks is not None:
                out["pore"] = (clocks[:, slots_of] - self.E[slots_of][None, :], slots_of)
        return out

    def tolerance(self, name, slot=0):
        """A guard's tolerance at the re-stepped state (§3.2 step 4): ten times the step control's
        own tolerance on the guard's scale (counts for the envelope and the floor, σ_max for
        lysis, 1 for the kink's logarithm; for the pore clock its threshold E, with the clock's
        own bound H_ERROR as its absolute part)."""
        p, x = self.p, self.x
        if name == "pore":
            return 10.0 * (H_ERROR + x.rtol * max(1.0, float(self.E[slot])))
        scale = {"envelope": x.min_count, "floor": getattr(p, "floor", 1.0),
                 "lysis": getattr(p, "sigma_max", 1.0), "kink": 1.0}[name]  # fmt: skip
        absolute = x.atol_count if name in ("envelope", "floor") else 0.0
        return 10.0 * (absolute + x.rtol * scale)

    def carry(self, y, hh, result):
        """The pore clocks' step over the step from y (its stages), as host arrays, or None."""
        if self.prog["carry"] is None:
            return None
        c = self.prog["carry"](y, hh, result.stages, jnp.asarray(self.alive), self.sigma_hold)
        return {name: np.asarray(getattr(c, name), dtype=np.float64)
                for name in ("increment", "error", "k1", "k2")}  # fmt: skip

    def advance_clock(self, carried):
        """H += the accepted step's increment; its error estimate monitored per vesicle (§3.5,
        D309): a run where |U^H_v| passes H_ERROR + H_RELATIVE |dH_v|, dH_v the step's own
        increment of that vesicle's clock, is refused, never silently inaccurate."""
        if carried is None:
            return
        error = np.abs(np.where(self.alive, carried["error"], 0.0))
        increment = np.abs(np.where(self.alive, carried["increment"], 0.0))
        bound = H_ERROR + H_RELATIVE * increment
        self.clock_error = max(self.clock_error, float(np.max(error, initial=0.0)))
        self.clock_fraction = max(self.clock_fraction, float(np.max(error / bound, initial=0.0)))
        if np.any(error > bound):
            slot = int(np.argmax(error - bound))
            raise ConfigError(
                f"{RATE_EQUATIONS}: the pore clock's error estimate, {error[slot]:.3g}, passes "
                f"its bound {H_ERROR:g} + {H_RELATIVE:g} |dH| = {bound[slot]:.3g} (dH = "
                f"{increment[slot]:.3g}, slot {slot}; D309) at t = {self.t!r} s: the run is "
                "refused, never silently inaccurate (the note's §3.5); smaller tolerances (rtol "
                "and atol_count together) are the remedy"
            )
        self.H = np.where(self.alive, self.H + carried["increment"], self.H)

    def crossing(self, y, result, hh, landing, stop):
        """The earliest crossing within an accepted step, or None (§3.2 steps 1 and 2)."""
        states = np.array(self.prog["dense"](y, result, jnp.asarray(THETAS)))
        states[0], states[-1] = np.asarray(y), np.asarray(result.y)
        carried = self.carried
        clocks = None
        if carried is not None:
            clocks = _dense_clock(self.H, carried, THETAS)
            clocks[0], clocks[-1] = self.H, self.H + carried["increment"]
        values = self.guards(states, clocks)
        found = []
        for name, (g, slots) in values.items():
            direction = GUARDS[name][0]
            for c, slot in enumerate(slots):
                col = g[:, c]
                for i in range(len(THETAS) - 1):
                    a, b = col[i], col[i + 1]
                    if i == 0 and (name, slot) in self.just:
                        continue  # the crossing just handled at this time
                    if _crosses(direction, a, b):
                        found.append((name, c, slot, i))
                        break
        if not found:
            return None
        located = []
        for name, c, slot, i in found:

            def at(theta, name=name, c=c):
                state = np.asarray(self.prog["dense"](y, result, jnp.asarray([theta])))
                clock = None if carried is None else _dense_clock(self.H, carried, [theta])
                return float(self.guards(state, clock)[name][0][0, c])

            ga, gb = values[name][0][i, c], values[name][0][i + 1, c]
            theta = THETAS[i + 1] if gb == 0 else _locate(at, THETAS[i], THETAS[i + 1], ga, gb)
            located.append(Crossing(name, slot, float(theta), self.t + float(theta) * hh))
        located.sort(key=lambda c: (c.time, c.guard, c.slot))
        first = located[0]
        tied = [c for c in located if same_instant(c.time, first.time)]
        events = [c for c in tied if GUARDS[c.guard][1] in EVENTS]
        if len(events) > 1:
            raise ConfigError(
                f"{RATE_EQUATIONS}: two lyses at one instant (slots {events[0].slot} and "
                f"{events[1].slot}, t = {first.time!r} s): relations have no order between "
                "same-time events (FR-20's rule)"
            )
        if events and landing and same_instant(first.time, stop):
            raise ConfigError(
                f"{RATE_EQUATIONS}: a lysis of slot {events[0].slot} falls at the stop "
                f"t = {stop!r} s: relations have no order between same-time events"
            )
        self.tied = tied[1:]  # crossings at the same instant, handled with the first
        return first

    def restep(self, y, hh, crossing):
        """The step re-taken from its start to the root (§3.2 steps 3 and 4): (state, θ, the pore
        clocks' carried step) with the guard within its tolerance, or None (the run stops
        stalled)."""
        name, slot = crossing.guard, crossing.slot
        tolerance = self.tolerance(name, slot)
        theta, previous = crossing.theta, None
        for _ in range(RESTEPS + 1):
            again = self.prog["step"](y, theta * hh, jnp.asarray(self.alive))
            carried = self.carry(y, theta * hh, again)
            clocks = None if carried is None else (self.H + carried["increment"])[None, :]
            values = self.guards(np.asarray(again.y)[None, :], clocks)[name]
            g = float(values[0][0, values[1].index(slot)])
            if abs(g) <= tolerance and bool(again.finite):
                return again.y, theta, carried
            if previous is not None and g != previous[1]:
                theta, previous = theta - g * (theta - previous[0]) / (g - previous[1]), (theta, g)
            else:
                previous = (theta, g)
                theta = theta * (1.0 - 1e-6) if theta > 0 else 1e-9
            theta = min(max(theta, 0.0), 1.0)
        return None

    # -- the loop
    def integrate(self, stop):
        """Advance to `stop` (or to the run's end), locating every crossing on the way."""
        x, prog = self.x, self.prog
        while self.t < stop and self.status is None:
            opened = self.e2 and self.at_zero(self.y)  # FR-47: a step from an E2 zero
            if self.h is None:
                self.h = rd.initial_step(lambda z: self.shape.rhs(z, jnp.asarray(self.alive)),
                                         self.y, x.rtol, x.atol_count,
                                         self.shape.weight(heat=not opened),
                                         stop - self.t)  # fmt: skip
            landing = self.t + self.h >= stop
            hh = stop - self.t if landing else self.h
            alive = jnp.asarray(self.alive)
            result = prog["step"](self.y, hh, alive)
            err = float(prog["norm_open" if opened else "norm"](result.error, self.y, result.y))
            ok = bool(result.finite) and err <= 1.0
            if ok and self._below_half(result.y):
                ok, err = False, 4.0**rd.ORDER  # inside the envelope's half: retry at h/4
            below = ok and self.e2 and self.below_zero(result.y)
            if not ok or below:
                self.rejected += 1
                self.below_rejected += int(below)
                if below:  # FR-47's E2: an E2 place below −10 atol_count, retried at h/4
                    self.h = hh / 4.0
                else:
                    self.h = rd.next_step(hh, err if math.isfinite(err) else math.inf, True)
                if self.h <= 16 * EPS * max(abs(self.t), self.horizon):
                    self.status = "stalled"
                continue
            self.carried = self.carry(self.y, hh, result)
            crossing = self.crossing(self.y, result, hh, landing, stop)
            self.h = rd.next_step(hh, err, False)
            if crossing is not None:
                located = self.restep(self.y, hh, crossing)
                if located is None:
                    self.status = "stalled"
                    break
                y, theta, carried = located
                self.y = self.closed_heat(self.y, y) if opened else y
                self.advance_clock(carried)
                self.t = self.t + theta * hh
                self.accepted += 1
                self.located += 1
                self.handle(crossing)
                continue
            self.advance_clock(self.carried)
            self.t = stop if landing else self.t + hh
            self.y = self.closed_heat(self.y, result.y) if opened else result.y
            self.just = set()
            self.accepted += 1
            self.dissipation = min(self.dissipation,
                                   float(prog["dissipation"](self.y, alive)))  # fmt: skip
            if self.accepted >= x.step_limit:
                self.status = "step_limit"

    def _below_half(self, y):
        for name, (g, _) in self.guards(np.asarray(y)[None, :]).items():
            if name == "envelope" and g.size and g.min() < -0.5 * self.x.min_count:
                return True
        return False

    # -- FR-47's E2
    def at_zero(self, y):
        """Whether an E2 place of the pool or of a living slot is at or below 0 at y."""
        return bool(np.any(self.shape.e2_counts(y, self.alive) <= 0.0))

    def below_zero(self, y):
        """The rule below zero: whether a step result holds an E2 place below −10·atol_count."""
        counts = self.shape.e2_counts(y, self.alive)
        return bool(np.any(counts < -BELOW_ZERO * self.x.atol_count))

    def closed_heat(self, y0, y1):
        """y1 with the step's heat booked by the closure identity (E2, FR-47): the step starts with
        an E2 place at or below 0, where μ = ln n diverges, integrably, so the heat is not
        integrated across it. Q1 = Q0 + (W1 − W0) − (F_cont(y1) − F_cont(y0)), with the step's own
        counts and work (no sink acts within a step)."""
        y0 = np.asarray(y0, dtype=np.float64)
        y1 = np.asarray(y1, dtype=np.float64).copy()
        q, w = self.shape.heat_at, self.shape.heat_at + 1
        y1[q] = y0[q] + (y1[w] - y0[w]) - (self.world_f(y1) - self.world_f(y0))
        self.zero_starts += 1
        return jnp.asarray(y1)

    def handle(self, crossing):
        """A located crossing, with any others at the same instant (restarts and stops; two events
        there are refused): the lysis acts first, then a stop ends the run."""
        tied = [crossing, *self.tied]
        self.just = {(c.guard, c.slot) for c in tied}
        kinds = [GUARDS[c.guard][1] for c in tied]
        self.restarts += kinds.count("restart")
        for c in tied:
            if GUARDS[c.guard][1] == "lysis":
                self.lyse(c.slot, "threshold")
            elif GUARDS[c.guard][1] == "rupture":
                self.rupture(c.slot)
        stops = [c for c in tied if GUARDS[c.guard][1] == "stop"]
        if stops and self.status is None:
            self.row("outside_envelope")
            self.status, self.stop_reason = "outside_envelope", stops[0].guard

    # -- the operators
    def release(self, slot):
        """A vesicle's molecules to their pool places (a held place's reservoir takes them back,
        with its work) and its slot emptied; returns (returned {place: amount}, w_r)."""
        p, shape, world = self.p, self.shape, self.world
        y = np.asarray(self.y, dtype=np.float64).copy()
        pool, slots = shape.split(y)[:2]
        pool, supplied = pool.copy(), y[shape.supply_at : shape.supply_at + p.P].copy()
        if shape.population:
            vesicle = np.zeros(p.P)
            vesicle[shape.places] = slots[slot]
        else:
            vesicle = np.where(p.vesicle, pool, 0.0)
            pool = np.where(p.vesicle, 0.0, pool)
        returned, work = {}, 0.0
        for i in np.flatnonzero(p.vesicle):
            amount = float(vesicle[i])
            j = int(p.pool_of[i])
            if amount == 0.0:
                continue
            name = world.places[j].name
            returned[name] = returned.get(name, 0.0) + amount
            if p.held[j]:
                supplied[j] -= amount
                work -= amount * float(p.held_mu[j])
            else:
                pool[j] += amount
        y[: p.P] = pool
        if shape.population:
            block = y[p.P : p.P + shape.blocks].reshape((shape.K, shape.V))
            block[slot] = 0.0
            y[p.P : p.P + shape.blocks] = block.reshape(-1)
        y[shape.supply_at : shape.supply_at + p.P] = supplied
        self.y = jnp.asarray(y)
        return returned, work

    def lyse(self, slot, cause, *, at_birth=False, opening=None):
        """§3.3: the release, booked as one row, q = −(F_cont(after) − F_cont(before)) + w_r; after
        a pore's opening (`opening`, S3) the release is from the open state, F(open) = F(n) + ΔF,
        and the opening's own heat and work are booked with it, so ΔF cancels in the event's
        total."""
        before = self.world_f()
        sigma = None
        for s, n in self.shape.assemblies(self.y, self.alive):
            if s == slot:
                sigma = float(self.p.tension(n)) if self.p.osmotic else None
        returned, w = self.release(slot)
        self.alive = self.alive.copy()
        self.alive[slot] = False
        record = {"kind": "lysis", "time_s": self.t, "slot": int(slot), "key": int(self.keys[slot]),
                  "cause": cause, "at_birth": at_birth}  # fmt: skip
        if opening is None:
            q = -(self.world_f() - before) + w
            self.booked["heat"] += q
            record |= {"sigma_N_per_m": sigma, "sigma_max_N_per_m": getattr(self.p, "sigma_max",
                                                                             None)}  # fmt: skip
        else:
            q = -(self.world_f() - (before + opening["delta_F_kT"])) + w
            self.booked["heat"] += opening["opening_heat_kT"] + q
            if opening["hold"] is not None:
                self.booked["hold"][opening["hold"]] += opening["work_kT"]
            record |= opening
        self.booked["reservoir"] += w
        record |= {"returned": returned, "release_heat_kT": q, "release_reservoir_work_kT": w}
        self.events.append(record)
        self.keys[slot] = -1
        self.drop_clock(slot)
        self.row("lysis")
        if not self.shape.population:
            self.status = "lysed"

    def rupture(self, slot):
        """§3.5: the opening at H = E, then Phase A's outcome, the rupture through the release
        (cause `pore`): q_open = −ΔF_open + w, under a hold w = σ_β/σ paid by the hold
        (pore_clock.opening), with σ from F w = 0 (pore_clock.opening_from_f)."""
        p = self.p
        (n,) = [n for s, n in self.shape.assemblies(self.y, self.alive) if s == slot]
        area = p.q * float(n @ p.quanta) / 2.0
        hold = self.hold_in_force()
        if p.held_tension:
            sigma = hold.sigma
            work, heat, delta_f = pore_clock.opening(self.world, area, sigma)
        else:
            sigma = float(p.tension(n))
            work, heat, delta_f = pore_clock.opening_from_f(self.world, area, sigma)
        rate = float(p.pore_rate(jnp.asarray(n), self.sigma_hold))
        self.lyse(slot, "pore", opening={
            "hold": None if hold is None else hold.index, "sigma_N_per_m": sigma, "area_m2": area,
            "rate_per_s": rate, "threshold_E": float(self.E[slot]), "counter": 0,
            "clock_H": float(self.H[slot]), "work_kT": work, "opening_heat_kT": heat,
            "delta_F_kT": delta_f})  # fmt: skip

    def hold_in_force(self):
        """The hold whose interval [start_s, end_s) holds the segment in progress, or None."""
        for hold in self.holds:
            if hold.start <= self.t < hold.end:
                return hold
        return None

    def stop_events(self, events):
        """A stop's scheduled events, in schedule-index order (§3.1), on the assemblies alive at
        each one's start."""
        by_index = {s.index: s for s in self.e.schedules}
        for event in events:
            schedule = by_index[event[1]]
            if schedule.kind == "transfer":
                self.transfer(schedule)
            elif schedule.kind == "replacement":  # FR-47
                self.replacement(schedule)
            elif schedule.kind == "withdrawal":  # FR-47
                self.withdrawal(schedule)
            else:
                self.shear(event)
            if self.status is not None:
                return

    def shear(self, event):
        """§3.4: each living assembly's attempt at a shear event, in slot order."""
        from cells.models.assembly_lineages import keys as keys_rules
        from cells.models.assembly_lineages_v2 import division

        time, index, k, stress = event
        p, shape, world = self.p, self.shape, self.world
        critical = world.division["critical_stress_Pa"]
        for slot, n in self.shape.assemblies(self.y, self.alive):
            parent = int(self.keys[slot])
            record = {"kind": "fission", "time_s": time, "schedule": index, "k": k,
                      "slot": slot, "parent": parent,
                      "parent_counts": n[: len(world.places)].tolist()}  # fmt: skip
            if critical is not None and not stress >= critical[0]:
                self.events.append(record | {"outcome": "refused_stress"})
                continue
            footprint = float(p.footprint(n))
            if not division.admitted_volume(p.volume_L(n), footprint, p.q, k):
                self.events.append(record | {"outcome": "refused_volume"})
                continue
            free = [int(s) for s in np.flatnonzero(~self.alive)] if shape.population else []
            if shape.population and len(free) < k - 1:
                self.events.append(record | {"outcome": "slots_full"})
                self.row("slots_full")
                self.status = "slots_full"
                return
            vesicle = np.where(p.vesicle, n, 0.0)
            share = vesicle / k
            daughters = [share.copy() for _ in range(k - 1)]
            daughters.append(vesicle - (k - 1) * share)  # the last takes the complement
            if any(float(d @ p.quanta) < p.floor for d in daughters):
                self.events.append(record | {"outcome": "refused_floor"})
                continue
            pool = np.where(p.vesicle, 0.0, n)
            if shape.population:
                followed = -1
                next_key = keys_rules.key(int(self.lineage[slot]),
                                          self.count[int(self.lineage[slot])] + 1)  # fmt: skip
            else:
                followed = 0
                if world.division["continuation"] == "uniform":
                    key = streams.stream_key_data(self.base_key, parent, "continuation")
                    followed = int(np.floor(float(streams.uniforms(key, 0, 1)[0]) * k))
                next_key = self.next_key
            keys = [next_key + j for j in range(k)]
            energies = [self.vesicle_f(pool, d) for d in daughters]
            work = math.fsum(energies) - self.vesicle_f(pool, vesicle)
            lysed = [bool(p.tension(pool + d) > p.sigma_max) for d in daughters]
            sink = 0.0
            if not shape.population:
                sink = math.fsum(e for j, e in enumerate(energies) if j != followed)
                for j, d in enumerate(daughters):
                    if j != followed:
                        self.moiety_out += p.moieties @ d
                y = np.asarray(self.y).copy()
                y[: p.P] = pool + daughters[followed]
                self.y = jnp.asarray(y)
                self.keys[0] = keys[followed]
                self.next_key += k
                homes = [0]
                if p.pores:  # the followed daughter's own clock (§3.5); the parent's ends here
                    self.draw_threshold(0)
            else:
                sub = int(self.lineage[slot])
                self.count[sub] += k
                homes = [slot, *free[: k - 1]]
                y = np.asarray(self.y).copy()
                block = y[p.P : p.P + shape.blocks].reshape((shape.K, shape.V))
                for j, home in enumerate(homes):
                    block[home] = daughters[j][shape.places]
                    self.alive[home], self.keys[home] = True, keys[j]
                    self.generation[home] = self.generation[slot] + 1
                    if j > 0:
                        self.lineage[home] = self.next_sub
                        self.count[self.next_sub] = 0
                        self.next_sub += 1
                    if p.pores:  # each daughter's own clock (§3.5); the parent's ends here
                        self.draw_threshold(home)
                y[p.P : p.P + shape.blocks] = block.reshape(-1)
                self.y = jnp.asarray(y)
            self.booked["shear"][index] = self.booked["shear"].get(index, 0.0) + work
            self.booked["sink"] += sink
            self.events.append(record | {"outcome": "split", "keys": keys, "followed": followed,
                                         "homes": homes, "shear_work_kT": work, "sink_kT": sink,
                                         "lysed_at_birth": lysed,
                                         "daughters": [d[: len(world.places)].tolist()
                                                       for d in daughters]})  # fmt: skip
            self.row("shear")
            living = homes if shape.population else [0]
            for j, home in enumerate(homes if shape.population else [0]):
                if lysed[j if shape.population else followed]:
                    self.lyse(home, "threshold", at_birth=True)
            if self.status is not None:
                return
            self.envelope_after(living)
            if self.status is not None:
                return

    def envelope_after(self, slots):
        """After an operator: a living assembly outside the envelope stops the run (§3.4)."""
        for name, (g, columns) in self.guards(np.asarray(self.y)[None, :]).items():
            if name not in ("envelope", "floor"):
                continue
            for c, slot in enumerate(columns):
                if (slot in slots or slot == -1) and g[0, c] < 0:
                    self.row("outside_envelope")
                    self.status, self.stop_reason = "outside_envelope", name
                    return

    def transfer(self, schedule):
        """cells.operator.serial_transfer@1 (transfer.py's draws on domain 6): the kept sample, the removed
        vesicles to the sink with the old pool, the fresh pool paid by the schedule's work."""
        from cells.models.assembly_lineages_v2 import transfer

        p, shape = self.p, self.shape
        living = [int(s) for s in np.flatnonzero(self.alive)]
        counter = self.transfer_counter.get(schedule.index, 0)
        kept, drawn, self.transfer_counter[schedule.index] = transfer.sample(
            self.base_key, schedule, counter, living, schedule.keep
        )
        y = np.asarray(self.y, dtype=np.float64).copy()
        pool, slots = shape.split(y)[:2]
        pool_only = np.where(shape.pool_place, pool, 0.0)
        old_pool = float(self.prog["free_energy"](pool_only))
        removed = [s for s in living if s not in kept]
        full = shape.full(pool, slots, np)
        vesicles = [float(self.prog["free_energy"](full[s])) - old_pool + p.closure
                    for s in removed]  # fmt: skip
        self.moiety_out += p.moieties @ pool_only
        for s in removed:
            self.moiety_out += p.moieties @ (full[s] - pool_only)
        fresh = transfer.fresh_vector(self.world, schedule, p.P).astype(np.float64)
        finite_pool = shape.pool_place & p.finite
        new_pool = np.where(finite_pool, fresh, pool)
        self.moiety_out -= p.moieties @ np.where(finite_pool, fresh, 0.0)
        y[: p.P] = new_pool
        block = y[p.P : p.P + shape.blocks].reshape((shape.K, shape.V))
        for s in removed:
            block[s] = 0.0
            self.alive[s], self.keys[s], self.lineage[s] = False, -1, -1
            self.drop_clock(s)
        y[p.P : p.P + shape.blocks] = block.reshape(-1)
        self.y = jnp.asarray(y)
        work = float(self.prog["free_energy"](np.where(shape.pool_place, new_pool, 0.0)))
        sink = math.fsum(vesicles) + old_pool
        self.booked["sink"] += sink
        self.booked["transfer"][schedule.index] = (self.booked["transfer"].get(schedule.index, 0.0)
                                                   + work)  # fmt: skip
        self.events.append({"kind": "transfer", "time_s": self.t, "schedule": schedule.index,
                            "draws": [list(d[:3]) for d in drawn], "kept": kept,
                            "removed": removed, "sink_kT": sink, "work_kT": work})  # fmt: skip
        self.row("transfer")
        self.envelope_after(kept)

    # -- FR-47: the washes, every slot kept as it stands
    def _pool_parts(self):
        """(y, the pool [P], its finite places [P] bool, F_cont of a pool vector) on the host."""
        p, shape = self.p, self.shape
        y = np.asarray(self.y, dtype=np.float64).copy()
        finite = shape.pool_place & p.finite

        def pool_f(c):
            return float(self.prog["free_energy"](np.where(shape.pool_place, c, 0.0)))

        return y, y[: p.P].copy(), finite, pool_f

    def _by_place(self, vector):
        """{place: real amount} over the pool's finite places (no integer cast: the counts are
        real in this representation)."""
        finite = self.shape.pool_place & self.p.finite
        return {self.world.places[i].name: float(vector[i])
                for i in np.flatnonzero(finite[: len(self.world.places)])}  # fmt: skip

    def _wash_done(self, y, pool, removed, supplied, record, kind):
        """The pool written back, the removed and supplied moieties booked, the record and the
        row, then the envelope (E1's places; E2's are outside it)."""
        p = self.p
        y[: p.P] = pool
        self.y = jnp.asarray(y)
        self.moiety_out += p.moieties @ removed - p.moieties @ supplied
        self.events.append(record)
        self.row(kind)
        self.envelope_after([int(s) for s in np.flatnonzero(self.alive)])

    def replacement(self, schedule):
        """cells.operator.pool_replacement@1 (replacement.py), the same deterministic map here: the pool's
        finite places take the declared composition; the sink takes F_cont of the old pool, the
        schedule's work column F_cont of the fresh one."""
        from cells.models.assembly_lineages_v2 import transfer

        y, pool, finite, pool_f = self._pool_parts()
        fresh = transfer.fresh_vector(self.world, schedule, self.p.P).astype(np.float64)
        new = np.where(finite, fresh, pool)
        old_f, work = pool_f(pool), pool_f(new)
        removed, supplied = np.where(finite, pool, 0.0), np.where(finite, fresh, 0.0)
        self.booked["sink"] += old_f
        self.booked["transfer"][schedule.index] = (self.booked["transfer"].get(schedule.index, 0.0)
                                                   + work)  # fmt: skip
        record = {"kind": "replacement", "time_s": self.t, "schedule": schedule.index,
                  "removed": self._by_place(removed), "supplied": self._by_place(supplied),
                  "sink_kT": old_f, "work_kT": work}  # fmt: skip
        self._wash_done(y, new, removed, supplied, record, "replacement")

    def withdrawal(self, schedule):
        """cells.operator.pool_withdrawal@1's mean (withdrawal.py): each finite pool place n -> (1 − f)·n
        + b, b the buffer's counts in the withdrawn volume; booked as the exact operator books,
        with F_cont and F(c; gV) = F_cont(c) − F_cont(0) − (Σc)·ln g: the sink F(n; V) −
        F(kept; (1 − f)V), the schedule's work column F(b; fV) and the heat the mixing heat
        F(kept; (1 − f)V) + F(b; fV) − F(after; V), −(1 − f)·n·ln(1 − f) for an empty buffer."""
        from cells.models.assembly_lineages_v2 import withdrawal

        f = schedule.fraction
        y, pool, finite, pool_f = self._pool_parts()
        before = np.where(finite, pool, 0.0)
        kept = (1.0 - f) * before
        removed = before - kept
        buffer = withdrawal.buffer_vector(self.world, schedule, self.p.P).astype(np.float64)
        after = kept + buffer
        zero = pool_f(np.where(finite, 0.0, pool))
        ln_f, ln_rest = math.log(f), math.log1p(-f)

        def F(c, ln_g):  # F(c; gV), an empty c 0 at any volume
            total = math.fsum(c[finite])
            return pool_f(np.where(finite, c, pool)) - zero - (total * ln_g if total else 0.0)

        f_before, f_kept, f_after = F(before, 0.0), F(kept, ln_rest), F(after, 0.0)
        sink, work = f_before - f_kept, F(buffer, ln_f)
        heat = f_kept + work - f_after
        self.booked["sink"] += sink
        self.booked["heat"] += heat
        self.booked["transfer"][schedule.index] = (self.booked["transfer"].get(schedule.index, 0.0)
                                                   + work)  # fmt: skip
        record = {"kind": "withdrawal", "time_s": self.t, "schedule": schedule.index,
                  "fraction": f, "before": self._by_place(before),
                  "removed": self._by_place(removed), "remaining": self._by_place(kept),
                  "supplied": self._by_place(buffer), "pool_loss_kT": sink, "buffer_F_kT": work,
                  "mixing_heat_kT": heat}  # fmt: skip
        self._wash_done(y, np.where(finite, after, pool), removed, buffer, record, "withdrawal")


def run(spec):
    """One world in this representation, from its founders to the end of its lifecycle."""
    from cells.models.assembly_lineages_v2 import runner

    started = perf_counter()
    generic = verdict()
    state = _Run(spec)
    setup_done = perf_counter()
    plan, draws = runner._plan(spec, state.base_key)  # domain 6's draws, as exact
    if any(s.kind in WASHES for s in spec.experiment.schedules):  # FR-47: a wash stands alone
        from cells.models.assembly_lineages_v2 import population

        population._refuse_shared_replacements(spec, plan)
    horizon = state.horizon
    observed = sorted({float(t) for t in spec.experiment.observation_times_s if 0.0 < t <= horizon})
    edges = {float(t) for h in state.holds for t in (h.start, h.end) if 0.0 < t < horizon}
    times = sorted({t for t, _ in plan} | set(observed) | {horizon} | edges)  # S3: hold edges
    scheduled = dict(plan)
    state.row("start")
    for stop in times:
        hold = state.hold_in_force()  # the segment's tension: k_v jumps only at its edges
        state.sigma_hold = 0.0 if hold is None else float(hold.sigma)
        state.integrate(stop)
        if state.status is not None:
            break
        if stop in scheduled:
            state.just = set()
            state.stop_events(scheduled[stop])
            if state.status is not None:
                break
        if stop in observed:
            state.row("observed")
    if state.status is None:
        state.status = "complete"
    if state.status not in ("outside_envelope", "lysed", "slots_full"):
        state.row("end")
    arrays = _arrays(state)
    ledger, moiety = _books(state)
    finished = perf_counter()
    out = RateEquationsRun(
        spec=spec,
        status=state.status,
        rows=arrays,
        statistics={"accepted": state.accepted, "rejected": state.rejected,
                    "restarts": state.restarts, "crossings": state.located,
                    "method": state.x.method,
                    "rtol": state.x.rtol, "atol_count": state.x.atol_count, "end_time_s": state.t,
                    "stop_reason": state.stop_reason, "schedule_draws": [list(d) for d in draws],
                    **({"pores": {"draws": [list(d) for d in state.draws],
                                  "largest_clock_error": state.clock_error,
                                  "largest_clock_error_fraction": state.clock_fraction,
                                  "clock_error_bound": H_ERROR,
                                  "clock_error_relative": H_RELATIVE}} if state.p.pores else {}),
                    **({"e2": {"places": [pl.name for pl, on in zip(
                        state.world.places, state.p.e2, strict=False) if on],
                               "zero_starts": state.zero_starts,
                               "below_zero_rejections": state.below_rejected,
                               "below_zero_bound": -BELOW_ZERO * state.x.atol_count}}
                       if state.e2 else {})},
        ledger=ledger,
        moieties=moiety,
        dissipation={"smallest_margin": state.dissipation, "tolerance": -64 * EPS,
                     "holds": state.dissipation >= -64 * EPS},
        check={"generic": generic, "world": state.prog["check"]},
        events=state.events,
        timings={"run_seconds": finished - started,
                 "setup_seconds": setup_done - started},
    )  # fmt: skip
    out.check_books()  # a run whose books do not close is refused, as the exact runner's
    return out


def _arrays(state):
    """The rows (FORMAT_RATE_EQUATIONS.md): the counts of every place (single lineage) or the pool
    and each slot's vesicle (population), held supplies, the continuous heat and reservoir work,
    the bookings at events, and the sinks."""
    p, shape = state.p, state.shape
    places = len(p.world.places)
    kinds, times, ys, alive, keys, booked, _, extras = zip(*state.rows, strict=True)
    ys = np.stack(ys)
    booked = np.asarray(booked, dtype=np.float64)
    out = {
        "row_kind": np.asarray(kinds),
        "row_time_s": np.asarray(times),
        "supplied": ys[:, shape.supply_at : shape.supply_at + places],
        "heat_kT": ys[:, shape.heat_at] + booked[:, 0],
        "work_kT": ys[:, shape.heat_at + 1] + booked[:, 1] + booked[:, 2] + booked[:, 3]
        + booked[:, 5],
        "continuous_heat_kT": ys[:, shape.heat_at],
        "reservoir_work_kT": ys[:, shape.heat_at + 1] + booked[:, 1],
        "shear_work_kT": booked[:, 2],
        "transfer_work_kT": booked[:, 3],
        "sink_kT": booked[:, 4],
        "alive": np.stack(alive),
        "keys": np.stack(keys),
    }
    if p.pores:  # S3: each slot's pore clock H (0 in an empty slot)
        out["pore_clock_H"] = np.stack([e["H"] for e in extras])
    if state.holds:  # the holds' work, cumulative, by hold (source:tension_hold/<index>)
        out["tension_hold_work_kT"] = np.asarray([e["hold"] for e in extras], dtype=np.float64)
    if shape.population:
        out["pool_counts"] = ys[:, :places]
        block = ys[:, p.P : p.P + shape.blocks].reshape((len(ys), shape.K, shape.V))
        slots = np.zeros((len(ys), shape.K, p.P))
        slots[:, :, shape.places] = block
        out["slot_counts"] = slots[:, :, :places]
    else:
        out["counts"] = ys[:, :places]
    return out


def _books(state):
    """The closure (§2.2) and the moieties (§2.4) at every row."""
    p, shape, x = state.p, state.shape, state.x
    f = np.asarray([shape.free_energy(r[2], r[3], state.prog["free_energy"])
                    for r in state.rows])  # fmt: skip
    ys = np.stack([r[2] for r in state.rows])
    booked = np.asarray([r[5] for r in state.rows], dtype=np.float64)
    heat = ys[:, shape.heat_at] + booked[:, 0]
    work = ys[:, shape.heat_at + 1] + booked[:, 1] + booked[:, 2] + booked[:, 3] + booked[:, 5]
    sink = booked[:, 4]
    residual = (f - f[0]) - (work - heat - sink)
    scale = np.abs(ys[:, shape.heat_at]) + np.abs(ys[:, shape.heat_at + 1])
    events = np.abs(booked).sum(axis=1)
    tolerance = 100 * x.rtol * np.maximum(1.0, scale + events) + 64 * EPS * (
        np.abs(f) + abs(f[0]) + events
    )
    totals = []
    for _, _, y, alive, _, _, out, _ in state.rows:
        pool, slots, supplied = shape.split(y)[:3]
        total = p.moieties @ pool - p.moieties @ supplied + out
        if shape.population:
            full = np.zeros((shape.K, p.P))
            full[:, shape.places] = slots
            total = total + p.moieties @ full[alive].sum(axis=0)
        totals.append(total)
    totals = np.asarray(totals)
    drift = np.abs(totals - totals[0]) / np.maximum(1.0, np.abs(totals[0]))
    ledger = {
        "free_energy_kT": f.tolist(),
        "residual_kT": residual.tolist(),
        "tolerance_kT": tolerance.tolist(),
        "closes": bool(np.all(np.abs(residual) <= tolerance)),
    }
    moiety = {
        "names": list(p.moiety_names),
        "largest_relative_drift": float(drift.max(initial=0.0)),
        "tolerance": 1e-12,
        "closes": bool(drift.max(initial=0.0) <= 1e-12),
    }
    return ledger, moiety


def components(spec):
    """The registered IDs the definition uses: the world's, and this representation."""
    out = model.components(spec)
    return {**out, "representation": RATE_EQUATIONS}


def is_representation(spec):
    return isinstance(spec.execution, RepresentationExecution)


def simulation_spec(model_spec, experiment, execution):
    return SimulationSpec(model_spec, experiment, execution)


# ------------------------------------------------------------------ records

RUN_FORMAT = "cells.rate_equations_run@1"
NO_LIMIT_HOOK = {  # the representation's rule for what declares no limit kernel (§1.4)
    BILAYER_GEOMETRY: {"rule": FORMULAS["geometry"]},
    PORE_NUCLEATION: PORE_LIMIT,
    PRESCRIBED_SHELL: {"rule": FR47_FORMULAS["shell"]},  # FR-47
}


def fr47_paths(spec):
    """The FR-47 paths a (d) run's world uses: the shell, its washes, E2 and the gate."""
    world, experiment = spec.model.world, spec.experiment
    out = []
    if world.geometry is not None and world.geometry[0] == PRESCRIBED_SHELL:
        out.append("shell")
    if any(s.kind in WASHES for s in experiment.schedules):
        out.append("washes")
    if any(e2_places(world, experiment, spec.execution.min_count)):
        out.append("e2")
    if world.rate_factor is not None and world.rate_factor[0] == GATE_FACTOR:
        out.append("gate")
    return out


def qualification_of(spec):
    """FR-47's status for one run's record, or None: the newly admitted deterministic shell paths
    stay unqualified until the registered protocol's verdict (the lead's ruling at the landing).
    Written only where a world uses them, so no other run's record moves."""
    paths = fr47_paths(spec)
    if not paths:
        return None
    return {"status": FR47_STATUS, "protocol": FR47_PROTOCOL, "paths": paths}


def formulas_of(spec):
    """The representation's formulas for one run's record: FORMULAS, and FR-47's only where the
    world uses them (a shell, a wash, an E2 place), so no other run's record moves."""
    out = dict(FORMULAS)
    for path in fr47_paths(spec):
        if path in FR47_FORMULAS:
            out[path] = FR47_FORMULAS[path]
    return out


def write_run(directory, run, *, provenance=None):
    """run.json and rows.npz (validation/assembly_lineages_v2/FORMAT_RATE_EQUATIONS.md)."""
    import json
    from pathlib import Path

    from cells.models.assembly_lineages_v2 import conventions as conventions_rules
    from cells.models.assembly_lineages_v2 import records as exact_records
    from cells.models.assembly_lineages_v2 import spec as spec_rules

    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    spec = run.spec
    world = spec.model.world
    used = components(spec)
    registry = law_registry.active()
    laws = []
    for law_id in used["laws"]:
        formulas = getattr(registry.lookup(law_id), "limit_formulas", None)
        laws.append({**exact_records._law(law_id),
                     "limit_formulas": formulas or NO_LIMIT_HOOK[law_id]})  # fmt: skip
    block = execution_to_dict(spec.execution)["representation"]
    qualification = qualification_of(spec)  # FR-47: development-only until its verdict
    record = {
        "format": RUN_FORMAT,
        "world": spec_rules.world_id(world),
        "model": MODEL_ID,
        "engine_models": used,
        "definition_sha256": spec.fingerprint,
        "representation": {
            **block,
            "formulas": formulas_of(spec),
            "statuses": list(STATUSES),
            "not_applicable": list(NOT_APPLICABLE),
            "statistics": run.statistics,
            **({"qualification": qualification} if qualification else {}),
        },
        "conventions": conventions_rules.to_dict(world.conventions),
        "laws": laws,
        "status": run.status,
        "events": run.events,
        "ledger": run.ledger,
        "moieties": run.moieties,
        "dissipation": run.dissipation,
        "check": run.check,
        "rows": {"count": int(run.rows["row_time_s"].shape[0]),
                 "kinds": run.rows["row_kind"].tolist(),
                 "places": [p.name for p in world.places]},
        "timings": run.timings,
        "provenance": provenance,
    }  # fmt: skip
    if world.hazard is not None:  # S3: the pore law's block, as an exact run's (pore_clock.block)
        ruptures = [e for e in run.events if e.get("cause") == "pore"]
        causes = {}
        for e in run.events:
            if e["kind"] == "lysis":
                causes[e["cause"]] = causes.get(e["cause"], 0) + 1
        record["pores"] = pore_clock.block(spec, ruptures, causes)
        record["pores"]["reads"] = (
            "this representation's ruptures are its lysis events with cause pore: each one's heat "
            "is opening_heat_kT + release_heat_kT, its work work_kT (the hold's column; 0 with "
            "sigma from F) + release_reservoir_work_kT; the opening's delta_F_kT cancels across "
            "the two; clock_H is H at the located crossing, threshold_E its E"
        )
    if spec.experiment.tension_holds:
        record["tension_hold"] = pore_clock.holds_block(spec)
    text = json.dumps(record, indent=1, sort_keys=True, default=float)
    (out / "run.json").write_text(text + "\n")
    np.savez(out / "rows.npz", **{k: np.asarray(v) for k, v in run.rows.items()})
    return out
