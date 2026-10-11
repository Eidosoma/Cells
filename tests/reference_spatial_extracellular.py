"""SPEC-009 instantaneous NumPy reference, deliberately outside production.

No Cells/JAX dynamics, solver or observer imports. The passive membrane law and
input checks come from the frozen independent multispecies reference. Bulk-face
arithmetic and the capacitance-component/current-continuity solve are new here.
"""

import math
from dataclasses import dataclass

import numpy as np

from tests import reference_multispecies as ion

F, R, A = ion.F, ion.R, 1e-15
RTOL, CHARGE_ATOL, CURRENT_ATOL = 2e-12, 1e-20, 1e-23


def components(count, pairs):
    neighbours = [set() for _ in range(count)]
    for left, right in pairs:
        neighbours[left].add(right)
        neighbours[right].add(left)
    remaining, groups = set(range(count)), []
    while remaining:
        todo, group = [min(remaining)], []
        while todo:
            node = todo.pop()
            if node not in remaining:
                continue
            remaining.remove(node)
            group.append(node)
            todo.extend(sorted(neighbours[node] & remaining, reverse=True))
        groups.append(sorted(group))
    return groups


def incidence(count, pairs):
    result = np.zeros((count, len(pairs)), dtype=float)
    for edge, (left, right) in enumerate(pairs):
        result[left, edge], result[right, edge] = 1.0, -1.0
    return result


def log_mean(left, right):
    """Positive log mean and log ratio, including the exact equal limit."""
    ion.number(left, "left concentration", positive=True)
    ion.number(right, "right concentration", positive=True)
    if left == right:
        return left, 0.0
    difference = left - right
    log_ratio = (
        math.log1p(difference / right)
        if abs(difference) <= 0.5 * max(left, right)
        else math.log(left) - math.log(right)
    )
    mean = ion.number(difference / log_ratio, "logarithmic mean", positive=True)
    return mean, log_ratio


@dataclass(frozen=True)
class Geometry:
    ids: tuple
    species_ids: tuple
    z: np.ndarray
    temperature: float
    volume: np.ndarray
    initial: np.ndarray
    initial_charge: np.ndarray
    membrane_pairs: tuple
    capacitance: np.ndarray
    membrane_area: np.ndarray
    permeability: np.ndarray
    face_pairs: tuple
    face_factor: np.ndarray
    bm: np.ndarray
    bf: np.ndarray
    lc: np.ndarray
    groups: tuple
    p: np.ndarray


