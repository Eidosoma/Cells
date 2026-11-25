"""The store world of SPEC.md section 3: its equations, its integration and its observables, in decimal arithmetic.

The unknowns are the movers' own transfers since t = 0 (fmol), the two gates, and each mover's heat and work since t = 0
(pJ). Amounts follow from the transfers by whole-number coefficients, and voltages from the charge those transfers carry. So
matter and charge are conserved by construction, a small change of a large pool keeps all its digits, and the cumulative
quantities of SPEC.md come out of the same integration.

No splitting: all movers act together at every instant. The integrator and its settings are `SETTINGS`.
"""

import copy
import sys
from decimal import Decimal, getcontext
from pathlib import Path

if __package__:
    from . import forms, integrators
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import forms
    import integrators

ZERO = Decimal(0)
ONE = Decimal(1)

# How the published values are made. `accuracy_study.py` shows what these settings reach.
SETTINGS = {"digits": 40, "steps_per_interval": 2, "columns": 12}

NODES = ("cell", "store", "outside")

# The movers' transfers, in the order of the unknowns: (mover, label). The label is the species a constant-field mover moves,
# "cycles" for a pump or the exchanger, and the site for a reaction.
TRANSFERS = (
    ("plasma_permeability", "Na"),
    ("plasma_permeability", "K"),
    ("plasma_permeability", "Cl"),
    ("bounding_permeability", "K"),
    ("bounding_permeability", "Cl"),
    ("plasma_leak", "Ca"),
    ("store_leak", "Ca"),
    ("release", "Ca"),
    ("calcium_channel", "Ca"),
    ("plasma_pump", "cycles"),
    ("store_pump", "cycles"),
    ("exchanger", "cycles"),
    ("bind_first", "cell"),
    ("bind_first", "store"),
    ("bind_second", "cell"),
    ("bind_second", "store"),
)
GATES = ("m", "h")
WORKS = ("plasma_pump", "store_pump")

N_TRANSFERS = len(TRANSFERS)
N_DYNAMIC = N_TRANSFERS + len(GATES)
N_HEATS = N_TRANSFERS
N_WORKS = len(WORKS)
N_UNKNOWNS = N_DYNAMIC + N_HEATS + N_WORKS

# The material block of SPEC.md section 3.
MATERIAL_ROWS = (("cell", "Ca"), ("store", "Ca"), ("outside", "Ca"), ("cell", "Na"), ("outside", "Na"))

VARIANTS = ("store_world", "store_world_without_buffers")

_PERCENT = "constants_one_percent: "

# Where each constant of the `constants_one_percent` control is in `store_world`.
_CONSTANT_PATHS = {
    "plasma permeability K": ("patches", "plasma", "permeability_m_per_s", "K"),
    "bounding permeability K": ("patches", "bounding", "permeability_m_per_s", "K"),
    "plasma_leak permeability": ("calcium_routes", "plasma_leak", "permeability_m_per_s"),
    "store_leak permeability": ("calcium_routes", "store_leak", "permeability_m_per_s"),
    "release permeability": ("calcium_routes", "release", "permeability_m_per_s"),
    "channel max_permeability": ("calcium_channel", "max_permeability_m_per_s"),
    "plasma_pump capacity": ("pumps", "plasma_pump", "capacity_fmol_per_s"),
    "store_pump capacity": ("pumps", "store_pump", "capacity_fmol_per_s"),
    "exchanger capacity": ("exchanger", "capacity_fmol_per_s"),
    "bind_first forward_rate": ("buffers", "reactions", "bind_first", "forward_rate_per_s"),
    "bind_second forward_rate": ("buffers", "reactions", "bind_second", "forward_rate_per_s"),
    "release_calcium activation half_saturation": (
        "conditions", "release_calcium", "reads", "activation", "half_saturation_mM",
    ),
    "release_ip3 half_saturation": ("conditions", "release_ip3", "reads", "activation", "half_saturation_mM"),
    "plasma capacitance": ("patches", "plasma", "capacitance_F"),
    "bounding capacitance": ("patches", "bounding", "capacitance_F"),
}


