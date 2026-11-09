"""stationary_continuation_analysis@1: stationary states and their stability.

An opt-in analysis of an ordinary configured world (a definition or a complete
checkpoint) that answers "where does this world end up, and is a given state
stable?" without time stepping. It is read-only: it evaluates the declared
model's own functions on candidate states and never writes a run, a checkpoint
or a definition. Ordinary runs do not import it.

Supported models: the resolved pump family (MODEL_IDS). Their state holds four
dynamical fields (DYNAMIC_FIELDS: cell and finite extracellular amounts, channel
gates and junction gates); every other field is an accumulating ledger
(transfers, dissipation, work, electrode charge, pump cycles) that no rate
reads. A candidate is a vector u of the active dynamical entries in units of
1 mM (amount / node volume), gate fraction, or 10 mV (fast-mode charge offset /
node capacitance); the ledgers are held at zero.

Two stationary problems (MODES):

* slow: the full pump-leak steady state, every dynamical entry free.
* fast: the electrical state at frozen ion composition (the fast I-V state).
  Every amount stays at the base world's value; each non-reservoir node gets a
  charge offset dQ added to the model's background charge (so the composition
  is untouched), and the unknowns are those offsets and the gates. This is the
  singular-perturbation fast subsystem: the charge behind a membrane voltage
  is about 1e-4 of a cell's ions, and reduced I-V models freeze composition.

Two formulations of "stationary" (FORMULATIONS):

* rhs: zeros of the law's own time derivative, model.rhs. For this family the
  derivative already contains the algebraic field solve (capacitor reduction
  plus Kirchhoff offsets) at every evaluation: it is what RK4 reference runs
  integrate and the first stage of every IMEX step, so no separate continuous
  right-hand side is written here.
* step_map: fixed points of the engine's own checked step, Phi_T(u) = u with
  T = k declared steps of model.checked_step (Newton-Krylov shooting: Kelley
  2003, Solving Nonlinear Equations with Newton's Method, SIAM; Tuckerman and
  Barkley 2000, IMA Vol. Math. Appl. 119:453). A refused step returns NaN, never
  the unchanged state, so a refusal cannot pose as a fixed point. Slow mode.

The declared IMEX schemes are stiffly accurate and the exponential gate update
leaves a gate at its target, so a zero of the derivative is a fixed point of
the step map and conversely. Every solution is checked both ways (consistency):
its distance to the nearest derivative zero and to the nearest fixed point of
Phi_T for T = k and 2k steps, each measured as one Newton correction.

Conservation (conservation_laws). Laws make the Jacobian singular and are
derived structurally, then checked numerically:

* closed species totals: for each species, the total over a connected set of
  non-reservoir nodes joined by routes that carry it (membrane leak, channel,
  pump, junction, face) is constant;
* floating-component charge (rhs only): the field law fixes the voltage offset
  of a capacitor component without a clamp by current continuity, so its total
  charge is constant (zero for a valid state). The IMEX step instead relaxes
  that charge implicitly through the faces, so for the step map it is a fast
  mode (multiplier near 0), not a law;
* closed charge totals (fast mode): the charge of a connected set without a
  reservoir.

Each law is a column c of a matrix C with c . du/dt = 0. The problem is solved
on the affine set C^T u = C^T u_base, u = u_p + B z with B an orthonormal basis
of the complement, so B^T J B carries the spectrum of J without the laws' zero
eigenvalues. Laws are reported as neutral directions, never as marginal modes.
Held baths open a node set, so isolated stationary states are expected there.

Nonlinear solver: damped Newton with Deuflhard's natural monotonicity test,
or pseudo-transient continuation (Kelley and Keyes 1998, SIAM J. Numer. Anal.
35:508) from guesses far from a solution; "auto" tries Newton first.

Stability: eigenvalues of the reduced linearisation, dense for small worlds or
Arnoldi (ARPACK) on the JVP of the step map for larger ones, whose multipliers
mu map to growth rates log(mu)/T. Each dense eigenvalue carries the first-order
bound kappa eps ||J||_F sqrt(n) (kappa its condition number); a mode is called
stable or unstable only outside that bound, otherwise marginal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np
import scipy.linalg
import scipy.sparse.linalg

from cells.core.specs import ConfigError
from cells.processes.electrochemistry import CHARGE_PER_FMOL

ANALYSIS_ID = "stationary_continuation_analysis@1"
MODEL_IDS = ("resolved_pump_tissue@1", "resolved_pump_tissue@2", "resolved_pump_tissue@3")
DYNAMIC_FIELDS = (
    "amount_increment",
    "extracellular_amount_increment",
    "channel_gate",
    "junction_gate",
)
MODES = ("slow", "fast")
FORMULATIONS = ("rhs", "step_map")
GLOBALIZATIONS = ("newton", "pseudo_transient", "auto")
AMOUNT_UNIT_mM = 1.0
CHARGE_UNIT_V = 0.01
EPS = float(np.finfo(float).eps)
# Newton stops when a full correction is at most this in u units (1e-10 mM,
# 1e-10 gate fraction, 1e-12 V); the reported error estimate is the next one.
NEWTON_TOLERANCE = 1e-10
NEWTON_MAX_ITERATIONS = 60
PSEUDO_TRANSIENT_START_S = 1e-4
PSEUDO_TRANSIENT_MAX_ITERATIONS = 400
# Beyond this pseudo time step (s) a step is a Newton step to rounding.
PSEUDO_TRANSIENT_NEWTON_S = 1e12
DENSE_LIMIT = 2500
LAW_RANK_TOLERANCE = 1e-10


@dataclass(frozen=True)
class Block:
    """One coordinate group: entries `flat` of a state field (or node charges)."""

    field: str
    kind: str  # amount, gate or charge
    flat: np.ndarray
    unit: np.ndarray
    labels: tuple


@dataclass(frozen=True)
class Parameter:
    """A continuation parameter: an availability (control) or a layout scale."""

    kind: str
    ids: tuple
    target: str
    index: tuple
    base: float

    def to_dict(self):
        return dict(kind=self.kind, ids=list(self.ids), base_value=self.base)


PARAMETER_KINDS = {
    "channel_availability": ("control", "channel"),
    "membrane_availability": ("control", "membrane"),
    "junction_availability": ("control", "junction"),
    "pump_availability": ("control", "pump"),
    "channel_permeability_scale": ("layout", "channel_permeability"),
    "membrane_permeability_scale": ("layout", "membrane_permeability"),
    "junction_permeability_scale": ("layout", "junction_permeability"),
}


def _owner_ids(spec, owner):
    m = spec.model
    if owner == "channel":
        return [c.id for c in getattr(m, "channels", ())]
    if owner == "membrane":
        return [p.id for p in m.membranes]
    if owner == "junction":
        return [p.id for p in m.junctions]
    return [None if p.pump is None else p.pump.id for p in m.membranes]


def parameter(spec, kind, ids, *, species=None):
    """Resolve a declared parameter against a definition (its IDs must exist).

    Availabilities replace the scheduled control of the named owners by theta
    (the family keeps them in [0, 1]; the base value is their common scheduled
    value, filled in by problem()); scales multiply the named owners' layout
    permeabilities by theta (base value 1).
    """
    if kind not in PARAMETER_KINDS:
        raise ConfigError("Unknown continuation parameter kind: " + str(kind))
    owner = kind.split("_")[0]
    known = _owner_ids(spec, owner)
    ids = tuple(k for k in known if k is not None) if ids == "all" else tuple(ids or ())
    if not ids or any(i not in known for i in ids) or len(set(ids)) != len(ids):
        raise ConfigError(f"Continuation {kind} requires existing distinct {owner} IDs")
    index = np.array([known.index(i) for i in ids], dtype=np.int64)
    if (species is not None) != (kind == "membrane_permeability_scale"):
        raise ConfigError("Only membrane_permeability_scale takes (and requires) a species")
    if kind == "membrane_permeability_scale":
        if species not in spec.model.species_ids:
            raise ConfigError("membrane_permeability_scale requires a declared species")
        index = (np.int64(spec.model.species_ids.index(species)), index)
    elif kind == "junction_permeability_scale":
        index = (slice(None), index)
    else:
        index = (index,)
    base = None if PARAMETER_KINDS[kind][0] == "control" else 1.0
    return Parameter(kind, ids, PARAMETER_KINDS[kind][1], index, base)


def _numpy(tree):
    return type(tree)(*(np.asarray(v) for v in tree))


def _norm(v):
    return float(np.max(np.abs(v), initial=0.0))


def _finite(v):
    return bool(np.all(np.isfinite(v)))


@dataclass(frozen=True)
class Reduction:
    """Conservation laws of one formulation and the affine coordinates they leave."""

    laws: tuple
    matrix: np.ndarray  # [coordinate, law]
    basis: np.ndarray | None  # orthonormal complement, None without laws
    anchor: np.ndarray  # base-state coordinates: the totals held

    @property
    def size(self):
        return self.matrix.shape[0] if self.basis is None else self.basis.shape[1]

    def project(self, u):
        """The closest point to u with the base state's totals."""
        u = np.asarray(u, dtype=float)
        c = self.matrix
        if c.shape[1] == 0:
            return u
        shift = np.linalg.lstsq(c.T @ c, c.T @ (u - self.anchor), rcond=None)[0]
        return u - c @ shift

    def lift(self, origin, z):
        return origin + (z if self.basis is None else self.basis @ z)

    def full(self, z):
        return z if self.basis is None else self.basis @ z

    def vector(self, v):
        return v if self.basis is None else self.basis.T @ v

    def operator(self, jac):
        return jac if self.basis is None else self.basis.T @ jac @ self.basis


