"""FR-49's registered plants for World B, C1 and C2 (validation/fr49/REGISTRATION.md §4.2 and
§5).

Each engine plant is a context manager that changes the engine in its run's own process only, for
one plant run, and never on disk; a definition plant (`definition`) changes the world's declared
values instead. Two plants, (b) and (d), are exactly what FR-49's new refusals refuse (the facing
rule and the compartment-node refusal), so they are planted below those checks (D424): the
definition stays the honest one, which passes both checks, and the engine's binding is changed
underneath. A reviewer who is not the builder confirms each against the registered plant rows
before the judge's tag (D424).

World B's, each of which must fail B2, B4 or B5:
- (a) no depletion: B from the free-ligand Langmuir with c0 = L_T / V_C. A judge-side
  substitution (validation/fr49/judge_bc.py), with no run.
- (b) the population reads the owner's pool (inward facing): site_occupancy.facing_node is
  patched so that World B's population, declared facing lys on lys's bounding patch, binds from
  its owner's cytosol (the specimen's S, at its trace). The declaration is unchanged, so the
  facing rule passes; the binding layout, its pools and the half-step read the owner's pool.
- (c) K_d x 2: the population's dissociation rate doubled in the definition (K_d = k_off / k_on).
- (d) the wash applied to every finite node: the wash's binding marks every finite outside node
  washed (wash_node), and its controls give each one the well's events (count, fraction and
  buffer), so lys is washed at 300 s too. The declaration names the well only, so the
  compartment-node refusal passes.
C1's, which must fail C1-2: the buffer given the window's label x. label_shares.exchange is
patched so that the supplied buffer joins label x (index 1, the label of the window open at
900 s) instead of the base, all else as the engine's.
C2's, which must fail C2-3: L2's association rate doubled in the definition.
"""

import contextlib

import jax.numpy as jnp
import numpy as np

LYS_FACE = "lys_face"  # validation/fr49/worlds_bc.py's bounding patch.
LUMEN_SITES = "lumen_sites"
WELL = "well"
LABEL_X = 1  # World L's labels: ["base", "x"].


@contextlib.contextmanager
def plant_b():
    """(b): World B's lumen population binds from its owner's cytosol, its declaration unchanged."""
    from cells.operators import site_occupancy as so

    original = so.facing_node

    def planted(m, population):
        if (
            population.id == LUMEN_SITES
            and population.owner_kind == "patch"
            and population.owner_id == LYS_FACE
            and population.facing == "outside"
        ):
            patch = next(p for p in m.membranes if p.id == population.owner_id)
            return so.CELL, patch.inside
        return original(m, population)

    so.facing_node = planted
    try:
        yield
    finally:
        so.facing_node = original


@contextlib.contextmanager
def plant_d():
    """(d): the wash applied at every finite outside node, each with the well's events."""
    from cells.operators import wash_schedule as ws

    original_bind = ws.bind
    original_controls = ws.ScheduledCompartmentWash.control_values

    def finite(spec):
        o = spec.execution.extracellular_capacity
        mask = np.zeros(o, dtype=bool)
        for k, node in enumerate(spec.model.extracellular):
            mask[k] = not node.reservoir
        return mask

    def bind(spec, declaration):
        state, layout = original_bind(spec, declaration)
        return state, dict(layout, wash_node=finite(spec))

    def control_values(self, spec, declaration, schedule, records, indices, times):
        count, fraction, buffer = (
            np.array(v) for v in original_controls(self, spec, declaration, schedule, records,
                                                   indices, times)
        )  # fmt: skip
        well = [c.id for c in spec.model.extracellular].index(WELL)
        for k in np.flatnonzero(finite(spec)):
            count[:, k], fraction[:, k], buffer[:, :, k] = (
                count[:, well],
                fraction[:, well],
                buffer[:, :, well],
            )
        return count, fraction, buffer

    ws.bind = bind
    ws.ScheduledCompartmentWash.control_values = control_values
    try:
        yield
    finally:
        ws.bind = original_bind
        ws.ScheduledCompartmentWash.control_values = original_controls


@contextlib.contextmanager
def plant_c1():
    """C1's: at a liquid exchange the supplied buffer joins label x, not the base."""
    from cells.numerics import label_shares
    from cells.numerics.species_sums import entity_sum

    original = label_shares.exchange

    def planted(shares, n0, removed, supplied, present, *, xp=jnp):
        declared = present if present.ndim == 3 else present[:, :, None]
        into = (xp.arange(shares.shape[1]) == LABEL_X)[None, :, None]  # The engine's: == 0.
        kept = (n0 - removed)[:, None, :] * shares
        x = xp.where(declared, kept + xp.where(into, supplied[:, None, :], 0.0), 0.0)
        total = entity_sum(x, axis=1, xp=xp)
        moved = ((removed > 0) | (supplied > 0)) & (total > 0)
        out = x / xp.where(moved, total, 1.0)[:, None, :]
        return xp.where(moved[:, None, :], out, shares)

    label_shares.exchange = planted
    try:
        yield
    finally:
        label_shares.exchange = original


ENGINE = {"b": plant_b, "d": plant_d, "c1": plant_c1}


def definition(raw, plant):
    """raw with a definition plant applied (a copy): (c) World B's k_off x 2; (c2) C2's L2 k_on x 2.
    Any other plant leaves the definition as it is."""
    import copy

    out = copy.deepcopy(raw)
    if plant not in ("c", "c2"):
        return out
    block = next(
        b for b in out["model"]["operators"] if b["law"] == "cells.operator.site_occupancy@1"
    )
    if plant == "c":
        population = next(p for p in block["populations"] if p["id"] == LUMEN_SITES)
        population["dissociation_rate_per_s"] *= 2.0
    else:
        member = next(p for p in block["populations"] if p.get("ligand") == "L2")
        member["association_rate_per_mM_per_s"] *= 2.0
    return out


@contextlib.contextmanager
def engine(plant):
    """The engine plant `plant` ("b", "d" or "c1") for the enclosed run; any other is a no-op."""
    if plant in ENGINE:
        with ENGINE[plant]():
            yield
    else:
        yield