def control_names(inputs):
    """Every control of `inputs.json`, by the name `store_world` takes: 2 changes of a law and 15 of a constant."""
    names = []
    for control in inputs["store_world"]["controls"]["list"]:
        if control["id"] == "constants_one_percent":
            names += [_PERCENT + constant for constant in control["constants"]]
        else:
            names.append(control["id"])
    return names


def _raise_by_one_percent(world, constant):
    """A copy of the `store_world` mapping with one constant at 1.01 times its number, exactly."""
    changed = copy.deepcopy(world)
    place = changed
    path = _CONSTANT_PATHS[constant]
    for key in path[:-1]:
        if isinstance(place, list):
            # a reaction by its id, a read by its form: exactly one entry carries it
            (place,) = [item for item in place if key in (item.get("id"), item.get("form"))]
        else:
            place = place[key]
    place[path[-1]] = Decimal(place[path[-1]]) * Decimal("1.01")
    return changed


class StoreWorld:
    """One variant of the store world, with at most one control. Use it inside `forms.working(digits)`."""

    def __init__(self, inputs, variant, control=None):
        if variant not in VARIANTS:
            raise ValueError(f"unknown variant {variant!r}")
        world = inputs["store_world"]
        if control is not None and control not in control_names(inputs):
            raise ValueError(f"unknown control {control!r}")
        if control is not None and control.startswith(_PERCENT):
            world = _raise_by_one_percent(world, control[len(_PERCENT):])
        self.variant, self.control = variant, control
        self.release_sign = -1 if control == "release_sign" else 1
        self.pumps_see_voltage = control != "pump_without_voltage"
        self.reactions_run = variant == "store_world"

        exact = forms.exact
        if exact(world["standard_concentration_mM"]) != 1:
            raise ValueError("SPEC.md section 1 has c0 = 1 mM")
        self.temperature = exact(world["temperature_K"])
        self.rt = forms.GAS_CONSTANT * self.temperature
        self.valence = {species: Decimal(z) for species, z in world["valence"].items()}
        self.volume = {node: exact(world["nodes"][node]["volume_pL"]) for node in NODES}
        self.initial = {
            (node, species): exact(amount)
            for node in NODES
            for species, amount in world["nodes"][node]["amounts_fmol"].items()
        }
        self.rows = tuple(self.initial)

        patches = world["patches"]
        if (patches["plasma"]["inside"], patches["plasma"]["outside"]) != ("cell", "outside"):
            raise ValueError("the plasma patch is not between the cell and the outside")
        if (patches["bounding"]["inside"], patches["bounding"]["outside"]) != ("cell", "store"):
            raise ValueError("the bounding patch is not between the cell and the store")
        self.area = {patch: exact(patches[patch]["area_m2"]) for patch in patches}
        self.capacitance = {patch: exact(patches[patch]["capacitance_F"]) for patch in patches}
        self.initial_voltage = {patch: exact(patches[patch]["initial_voltage_V"]) for patch in patches}
        if exact(world["variants"][variant]["bounding_initial_voltage_V"]) != self.initial_voltage["bounding"]:
            raise ValueError("the variant's bounding voltage differs from the patch's")
        self.permeability = {
            patch: {species: exact(P) for species, P in patches[patch]["permeability_m_per_s"].items()}
            for patch in patches
        }
        self.route = {name: exact(route["permeability_m_per_s"]) for name, route in world["calcium_routes"].items()}
        self.conditions = {}
        for name, condition in world["conditions"].items():
            if condition["node"] != "cell":
                raise ValueError("a condition of SPEC.md section 3 reads the cell")
            self.conditions[name] = [
                (read["species"], exact(read["half_saturation_mM"]), exact(read["hill_coefficient"]), read["form"])
                for read in condition["reads"]
            ]
        self.release_factors = tuple(world["calcium_routes"]["release"]["factors"])
        channel = world["calcium_channel"]
        self.channel_permeability = exact(channel["max_permeability_m_per_s"])
        self.channel_abundance = exact(channel["abundance"])
        self.initial_gates = (exact(channel["initial_m"]), exact(channel["initial_h"]))
        fuel_mu = {species: exact(mu) for species, mu in world["fuel_potentials_RT"].items()}
        self.pumps = {}
        for name, far_node in (("plasma_pump", "outside"), ("store_pump", "store")):
            pump = world["pumps"][name]
            if (pump["N"], pump["P"]) != ("cell", far_node):
                raise ValueError(f"{name} does not run from the cell to the {far_node}")
            self.pumps[name] = {
                "patch": pump["patch"],
                "far_node": far_node,
                "capacity": exact(pump["capacity_fmol_per_s"]),
                "n": Decimal(pump["stoichiometry"]),
                "K_role": exact(pump["K_role_mM"]),
                "K_atp": exact(pump["K_ATP_mM"]),
                "mu_atp": fuel_mu["ATP"],
                "mu_adp": fuel_mu["ADP"],
                "mu_pi": fuel_mu["Pi"],
            }
        exchanger = world["exchanger"]
        if (exchanger["N"], exchanger["P"]) != ("cell", "outside"):
            raise ValueError("the exchanger does not run between the cell and the outside")
        self.exchanger = {
            "K_Na": exact(exchanger["K_Na_mM"]),
            "K_Ca": exact(exchanger["K_Ca_mM"]),
            "capacity": exact(exchanger["capacity_fmol_per_s"]),
            "availability": ONE,
        }
        buffers = world["buffers"]
        self.mu = {species: exact(mu) for species, mu in buffers["standard_mu_RT"].items()}
        self.mu.update(fuel_mu)
        if tuple(buffers["sites"]) != ("cell", "store"):
            raise ValueError("the buffers' sites are not the cell and the store")
        self.reactions = {}
        for item in buffers["reactions"]:
            if set(item["reactants"].values()) | set(item["products"].values()) != {1}:
                raise ValueError("a reaction of SPEC.md section 2.7 has unit coefficients")
            reactants, products = tuple(item["reactants"]), tuple(item["products"])
            delta_mu = sum((self.mu[s] for s in products), ZERO) - sum((self.mu[s] for s in reactants), ZERO)
            self.reactions[item["id"]] = (reactants, products, exact(item["forward_rate_per_s"]), delta_mu)

        self.charge_coulomb = forms.FEMTO * forms.FARADAY  # of one fmol of unit charge
        self._stoichiometry = self._make_stoichiometry()
        self.fixed_charge = self._make_fixed_charges()

    # Amounts, charges and voltages

    def _make_stoichiometry(self):
        """For each row that moves, its (transfer index, whole number) pairs."""
        table = {}

        def add(row, index, coefficient):
            table.setdefault(row, []).append((index, Decimal(coefficient)))

        for index, (mover, label) in enumerate(TRANSFERS):
            if mover in ("plasma_permeability", "plasma_leak", "calcium_channel"):
                add(("cell", label), index, -1)
                add(("outside", label), index, 1)
            elif mover in ("bounding_permeability", "store_leak"):
                add(("cell", label), index, -1)
                add(("store", label), index, 1)
            elif mover == "release":  # positive from the store into the cell
                add(("store", label), index, -1)
                add(("cell", label), index, 1)
            elif mover in self.pumps:
                pump = self.pumps[mover]
                add(("cell", "Ca"), index, -pump["n"])
                add((pump["far_node"], "Ca"), index, pump["n"])
            elif mover == "exchanger":
                add(("cell", "Na"), index, 3)
                add(("outside", "Na"), index, -3)
                add(("cell", "Ca"), index, -1)
                add(("outside", "Ca"), index, 1)
            else:
                reactants, products, _k, _mu = self.reactions[mover]
                for species in reactants:
                    add((label, species), index, -1)
                for species in products:
                    add((label, species), index, 1)
        missing = [row for row in table if row not in self.initial]
        if missing:
            raise ValueError(f"a mover reaches rows that are not there: {missing}")
        return table

    def changes(self, y):
        """Each row's amount less its initial amount (fmol)."""
        result = {row: ZERO for row in self.rows}
        for row, pairs in self._stoichiometry.items():
            result[row] = sum((coefficient * y[index] for index, coefficient in pairs), ZERO)
        return result

    def voltage_changes(self, changes):
        """(V_m, V_b) less their initial values (V), from the charge moved since t = 0."""
        cell = sum((self.valence[s] * d for (node, s), d in changes.items() if node == "cell"), ZERO)
        store = sum((self.valence[s] * d for (node, s), d in changes.items() if node == "store"), ZERO)
        return (
            self.charge_coulomb * (cell + store) / self.capacitance["plasma"],
            -self.charge_coulomb * store / self.capacitance["bounding"],
        )

    def _make_fixed_charges(self):
        """X_v of SPEC.md section 2.8 (fmol of unit charge), so that the charges at t = 0 give the declared voltages."""
        q_store = -self.capacitance["bounding"] * self.initial_voltage["bounding"]
        q_cell = self.capacitance["plasma"] * self.initial_voltage["plasma"] - q_store
        charge = {"cell": q_cell, "store": q_store, "outside": -(q_cell + q_store)}
        return {
            node: charge[node] / self.charge_coulomb
            - sum((self.valence[s] * n for (where, s), n in self.initial.items() if where == node), ZERO)
            for node in NODES
        }

    # The rates

    def initial_unknowns(self):
        return [ZERO] * N_TRANSFERS + list(self.initial_gates) + [ZERO] * (N_HEATS + N_WORKS)

    def concentrations(self, changes):
        return {row: (self.initial[row] + changes[row]) / self.volume[row[0]] for row in self.rows}

    def condition_factors(self, c):
        """The factor of each condition at the cell's present concentrations."""
        return {
            name: forms.condition_factor([(c["cell", species], K, n, form) for species, K, n, form in reads])
            for name, reads in self.conditions.items()
        }

    def release_opening(self, c):
        opening = ONE
        factors = self.condition_factors(c)
        for name in self.release_factors:
            opening *= factors[name]
        return opening

    def rates(self, y):
        """(transfer rates, gate rates, heat rates, work rates): lists in the order of the unknowns."""
        changes = self.changes(y)
        dV_m, dV_b = self.voltage_changes(changes)
        voltage = {"plasma": self.initial_voltage["plasma"] + dV_m, "bounding": self.initial_voltage["bounding"] + dV_b}
        c = self.concentrations(changes)
        m, h = y[N_TRANSFERS], y[N_TRANSFERS + 1]
        transfer_rates, heat_rates, work_rates = [], [], []
        for mover, label in TRANSFERS:
            if mover in self.reactions:
                rate, heat = self._reaction(mover, label, c)
            elif mover in self.pumps:
                cycle = self._pump(mover, c, voltage)
                rate, heat = cycle["J"], cycle["heat_rate"]
                work_rates.append(cycle["work_rate"])
            elif mover == "exchanger":
                cycle = self._exchanger(c, voltage)
                rate, heat = cycle["J"], cycle["heat_rate"]
            else:
                rate, heat = self._constant_field(mover, label, c, voltage, m, h)
            transfer_rates.append(rate)
            heat_rates.append(heat)
        return transfer_rates, list(forms.channel_gate_rates(voltage["plasma"], m, h)), heat_rates, work_rates

    def route_of(self, mover, label, c, m, h):
        """(patch, far node, permeability, opening) of a constant-field mover."""
        if mover == "plasma_permeability":
            return "plasma", "outside", self.permeability["plasma"][label], ONE
        if mover == "bounding_permeability":
            return "bounding", "store", self.permeability["bounding"][label], ONE
        if mover == "plasma_leak":
            return "plasma", "outside", self.route["plasma_leak"], ONE
        if mover == "store_leak":
            return "bounding", "store", self.route["store_leak"], ONE
        if mover == "release":
            return "bounding", "store", self.route["release"], self.release_opening(c)
        if mover == "calcium_channel":
            return "plasma", "outside", self.channel_permeability, self.channel_abundance * m * m * h
        raise ValueError(mover)

    def _constant_field(self, mover, label, c, voltage, m, h):
        patch, far_node, permeability, opening = self.route_of(mover, label, c, m, h)
        flux, heat = forms.constant_field(
            valence=self.valence[label],
            temperature=self.temperature,
            voltage=voltage[patch],
            area=self.area[patch],
            permeability=permeability,
            opening=opening,
            c_inside=c["cell", label],
            c_outside=c[far_node, label],
        )
        if mover == "release":  # reported from the store into the cell; `release_sign` turns the flux and its heat
            return -self.release_sign * flux, self.release_sign * heat
        return flux, heat

    def _pump(self, mover, c, voltage):
        pump = self.pumps[mover]
        return forms.pump_cycle(
            temperature=self.temperature,
            z=self.valence["Ca"],
            n=pump["n"],
            c_N=c["cell", "Ca"],
            c_P=c[pump["far_node"], "Ca"],
            atp=c["cell", "ATP"],
            adp=c["cell", "ADP"],
            pi=c["cell", "Pi"],
            mu_atp=pump["mu_atp"],
            mu_adp=pump["mu_adp"],
            mu_pi=pump["mu_pi"],
            K_role=pump["K_role"],
            K_atp=pump["K_atp"],
            capacity=pump["capacity"],
            availability=ONE,
            V_NP=voltage[pump["patch"]],
            with_voltage=self.pumps_see_voltage,
        )

    def _exchanger(self, c, voltage):
        return forms.exchanger_cycle(
            temperature=self.temperature,
            Na_N=c["cell", "Na"],
            Na_P=c["outside", "Na"],
            Ca_N=c["cell", "Ca"],
            Ca_P=c["outside", "Ca"],
            V_NP=voltage["plasma"],
            **self.exchanger,
        )

    def _reaction(self, mover, site, c):
        if not self.reactions_run:
            return ZERO, ZERO
        reactants, products, rate_constant, delta_mu = self.reactions[mover]
        return forms.reaction(
            temperature=self.temperature,
            volume=self.volume[site],
            rate_constant=rate_constant,
            reactants=[c[site, s] for s in reactants],
            products=[c[site, s] for s in products],
            delta_mu=delta_mu,
        )

    def derivative(self, unknowns):
        """The rates of change of all the unknowns."""
        transfer_rates, gate_rates, heat_rates, work_rates = self.rates(unknowns)
        return transfer_rates + gate_rates + heat_rates + work_rates

    def dynamic_derivative(self, y):
        """The rates of change of the transfers and the gates, which do not read the heats and works."""
        transfer_rates, gate_rates, _heats, _works = self.rates(y)
        return transfer_rates + gate_rates

    def dissipation(self, y):
        """The heat and work rates (pJ/s), in the order of the unknowns."""
        _transfers, _gates, heat_rates, work_rates = self.rates(y)
        return heat_rates + work_rates

    # The solution

    def times(self, inputs):
        times = [forms.exact(t) for t in inputs["store_world"]["times_s"]]
        if times[0] != 0:
            raise ValueError("the first time is not 0")
        return times

    def solve(self, times, steps_per_interval=None, columns=None):
        """The unknowns at each of `times`, by the settings of the published values."""
        return integrators.extrapolated_midpoint(
            self.derivative,
            self.initial_unknowns(),
            times,
            steps_per_interval or SETTINGS["steps_per_interval"],
            columns or SETTINGS["columns"],
        )

    # What SPEC.md section 3 asks

    def capacitor_energy(self, V_m, V_b):
        """pJ."""
        return Decimal("1e12") * (
            self.capacitance["plasma"] * V_m**2 / 2 + self.capacitance["bounding"] * V_b**2 / 2
        )

    def free_energy(self, changes, V_m, V_b):
        """G of SPEC.md section 3, observable 4 (pJ): every row of every node, the constant ones too."""
        total = ZERO
        for row in self.rows:
            n = self.initial[row] + changes[row]
            c = n / self.volume[row[0]]
            total += n * (c.ln() - 1 + self.mu.get(row[1], ZERO))
        return forms.PICO_FROM_RATE * self.rt * total + self.capacitor_energy(V_m, V_b)

    def observables(self, times, values):
        """The observables 1 to 4 of SPEC.md section 3 at each time, as nested mappings of lists of Decimals."""
        V_m0, V_b0 = self.initial_voltage["plasma"], self.initial_voltage["bounding"]
        out = {
            "times_s": list(times),
            "amounts_fmol": {},
            "amount_changes_fmol": {},
            "V_m_V": [],
            "V_b_V": [],
            "V_m_change_V": [],
            "V_b_change_V": [],
            "m": [],
            "h": [],
            "transfers_fmol": {},
            "heats_pJ": {},
            "works_pJ": {name: [] for name in WORKS},
            "capacitor_energy_pJ": [],
            "capacitor_energy_change_pJ": [],
            "free_energy_pJ": [],
            "free_energy_change_pJ": [],
            "heat_total_pJ": [],
            "work_total_pJ": [],
        }
        for node, species in self.rows:
            out["amounts_fmol"].setdefault(node, {})[species] = []
            out["amount_changes_fmol"].setdefault(node, {})[species] = []
        for mover, label in TRANSFERS:
            out["transfers_fmol"].setdefault(mover, {})[label] = []
            out["heats_pJ"].setdefault(mover, {})[label] = []
        for mover in ("plasma_permeability", "bounding_permeability", "bind_first", "bind_second"):
            out["heats_pJ"][mover]["total"] = []
        first_energy = first_free = None
        for y in values:
            changes = self.changes(y)
            dV_m, dV_b = self.voltage_changes(changes)
            V_m, V_b = V_m0 + dV_m, V_b0 + dV_b
            for node, species in self.rows:
                out["amounts_fmol"][node][species].append(self.initial[node, species] + changes[node, species])
                out["amount_changes_fmol"][node][species].append(changes[node, species])
            out["V_m_V"].append(V_m)
            out["V_b_V"].append(V_b)
            out["V_m_change_V"].append(dV_m)
            out["V_b_change_V"].append(dV_b)
            out["m"].append(y[N_TRANSFERS])
            out["h"].append(y[N_TRANSFERS + 1])
            sums = {}
            heats = y[N_DYNAMIC:N_DYNAMIC + N_HEATS]
            works = y[N_DYNAMIC + N_HEATS:]
            for (mover, label), transfer, heat in zip(TRANSFERS, y, heats):
                out["transfers_fmol"][mover][label].append(transfer)
                out["heats_pJ"][mover][label].append(heat)
                sums[mover] = sums.get(mover, ZERO) + heat
            for mover, total in sums.items():
                if "total" in out["heats_pJ"][mover]:
                    out["heats_pJ"][mover]["total"].append(total)
            for name, work in zip(WORKS, works):
                out["works_pJ"][name].append(work)
            energy, free = self.capacitor_energy(V_m, V_b), self.free_energy(changes, V_m, V_b)
            if first_energy is None:
                first_energy, first_free = energy, free
            out["capacitor_energy_pJ"].append(energy)
            out["capacitor_energy_change_pJ"].append(energy - first_energy)
            out["free_energy_pJ"].append(free)
            out["free_energy_change_pJ"].append(free - first_free)
            out["heat_total_pJ"].append(sum(heats, ZERO))
            out["work_total_pJ"].append(sum(works, ZERO))
        return out

    def initial_rates(self):
        """What SPEC.md section 3 asks at t = 0."""
        y = self.initial_unknowns()
        transfer_rates, gate_rates, heat_rates, work_rates = self.rates(y)
        rate_of_change = self.changes(transfer_rates)  # linear, so it maps rates to rates
        dV_m, dV_b = self.voltage_changes(rate_of_change)
        out = {
            "rates_fmol_per_s": {},
            "heat_rates_pJ_per_s": {},
            "work_rates_pJ_per_s": dict(zip(WORKS, work_rates)),
            "condition_factors": self.condition_factors(self.concentrations(self.changes(y))),
            "release_opening": None,
            "dV_m_dt_V_per_s": dV_m,
            "dV_b_dt_V_per_s": dV_b,
            "dm_dt_per_s": gate_rates[0],
            "dh_dt_per_s": gate_rates[1],
            "amount_rates_fmol_per_s": {},
            "fixed_charges_fmol": dict(self.fixed_charge),
        }
        opening = ONE
        for name in self.release_factors:
            opening *= out["condition_factors"][name]
        out["release_opening"] = opening
        for (mover, label), rate, heat in zip(TRANSFERS, transfer_rates, heat_rates):
            out["rates_fmol_per_s"].setdefault(mover, {})[label] = rate
            out["heat_rates_pJ_per_s"].setdefault(mover, {})[label] = heat
        for mover in ("plasma_permeability", "bounding_permeability", "bind_first", "bind_second"):
            labels = out["heat_rates_pJ_per_s"][mover]
            labels["total"] = sum(labels.values(), ZERO)
        for node, species in self.rows:
            out["amount_rates_fmol_per_s"].setdefault(node, {})[species] = rate_of_change[node, species]
        return out

    # The material block

    def material_block(self, y):
        """The two 5 x 5 Jacobians of SPEC.md section 3 at the unknowns y, with their eigenvalues."""
        out = {"rows": [list(row) for row in MATERIAL_ROWS]}
        for name, opening_moves in (("release_opening_moving", True), ("release_opening_held", False)):
            matrix = self.material_jacobian(y, opening_moves)
            eigenvalues = material_eigenvalues(matrix)
            out[name] = {
                "jacobian_per_s": matrix,
                "eigenvalues_per_s": [list(pair) for pair in eigenvalues],
                "largest_modulus_per_s": max((a * a + b * b).sqrt() for a, b in eigenvalues),
            }
        return out

    def _state(self, y):
        changes = self.changes(y)
        dV_m, dV_b = self.voltage_changes(changes)
        voltage = {"plasma": self.initial_voltage["plasma"] + dV_m, "bounding": self.initial_voltage["bounding"] + dV_b}
        return changes, voltage, self.concentrations(changes)

    def material_jacobian(self, y, opening_moves):
        """dg/dy (1/s) in the order of MATERIAL_ROWS, the potentials and the gates held, from the slopes of the laws."""
        _changes, voltage, c = self._state(y)
        m, h = y[N_TRANSFERS], y[N_TRANSFERS + 1]
        index = {row: i for i, row in enumerate(MATERIAL_ROWS)}
        matrix = [[ZERO] * len(MATERIAL_ROWS) for _ in MATERIAL_ROWS]

        def add(moves, slopes):
            """`moves`: row -> units gained per unit of rate. `slopes`: row -> d rate/d concentration (fmol/s per mM)."""
            for gained, units in moves.items():
                for read, slope in slopes.items():
                    matrix[index[gained]][index[read]] += units * slope / self.volume[read[0]]

        for mover in ("plasma_leak", "store_leak", "release", "calcium_channel"):
            patch, far_node, permeability, opening = self.route_of(mover, "Ca", c, m, h)
            near, far = ("cell", "Ca"), (far_node, "Ca")
            arguments = {
                "valence": self.valence["Ca"],
                "temperature": self.temperature,
                "voltage": voltage[patch],
                "area": self.area[patch],
                "permeability": permeability,
                "opening": opening,
            }
            inside, outside = forms.constant_field_slopes(**arguments)
            slopes = {near: inside, far: outside}
            if mover == "release" and opening_moves:
                flux, _heat = forms.constant_field(c_inside=c[near], c_outside=c[far], **arguments)
                for name in self.release_factors:
                    reads = self.conditions[name]
                    log_slope = forms.condition_log_slope(
                        [(c["cell", species], K, n, form) for species, K, n, form in reads],
                        [species == "Ca" for species, _K, _n, _form in reads],
                    )
                    slopes[near] += flux * log_slope / c[near]
            sign = self.release_sign if mover == "release" else 1
            add({near: -sign, far: sign}, slopes)
        for mover, pump in self.pumps.items():
            near, far = ("cell", "Ca"), (pump["far_node"], "Ca")
            cycle = self._pump(mover, c, voltage)
            slope_N, slope_P = forms.pump_slopes(cycle, n=pump["n"], c_N=c[near], c_P=c[far], K_role=pump["K_role"])
            add({near: -pump["n"], far: pump["n"]}, {near: slope_N, far: slope_P})
        slopes = forms.exchanger_slopes(self._exchanger(c, voltage), **self.exchanger)
        add(
            {("cell", "Na"): Decimal(3), ("outside", "Na"): Decimal(-3), ("cell", "Ca"): -ONE, ("outside", "Ca"): ONE},
            {
                ("cell", "Na"): slopes["Na_N"],
                ("outside", "Na"): slopes["Na_P"],
                ("cell", "Ca"): slopes["Ca_N"],
                ("outside", "Ca"): slopes["Ca_P"],
            },
        )
        return matrix

    def material_rates(self, y, amounts, opening):
        """g at the five amounts (fmol/s), the potentials and gates of y held; an `opening` of None moves with Ca."""
        _changes, voltage, c = self._state(y)
        for row, amount in zip(MATERIAL_ROWS, amounts):
            c[row] = amount / self.volume[row[0]]
        m, h = y[N_TRANSFERS], y[N_TRANSFERS + 1]
        g = {row: ZERO for row in MATERIAL_ROWS}
        for mover in ("plasma_leak", "store_leak", "release", "calcium_channel"):
            patch, far_node, permeability, present = self.route_of(mover, "Ca", c, m, h)
            if mover == "release" and opening is not None:
                present = opening
            flux, _heat = forms.constant_field(
                valence=self.valence["Ca"],
                temperature=self.temperature,
                voltage=voltage[patch],
                area=self.area[patch],
                permeability=permeability,
                opening=present,
                c_inside=c["cell", "Ca"],
                c_outside=c[far_node, "Ca"],
            )
            if mover == "release":
                flux *= self.release_sign
            g["cell", "Ca"] -= flux
            g[far_node, "Ca"] += flux
        for mover, pump in self.pumps.items():
            moved = pump["n"] * self._pump(mover, c, voltage)["J"]
            g["cell", "Ca"] -= moved
            g[pump["far_node"], "Ca"] += moved
        J = self._exchanger(c, voltage)["J"]
        g["cell", "Na"] += 3 * J
        g["outside", "Na"] -= 3 * J
        g["cell", "Ca"] -= J
        g["outside", "Ca"] += J
        return [g[row] for row in MATERIAL_ROWS]

    def material_amounts(self, y):
        changes = self.changes(y)
        return [self.initial[row] + changes[row] for row in MATERIAL_ROWS]