@dataclass
class Problem:
    """A configured world, mode and formulation, with jitted model evaluations.

    u holds the coordinates; theta the continuation parameter (unused without
    one). Residuals are du/dt in u units per second; for the step map that is
    (Phi_T(u) - u) / T.
    """

    spec: Any
    model: Any
    mode: str
    formulation: str
    steps: int
    dt: float
    p: Any
    control: Any
    base: Any
    blocks: tuple
    parameter: Parameter | None
    control_time: float
    anchor: np.ndarray = None
    step_map_admitted: bool = False  # the declared dt passes the model's step checks
    _cache: dict = field(default_factory=dict, repr=False)

    @property
    def size(self):
        return int(sum(len(b.flat) for b in self.blocks))

    def kinds(self):
        return np.concatenate([np.full(len(b.flat), b.kind) for b in self.blocks])

    def labels(self):
        return [label for b in self.blocks for label in b.labels]

    def theta0(self):
        return 0.0 if self.parameter is None else self.parameter.base

    def _split(self, u):
        out, start = {}, 0
        for b in self.blocks:
            out[b.field] = u[start : start + len(b.flat)]
            start += len(b.flat)
        return out

    def _apply(self, theta):
        p, control, q = self.p, self.control, self.parameter
        if q is None:
            return p, control
        owner = control if PARAMETER_KINDS[q.kind][0] == "control" else p
        base = np.asarray(getattr(owner, q.target))
        mask = np.zeros(base.shape, dtype=bool)
        mask[q.index] = True
        if owner is control:
            value = jnp.where(mask, theta, base)
            return p, control._replace(**{q.target: value})
        value = base * jnp.where(mask, theta, 1.0)
        return p._replace(**{q.target: value}), control

    def embed(self, u, theta=None):
        """(state, layout, control) at coordinates u and parameter theta; ledgers zero."""
        theta = self.theta0() if theta is None else theta
        p, control = self._apply(theta)
        parts = self._split(u)
        state = {
            k: jnp.asarray(v) if k in DYNAMIC_FIELDS else jnp.zeros_like(jnp.asarray(v))
            for k, v in self.base._asdict().items()
        }
        for b in self.blocks:
            if b.field == "node_charge":
                n = self.p.active.size
                charge = (
                    jnp.zeros(n + self.p.outside_active.size)
                    .at[b.flat]
                    .set(parts[b.field] * b.unit)
                )
                p = p._replace(
                    initial_cell_charge_C=p.initial_cell_charge_C + charge[:n],
                    initial_outside_charge_C=p.initial_outside_charge_C + charge[n:],
                )
                continue
            value = state[b.field]
            state[b.field] = (
                value.ravel().at[b.flat].set(parts[b.field] * b.unit).reshape(value.shape)
            )
        state = type(self.base)(**state)
        return state, self._hold_floating_charge(state, p), control

    def _floating(self):
        """Membership [group, node], representative one-hot and base totals of floating groups.

        A capacitor component without a clamp has its offset fixed by current
        continuity; its representative node's potential is not solved from its
        charge, which only enters the law's consistency check (2e-12 relative to
        the node charge). Coordinates far from the base round that group total
        at eps times the ionic content, above the check: the representative's
        background therefore takes the group's base total exactly. Potentials
        and rates are unchanged; on the conservation set the shift is rounding.
        """
        if "floating" not in self._cache:
            basis = np.asarray(self.p.field_floating_basis)
            free = np.asarray(self.p.field_offset_free, dtype=bool)
            fixed = np.asarray(self.p.field_fixed, dtype=bool)
            members = basis[:, free].T > 0 if basis.size else np.zeros((0, basis.shape[0]), bool)
            representative = members & fixed[None, :]
            if np.any(representative.sum(axis=1) != 1):
                raise ConfigError("A floating capacitor component needs one representative")
            totals = members.astype(float) @ _node_charge(self.base, self.p)
            self._cache["floating"] = (members.astype(float), representative.astype(float), totals)
        return self._cache["floating"]

    def _hold_floating_charge(self, state, p):
        members, representative, totals = self._floating()
        if not len(totals):
            return p
        n = self.p.active.size
        z = p.valence
        q = jnp.concatenate(
            (
                p.initial_cell_charge_C
                + CHARGE_PER_FMOL * jnp.sum(z * state.amount_increment, axis=0),
                p.initial_outside_charge_C
                + CHARGE_PER_FMOL * jnp.sum(z * state.extracellular_amount_increment, axis=0),
            )
        )
        shift = representative.T @ (totals - members @ q)
        return p._replace(
            initial_cell_charge_C=p.initial_cell_charge_C + shift[:n],
            initial_outside_charge_C=p.initial_outside_charge_C + shift[n:],
        )

    def coordinates(self, state, layout=None):
        """u of a model state on this world.

        Slow mode: physical amounts (layout reference + increment) relative to
        this world's reference, and the state's gates. Fast mode: the state's
        node charge minus this world's, and its gates (amounts stay frozen).
        """
        p = self.p if layout is None else _numpy(layout)
        state, values = _numpy(state), []
        for b in self.blocks:
            if b.field == "node_charge":
                delta = _node_charge(state, p) - _node_charge(self.base, self.p)
                values.append(delta[b.flat] / b.unit)
            elif b.field in ("amount_increment", "extracellular_amount_increment"):
                reference = (
                    "amount_reference"
                    if b.field == "amount_increment"
                    else "extracellular_amount_reference"
                )
                physical = getattr(p, reference) + getattr(state, b.field)
                values.append((physical - getattr(self.p, reference)).ravel()[b.flat] / b.unit)
            else:
                values.append(np.asarray(getattr(state, b.field)).ravel()[b.flat] / b.unit)
        return np.concatenate(values) if values else np.zeros(0)

    def _rates(self, derivative, p):
        out = []
        for b in self.blocks:
            if b.field == "node_charge":
                q = CHARGE_PER_FMOL * jnp.concatenate(
                    (
                        jnp.sum(p.valence * derivative.amount_increment, axis=0),
                        jnp.sum(p.valence * derivative.extracellular_amount_increment, axis=0),
                    )
                )
                out.append(q[b.flat] / b.unit)
            else:
                out.append(getattr(derivative, b.field).ravel()[b.flat] / b.unit)
        return jnp.concatenate(out)

    def _extract(self, state):
        return jnp.concatenate(
            [getattr(state, b.field).ravel()[b.flat] / b.unit for b in self.blocks]
        )

    def rhs_residual(self, u, theta):
        state, p, control = self.embed(u, theta)
        return self._rates(self.model.rhs(state, control, p, p.active), p)

    def step_residual(self, u, theta, steps):
        """(Phi_T(u) - u) / T for T = steps declared steps; NaN if any step is refused.

        steps may be traced: one compiled map serves every T (fori_loop).
        """
        if self.mode != "slow":
            raise ConfigError("The step map is defined for the slow mode only")
        state, p, control = self.embed(u, theta)
        dt, checked = self.dt, self.model.checked_step

        def advance(_, carry):
            current, ok = carry
            new, valid = checked(current, dt, control, p, p.active)
            return new, ok & valid

        final, ok = jax.lax.fori_loop(0, steps, advance, (state, jnp.asarray(True)))
        return jnp.where(ok, (self._extract(final) - u) / (steps * dt), jnp.nan)

    def _key(self, formulation, steps):
        formulation = self.formulation if formulation is None else formulation
        if formulation not in FORMULATIONS:
            raise ConfigError("Unknown formulation")
        if formulation == "rhs":
            return formulation, None
        steps = self.steps if steps is None else steps
        if type(steps) is not int or steps < 1:
            raise ConfigError("The step map needs a positive integer number of declared steps")
        return formulation, steps

    def functions(self, formulation=None):
        """Jitted evaluations of one formulation, compiled once per problem.

        linearize(u, theta, k) -> (residual, d/du, d/dtheta, membrane voltages,
        field converged): one forward-mode pass over (u, theta); k (the step
        count of the step map) is a traced argument, ignored by the rhs.
        """
        kind = self._key(formulation, None)[0]
        if kind not in self._cache:
            if kind == "rhs":

                def f(u, theta, k):
                    return self.rhs_residual(u, theta)

            else:
                f = self.step_residual

            def with_aux(w, k):
                u, theta = w[:-1], w[-1]
                state, p, control = self.embed(u, theta)
                if kind == "rhs":
                    # One law evaluation: model.rhs is readouts' derivative where valid.
                    values = self.model.readouts(state, control, p)
                    derivative = type(values.derivative)(
                        *(jnp.where(values.valid, v, jnp.nan) for v in values.derivative)
                    )
                    r, field, ok = self._rates(derivative, p), values.field, values.valid
                else:
                    field = self.model.field_values(state, control, p)
                    r, ok = f(u, theta, k), field.converged
                return r, (r, field.rates.membrane_voltage_V, ok)

            linear = jax.jit(jax.jacfwd(with_aux, has_aux=True))

            def linearize(u, theta, k):
                jac, (r, voltage, ok) = linear(jnp.concatenate((u, jnp.atleast_1d(theta))), k)
                return r, jac[:, :-1], jac[:, -1], voltage, ok

            self._cache[kind] = dict(
                linearize=linearize,
                jvp=jax.jit(
                    lambda u, theta, k, v: jax.jvp(lambda x: f(x, theta, k), (u,), (v,))[1]
                ),
            )
        return self._cache[kind]

    def evaluate(self, u, theta=None, formulation=None, steps=None):
        """Numpy (residual, Jacobian, d residual / d theta, voltages, field converged)."""
        theta = self.theta0() if theta is None else float(theta)
        kind, k = self._key(formulation, steps)
        r, ju, jt, v, ok = self.functions(kind)["linearize"](
            jnp.asarray(u, dtype=float), theta, jnp.asarray(k or 1, dtype=jnp.int32)
        )
        return np.asarray(r), np.asarray(ju), np.asarray(jt), np.asarray(v), bool(ok)

    def reduction(self, formulation=None):
        """The formulation's laws and coordinates (floating charge: rhs only)."""
        formulation = self._key(formulation, None)[0]
        key = ("reduction", formulation)
        if key not in self._cache:
            laws, matrix = conservation_laws(self, formulation)
            basis = None
            if matrix.shape[1] and np.all(np.count_nonzero(matrix, axis=0) == 1):
                # Laws on single coordinates (impermeant species): drop them, so the
                # reduced coordinates stay the physical ones.
                keep = np.flatnonzero(~np.any(matrix != 0, axis=1))
                basis = np.eye(matrix.shape[0])[:, keep]
            elif matrix.shape[1]:
                normal = matrix / np.linalg.norm(matrix, axis=0)
                basis = scipy.linalg.null_space(normal.T)
            self._cache[key] = Reduction(laws, matrix, basis, self.anchor)
        return self._cache[key]


