"""transporter@1: the inner model's transporter kind (B5), against §7.4 (k)'s kind interface.

fr45/transporter/PLAN.md §7–8. A declared list of transporter populations on membrane patches,
absent unless declared. Version 1 admits FR-4's held-fuel proton pump
(proton_atp_mass_action_positive@1, a charged role) and R-fuel's neutral pump on finite fuel
(atp_driven_transporter_mass_action_positive@1). Finite fuel at a node with a dynamic proton row
is refused (§5.2). The hooks are pure and xp-generic, close over structure only and read no other
kind's fields. The core's hook calls are stood in for by the tests until the seams land.
"""

from dataclasses import dataclass

import jax.numpy as jnp

from cells.processes import atp_transporter as neutral
from cells.processes import proton_pump as proton
from cells.processes.electrochemistry import CHARGE_PER_FMOL

KIND_ID = "cells.transporter@1"  # namespaced (§7.4 (k))
LAWS = {
    proton.LAW_ID: "charged H+ role, held fuel",
    neutral.LAW_ID: "neutral role, finite or held fuel",
}
STATE_FIELDS = (
    "transporter_cycles",
    "transporter_dissipated_energy_pJ",
    "transporter_metabolic_work_pJ",
)
CONTROL_FIELDS = ("transporter_availability",)
OBSERVATION_COLUMNS = STATE_FIELDS
FUEL_KINDS = ("held", "finite")
ENTRY_FIELDS = {
    "id",
    "patch",
    "law",
    "capacity_fmol_s",
    "stoichiometry",
    "km_role_mM",
    "km_atp_mM",
    "role",
    "fuel",
}
FUEL_FIELDS = {"kind", "node", "rows", "ph_ref", "ph_band"}


class TransporterError(ValueError):
    """A refused declaration, with its reason."""


@dataclass(frozen=True)
class Transporter:
    id: str
    patch: str
    law: str
    capacity_fmol_s: float
    stoichiometry: int
    km_role_mM: float
    km_atp_mM: float
    role: str
    inside: str
    outside: str
    fuel_kind: str
    fuel_node: str
    fuel_rows: tuple
    ph_ref: float | None
    ph_band: float | None


def parse_entries(raw_list, patches, valence, registry, dynamic_proton_nodes=frozenset()):
    """Parse and check a model block's `transporters` (check_definition's refusals)."""
    out = []
    for raw in raw_list or ():
        missing, extra = ENTRY_FIELDS - set(raw), set(raw) - ENTRY_FIELDS
        if missing or extra:
            raise TransporterError(
                f"transporter: missing={sorted(missing)}, unknown={sorted(extra)}"
            )
        if raw["law"] not in LAWS:
            raise TransporterError(f"transporter {raw['id']}: law must be one of {sorted(LAWS)}")
        if raw["patch"] not in patches:
            raise TransporterError(f"transporter {raw['id']}: unknown patch {raw['patch']!r}")
        inside, outside = patches[raw["patch"]]
        fuel = raw["fuel"]
        if set(fuel) != FUEL_FIELDS or fuel["kind"] not in FUEL_KINDS:
            raise TransporterError(f"transporter {raw['id']}: fuel needs {sorted(FUEL_FIELDS)}")
        role = raw["role"]
        if role not in valence:
            raise TransporterError(f"transporter {raw['id']}: role {role!r} is not a declared row")
        charged = raw["law"] == proton.LAW_ID
        if charged and valence[role] != 1:
            raise TransporterError(
                f"transporter {raw['id']}: the proton pump's role must have valence +1"
            )
        if not charged and valence[role] != 0:
            raise TransporterError(
                f"transporter {raw['id']}: version 1's neutral law needs a valence-0 role"
            )
        if charged and fuel["kind"] != "held":
            raise TransporterError(
                f"transporter {raw['id']}: the proton pump runs on held fuel in version 1"
            )
        if fuel["kind"] == "finite" and fuel["node"] in dynamic_proton_nodes:
            raise TransporterError(
                f"transporter {raw['id']}: finite fuel at a node with a dynamic "
                "proton row is refused (§5.2)"
            )
        for row in fuel["rows"]:
            if row not in registry or "standard_mu_RT" not in registry[row]:
                raise TransporterError(
                    f"transporter {raw['id']}: fuel row {row!r} has no registry potential"
                )
        n = raw["stoichiometry"]
        if type(n) is not int or not 1 <= n <= 4:
            raise TransporterError(f"transporter {raw['id']}: stoichiometry is an integer 1..4")
        out.append(
            Transporter(
                raw["id"],
                raw["patch"],
                raw["law"],
                float(raw["capacity_fmol_s"]),
                n,
                float(raw["km_role_mM"]),
                float(raw["km_atp_mM"]),
                role,
                inside,
                outside,
                fuel["kind"],
                fuel["node"],
                tuple(fuel["rows"]),
                fuel["ph_ref"],
                fuel["ph_band"],
            )
        )
    return tuple(out)


