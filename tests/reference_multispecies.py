"""Independent scalar SPEC-005 reference; no Cells/JAX imports or time integrator.

Strict host resolution precedes scalar evaluation of immutable aligned tuples.
This is a reference contract, not the production array/state/checkpoint schema.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path

SCHEMA = "cells.multispecies_membrane_reference@1"
F = 6.02214076e23 * 1.602176634e-19
R = 6.02214076e23 * 1.380649e-23
MOL_PER_FMOL = 1e-15
M3_PER_PL = 1e-15
CHARGE_PER_FMOL = F * MOL_PER_FMOL
MAX_ABS_X = 50.0
ANCHOR_TOLERANCE_V = 1e-10
BATH_TOLERANCE_MM = 1e-12
VALENCES = (-3, -2, -1, 1, 2, 3)


def number(value, name, *, positive=False, nonnegative=False):
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number, not a boolean/string")
    try:
        value = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} cannot be represented as a finite scalar") from error
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if (positive and value <= 0) or (nonnegative and value < 0):
        raise ValueError(f"{name} outside its positive/nonnegative domain")
    return float(value)


def finite_sum(values, name):
    try:
        return number(math.fsum(values), name)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{name} is not a finite sum") from error


def identifier(value):
    if not isinstance(value, str) or not value or not value.isascii():
        raise ValueError("IDs must be nonempty ASCII strings")
    if not all(c.isalnum() or c in "_-" for c in value):
        raise ValueError("IDs may contain only letters, digits, underscore and hyphen")
    return value


def fields(value, expected, name):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"{name} requires exactly these fields: {sorted(expected)}")
    return value


def vector(value, length, name, **domain):
    if not isinstance(value, (tuple, list)) or len(value) != length:
        raise ValueError(f"{name} requires {length} ordered numbers")
    return tuple(number(v, name, **domain) for v in value)


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Nonfinite JSON constant: {value}")

    return json.loads(
        Path(path).read_text(),
        object_pairs_hook=unique,
        parse_constant=invalid_constant,
        parse_float=lambda value: number(float(value), "JSON number"),
    )


@dataclass(frozen=True)
class Resolved:
    species_ids: tuple[str, ...]
    valence: tuple[int, ...]
    cell_id: str
    bath_id: str
    membrane_id: str
    volume_pL: float
    area_m2: float
    specific_capacitance_F_per_m2: float
    temperature_K: float
    initial_amount_fmol: tuple[float, ...]
    bath_mM: tuple[float, ...]
    permeability_m_per_s: tuple[float, ...]
    fixed_charge_equivalent_fmol: float
    initial_voltage_V: float
    bath_background_charge_mM: float
    pump_id: str | None
    pump_roles: tuple[str, str] | None
    stoichiometry: tuple[int, ...]
    capacity_fmol_per_s: float
    drive_J_per_mol: float

    def __post_init__(self):
        for name in (
            "species_ids",
            "valence",
            "initial_amount_fmol",
            "bath_mM",
            "permeability_m_per_s",
            "stoichiometry",
        ):
            if not isinstance(getattr(self, name), tuple):
                raise ValueError(f"Resolved {name} must be an immutable tuple")
        count = len(self.species_ids)
        for value in self.species_ids:
            identifier(value)
        if count == 0 or len(set(self.species_ids)) != count:
            raise ValueError("Species IDs must be nonempty and unique")
        owners = [self.cell_id, self.bath_id, self.membrane_id]
        if self.pump_id is not None:
            owners.append(self.pump_id)
        for value in owners:
            identifier(value)
        if len(set(owners)) != len(owners):
            raise ValueError("Cell, bath, membrane and pump IDs must be distinct")
        if len(self.valence) != count or any(
            type(z) is not int or z not in VALENCES for z in self.valence
        ):
            raise ValueError("Valences must be signed nonzero integers of magnitude at most three")
        for name in ("volume_pL", "area_m2", "specific_capacitance_F_per_m2", "temperature_K"):
            number(getattr(self, name), name, positive=True)
        vector(self.initial_amount_fmol, count, "initial amounts", positive=True)
        vector(self.bath_mM, count, "bath concentrations", positive=True)
        vector(self.permeability_m_per_s, count, "permeabilities", nonnegative=True)
        for name in (
            "fixed_charge_equivalent_fmol",
            "initial_voltage_V",
            "bath_background_charge_mM",
            "drive_J_per_mol",
        ):
            number(getattr(self, name), name)
        number(self.capacity_fmol_per_s, "pump capacity", nonnegative=True)
        if len(self.stoichiometry) != count or any(
            type(nu) is not int for nu in self.stoichiometry
        ):
            raise ValueError("Stoichiometry requires one integer per species")
        if self.pump_id is None:
            if self.pump_roles is not None or any(self.stoichiometry):
                raise ValueError("Absent pump cannot own roles or species flux")
            if self.capacity_fmol_per_s != 0 or self.drive_J_per_mol != 0:
                raise ValueError("Absent pump cannot own capacity or drive")
        else:
            if not isinstance(self.pump_roles, tuple) or len(self.pump_roles) != 2:
                raise ValueError("Pump requires immutable sodium/potassium role bindings")
            sodium, potassium = self.pump_roles
            if sodium == potassium or any(s not in self.species_ids for s in self.pump_roles):
                raise ValueError("Pump roles require distinct existing species")
            for species in self.pump_roles:
                if self.valence[self.species_ids.index(species)] != 1:
                    raise ValueError("Na/K pump roles require monovalent positive species")
            expected = tuple(
                -3 if s == sodium else 2 if s == potassium else 0 for s in self.species_ids
            )
            if self.stoichiometry != expected:
                raise ValueError("Pump stoichiometry must match the named -3 Na / +2 K law")
        number(self.capacitance_F, "derived capacitance", positive=True)
        number(CHARGE_PER_FMOL / self.capacitance_F, "charge/voltage conversion", positive=True)
        number(R * self.temperature_K, "thermal energy", positive=True)
        for amount in self.initial_amount_fmol:
            number(amount / self.volume_pL, "derived concentration", positive=True)
        if abs(self.bath_charge_residual_mM) > BATH_TOLERANCE_MM:
            raise ValueError("Maintained bath charge plus explicit background must balance")
        if abs(self.anchor_residual_V) > ANCHOR_TOLERANCE_V:
            raise ValueError("Fixed charge, initial amounts and voltage anchor are inconsistent")
        for z in self.valence:
            dimensionless_voltage(z, self.initial_voltage_V, self.temperature_K)

    @property
    def capacitance_F(self):
        return self.area_m2 * self.specific_capacitance_F_per_m2

    @property
    def bath_charge_residual_mM(self):
        return finite_sum(
            [self.bath_background_charge_mM]
            + [z * co for z, co in zip(self.valence, self.bath_mM, strict=True)],
            "bath charge",
        )

    def direct_voltage(self, amount):
        amount = vector(amount, len(self.species_ids), "amounts", positive=True)
        charge = finite_sum(
            [self.fixed_charge_equivalent_fmol]
            + [z * n for z, n in zip(self.valence, amount, strict=True)],
            "cell charge",
        )
        return number(CHARGE_PER_FMOL / self.capacitance_F * charge, "direct voltage")

    @property
    def anchor_residual_V(self):
        return self.direct_voltage(self.initial_amount_fmol) - self.initial_voltage_V

    def voltage(self, amount):
        n = vector(amount, len(self.species_ids), "amounts", positive=True)
        change = finite_sum(
            (
                z * (a - b)
                for z, a, b in zip(self.valence, n, self.initial_amount_fmol, strict=True)
            ),
            "charge increment",
        )
        return number(
            self.initial_voltage_V + CHARGE_PER_FMOL / self.capacitance_F * change,
            "derived voltage",
        )


def resolve(definition):
    root = fields(definition, {"schema", "species", "cell", "bath", "membrane"}, "assembly")
    if root["schema"] != SCHEMA:
        raise ValueError("Unsupported multispecies reference schema")
    if not isinstance(root["species"], list) or not root["species"]:
        raise ValueError("Species must be a nonempty ordered list")
    species = [fields(s, {"id", "valence"}, "species") for s in root["species"]]
    ids = tuple(identifier(s["id"]) for s in species)
    cell = fields(
        root["cell"],
        {
            "id",
            "volume_pL",
            "initial_amount_fmol",
            "fixed_charge_equivalent_fmol",
            "initial_voltage_V",
        },
        "cell",
    )
    bath = fields(
        root["bath"],
        {
            "id",
            "temperature_K",
            "concentration_mM",
            "background_charge_mM",
        },
        "bath",
    )
    membrane = fields(
        root["membrane"],
        {
            "id",
            "inside",
            "outside",
            "area_m2",
            "specific_capacitance_F_per_m2",
            "passive",
            "pump",
        },
        "membrane",
    )
    if membrane["inside"] != cell["id"] or membrane["outside"] != bath["id"]:
        raise ValueError("The sole membrane must face the declared cell and maintained bath")
    passive = fields(membrane["passive"], {"law", "permeability_m_per_s"}, "passive mechanism")
    if passive["law"] != "constant_field@1":
        raise ValueError("Unsupported passive transport law")

    def aligned(mapping, name):
        fields(mapping, ids, name)
        return tuple(mapping[s] for s in ids)

    pump = membrane["pump"]
    roles = None
    stoichiometry = (0,) * len(ids)
    if pump is not None:
        fields(
            pump,
            {
                "id",
                "law",
                "roles",
                "stoichiometry",
                "capacity_fmol_per_s",
                "drive_J_per_mol",
            },
            "pump",
        )
        if pump["law"] != "nak_atp_affinity_tanh@1":
            raise ValueError("Unsupported pump kinetic/energy law")
        fields(pump["roles"], {"sodium", "potassium"}, "pump roles")
        roles = tuple(identifier(pump["roles"][role]) for role in ("sodium", "potassium"))
        fields(pump["stoichiometry"], roles, "pump stoichiometry")
        stoichiometry = tuple(pump["stoichiometry"].get(s, 0) for s in ids)
    return Resolved(
        species_ids=ids,
        valence=tuple(s["valence"] for s in species),
        cell_id=cell["id"],
        bath_id=bath["id"],
        membrane_id=membrane["id"],
        volume_pL=cell["volume_pL"],
        area_m2=membrane["area_m2"],
        specific_capacitance_F_per_m2=membrane["specific_capacitance_F_per_m2"],
        temperature_K=bath["temperature_K"],
        initial_amount_fmol=aligned(cell["initial_amount_fmol"], "initial amounts"),
        bath_mM=aligned(bath["concentration_mM"], "bath concentrations"),
        permeability_m_per_s=aligned(passive["permeability_m_per_s"], "permeabilities"),
        fixed_charge_equivalent_fmol=cell["fixed_charge_equivalent_fmol"],
        initial_voltage_V=cell["initial_voltage_V"],
        bath_background_charge_mM=bath["background_charge_mM"],
        pump_id=None if pump is None else pump["id"],
        pump_roles=roles,
        stoichiometry=stoichiometry,
        capacity_fmol_per_s=0.0 if pump is None else pump["capacity_fmol_per_s"],
        drive_J_per_mol=0.0 if pump is None else pump["drive_J_per_mol"],
    )


def dimensionless_voltage(z, voltage, temperature):
    if type(z) is not int or z not in VALENCES:
        raise ValueError("Unsupported valence")
    number(voltage, "voltage")
    number(temperature, "temperature", positive=True)
    thermal = number(R * temperature, "thermal energy", positive=True)
    x = number(z * F * voltage / thermal, "dimensionless voltage")
    if abs(x) > MAX_ABS_X:
        raise ValueError("Voltage exceeds abs(z F V / R T) <= 50")
    return x


def bernoulli(x):
    number(x, "Bernoulli argument")
    if abs(x) > MAX_ABS_X:
        raise ValueError("Bernoulli argument outside the reference domain")
    if abs(x) < 1e-4:
        return 1.0 - x / 2.0 + x * x / 12.0 - x**4 / 720.0
    return x / math.expm1(x)


def passive_flux(z, ci, co, voltage, temperature, area, permeability, control=1.0):
    for name, value in (("inside concentration", ci), ("bath concentration", co), ("area", area)):
        number(value, name, positive=True)
    number(permeability, "permeability", nonnegative=True)
    number(control, "passive control", nonnegative=True)
    if control > 1:
        raise ValueError("Passive control must lie in [0, 1]")
    x = dimensionless_voltage(z, voltage, temperature)
    if permeability == 0 or control == 0:
        return 0.0
    return number(
        area * permeability * control / MOL_PER_FMOL * (co * bernoulli(x) - ci * bernoulli(-x)),
        "passive flux",
    )


def potential(z, ci, co, voltage, temperature):
    number(ci, "inside concentration", positive=True)
    number(co, "bath concentration", positive=True)
    dimensionless_voltage(z, voltage, temperature)
    return number(R * temperature * (math.log(ci) - math.log(co)) + z * F * voltage, "potential")


@dataclass(frozen=True)
class Instantaneous:
    voltage_V: float
    concentration_mM: tuple[float, ...]
    potential_J_per_mol: tuple[float, ...]
    passive_fmol_per_s: tuple[float, ...]
    pump_species_fmol_per_s: tuple[float, ...]
    amount_rate_fmol_per_s: tuple[float, ...]
    bath_rate_fmol_per_s: tuple[float, ...]
    pump_cycles_fmol_per_s: float
    cycle_energy_J_per_mol: float | None
    inward_current_A: float
    voltage_rate_V_per_s: float
    passive_dissipation_W: tuple[float, ...]
    pump_dissipation_W: float
    chemical_power_W: float
    stored_energy_rate_W: float


def pump_cycle(p, mu, control=1.0):
    values = vector(mu, len(p.species_ids), "electrochemical potentials")
    number(control, "pump control", nonnegative=True)
    if control > 1:
        raise ValueError("Pump control must lie in [0, 1]")
    if p.pump_id is None:
        return 0.0, None
    energy = number(
        p.drive_J_per_mol
        + finite_sum(
            (nu * m for nu, m in zip(p.stoichiometry, values, strict=True)),
            "pump transport energy",
        ),
        "cycle energy",
    )
    rate = number(
        p.capacity_fmol_per_s
        * control
        * math.tanh(
            number(
                -energy / number(2 * R * p.temperature_K, "pump thermal scale", positive=True),
                "pump affinity",
            )
        ),
        "pump rate",
    )
    return rate, energy


def evaluate(p, amount=None, *, leak_control=None, pump_control=1.0):
    n = (
        p.initial_amount_fmol
        if amount is None
        else vector(amount, len(p.species_ids), "amounts", positive=True)
    )
    controls = (
        (1.0,) * len(n)
        if leak_control is None
        else vector(leak_control, len(n), "leak controls", nonnegative=True)
    )
    number(pump_control, "pump control", nonnegative=True)
    if pump_control > 1 or any(u > 1 for u in controls):
        raise ValueError("Controls must lie in [0, 1]")
    voltage = p.voltage(n)
    ci = tuple(number(a / p.volume_pL, "concentration", positive=True) for a in n)
    passive, mu = [], []
    for z, inside, outside, permeability, control in zip(
        p.valence, ci, p.bath_mM, p.permeability_m_per_s, controls, strict=True
    ):
        passive.append(
            passive_flux(
                z, inside, outside, voltage, p.temperature_K, p.area_m2, permeability, control
            )
        )
        mu.append(potential(z, inside, outside, voltage, p.temperature_K))
    rate, cycle_energy = pump_cycle(p, mu, pump_control)
    pump_species = tuple(number(nu * rate, "pump species rate") for nu in p.stoichiometry)
    total = tuple(number(j + k, "amount rate") for j, k in zip(passive, pump_species, strict=True))
    current = number(
        CHARGE_PER_FMOL
        * finite_sum((z * j for z, j in zip(p.valence, total, strict=True)), "inward charge rate"),
        "inward current",
    )
    voltage_rate = number(current / p.capacitance_F, "voltage rate")
    passive_dissipation = tuple(
        number(-MOL_PER_FMOL * j * m, "passive dissipation")
        for j, m in zip(passive, mu, strict=True)
    )
    pump_dissipation = (
        0.0
        if cycle_energy is None
        else number(-MOL_PER_FMOL * rate * cycle_energy, "pump dissipation")
    )
    chemical_power = number(-MOL_PER_FMOL * p.drive_J_per_mol * rate, "chemical power")
    chemical_rate = number(
        MOL_PER_FMOL
        * R
        * p.temperature_K
        * finite_sum(
            ((math.log(a) - math.log(b)) * j for a, b, j in zip(ci, p.bath_mM, total, strict=True)),
            "relative chemical energy rate",
        ),
        "relative chemical power",
    )
    stored_rate = number(chemical_rate + p.capacitance_F * voltage * voltage_rate, "energy rate")
    return Instantaneous(
        voltage,
        ci,
        tuple(mu),
        tuple(passive),
        pump_species,
        total,
        tuple(-j for j in total),
        rate,
        cycle_energy,
        current,
        voltage_rate,
        passive_dissipation,
        pump_dissipation,
        chemical_power,
        stored_rate,
    )


def ledger_residuals(p, amount, passive_fmol, pump_cycles_fmol):
    """Check supplied algebraic state/ledgers; never take a numerical timestep."""
    n = vector(amount, len(p.species_ids), "amounts", positive=True)
    leak = vector(passive_fmol, len(n), "passive ledger")
    cycles = number(pump_cycles_fmol, "cycle ledger")
    if p.pump_id is None and cycles != 0:
        raise ValueError("An absent pump cannot own a nonzero cycle ledger")
    transfer = tuple(
        number(transfer + nu * cycles, "total transfer")
        for transfer, nu in zip(leak, p.stoichiometry, strict=True)
    )
    residual = tuple(
        number(a - b - d, "material residual")
        for a, b, d in zip(n, p.initial_amount_fmol, transfer, strict=True)
    )
    ledger_voltage = number(
        CHARGE_PER_FMOL
        / p.capacitance_F
        * finite_sum((z * d for z, d in zip(p.valence, transfer, strict=True)), "ledger charge"),
        "ledger voltage",
    )
    return {
        "material_residual_fmol": residual,
        "charge_residual_V": p.voltage(n) - p.initial_voltage_V - ledger_voltage,
        "bath_exchange_fmol": tuple(-d for d in transfer),
    }