def _node_charge(state, p):
    z = p.valence
    return np.r_[
        p.initial_cell_charge_C + CHARGE_PER_FMOL * np.sum(z * state.amount_increment, axis=0),
        p.initial_outside_charge_C
        + CHARGE_PER_FMOL * np.sum(z * state.extracellular_amount_increment, axis=0),
    ]


def _names(spec, p):
    m = spec.model
    cells = [c.id for c in m.cells]
    cells += [f"cell_slot_{i}" for i in range(len(cells), np.asarray(p.active).size)]
    outside = [c.id for c in m.extracellular]
    outside += [f"outside_slot_{i}" for i in range(len(outside), np.asarray(p.outside_active).size)]
    return cells, outside


def _blocks(spec, p, base, mode):
    """Coordinate blocks over the active dynamical entries."""
    if any(k not in type(base)._fields for k in DYNAMIC_FIELDS):
        raise ConfigError("Model state lacks the resolved family's dynamical fields")
    species = list(spec.model.species_ids)
    cells, outside = _names(spec, p)
    finite = np.asarray(p.outside_active) & ~np.asarray(p.reservoir)
    blocks = []
    if mode == "slow":
        for name, mask, volume, nodes in (
            ("amount_increment", np.asarray(p.active), p.volume, cells),
            ("extracellular_amount_increment", finite, p.extracellular_volume, outside),
        ):
            s, n = np.asarray(getattr(base, name)).shape
            flat = np.flatnonzero(np.broadcast_to(mask[None, :], (s, n)))
            unit = np.broadcast_to(np.asarray(volume)[None, :] * AMOUNT_UNIT_mM, (s, n))
            labels = tuple(f"{species[i // n]}@{nodes[i % n]}" for i in flat)
            blocks.append(Block(name, "amount", flat, unit.ravel()[flat], labels))
    else:
        flat = np.flatnonzero(np.r_[np.asarray(p.active), finite])
        capacitance = np.diagonal(np.asarray(p.field_capacitor_matrix))[flat]
        unit = np.where(capacitance > 0, capacitance, 1e-12) * CHARGE_UNIT_V
        names = cells + outside
        labels = tuple(f"charge@{names[i]}" for i in flat)
        blocks.append(Block("node_charge", "charge", flat, unit, labels))
    gate = np.asarray(base.channel_gate)
    if gate.size and hasattr(p, "channel_gate_active"):
        flat = np.flatnonzero(np.asarray(p.channel_gate_active) & np.asarray(p.channel_active))
        ids = [c.id for c in spec.model.channels]
        width = gate.shape[1]
        labels = tuple(f"gate{i // width}@{ids[i % width]}" for i in flat)
        blocks.append(Block("channel_gate", "gate", flat, np.ones(len(flat)), labels))
    flat = np.flatnonzero(np.asarray(p.junction_active))
    labels = tuple(f"gate@{spec.model.junctions[i].id}" for i in flat)
    blocks.append(Block("junction_gate", "gate", flat, np.ones(len(flat)), labels))
    return tuple(b for b in blocks if len(b.flat))