def to_dict(t):
    return dict(
        id=t.id,
        patch=t.patch,
        law=t.law,
        capacity_fmol_s=t.capacity_fmol_s,
        stoichiometry=t.stoichiometry,
        km_role_mM=t.km_role_mM,
        km_atp_mM=t.km_atp_mM,
        role=t.role,
        fuel=dict(
            kind=t.fuel_kind,
            node=t.fuel_node,
            rows=list(t.fuel_rows),
            ph_ref=t.ph_ref,
            ph_band=t.ph_band,
        ),
    )


def structure_entry(declaration):
    """The kind's part of InnerStructure: declared law IDs and fuel kinds (value-free)."""
    return (
        KIND_ID,
        tuple(sorted({t.law for t in declaration})),
        tuple(sorted({t.fuel_kind for t in declaration})),
    )


def control_values(schedule, times):
    """Piecewise-constant availability at each time: schedule [(time, availability), ...]."""
    values = []
    for t in times:
        current = schedule[0][1]
        for time, value in schedule:
            if time <= t:
                current = value
        values.append(current)
    return values


def moved_rows(declaration):
    """(species, node ID) pairs every population moves in the step: the role at both nodes, and
    finite fuel rows at the fuel node. Held fuel rows are read, never moved."""
    pairs = set()
    for t in declaration:
        pairs |= {(t.role, t.inside), (t.role, t.outside)}
        if t.fuel_kind == "finite":
            pairs |= {(row, t.fuel_node) for row in t.fuel_rows}
    return tuple(sorted(pairs))


def proton_rates(inputs, parameters, availability, *, xp=jnp):
    """Additive-rates hook for the proton pump: (role inward fmol/s, current A inward, rates)."""
    r = proton.kinetics(inputs, parameters, availability, xp=xp)
    inward = proton.proton_inward_fmol_s(r, parameters)
    return inward, CHARGE_PER_FMOL * inward, r


def neutral_rates(inputs, parameters, availability, *, xp=jnp):
    """Additive-rates hook for the neutral law: (role inward, fuel row changes, rates)."""
    r = neutral.kinetics(inputs, parameters, availability, xp=xp)
    fuel = {row: coeff * r.cycles_fmol_s for row, coeff in neutral.FUEL_STOICHIOMETRY.items()}
    return neutral.role_inward_fmol_s(r, parameters), fuel, r


def book_rates(rates, held, *, xp=jnp):
    """(cycles, heat pJ/s, work pJ/s): heat -cycles dG_cyc; work only for held fuel."""
    heat = -1e-3 * rates.cycles_fmol_s * rates.cycle_free_energy_J_mol
    work = xp.where(held, -1e-3 * rates.cycles_fmol_s * rates.chemical_drive_J_mol, 0.0)
    return rates.cycles_fmol_s, heat, work


def ledger_sums(heat_pJ, work_pJ, *, xp=jnp):
    return xp.sum(heat_pJ), xp.sum(work_pJ)


def law_domain(law_id, inputs, parameters, availability, *, xp=jnp):
    mod = proton if resolve_law(law_id) == resolve_law(proton.LAW_ID) else neutral
    return mod.domain_valid(inputs, parameters, availability, xp=xp)


# --- §7.4 (k)'s published signatures ------------------------------------------------------------
# Law IDs are namespaced; a bare ID resolves to "cells.". No global law code: a population's law
# index is bound per definition, in the order of the declaration's sorted law IDs.


def resolve_law(law_id):
    return law_id if "." in law_id.split("@")[0] else "cells." + law_id


def law_index(declaration):
    """Per-definition law indices (no global codes): {namespaced law ID: index}."""
    return {law: k for k, law in enumerate(sorted({resolve_law(t.law) for t in declaration}))}


def parse(raw_model, raw_experiment, base):
    """§7.4 (k): the declaration from the model block. `base` gives patches {id: (inside, outside)},
    valence, registry and dynamic_proton_nodes (the core's parsed model; a stand-in in tests)."""
    del raw_experiment
    return parse_entries(
        raw_model.get("transporters"),
        base.patches,
        base.valence,
        base.registry,
        base.dynamic_proton_nodes,
    )


def check_definition(spec):
    """§7.4 (k): definition-time refusals; parse_entries raises them (TransporterError)."""
    return spec


def initial(spec, layout):
    """§7.4 (k): the kind's state fields start at zero, one slot per population."""
    del layout
    return {name: [0.0] * len(spec) for name in STATE_FIELDS}


_PENDING = "needs schema A's layout gather (the core's seam); the law helpers above are complete"


def rates(state, potentials, control, layout, *, xp=jnp):
    raise NotImplementedError("transporter rates " + _PENDING)


def ledger_terms(state, layout):
    raise NotImplementedError("transporter ledger_terms " + _PENDING)


def readouts(*args, **kwargs):
    raise NotImplementedError("transporter readouts " + _PENDING)
