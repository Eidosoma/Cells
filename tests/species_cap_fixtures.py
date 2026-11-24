"""A world above the old species cap of 7 that exercises the host's sum order (FR-9 / D165).

The W4 probe's cell_charged_9 (/mnt/workspaces/Cells/inventory-coupling-20261114-01/w4-cap-probe/
species_cap_probe.py, cell(1, charged=4)), rebuilt here from the validation fixtures:
- one heredity cell, H kicked by 4 mV so its ions move, on its held bath: a single column on both
  node axes, NumPy's pairwise case;
- four mobile charged species Q1 to Q4 (valences 1, -1, 2, -2) at cell-to-bath gradients,
  permeant through the membrane at 1e-10 m/s and immobile on faces and junctions, each node's
  fixed background absorbing their charge so every charge anchor is unchanged;
- D150's neutral species S, produced and cleared in the cell by scheduled_species_turnover@1.

That is 9 species (Na, K, M, P, Q1 to Q4, S), seven of them moving charged rows below slot 8. At 8
or more terms NumPy's host sums over the species axis take the pairwise order, so the host
charge_increment can differ from the explicit species-order sum that every ledger uses.

FR-43's chain world (chain_world; docs/FR43_SHARED_INVENTORIES_DESIGN.md §1.2), any size from 5 to
1,024 species, with its closed-form solution and the checks its runs share (chain_checks): below.
"""

import copy
import math

import numpy as np

from cells.definitions import pump_composite_spec as cs
from cells.registry.inventory_species import add_inventory_species
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rfx
from validation.tissue import surface_pump_v3_fixtures as v3fx

Q_SPECIES = ((1, 2.0, 4.0), (-1, 3.0, 1.5), (2, 1.0, 2.0), (-2, 1.5, 0.5))  # z, cell mM, bath mM.
Q_PERMEABILITY = 1e-10  # m/s.


def add_charged(raw, name, valence, cell_mM, bath_mM, permeability):
    """A charged species at cell_mM in every cell and bath_mM in every outside node, permeant
    through every membrane, immobile on faces and junctions; each node's fixed background absorbs
    its charge."""
    out = copy.deepcopy(raw)
    m, x = out["model"], out["execution"]
    m["species"].append(dict(id=name, valence=valence))
    for nodes, mM in ((m["cells"], cell_mM), (m["extracellular"], bath_mM)):
        for node in nodes:
            amount = mM * node["volume_pL"]
            node["initial_amount_fmol"][name] = amount
            node["fixed_charge_equivalent_fmol"] -= valence * amount
    for patch in m["membranes"]:
        patch["permeability_m_per_s"][name] = permeability
    for junction in m.get("junctions", []):
        junction["permeability_m_per_s"][name] = 0.0
    for face in m.get("faces", []):
        face["diffusivity_m2_per_s"][name] = 0.0
    x["material_balance_atol_fmol"][name] = 1e-10
    return out


def charged_nine(*, dt=1e-3, steps=50):
    """The 9-species world, observed at every step."""
    end = steps * dt
    state = v3fx.kicked(v3fx.HEREDITY_STATES["H"], 4.0)
    raw = v3fx.heredity_cells(
        [state],
        dt=dt,
        end_time=end,
        observation_times=[k * dt for k in range(steps)] + [end],
        gate_voltages=[v3fx.HEREDITY_STATES["H"][0]],
    )
    for j, (z, cell_mM, bath_mM) in enumerate(Q_SPECIES):
        raw = add_charged(raw, f"Q{j + 1}", z, cell_mM, bath_mM, Q_PERMEABILITY)
    raw = add_inventory_species(
        raw,
        fx.SPECIES,
        trace_mM=1e-5,
        diffusivity_m2_per_s=1e-10,
        floor_fmol=1e-20,
        concentrations_mM={"cell_0": 1e-4},
    )
    raw = cs.frozen_definition(raw)
    routes = [("produce_S", "cell_0", "production"), ("clear_S", "cell_0", "clearance")]
    controls = [("produce_S", "cell_0", [(0.0, 1e-5)]), ("clear_S", "cell_0", [(0.0, 0.2)])]
    return fx.with_turnover(raw, routes, controls)