class _Union:
    def __init__(self, size):
        self.parent = list(range(size))

    def root(self, i):
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def join(self, i, j):
        self.parent[self.root(i)] = self.root(j)


def _carries(p, control, k, m):
    """Does membrane patch m move species k at the analysed controls?"""
    if np.asarray(control.membrane)[m] > 0 and p.membrane_permeability[k, m] > 0:
        return True
    if hasattr(p, "pump_present") and p.pump_present[m] and np.asarray(control.pump)[m] > 0:
        if p.stoichiometry[k, m] != 0:
            return True
    if hasattr(p, "calcium_pump_present") and p.calcium_pump_present[m]:
        if np.asarray(control.calcium_pump)[m] > 0 and p.calcium_stoichiometry[k, m] != 0:
            return True
    if hasattr(p, "channel_relative_permeability"):
        route = (
            np.asarray(p.channel_active)
            & (np.asarray(p.channel_membranes) == m)
            & (np.asarray(control.channel) > 0)
            & (p.channel_relative_permeability[k] * p.channel_permeability > 0)
            & (np.asarray(p.channel_abundance) > 0)
        )
        return bool(np.any(route))
    return False


def _components(p, control, species):
    """Connected node sets (cell + outside numbering) under routes carrying `species`."""
    n, o = np.asarray(p.active).size, np.asarray(p.outside_active).size
    union = _Union(n + o)
    for m in np.flatnonzero(np.asarray(p.membrane_active)):
        if any(_carries(p, control, k, m) for k in species):
            union.join(int(p.membrane_cell[m]), n + int(p.membrane_outside[m]))
    for j in np.flatnonzero(np.asarray(p.junction_active)):
        if np.asarray(control.junction)[j] > 0 and any(
            p.junction_permeability[k, j] > 0 for k in species
        ):
            union.join(int(p.junction_sender[j]), int(p.junction_receiver[j]))
    for f in np.flatnonzero(np.asarray(p.face_active)):
        if any(p.face_factor[k, f] > 0 for k in species):
            union.join(n + int(p.face_sender[f]), n + int(p.face_receiver[f]))
    groups = {}
    for i in np.flatnonzero(np.r_[np.asarray(p.active), np.asarray(p.outside_active)]):
        groups.setdefault(union.root(int(i)), []).append(int(i))
    return list(groups.values())