def resolve(raw):
    ion.fields(
        raw,
        {"id", "species_ids", "valence", "temperature_K", "compartments", "membranes", "faces"},
        "spatial reference",
    )
    ion.identifier(raw["id"])
    species = tuple(ion.identifier(s) for s in raw["species_ids"])
    if not species or len(set(species)) != len(species):
        raise ValueError("Species IDs must be nonempty and unique")
    z = tuple(raw["valence"])
    if len(z) != len(species) or any(type(v) is not int or v not in ion.VALENCES for v in z):
        raise ValueError("Explicit supported integer valences required")
    temperature = ion.number(raw["temperature_K"], "temperature", positive=True)
    ids, kinds, volume, initial, fixed = [], [], [], [], []
    for c in raw["compartments"]:
        ion.fields(
            c,
            {"id", "kind", "volume_pL", "initial_amount_fmol", "fixed_charge_equivalent_fmol"},
            "compartment",
        )
        ids.append(ion.identifier(c["id"]))
        if c["kind"] not in {"intracellular", "extracellular"}:
            raise ValueError("Unknown compartment kind")
        kinds.append(c["kind"])
        volume.append(ion.number(c["volume_pL"], "volume", positive=True))
        initial.append(ion.vector(c["initial_amount_fmol"], len(z), "inventory", positive=True))
        fixed.append(ion.number(c["fixed_charge_equivalent_fmol"], "fixed charge"))
    if not ids or len(set(ids)) != len(ids) or "extracellular" not in kinds:
        raise ValueError("Unique compartment IDs and at least one outside required")
    indices = {name: i for i, name in enumerate(ids)}

    def endpoints(edge, left, right, left_kind, right_kind):
        if edge[left] not in indices or edge[right] not in indices:
            raise ValueError("Unknown interface endpoint")
        u, v = indices[edge[left]], indices[edge[right]]
        if u == v or kinds[u] != left_kind or kinds[v] != right_kind:
            raise ValueError("Invalid interface endpoint roles")
        return u, v

    mp, caps, areas, permeability, voltages, interface_ids = [], [], [], [], [], []
    for m in raw["membranes"]:
        ion.fields(
            m,
            {
                "id",
                "inside",
                "outside",
                "area_m2",
                "capacitance_F",
                "initial_voltage_V",
                "permeability_m_per_s",
            },
            "membrane",
        )
        interface_ids.append(ion.identifier(m["id"]))
        mp.append(endpoints(m, "inside", "outside", "intracellular", "extracellular"))
        caps.append(ion.number(m["capacitance_F"], "capacitance", positive=True))
        areas.append(ion.number(m["area_m2"], "membrane area", positive=True))
        permeability.append(
            ion.vector(m["permeability_m_per_s"], len(z), "permeability", nonnegative=True)
        )
        voltages.append(ion.number(m["initial_voltage_V"], "initial voltage"))
    inside = [i for i, kind in enumerate(kinds) if kind == "intracellular"]
    if sorted(u for u, _ in mp) != inside:
        raise ValueError("First reference requires exactly one membrane per cell")
    fp, factors = [], []
    for f in raw["faces"]:
        ion.fields(
            f, {"id", "left", "right", "area_m2", "length_m", "diffusivity_m2_per_s"}, "bulk face"
        )
        interface_ids.append(ion.identifier(f["id"]))
        fp.append(endpoints(f, "left", "right", "extracellular", "extracellular"))
        area = ion.number(f["area_m2"], "face area", positive=True)
        length = ion.number(f["length_m"], "face length", positive=True)
        ds = ion.vector(f["diffusivity_m2_per_s"], len(z), "diffusivity", nonnegative=True)
        factor = [ion.number(d * area / length, "face factor", nonnegative=True) for d in ds]
        if not any(d > 0 for d in factor):
            raise ValueError("Each static face requires positive charged conductivity")
        factors.append(factor)
    if len(interface_ids) != len(set(interface_ids)):
        raise ValueError("Interface IDs must be unique")
    if len({tuple(sorted(pair)) for pair in fp}) != len(fp):
        raise ValueError("Duplicate bulk face; first reference has one face per pair")
    if len(components(len(ids), mp + fp)) != 1:
        raise ValueError("First reference requires a connected conducting world")
    bm, bf = incidence(len(ids), mp), incidence(len(ids), fp)
    caps, initial, z = np.asarray(caps), np.asarray(initial), np.asarray(z)
    q0 = bm @ (caps * np.asarray(voltages))
    ionic_q0 = (
        A
        * F
        * np.asarray(
            [
                math.fsum([x, *(int(v) * float(n) for v, n in zip(z, row, strict=True))])
                for x, row in zip(fixed, initial, strict=True)
            ]
        )
    )
    if np.max(np.abs(ionic_q0 - q0)) > CHARGE_ATOL:
        raise ValueError("Initial inventory/background/capacitor charge mismatch")
    groups = tuple(tuple(g) for g in components(len(ids), mp))
    p = np.zeros((len(ids), len(groups)))
    for j, group in enumerate(groups):
        p[list(group), j] = 1
    result = Geometry(
        tuple(ids),
        species,
        z,
        temperature,
        np.asarray(volume),
        initial,
        q0,
        tuple(mp),
        caps,
        np.asarray(areas),
        np.asarray(permeability).reshape(-1, len(z)),
        tuple(fp),
        np.asarray(factors).reshape(-1, len(z)),
        bm,
        bf,
        (bm * caps) @ bm.T,
        groups,
        p,
    )
    for value in vars(result).values():
        if isinstance(value, np.ndarray):
            value.setflags(write=False)
    return result


def bulk_terms(g, concentration):
    mobility = np.zeros((len(g.face_pairs), len(g.z)))
    logs = np.zeros_like(mobility)
    for e, (u, v) in enumerate(g.face_pairs):
        for s in range(len(g.z)):
            mean, logs[e, s] = log_mean(float(concentration[u, s]), float(concentration[v, s]))
            mobility[e, s] = g.face_factor[e, s] * mean
    diffusion_current = F * ((mobility * logs) @ g.z)
    conductance = F * F / (R * g.temperature) * (mobility @ (g.z * g.z))
    if not np.all(np.isfinite(conductance)) or np.any(conductance <= 0):
        raise ValueError("Invalid or numerically zero field conductance")
    if not np.all(np.isfinite(diffusion_current)):
        raise ValueError("Nonfinite diffusion current")
    return mobility, logs, diffusion_current, conductance