def material_eigenvalues(matrix):
    """The five eigenvalues as (real, imaginary) pairs, by falling modulus.

    Every column of the block sums to zero over the calcium rows and over the sodium rows, because the movers conserve both.
    So two eigenvalues are exactly zero. The other three are those of the 3 x 3 block on (Ca cell, Ca store, Na cell), with
    Ca outside and Na outside taking what those three leave. They are the roots of a cubic.
    """
    reduced = [
        [matrix[0][0] - matrix[0][2], matrix[0][1] - matrix[0][2], matrix[0][3] - matrix[0][4]],
        [matrix[1][0] - matrix[1][2], matrix[1][1] - matrix[1][2], matrix[1][3] - matrix[1][4]],
        [matrix[3][0] - matrix[3][2], matrix[3][1] - matrix[3][2], matrix[3][3] - matrix[3][4]],
    ]
    (a, b, c), (d, e, f), (g, h, i) = reduced
    trace = a + e + i
    minors = (a * e - b * d) + (a * i - c * g) + (e * i - f * h)
    determinant = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    roots = cubic_roots(-trace, minors, -determinant) + [(ZERO, ZERO), (ZERO, ZERO)]
    return sorted(roots, key=lambda pair: (-(pair[0] * pair[0] + pair[1] * pair[1]), -pair[1]))


def cubic_roots(p, q, r):
    """The roots of x^3 + p x^2 + q x + r as (real, imaginary) pairs: one real root by bisection, then a quadratic."""

    def value(x):
        return ((x + p) * x + q) * x + r

    bound = 1 + abs(p) + abs(q) + abs(r)
    left, right = -bound, bound
    while True:
        middle = (left + right) / 2
        if middle in (left, right):
            break
        if value(middle) > 0:
            right = middle
        else:
            left = middle
        if right - left <= abs(middle) * Decimal(10) ** (3 - getcontext().prec):
            break
    real = (left + right) / 2
    s = p + real
    t = q + s * real
    discriminant = s * s - 4 * t
    if discriminant < 0:
        half = (-discriminant).sqrt() / 2
        return [(real, ZERO), (-s / 2, half), (-s / 2, -half)]
    root = discriminant.sqrt()
    large = (-s - root) / 2 if s > 0 else (-s + root) / 2
    small = t / large if large != 0 else ZERO
    return [(real, ZERO), (large, ZERO), (small, ZERO)]