def conservation_laws(pb, formulation):
    """Structural laws [coordinate, law] in u space for one formulation (module doc)."""
    p, control, spec = pb.p, pb.control, pb.spec
    n = np.asarray(p.active).size
    reservoir = np.r_[np.zeros(n, dtype=bool), np.asarray(p.reservoir)]
    cells, outside = _names(spec, p)
    names = cells + outside
    position, start = {}, 0
    for b in pb.blocks:
        position[b.field] = (start, b)
        start += len(b.flat)
    size, candidates = start, []
    z = np.asarray(p.valence).ravel()

    def column(members, species):
        c = np.zeros(size)
        for i in members:
            if pb.mode == "fast":
                begin, b = position["node_charge"]
                where = np.flatnonzero(b.flat == i)
                c[begin + where] = b.unit[where]
                continue
            key = "amount_increment" if i < n else "extracellular_amount_increment"
            begin, b = position[key]
            node, width = (i, n) if i < n else (i - n, np.asarray(p.outside_active).size)
            for k, weight in species:
                where = np.flatnonzero(b.flat == k * width + node)
                c[begin + where] = weight * b.unit[where]
        return c

    if pb.mode == "slow":
        for k, sid in enumerate(spec.model.species_ids):
            for members in _components(p, control, [k]):
                if not reservoir[members].any():
                    candidates.append(
                        (
                            column(members, [(k, 1.0)]),
                            dict(
                                kind="closed_species_total",
                                species=sid,
                                nodes=[names[i] for i in members],
                            ),
                        )
                    )
    else:
        every = range(len(z))
        for members in _components(p, control, every):
            if not reservoir[members].any():
                candidates.append(
                    (
                        column(members, None),
                        dict(
                            kind="closed_charge_total",
                            species=None,
                            nodes=[names[i] for i in members],
                        ),
                    )
                )
    if formulation == "rhs":
        basis = np.asarray(p.field_floating_basis)
        free = np.asarray(p.field_offset_free)
        for g in np.flatnonzero(free):
            members = [int(i) for i in np.flatnonzero(basis[:, g] > 0)]
            charged = [(k, z[k]) for k in range(len(z)) if z[k] != 0]
            candidates.append(
                (
                    column(members, charged),
                    dict(
                        kind="floating_component_charge",
                        species=None,
                        nodes=[names[i] for i in members],
                        note="current-continuity closure fixes this component's total charge",
                    ),
                )
            )
    laws, columns = [], []
    for c, law in candidates:
        if not np.any(c):
            continue
        trial = np.stack([*columns, c], axis=1)
        normal = trial / np.linalg.norm(trial, axis=0)
        singular = np.linalg.svd(normal, compute_uv=False)
        if singular[-1] > LAW_RANK_TOLERANCE:
            columns.append(c)
            laws.append(law)
    matrix = np.stack(columns, axis=1) if columns else np.zeros((size, 0))
    return tuple(laws), matrix


def model_identity(spec):
    return spec.to_dict()["model"]["id"]


def problem(
    spec,
    *,
    state=None,
    layout=None,
    mode="slow",
    formulation="rhs",
    steps=1,
    control_time=0.0,
    parameter=None,
):
    """A Problem from a parsed definition and, optionally, a checkpoint state.

    state/layout default to the definition's initial values. They are the base
    world: the frozen composition in fast mode and the conserved totals in
    slow mode. Controls are the schedules' values at control_time.
    """
    from cells.core.schedule import control_values
    from cells.models.registry import get_model

    model_id = model_identity(spec)
    if model_id not in MODEL_IDS:
        raise ConfigError(f"{ANALYSIS_ID} supports {', '.join(MODEL_IDS)}, not {model_id}")
    if mode not in MODES or formulation not in FORMULATIONS:
        raise ConfigError("Unknown stationary mode or formulation")
    if mode == "fast" and formulation != "rhs":
        raise ConfigError("Fast (frozen-composition) states use the rhs formulation")
    if type(steps) is not int or steps < 1:
        raise ConfigError("The step map needs a positive integer number of declared steps")
    if spec.execution.precision != "float64" or not jax.config.jax_enable_x64:
        raise ConfigError("Stationary analysis requires float64 (JAX_ENABLE_X64=1)")
    model = get_model(spec.model)
    initial_state, initial_layout = model.initial_values(spec)
    if (state is None) != (layout is None):
        raise ConfigError("Give a checkpoint state together with its layout")
    if state is None:
        state, layout = initial_state, initial_layout
    state, p = _numpy(state), _numpy(model.parameters(spec, _numpy(layout)))
    for name, a, b in zip(type(initial_layout)._fields, p, _numpy(initial_layout), strict=True):
        if a.shape != b.shape or a.dtype != b.dtype or not np.array_equal(a, b):
            raise ConfigError(f"Checkpoint layout {name} differs from the definition")
    controls = control_values(spec, [float(control_time)])
    control = type(controls)(*(np.asarray(v[0], dtype=float) for v in controls))
    admitted = mode == "slow"
    if admitted:
        try:
            model.check_steps(spec, np.array([spec.execution.dt]), controls)
        except ConfigError:
            if formulation == "step_map":
                raise
            admitted = False
    if parameter is not None and parameter.base is None:
        values = np.asarray(getattr(control, parameter.target))[parameter.index]
        if not np.all(values == values.flat[0]):
            raise ConfigError("A continued availability needs one common scheduled value")
        parameter = replace(parameter, base=float(values.flat[0]))
    pb = Problem(
        spec,
        model,
        mode,
        formulation,
        steps,
        float(spec.execution.dt),
        p,
        control,
        state,
        _blocks(spec, p, state, mode),
        parameter,
        float(control_time),
    )
    pb.anchor = pb.coordinates(state, p)
    pb.step_map_admitted = admitted
    return pb


# ------------------------------------------------------------------ solvers


@dataclass
class Solution:
    u: np.ndarray
    theta: float
    converged: bool
    iterations: int
    residual_inf: float  # du/dt in u units per second
    last_correction: float  # the final full Newton step, u units
    error_estimate: float  # the next Newton correction at the result, u units
    history: list
    message: str
    method: str