def potential(g, q, diffusion_current, conductance, gauge_id, gauge_voltage):
    if np.max(np.abs(g.p.T @ q)) > CHARGE_ATOL:
        raise ValueError("Charge incompatible with capacitance components")
    local = np.zeros(len(g.ids))
    for group in g.groups:
        free = list(group[1:])
        if free:
            local[free] = np.linalg.solve(g.lc[np.ix_(free, free)], q[free])
    offsets = np.zeros(len(g.groups))
    reduced_incidence = g.p.T @ g.bf
    reduced = (reduced_incidence * conductance) @ reduced_incidence.T
    rhs = -reduced_incidence @ (diffusion_current + conductance * (g.bf.T @ local))
    if len(offsets) > 1:
        # One gauge only. No least-squares repair, pseudoinverse or epsilon grounding.
        scale = float(np.max(np.abs(reduced)))
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("Singular extracellular constraint")
        try:
            offsets[1:] = np.linalg.solve(reduced[1:, 1:] / scale, rhs[1:] / scale)
        except np.linalg.LinAlgError as exc:
            raise ValueError("Singular extracellular constraint") from exc
    phi = local + g.p @ offsets
    phi += gauge_voltage - phi[g.ids.index(gauge_id)]
    if not np.all(np.isfinite(phi)) or np.max(np.abs(g.lc @ phi - q)) > CHARGE_ATOL:
        raise ValueError("Capacitor potential residual exceeds arithmetic limit")
    return phi


def evaluate(g, increment=None, *, gauge_id=None, gauge_voltage=0.0, membrane_availability=1.0):
    """One same-state evaluation, not an integration step or a production API."""
    gauge_id = g.ids[-1] if gauge_id is None else gauge_id
    if gauge_id not in g.ids:
        raise ValueError("Unknown gauge compartment")
    ion.number(gauge_voltage, "gauge voltage")
    ion.number(membrane_availability, "membrane availability", nonnegative=True)
    if membrane_availability > 1:
        raise ValueError("Membrane availability must lie in [0,1]")
    delta = np.zeros_like(g.initial) if increment is None else np.asarray(increment, dtype=float)
    if delta.shape != g.initial.shape or not np.all(np.isfinite(delta)):
        raise ValueError("Invalid amount increment")
    amount = g.initial + delta
    if np.any(amount <= 0) or not np.all(np.isfinite(amount)):
        raise ValueError("Nonpositive or nonfinite amount")
    concentration = amount / g.volume[:, None]
    if not np.all(np.isfinite(concentration)) or np.any(concentration <= 0):
        raise ValueError("Invalid concentration")
    q = g.initial_charge + A * F * (delta @ g.z)
    mobility, logs, diffusion_current, conductance = bulk_terms(g, concentration)
    phi = potential(g, q, diffusion_current, conductance, gauge_id, gauge_voltage)
    face_mu = R * g.temperature * logs + F * (g.bf.T @ phi)[:, None] * g.z
    face_flux = mobility / A * (face_mu / (R * g.temperature))
    face_current = A * F * (face_flux @ g.z)
    current_residual = g.p.T @ g.bf @ face_current
    current_scale = max(
        float(np.max(np.abs(diffusion_current), initial=0)),
        float(np.max(np.abs(conductance * (g.bf.T @ phi)), initial=0)),
    )
    if np.max(np.abs(current_residual), initial=0) > CURRENT_ATOL + RTOL * current_scale:
        raise ValueError("Physical current residual exceeds arithmetic limit")
    membrane_flux = np.zeros((len(g.membrane_pairs), len(g.z)))
    membrane_mu = np.zeros_like(membrane_flux)
    for e, (u, v) in enumerate(g.membrane_pairs):
        for s, z in enumerate(g.z):
            args = (
                int(z),
                float(concentration[u, s]),
                float(concentration[v, s]),
                float(phi[u] - phi[v]),
                g.temperature,
            )
            membrane_flux[e, s] = -ion.passive_flux(
                *args,
                float(g.membrane_area[e]),
                float(g.permeability[e, s]),
                membrane_availability,
            )
            membrane_mu[e, s] = ion.potential(*args)
    rate = -g.bm @ membrane_flux - g.bf @ face_flux
    charge_rate = A * F * (rate @ g.z)
    chemical_rate = A * R * g.temperature * float(np.sum(np.log(concentration) * rate))
    stored_rate = chemical_rate + float(phi @ charge_rate)
    dissipation = A * float(np.sum(face_flux * face_mu) + np.sum(membrane_flux * membrane_mu))
    result = {
        "amount_fmol": amount,
        "potential_V": phi,
        "membrane_voltage_V": g.bm.T @ phi,
        "amount_rate_fmol_per_s": rate,
        "charge_C": q,
        "charge_rate_A": charge_rate,
        "membrane_flux_fmol_per_s": membrane_flux,
        "face_flux_fmol_per_s": face_flux,
        "face_current_A": face_current,
        "face_conductance_S": conductance,
        "component_charge_residual_C": g.p.T @ q,
        "capacitor_residual_C": g.lc @ phi - q,
        "component_current_residual_A": current_residual,
        "stored_energy_rate_W": stored_rate,
        "dissipation_W": dissipation,
    }
    if any(not np.all(np.isfinite(value)) for value in result.values()):
        raise ValueError("Nonfinite instantaneous result")
    return result