def species_order(spec, result):
    """On every observed state: NumPy's charge_increment (the host's sum over the species axis)
    against the explicit species-order sum (capacitor_change, which the ledgers use), and the
    explicit host sum against the compiled one. Returns (rows, rows where NumPy differs in the
    cells, explicit host equal to compiled on every row)."""
    import jax
    import jax.numpy as jnp

    from cells.models import pump_composite as pc
    from cells.models import surface_tissue as tissue

    model = pc.model_for(spec.model)
    _, parameters = model.initial_values(spec)
    layout = model.inner.inner_layout(parameters)
    cells = layout.active.size
    compiled = jax.jit(lambda s: tissue.capacitor_change(s, layout, xp=jnp)[0])
    differs, same_compiled = 0, True
    for i in range(len(result.times)):
        state = model.STATE_TYPE(*(np.asarray(v[i]) for v in result.history))
        inner = model.inner_state(state)
        numpy_sum = np.asarray(tissue.charge_increment(inner, layout, xp=np))
        explicit = np.asarray(tissue.capacitor_change(inner, layout, xp=np)[0])
        differs += int(not np.array_equal(numpy_sum[:cells], explicit[:cells]))
        same_compiled &= bool(np.array_equal(explicit, np.asarray(compiled(inner))))
    return len(result.times), differs, same_compiled


# ------------------------------------------------------------------ FR-43's chain world

CHAIN_IONS = 3  # Na, K and Cl (fx.ION_SPECIES), counted in every size.
CHAIN_K_FAST, CHAIN_K_SLOW = 20.0, 0.2  # 1/s: the odd and the even links' forward constants.
CHAIN_C0_mM = 1e-3  # The chain's concentration scale: 1 µM.
CHAIN_CELL = "cell_0"
# FR-43 §1.2's declared accuracy at dt = 5 ms: the largest error over every saved step and species,
# over the largest initial amount. The 16-row control's measured error is 1.63e-5 at every size.
CHAIN_ACCURACY = 2e-5


def chain_names(k):
    return ["S"] + [f"X{i}" for i in range(2, k + 1)]


def chain_mu_RT(k):
    """mu°/RT of X1 .. Xk at c0: a fixed pattern in [-0.5, 0.5]."""
    return [0.25 * ((7 * i) % 5) - 0.5 for i in range(k)]


def chain_forward(k, k_fast=CHAIN_K_FAST):
    """k_f (1/s) of the links X_i -> X_i+1, i = 1 .. k-1: fast, slow, fast, ..."""
    return [k_fast if j % 2 == 0 else CHAIN_K_SLOW for j in range(k - 1)]


def chain_initial_mM(k):
    return [CHAIN_C0_mM * (1 + (3 * i) % 7) / 4 for i in range(k)]


def chain_rate_matrix(k, *, k_fast=CHAIN_K_FAST, planted=False):
    """K [k, k] (1/s) of dn/dt = K n: every link is first order in amounts, so the volume cancels.
    planted: the middle link's forward constant 0.1% high (its reverse constant unchanged), the
    reference error a comparison must see."""
    mu, kf = chain_mu_RT(k), chain_forward(k, k_fast)
    K = np.zeros((k, k))
    for j in range(k - 1):
        kr = kf[j] * math.exp(mu[j + 1] - mu[j])
        K[j, j] -= kf[j]
        K[j + 1, j] += kf[j]
        K[j + 1, j + 1] -= kr
        K[j, j + 1] += kr
    if planted:
        j = (k - 1) // 2
        K[j, j] -= 1e-3 * kf[j]
        K[j + 1, j] += 1e-3 * kf[j]
    return K


def chain_world(rows, *, dt, end, every=None, max_trace_bytes=None, k_fast=CHAIN_K_FAST):
    """FR-43's chain with `rows` species in all, rows - 3 of them the chain X1 (D150's S) .. Xk.

    D150's quiescent species-only world (secreted_species_fixtures.world) with one 1 pL cell on its
    held bath and no finite node, contact or face, so the cell is the one compartment. Every link
    Xi <-> Xi+1 is a passive ideal_detailed_balance_mass_action@1 reaction in the cell, its forward
    constant fast and slow in turn, its reverse constant set by mu°/RT; initial amounts unequal.
    Synthetic values. Observed every `every` s (default: the end only)."""
    k = rows - CHAIN_IONS
    if k < 2:
        raise ValueError("a chain needs at least two species")
    chain = chain_names(k)
    profile = {n: {CHAIN_CELL: c} for n, c in zip(chain, chain_initial_mM(k), strict=True)}
    raw = fx.world(
        nodes=(),
        contacts=(),
        faces=(),
        dt=dt,
        end=end,
        observation_times=fx.grid_times(end, dt, end if every is None else every),
        concentrations_mM=profile["S"],
    )
    for n in chain[1:]:
        raw = add_inventory_species(
            raw,
            n,
            trace_mM=fx.TRACE_mM,
            diffusivity_m2_per_s=fx.D_S,
            floor_fmol=fx.FLOOR_FMOL,
            concentrations_mM=profile[n],
        )
    if max_trace_bytes is not None:
        raw["execution"]["max_trace_bytes"] = int(max_trace_bytes)
    species = [
        rfx.species(n, moieties={"X": 1}, mu=m) for n, m in zip(chain, chain_mu_RT(k), strict=True)
    ]
    reactions = [
        rfx.passive(f"link{j + 1}", {"cells": [CHAIN_CELL]}, {chain[j]: 1}, {chain[j + 1]: 1}, kf)
        for j, kf in enumerate(chain_forward(k, k_fast))
    ]
    return rfx.with_reactions(raw, species, reactions, rfx.always([r["id"] for r in reactions]))