class _Linear:
    """Reduced Jacobian solves at one point: dense LU or matrix-free GMRES."""

    def __init__(self, pb, red, u, theta, jac, linear_solver, formulation, steps, shift=0.0):
        self.red, self.solver = red, linear_solver
        if linear_solver == "dense":
            matrix = red.operator(jac) - shift * np.eye(red.size)
            self.lu = scipy.linalg.lu_factor(matrix, check_finite=False)
            self.ok = _finite(matrix)
        elif linear_solver == "gmres":
            kind, k = pb._key(formulation, steps)
            fn = pb.functions(kind)

            def matvec(v):
                vector = fn["jvp"](u, theta, jnp.asarray(k or 1, dtype=jnp.int32), red.full(v))
                return red.vector(np.asarray(vector)) - shift * v

            self.operator = scipy.sparse.linalg.LinearOperator(
                (red.size, red.size), matvec=matvec, dtype=float
            )
            self.ok = True
        else:
            raise ConfigError("linear_solver must be dense or gmres")

    def __call__(self, r):
        b = -self.red.vector(r)
        if self.solver == "dense":
            return scipy.linalg.lu_solve(self.lu, b, check_finite=False)
        x, info = scipy.sparse.linalg.gmres(
            self.operator, b, rtol=1e-12, atol=0.0, restart=min(200, len(b)), maxiter=20
        )
        return x if info == 0 else np.full(len(b), np.nan)


def newton(
    pb,
    u0,
    *,
    theta=None,
    tolerance=NEWTON_TOLERANCE,
    max_iterations=NEWTON_MAX_ITERATIONS,
    linear_solver="dense",
    globalization="auto",
    formulation=None,
    steps=None,
):
    """Stationary state near u0 on the base totals.

    Converged when a full Newton step is accepted and its size (max norm in u
    units) is at most tolerance; error_estimate is the size of one further
    correction at the result.
    """
    if globalization not in GLOBALIZATIONS:
        raise ConfigError("globalization must be newton, pseudo_transient or auto")
    theta = pb.theta0() if theta is None else float(theta)
    red = pb.reduction(formulation)
    origin = red.project(u0)
    args = (pb, red, origin, theta, tolerance, linear_solver, formulation, steps)
    if globalization in ("newton", "auto"):
        result = _damped_newton(*args, max_iterations)
        if result.converged or globalization == "newton":
            return result
        first = result
    result = _pseudo_transient(*args, PSEUDO_TRANSIENT_MAX_ITERATIONS)
    if globalization == "auto":
        result.history = [dict(stage="newton", message=first.message), *result.history]
    return result


def _finish(
    pb, red, u, theta, r, jac, step, iterations, history, linear_solver, formulation, steps, method
):
    solve = _Linear(pb, red, u, theta, jac, linear_solver, formulation, steps)
    estimate = _norm(red.full(solve(r))) if solve.ok else math.inf
    return Solution(
        u, theta, True, iterations, _norm(r), step, estimate, history, "converged", method
    )


def _fail(u, theta, iterations, r, history, message, method, step=math.inf):
    residual = _norm(r) if r is not None and _finite(r) else math.inf
    return Solution(u, theta, False, iterations, residual, step, math.inf, history, message, method)


def rounding_floor(pb, red, jac, u, steps):
    """Correction size (u units) that rounding alone produces at a step-map fixed point.

    Each of the k steps stores increments to about eps |u|, so (Phi_T(u) - u)/T
    carries about 4 k eps max(1, |u|) / T, amplified by ||(T B^T J B)^-1||
    (dense, max norm, lifted to u). With slow modes this floor is far above
    the rhs formulation's: at 1 ms steps a 1e4 s mode amplifies it 1e7 times.
    """
    period = steps * pb.dt
    inverse = np.linalg.inv(period * red.operator(jac))
    if red.basis is not None:
        inverse = red.basis @ inverse @ red.basis.T
    return float(np.linalg.norm(inverse, np.inf) * 4 * steps * EPS * max(1.0, _norm(u)))


def _tolerance(pb, red, jac, u, tolerance, linear_solver, formulation, steps):
    """The requested tolerance, raised to twice the step map's rounding floor."""
    kind, k = pb._key(formulation, steps)
    if kind != "step_map" or linear_solver != "dense":
        return tolerance
    return max(tolerance, 2 * rounding_floor(pb, red, jac, u, k))


def _damped_newton(pb, red, origin, theta, tolerance, linear_solver, formulation, steps, limit):
    """Newton with Deuflhard's natural monotonicity test on the simplified correction."""
    z, history = np.zeros(red.size), []
    u = red.lift(origin, z)
    r, jac, _, _, _ = pb.evaluate(u, theta, formulation, steps)
    if not _finite(r):
        return _fail(u, theta, 0, r, history, "initial residual invalid", "newton")
    step, requested = math.inf, tolerance
    for iteration in range(1, limit + 1):
        solve = _Linear(pb, red, u, theta, jac, linear_solver, formulation, steps)
        dz = solve(r) if solve.ok else np.full(red.size, np.nan)
        step = _norm(red.full(dz))
        if solve.ok and _finite(jac):
            tolerance = _tolerance(pb, red, jac, u, requested, linear_solver, formulation, steps)
        if not np.isfinite(step):
            return _fail(u, theta, iteration, r, history, "singular or invalid Jacobian", "newton")
        lam, accepted = 1.0, False
        while lam >= 2.0**-20:
            trial = red.lift(origin, z + lam * dz)
            tr, tj, _, _, _ = pb.evaluate(trial, theta, formulation, steps)
            if _finite(tr) and _finite(tj):
                simplified = _norm(red.full(solve(tr)))
                if step <= tolerance or simplified <= (1 - lam / 4) * step:
                    accepted = True
                    break
            lam /= 2
        history.append(
            dict(
                iteration=iteration,
                step=step,
                damping=lam,
                residual_inf=_norm(r),
                tolerance=tolerance,
            )
        )
        if not accepted:
            return _fail(u, theta, iteration, r, history, "line search failed", "newton", step)
        z, u, r, jac = z + lam * dz, trial, tr, tj
        if lam == 1.0 and step <= tolerance:
            return _finish(
                pb,
                red,
                u,
                theta,
                r,
                jac,
                step,
                iteration,
                history,
                linear_solver,
                formulation,
                steps,
                "newton",
            )
    return _fail(u, theta, limit, r, history, "iteration limit", "newton", step)


