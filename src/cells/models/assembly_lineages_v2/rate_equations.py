"""cells.rate_equations@1: the deterministic representation of the family's laws (OL6, D304).

The design is docs/OL6_DETERMINISTIC_REPRESENTATION_DESIGN.md (tag ol6-design-note-2026-11-22).
A definition chooses it by `execution.representation`, over the same world as exact events: the
world id, its laws, terms and founder are the world's; the representation is the definition's
choice, made before the run and recorded with it. A definition that declares none runs as exact
events, as before.

**The flux** (the note's §1.3). Every step r keeps its exact pair's rule in the large-count limit:

    J_r(n) = s_r(n) θ⁺_r(n) (1 − e^{ΔF_r}),   ΔF_r = ν_r·μ(n) − w_r,   μ = ∇F_cont,

with s, θ⁺ from each law's declared limit (arithmetic A: ff(n, a) → n^a, ff(N − c, r) → (N − c)^r,
m → n) and F_cont the terms' declared limits (Stirling's form of the declared F). μ is F_cont's
gradient by differentiation; w_r is the held places' work, as the exact kernel's. So −J_r ΔF_r ≥ 0
for every step at every state. J is evaluated in the factored form (i), with −expm1, which has no
cancellation near equilibrium; the limit's check compares it with the products' law (ii).

**The state** (§1.6): y = [n, supplied, Q, W]: the counts of every place (held places stay 0), each
held place's net supply, the heat Q and the reservoir work W (k_BT), all integrated by the same
stages; n, Q and W under the step control, the supplies not (a linear quadrature, kept exactly).

**The integrator** is declared apart (rosenbrock_rodas4_dense@1, numerics/rosenbrock_dense.py),
with its Jacobian the forward derivative of this module's right-hand side, so linear invariants (the
moieties) are kept to rounding.

**The envelope** (§1.5, E1): every finite place a rate reads holds at least `min_count`, at the
founder (else refused at parse) and at every accepted step (else the run stops `outside_envelope`
at the located crossing). A step whose end state is below min_count/2 is rejected and retried.

**The ledger** (§2): at every row F_cont(n_t) − F_cont(n_0) = W − Q, to the integrator's tolerance;
every moiety to rounding; and the second law per step, −J_r ΔF_r ≥ 0, at every accepted state.

**This slice (S1)** runs a single lineage without a geometry: OL1's laws. Geometry, populations,
division, schedules (S2) and the pore clock (S3) are refused with the slice that brings them.
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
    IDEAL_MIXING,
    MODE,
    MODEL_ID,
    RATE_EQUATIONS,
    kernel,
    model,
    streams,
)
from cells.models.assembly_lineages_v2 import world as world_rules
from cells.models.assembly_lineages_v2.interfaces import AssemblyRepresentation
from cells.modules import Citation, CitedWork
from cells.numerics import rosenbrock_dense as rd

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

TEST = "tests/unit/test_assembly_lineages_v2_rate_equations.py"
METHODS = (rd.METHOD_ID,)
STATUSES = ("complete", "lysed", "outside_envelope", "stalled", "step_limit", "slots_full")
READOUTS = (
    "the counts of every place, real, at the start, each observation time and the end",
    "each held place's net supply",
    "the heat Q and the reservoir work W (k_BT), and F_cont at each row",
    "vesicle-level events with their times (lysis, division, rupture), as their slices land",
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

FORMULAS = {
    "flux": "J_r = s_r(n) theta+_r(n) (1 - exp(dF_r)), dF_r = nu_r . mu(n) - w_r, mu = grad F_cont",
    "limit": "arithmetic A: ff(n, a) -> n^a, ff(N - c, r) -> (N - c)^r, m -> n; F_cont is "
    "Stirling's form of the declared F (each law's and term's declared limit)",
    "state": "dn/dt = sum_r nu_r J_r; d supplied_p/dt = -sum_r nu_r,p J_r (held p); "
    "dQ/dt = -sum_r J_r dF_r >= 0; dW/dt = sum_r J_r w_r",
    "closure": "F_cont(n_t) - F_cont(n_0) = W - Q at every row, to the integrator's tolerance",
    "envelope": "every finite place a rate reads holds at least min_count",
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
            "exactly": ("the world id, its laws, terms, founder and units", "every moiety, to "
                        "rounding", "F_cont's minima, and so every end state that is one"),
            "to_tolerance": ("the ledger's closure, F_cont(n_t) - F_cont(n_0) = W - Q",),
        },  # fmt: skip
        supports={"readouts": READOUTS, "refused": REFUSED_READOUTS},
        qualified={
            "envelope": "execution.representation.envelope.min_count, declared with provenance",
            "error_budget": "Protocol D's criterion B: b = 2 on the mean, c_r = 5 per replica "
            "(docs/OL6_DETERMINISTIC_REPRESENTATION_DESIGN.md §5.1)",
            "record": "development: Protocol D's registered tag is pending (S5)",
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
    if raw["mode"] != MODE:
        raise ConfigError(
            f"execution: {RATE_EQUATIONS} runs mode {MODE} in this slice (S1); a population "
            "comes with S2"
        )
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
    """Version 1's refusals for this slice (the note's §4), each by name, after the world and the
    experiment parse as they do for exact events."""
    later = (
        ("geometry", world.geometry is not None, "a geometry comes with S2"),
        ("population", world.population is not None, "a population comes with S2"),
        ("division", world.division is not None, "division comes with S2"),
        ("hazard", world.hazard is not None, "the pore clock comes with S3"),
        ("schedules", bool(experiment.schedules), "schedules come with S2"),
        ("tension_holds", bool(experiment.tension_holds), "a held tension comes with S3"),
    )
    for name, declared, reason in later:
        if declared:
            raise ConfigError(f"{RATE_EQUATIONS}: the world's {name} is refused in this slice: "
                              f"{reason}")  # fmt: skip
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
    envelope = enveloped(world)
    for i, place in enumerate(world.places):
        if envelope[i] and world.founder[i] < execution.min_count:
            raise ConfigError(
                f"{RATE_EQUATIONS}: the founder's {place.name} holds {world.founder[i]}, below the "
                f"envelope's min_count {execution.min_count:g}: the representation is valid only "
                "where every count a rate reads is large (a place rising from 0 is refused in "
                "version 1)"
            )


def enveloped(world):
    """[places] bool: the finite places some rate reads (§1.5): every place of a step, and every
    membrane place when a step has the membrane locus or a rate factor reads the membrane."""
    index = {p.name: i for i, p in enumerate(world.places)}
    out = [False] * len(world.places)
    membrane_read = world.rate_factor is not None
    for step in world.steps:
        for name, _ in (*step.reactants, *step.products):
            out[index[name]] = True
        membrane_read |= step.locus == world_rules.MEMBRANE
    for i, place in enumerate(world.places):
        if place.phase == world_rules.MEMBRANE and membrane_read:
            out[i] = True
        if place.held:
            out[i] = False
    return out


# ------------------------------------------------------------------ the arithmetic


class Problem:
    """One world's arithmetic in this representation: its layout (the exact builders', reused),
    its laws' limits and the matrices of the ODE. Built from any parsed spec of the world, exact or
    not (the limit's check uses exact specs too)."""

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
        self.membrane = np.asarray(self.tables.membrane, dtype=bool)
        self.finite = np.asarray(self.tables.finite, dtype=bool)
        mask = np.zeros(self.P, dtype=bool)
        mask[: len(world.places)] = enveloped(world)
        self.enveloped = mask
        # Moieties: C = sum_finite m n - sum_held m supplied is conserved (§2.4).
        names = sorted({m for s in world.species for m in s.moiety_counts()})
        matrix = np.zeros((len(names), self.P))
        for i, place in enumerate(world.places):
            for name, count in world.species_by_id(place.species).moiety_counts().items():
                matrix[names.index(name), i] = count
        self.moiety_names, self.moieties = tuple(names), matrix

    # -- the terms and the forces
    def free_energy(self, n, xp=jnp, terms=None):
        """F_cont(n) (k_BT): the declared terms' limits; `terms` selects a subset by index."""
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
        """The laws' View at real counts n with the common state m = n (consumed 0)."""
        totals = jnp.stack([
            jnp.sum(jnp.where(self.finite & (np.asarray(self.layout.place_phase) == p), n, 0.0))
            for p in range(3)
        ])  # fmt: skip
        v = kernel.view(n, totals, self.layout, self.offset, forward, jnp)
        return v._replace(consumed=jnp.zeros_like(v.consumed))

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
        """(J [R], ΔF [R]) at n: the factored form (i)."""
        lay = self.layout
        mu = self.potentials(n)
        d_f = jnp.asarray(self.nu_finite) @ mu - np.asarray(lay.step_work)
        log_a = self.log_direction(n, True)
        active = np.asarray(lay.step_active)
        safe = jnp.where(active, log_a, 0.0)
        rate = np.asarray(lay.kf) * jnp.exp(safe)
        j = jnp.where(active, rate * -jnp.expm1(d_f), 0.0)
        return j, jnp.where(active, d_f, 0.0)

    def log_reverse(self, n):
        """ln (a⁻ / k_f) of each step from the products' law (ii): the law's limit on the reverse
        view, k⁻ = k_f exp(Σ ν μ°), the same factor, and exp(ν·∇F_ex) for the excess terms."""
        log_a = self.log_direction(n, False) + np.asarray(self.layout.log_ratio)
        return log_a + jnp.asarray(self.nu_finite) @ self.excess_potentials(n)

    # -- the ODE
    def split(self, y):
        P = self.P
        return y[:P], y[P : 2 * P], y[2 * P], y[2 * P + 1]

    def rhs(self, y):
        n = self.split(y)[0]
        j, d_f = self.flux(n)
        dn = jnp.asarray(self.nu_finite).T @ j
        supplied = -(jnp.asarray(self.nu_held).T @ j)
        heat = -jnp.sum(j * d_f)
        work = jnp.sum(j * np.asarray(self.layout.step_work))
        return jnp.concatenate((dn, supplied, jnp.stack((heat, work))))

    def initial(self):
        n = np.zeros(self.P)
        n[: len(self.world.places)] = np.asarray(self.world.founder, dtype=np.float64)
        n[self.held] = 0.0
        return np.concatenate((n, np.zeros(self.P), np.zeros(2)))

    def weight(self):
        """The step control's weights: the finite counts, Q and W; not the supplies."""
        w = np.concatenate((self.finite.astype(np.float64), np.zeros(self.P), np.ones(2)))
        return w

    def margin(self, y):
        """min over enveloped places of (n_p − min_count), on the host."""
        n = np.asarray(y[: self.P])
        if not self.enveloped.any():
            return math.inf
        return float(np.min(n[self.enveloped])) - self.spec.execution.min_count


# ------------------------------------------------------------------ the limit's check


CHECK_SEED = 20261123
CHECK_STATES = 16
IDENTITY_ATOL = 1e-9  # ln units, as the exact kernel's check (balance.ATOL)


def limit_check(problem, rng, states=CHECK_STATES, low=1e2, high=1e4):
    """The limit's check (§1.4) on one problem: (1) the factored form equals the products' law,
    (2) μ equals central differences of F_cont, (3) −J_r ΔF_r ≥ 0. Returns the worst of each;
    raises ConfigError if one fails. Eager evaluation (no compile)."""
    worst = {"identity": 0.0, "potential": 0.0, "dissipation_margin": math.inf, "states": 0}
    places = len(problem.world.places)
    finite = np.flatnonzero(problem.finite[:places])
    active = np.asarray(problem.layout.step_active)
    for _ in range(states):
        n = np.zeros(problem.P)
        n[finite] = rng.uniform(low, high, finite.size)
        nj = jnp.asarray(n)
        j, d_f = problem.flux(nj)
        forward = problem.log_direction(nj, True)
        reverse = problem.log_reverse(nj)
        both = active & np.isfinite(np.asarray(forward)) & np.isfinite(np.asarray(reverse))
        gap = np.abs(np.asarray(reverse - forward - d_f))[both]
        worst["identity"] = max(worst["identity"], float(gap.max(initial=0.0)))
        mu = np.asarray(problem.potentials(nj))
        for p in finite:
            delta = 1e-4 * n[p]
            up, down = n.copy(), n.copy()
            up[p] += delta
            down[p] -= delta
            numeric = (float(problem.free_energy(jnp.asarray(up)))
                       - float(problem.free_energy(jnp.asarray(down)))) / (2 * delta)  # fmt: skip
            worst["potential"] = max(worst["potential"], abs(mu[p] - numeric) / (1 + abs(mu[p])))
        product = -np.asarray(j * d_f)
        scale = np.abs(product) + 1e-300
        worst["dissipation_margin"] = min(worst["dissipation_margin"],
                                          float(np.min(product / scale, initial=1.0)))  # fmt: skip
        worst["states"] += 1
    failed = []
    if worst["identity"] > IDENTITY_ATOL:
        failed.append(f"the factored flux is not the products' law (largest gap "
                      f"{worst['identity']:.3g} in ln units)")  # fmt: skip
    if worst["potential"] > 1e-6:
        failed.append(f"mu is not F_cont's gradient (largest relative gap {worst['potential']:.3g})")
    if worst["dissipation_margin"] < -64 * EPS:
        failed.append("a step's -J dF is negative")
    if failed:
        raise ConfigError(f"{RATE_EQUATIONS}: the limit's check fails: {'; '.join(failed)}")
    return worst


def parity(problem_spec, rng, scales=(1e2, 1e3, 1e4)):
    """Item 4 (§1.4): each law's limit against the exact kernel's forward rates at integer states
    scaled by λ: the largest gap in ln a⁺ falls as 1/λ (fitted order at least 0.9), or is
    rounding at every λ (identical forms). `problem_spec` is an exact spec's definition dict."""
    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages_v2 import balance

    world_places = None
    base = None
    gaps = []
    for scale in scales:
        raw = dict(problem_spec)
        raw["execution"] = dict(problem_spec["execution"])
        spec0 = parse_spec(raw)
        world_places = len(spec0.model.world.places)
        if base is None:
            base = rng.integers(3, 13, world_places)
        counts = (base * scale).astype(np.int64)
        membrane = sum(int(c) for c, p in zip(counts, spec0.model.world.places, strict=True)
                       if p.phase == "membrane")  # fmt: skip
        raw["execution"]["molecule_capacity"] = int(max(counts.max(), membrane)) + 8
        spec = parse_spec(raw)
        problem = Problem(spec)
        full = np.zeros(problem.P, dtype=np.int64)
        full[:world_places] = counts
        full[problem.held] = 0
        exact = balance.host_log_rates(full, problem.layout, problem.structure)[: problem.R]
        kf = np.asarray(problem.layout.kf)
        active = np.asarray(problem.layout.step_active) & (kf > 0)
        limit = np.log(np.where(active, kf, 1.0)) + np.asarray(
            problem.log_direction(jnp.asarray(full.astype(np.float64)), True)
        )
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


@functools.cache
def _generic_verdict():
    """The check on generic_probes(): every order up to three, held species, both measures,
    regular mixing and catalysis. Cached per process."""
    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages_v2 import balance

    rng = np.random.default_rng(CHECK_SEED)
    out = {"identity": 0.0, "potential": 0.0, "dissipation_margin": math.inf, "worlds": 0}
    for measure, last, regular, catalysis in generic_probes():
        raw = balance.probe_world(rng, measure, last, regular=regular, catalysis=catalysis)
        worst = limit_check(Problem(parse_spec(raw)), rng, states=4)
        out["identity"] = max(out["identity"], worst["identity"])
        out["potential"] = max(out["potential"], worst["potential"])
        out["dissipation_margin"] = min(out["dissipation_margin"], worst["dissipation_margin"])
        out["worlds"] += 1
    return out


def verdict():
    return dict(_generic_verdict())


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
    timings: dict = field(default_factory=dict)

    def check_books(self):
        """Raise if the books or the moieties did not close (a fault, never repaired)."""
        if not self.ledger["closes"]:
            raise ConfigError(f"{RATE_EQUATIONS}: the ledger did not close: {self.ledger}")
        if not self.moieties["closes"]:
            raise ConfigError(f"{RATE_EQUATIONS}: a moiety did not close: {self.moieties}")


class _Rows:
    def __init__(self, problem):
        self.problem, self.kinds, self.times, self.states = problem, [], [], []

    def add(self, kind, time, y):
        self.kinds.append(kind)
        self.times.append(float(time))
        self.states.append(np.asarray(y, dtype=np.float64).copy())

    def arrays(self):
        p = self.problem
        places = len(p.world.places)
        states = np.stack(self.states)
        return {
            "row_kind": np.asarray(self.kinds),
            "row_time_s": np.asarray(self.times),
            "counts": states[:, :places],
            "supplied": states[:, p.P : p.P + places],
            "heat_kT": states[:, 2 * p.P],
            "work_kT": states[:, 2 * p.P + 1],
        }


def _locate(margin_at, theta_low, theta_high, g_low, g_high, tolerance=1e-13):
    """The Illinois method on θ in [theta_low, theta_high], g_low ≥ 0 > g_high: the root of a
    guard on the dense output (§3.2)."""
    side = 0
    for _ in range(200):
        theta = (theta_low * g_high - theta_high * g_low) / (g_high - g_low)
        g = margin_at(theta)
        if g >= 0:
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


_PROGRAMS = {}


def _program(spec):
    """(problem, step, norm, dense, flux, the world's own check) for one definition, compiled once
    per process and kept by its fingerprint, as the exact kernel keeps a program per structure."""
    key = spec.fingerprint
    if key not in _PROGRAMS:
        problem = Problem(spec)
        x = spec.execution
        rhs = problem.rhs
        jac = jax.jacfwd(rhs)
        weight = jnp.asarray(problem.weight())
        atol, rtol = x.atol_count, x.rtol
        _PROGRAMS[key] = (
            problem,
            jax.jit(lambda y, h: rd.step(rhs, jac, y, h)),
            jax.jit(lambda err, y0, y1: rd.error_norm(err, y0, y1, rtol, atol, weight)),
            jax.jit(rd.dense),
            jax.jit(problem.flux),
            limit_check(problem, np.random.default_rng(CHECK_SEED)),
        )
    return _PROGRAMS[key]


def run(spec):
    """One world in this representation, from its founder to the end of its lifecycle."""
    started = perf_counter()
    x, e = spec.execution, spec.experiment
    generic = verdict()
    problem, step, norm, dense, flux, own = _program(spec)
    rhs = problem.rhs
    weight = jnp.asarray(problem.weight())
    atol = x.atol_count
    horizon = float(e.time_horizon_s)
    observed = sorted({float(t) for t in e.observation_times_s if 0.0 < t <= horizon})
    stops = sorted(set(observed) | {horizon})
    rows = _Rows(problem)
    y = jnp.asarray(problem.initial())
    rows.add("start", 0.0, y)
    t, status = 0.0, None
    accepted = rejected = 0
    dissipation = math.inf
    h = rd.initial_step(rhs, y, x.rtol, atol, weight, stops[0]) if stops[0] > 0 else horizon
    compile_done = None
    for stop in stops:
        while t < stop and status is None:
            landing = t + h >= stop
            hh = stop - t if landing else h
            result = step(y, hh)
            if compile_done is None:
                compile_done = perf_counter()
            err = float(norm(result.error, y, result.y))
            y_new = np.asarray(result.y)
            ok = bool(result.finite) and err <= 1.0
            if ok and problem.margin(y_new) < -0.5 * x.min_count:
                ok, err = False, 4.0 ** rd.ORDER  # inside the envelope's half: retry at h/4
            if not ok:
                rejected += 1
                h = rd.next_step(hh, err if math.isfinite(err) else math.inf, True)
                if h <= 16 * EPS * max(abs(t), horizon):
                    status = "stalled"
                continue
            if problem.margin(y_new) < 0:  # leaves the envelope within this step: locate it
                g0 = problem.margin(np.asarray(y))
                theta = _locate(lambda th: problem.margin(np.asarray(dense(y, result, th))),
                                0.0, 1.0, g0, problem.margin(y_new))  # fmt: skip
                again = step(y, theta * hh)
                t, y = t + theta * hh, again.y
                accepted += 1
                rows.add("outside_envelope", t, y)
                status = "outside_envelope"
                break
            t = stop if landing else t + hh
            y = result.y
            accepted += 1
            j, d_f = flux(problem.split(y)[0])
            product = -np.asarray(j * d_f)
            dissipation = min(dissipation, float(np.min(product / (np.abs(product) + 1e-300),
                                                         initial=1.0)))  # fmt: skip
            if accepted >= x.step_limit:
                status = "step_limit"
            h = rd.next_step(hh, err, False)
        if status is not None:
            break
        if stop in observed:
            rows.add("observed", t, y)
    if status is None:
        status = "complete"
    if status != "outside_envelope":
        rows.add("end", t, y)
    arrays = rows.arrays()
    ledger, moiety = _books(problem, rows, x)
    finished = perf_counter()
    return RateEquationsRun(
        spec=spec,
        status=status,
        rows=arrays,
        statistics={"accepted": accepted, "rejected": rejected, "method": x.method,
                    "rtol": x.rtol, "atol_count": x.atol_count, "end_time_s": t},
        ledger=ledger,
        moieties=moiety,
        dissipation={"smallest_margin": dissipation, "tolerance": -64 * EPS,
                     "holds": dissipation >= -64 * EPS},
        check={"generic": generic, "world": own},
        timings={"run_seconds": finished - started,
                 "compile_seconds": (compile_done or finished) - started},
    )  # fmt: skip


def _books(problem, rows, x):
    """The closure (§2.2) and the moieties (§2.4) at every row."""
    p = problem
    f = np.asarray([float(p.free_energy(jnp.asarray(s[: p.P]))) for s in rows.states])
    heat = np.asarray([s[2 * p.P] for s in rows.states])
    work = np.asarray([s[2 * p.P + 1] for s in rows.states])
    residual = (f - f[0]) - (work - heat)
    tolerance = 100 * x.rtol * np.maximum(1.0, np.abs(heat) + np.abs(work)) + 64 * EPS * (
        np.abs(f) + abs(f[0])
    )
    totals = np.asarray([p.moieties @ s[: p.P] - p.moieties @ s[p.P : 2 * p.P] for s in rows.states])
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
    laws = [
        {**exact_records._law(law_id), "limit_formulas": registry.lookup(law_id).limit_formulas}
        for law_id in used["laws"]
    ]
    block = execution_to_dict(spec.execution)["representation"]
    record = {
        "format": RUN_FORMAT,
        "world": spec_rules.world_id(world),
        "model": MODEL_ID,
        "engine_models": used,
        "definition_sha256": spec.fingerprint,
        "representation": {
            **block,
            "formulas": dict(FORMULAS),
            "statuses": list(STATUSES),
            "not_applicable": list(NOT_APPLICABLE),
            "statistics": run.statistics,
        },
        "conventions": conventions_rules.to_dict(world.conventions),
        "laws": laws,
        "status": run.status,
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
    (out / "run.json").write_text(json.dumps(record, indent=1, sort_keys=True, default=float) + "\n")
    np.savez(out / "rows.npz", **{k: np.asarray(v) for k, v in run.rows.items()})
    return out