def chain_amounts(spec, result):
    """[T, k] fmol of the chain in the cell, anchors plus increments, at every saved time."""
    from cells.registry.models import get_model

    k = len(spec.model.species_ids) - CHAIN_IONS
    _, p = get_model(spec.model).initial_values(spec)
    ids = list(spec.model.species_ids)
    rows = [ids.index(n) for n in chain_names(k)]
    reference = np.asarray(p.amount_reference)[rows, 0]
    return reference[None, :] + np.asarray(result.history.amount_increment)[:, rows, 0]


def chain_reference(n0, times, *, planted=False, k_fast=CHAIN_K_FAST):
    """[T, k] fmol: the closed form expm(K t) n0 at every time. On a uniform grid from 0 it is
    propagated by expm(K dt), one exponential (FR-43's probe: equal to expm(K t) n0 to 3e-14 of the
    largest species at 1,024 rows)."""
    from scipy.linalg import expm

    K = chain_rate_matrix(len(n0), k_fast=k_fast, planted=planted)
    times = np.asarray(times, dtype=float)
    steps = np.diff(times)
    if len(times) > 1 and times[0] == 0.0 and np.allclose(steps, steps[0], rtol=0, atol=1e-12):
        step, rows = expm(K * steps[0]), [np.asarray(n0, dtype=float)]
        for _ in steps:
            rows.append(step @ rows[-1])
        return np.asarray(rows)
    return np.asarray([expm(K * t) @ n0 for t in times])


def chain_free_energy_pJ(n, *, volume_pL, temperature_K, c0_mM):
    """F(n) = sum RT n (ln(n / V) - 1) + RT (mu°/RT - ln c0) n over the chain, in pJ (n in fmol and
    V in pL, so n / V in mM), at every row of n [T, k]."""
    from cells.laws.electrochemistry import R

    k = n.shape[-1]
    rt = 1e-3 * R * temperature_K  # pJ per fmol.
    standard = rt * (np.asarray(chain_mu_RT(k)) - math.log(c0_mM))
    return np.sum(rt * n * (np.log(n / volume_pL) - 1.0) + standard * n, axis=-1)


def chain_checks(raw, spec, result):
    """FR-43's C1.2 and C1.3 on a chain world's run, as numbers (the tests hold the bounds):
    - "amounts": [T, k] fmol of the chain at every saved time;
    - "error": the largest |n - expm(K t) n0| over every saved time and chain species, over the
      largest initial amount (the declared accuracy bounds it);
    - "seen": the same against the plant, the reference with the middle link's forward constant
      0.1% high, which a comparison at the declared accuracy must see;
    - "heat": the largest |booked heat - the engine's own free-energy drop F(n0) - F(n)|, over the
      drop's largest magnitude (a passive network books H = -dG per half-step, D152 §3.3)."""
    n = chain_amounts(spec, result)
    times = np.asarray(result.times)
    largest = float(np.max(n[0]))
    error = float(np.max(np.abs(n - chain_reference(n[0], times)))) / largest
    seen = float(np.max(np.abs(n - chain_reference(n[0], times, planted=True)))) / largest
    model = raw["model"]
    network = next(o for o in model["operators"] if o["law"] == rfx.REACTIONS)
    free = chain_free_energy_pJ(
        n,
        volume_pL=model["cells"][0]["volume_pL"],
        temperature_K=model["temperature_K"],
        c0_mM=network["standard_concentration_mM"],
    )
    drop = free[0] - free
    booked = np.asarray(result.history.reaction_dissipated_energy_pJ).sum(axis=1)
    heat = float(np.max(np.abs(booked - drop))) / float(np.max(np.abs(drop)))
    return dict(amounts=n, error=error, seen=seen, heat=heat)


def nbytes(tree):
    """Bytes of every array in a nest of tuples, lists, dicts and arrays."""
    if isinstance(tree, dict):
        return sum(nbytes(v) for v in tree.values())
    if isinstance(tree, (tuple, list)):
        return sum(nbytes(v) for v in tree)
    return np.asarray(tree).nbytes if tree is not None else 0


def held_bytes(result):
    """Bytes a run's result holds: its accepted history, observations and final layout (what the
    runner's trace estimate, execution/resources.trace_bytes, must cover)."""
    return nbytes(tuple(result.history)) + nbytes(result.observations) + nbytes(result.final.layout)