def _pseudo_transient(pb, red, origin, theta, tolerance, linear_solver, formulation, steps, limit):
    """Pseudo-transient continuation: (I/delta - J) dz = r with SER growth of delta.

    In u units an implicit-Euler step of the law itself, so a guess relaxes
    toward the stable state its trajectory reaches; at large delta the step is
    Newton's, and convergence is judged as for Newton.
    """
    z, history, delta = np.zeros(red.size), [], PSEUDO_TRANSIENT_START_S
    u = red.lift(origin, z)
    r, jac, _, _, _ = pb.evaluate(u, theta, formulation, steps)
    if not _finite(r):
        return _fail(u, theta, 0, r, history, "initial residual invalid", "pseudo_transient")
    for iteration in range(1, limit + 1):
        rejected = 0
        while True:
            solve = _Linear(pb, red, u, theta, jac, linear_solver, formulation, steps, 1.0 / delta)
            dz = solve(r) if solve.ok else np.full(red.size, np.nan)
            trial = red.lift(origin, z + dz)
            tr, tj, _, _, _ = (
                pb.evaluate(trial, theta, formulation, steps) if _finite(dz) else (None,) * 5
            )
            if tr is not None and _finite(tr) and _finite(tj):
                break
            delta /= 8
            rejected += 1
            if rejected > 30:
                return _fail(
                    u,
                    theta,
                    iteration,
                    r,
                    history,
                    "pseudo-transient step rejected",
                    "pseudo_transient",
                )
        step = _norm(red.full(dz))
        if delta >= PSEUDO_TRANSIENT_NEWTON_S:
            effective = _tolerance(pb, red, jac, u, tolerance, linear_solver, formulation, steps)
        else:
            effective = tolerance
        history.append(
            dict(
                iteration=iteration,
                step=step,
                delta_s=delta,
                residual_inf=_norm(r),
                tolerance=effective,
            )
        )
        ratio = _norm(red.vector(r)) / max(_norm(red.vector(tr)), 1e-300)
        z, u, r, jac = z + dz, trial, tr, tj
        if delta >= PSEUDO_TRANSIENT_NEWTON_S and step <= effective:
            return _finish(
                pb,
                red,
                u,
                theta,
                r,
                jac,
                step,
                iteration,
                history,
                linear_solver,
                formulation,
                steps,
                "pseudo_transient",
            )
        # Switched evolution relaxation, growing at least x2 after an accepted step.
        growth = 2.0 if rejected else min(max(ratio, 2.0), 10.0)
        delta = min(delta * growth, 1e3 * PSEUDO_TRANSIENT_NEWTON_S)
    return _fail(u, theta, limit, r, history, "iteration limit", "pseudo_transient")


# ------------------------------------------------------------------ stability


def growth_rates(pb, eigenvalues, formulation=None, steps=None):
    """Growth rates (1/s) and multipliers of reduced-Jacobian eigenvalues.

    rhs: the eigenvalues themselves (no multipliers). Step map: the residual
    is (Phi_T - u)/T, so mu = 1 + T lambda and the rate is log(mu)/T.
    """
    kind, k = pb._key(formulation, steps)
    values = np.asarray(eigenvalues, dtype=complex)
    if kind == "rhs":
        return values, None
    period = k * pb.dt
    mu = 1 + period * values
    with np.errstate(divide="ignore"):
        return np.log(mu) / period, mu


def dense_spectrum(pb, jac_reduced, formulation=None, steps=None):
    """Sorted growth rates, their error bounds and multipliers (dense, with kappa)."""
    values, left, right = scipy.linalg.eig(jac_reduced, left=True, right=True)
    left = left / np.linalg.norm(left, axis=0)
    right = right / np.linalg.norm(right, axis=0)
    kappa = 1.0 / np.maximum(np.abs(np.sum(np.conj(left) * right, axis=0)), 1e-300)
    bound = kappa * EPS * np.linalg.norm(jac_reduced) * max(1, jac_reduced.shape[0]) ** 0.5
    rates, mu = growth_rates(pb, values, formulation, steps)
    if mu is not None:
        bound = bound / np.maximum(np.abs(mu), 1e-300)  # d log(mu)/T / d lambda = 1/mu
    order = np.argsort(-rates.real)
    return rates[order], bound[order], None if mu is None else mu[order]


def stability(pb, u, *, theta=None, method="dense", count=12, formulation=None, steps=None):
    """Leading eigenvalues of the reduced linearisation and a classification."""
    theta = pb.theta0() if theta is None else float(theta)
    kind, k = pb._key(formulation, steps)
    red = pb.reduction(kind)
    if method == "dense":
        _, jac, _, _, _ = pb.evaluate(u, theta, kind, k)
        rates, bound, mu = dense_spectrum(pb, red.operator(jac), kind, k)
        operator = dict(kind="dense_reduced_jacobian", size=red.size)
    elif method == "arnoldi":
        # Always the step map's DPhi_T: T = steps (default the problem's) declared steps.
        steps = pb.steps if steps is None else steps
        rates, bound, mu, operator = _arnoldi(pb, red, u, theta, count, steps)
        kind, k = "step_map", operator["steps"]
    else:
        raise ConfigError("Stability method must be dense or arnoldi")
    unstable = rates.real > bound
    marginal = np.abs(rates.real) <= bound
    shown = slice(0, count or len(rates))
    return dict(
        method=method,
        formulation=kind,
        steps=k,
        operator=operator,
        classification="unstable" if unstable.any() else "marginal" if marginal.any() else "stable",
        unstable_count=int(unstable.sum()),
        marginal_count=int(marginal.sum()),
        leading_growth_rate_per_s=float(rates.real[0]) if len(rates) else None,
        eigenvalues_per_s=[[float(v.real), float(v.imag)] for v in rates[shown]],
        eigenvalue_error_bounds_per_s=[float(b) for b in bound[shown]],
        multipliers=None if mu is None else [[float(v.real), float(v.imag)] for v in mu[shown]],
        relaxation_times_s=[float(-1 / v) for v in rates.real[shown] if v < 0],
        neutral_directions=[dict(law) for law in red.laws],
    )


def _arnoldi(pb, red, u, theta, count, steps):
    """ARPACK on DPhi_T through the step map's JVP: largest |mu| = leading modes."""
    if pb.mode != "slow":
        raise ConfigError("Arnoldi stability uses the step map (slow mode)")
    red = pb.reduction("step_map")
    fn = pb.functions("step_map")
    period = steps * pb.dt
    count = max(1, min(count, red.size - 2))
    k = jnp.asarray(steps, dtype=jnp.int32)

    def matvec(v):
        return v + period * red.vector(np.asarray(fn["jvp"](u, theta, k, red.full(v))))

    operator = scipy.sparse.linalg.LinearOperator((red.size, red.size), matvec=matvec, dtype=float)
    tol = 1e-12
    mu = scipy.sparse.linalg.eigs(operator, k=count, which="LM", tol=tol, return_eigenvectors=False)
    rates = np.log(mu.astype(complex)) / period
    order = np.argsort(-rates.real)
    # ARPACK stops at a relative residual tol |mu|: rate error about tol / T.
    bound = np.full(len(mu), tol / period)
    return (
        rates[order],
        bound,
        mu[order],
        dict(kind="arnoldi_step_map_jvp", size=red.size, steps=steps),
    )


# ------------------------------------------------------------------ checks


def conservation_residual(pb, u, theta=None, formulation=None, steps=None):
    """max over laws of |c . du/dt| / sum |c_i du_i/dt| (rounding level, about 1e-15)."""
    red = pb.reduction(formulation)
    if not red.laws:
        return 0.0
    r = pb.evaluate(u, theta, formulation, steps)[0]
    c = red.matrix
    scale = np.abs(c).T @ np.abs(r)
    return float(np.max(np.abs(c.T @ r) / np.where(scale > 0, scale, 1.0)))


def correction_vector(pb, u, theta=None, *, formulation=None, steps=None, linear_solver="dense"):
    """(one Newton correction at u in u units, residual, Jacobian); None if invalid.

    At a converged solution its size is the a-posteriori error estimate, and
    the voltage change it causes is that estimate in volts.
    """
    theta = pb.theta0() if theta is None else theta
    red = pb.reduction(formulation)
    r, jac, _, _, _ = pb.evaluate(u, theta, formulation, steps)
    if not _finite(r):
        return None, r, jac
    solve = _Linear(pb, red, u, theta, jac, linear_solver, formulation, steps)
    return red.full(solve(r)), r, jac


def correction(pb, u, theta=None, *, formulation, steps=None, linear_solver="dense"):
    """(size of one Newton correction toward the formulation's solution, residual, Jacobian)."""
    delta, r, jac = correction_vector(
        pb, u, theta, formulation=formulation, steps=steps, linear_solver=linear_solver
    )
    if delta is None:
        return math.inf, math.inf, None
    return _norm(delta), _norm(r), jac


def consistency(pb, u, theta=None, *, steps=None, linear_solver="dense"):
    """Distances from u to the derivative zero and to fixed points of Phi_T, T = k and 2k.

    Each distance is one Newton correction (u units); the step map's comes with
    its rounding floor (rounding_floor).
    """
    steps = pb.steps if steps is None else steps
    distance, residual, _ = correction(pb, u, theta, formulation="rhs", linear_solver=linear_solver)
    out = dict(rhs=dict(correction=distance, residual_inf_per_s=residual))
    if pb.mode == "slow" and not pb.step_map_admitted:
        out["step_map"] = "not evaluated: the declared step fails the model's step checks"
    elif pb.mode == "slow":
        for k in (steps, 2 * steps):
            distance, residual, jac = correction(
                pb, u, theta, formulation="step_map", steps=k, linear_solver=linear_solver
            )
            floor = None
            if jac is not None and linear_solver == "dense":
                floor = rounding_floor(pb, pb.reduction("step_map"), jac, u, k)
            out[f"step_map_{k}"] = dict(
                correction=distance, residual_inf_per_s=residual, rounding_floor=floor
            )
    return out


def describe(pb, u, theta=None):
    """Physical summary of coordinates: voltages, concentrations, gates."""
    theta = pb.theta0() if theta is None else theta
    state, p, _ = pb.embed(jnp.asarray(u), theta)
    _, _, _, voltages, converged = pb.evaluate(u, theta, "rhs")
    state, p = _numpy(state), _numpy(p)
    m = pb.spec.model
    cells, outside = _names(pb.spec, pb.p)
    ci = (p.amount_reference + state.amount_increment) / p.volume
    co = (p.extracellular_amount_reference + state.extracellular_amount_increment) / np.where(
        p.outside_active, p.extracellular_volume, 1.0
    )
    finite = np.flatnonzero(np.asarray(p.outside_active) & ~np.asarray(p.reservoir))
    parts = pb._split(np.asarray(u))
    out = dict(
        field_converged=converged,
        membrane_voltage_V={
            m.membranes[i].id: float(voltages[i]) for i in np.flatnonzero(p.membrane_active)
        },
        cell_concentration_mM={
            cells[i]: {s: float(ci[k, i]) for k, s in enumerate(m.species_ids)}
            for i in np.flatnonzero(p.active)
        },
        cell_osmolarity_mM={cells[i]: float(np.sum(ci[:, i])) for i in np.flatnonzero(p.active)},
        extracellular_concentration_mM={
            outside[i]: {s: float(co[k, i]) for k, s in enumerate(m.species_ids)} for i in finite
        },
        gates={
            label: float(v)
            for b in pb.blocks
            if b.kind == "gate"
            for label, v in zip(b.labels, parts[b.field], strict=True)
        },
    )
    if pb.mode == "fast":
        b = pb.blocks[0]
        out["charge_offset_C"] = {
            label: float(v * w)
            for label, v, w in zip(b.labels, parts[b.field], b.unit, strict=True)
        }
    return out


def solve_and_check(
    pb, guess_u, *, label="", theta=None, newton_options=None, stability_options=None
):
    """Newton, stability, conservation and step-map consistency for one guess."""
    newton_options = dict(newton_options or {})
    solution = newton(pb, guess_u, theta=theta, **newton_options)
    record = dict(
        label=label,
        converged=solution.converged,
        message=solution.message,
        method=solution.method,
        iterations=solution.iterations,
        residual_inf_per_s=solution.residual_inf,
        last_correction=solution.last_correction,
        error_estimate=solution.error_estimate,
        newton_history=solution.history,
        parameter_value=solution.theta if pb.parameter is not None else None,
    )
    if not solution.converged:
        return record, solution
    linear = newton_options.get("linear_solver", "dense")
    record["state"] = describe(pb, solution.u, solution.theta)
    record["conservation_residual_relative"] = conservation_residual(pb, solution.u, solution.theta)
    record["consistency"] = consistency(pb, solution.u, solution.theta, linear_solver=linear)
    record["stability"] = stability(
        pb, solution.u, theta=solution.theta, **(stability_options or {})
    )
    return record, solution
