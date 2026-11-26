"""A second derivation of the same quantities, sharing no code with `forms.py` and `world.py`.

One idea carries it: a mover is a list of moves (units of a species gained at a node per unit of transfer) and a one-way
forward rate. Its free energy per unit over RT, `gap`, is the sum over the moves of units x (ln c + z F phi / RT + mu), plus
the fuel's part. Detailed balance gives the rest: J = forward (1 - e^gap), heat rate = -RT gap J.

- The kernel states and the world's rates at t = 0: exact fractions, with an exponential and a logarithm of their own
  (integer Taylor series, `BITS` bits), and derivatives by dual numbers instead of by hand.
- `World`: the store world in doubles, for SciPy's integrators. Its unknowns are the rows' amounts (less the initial ones),
  with the transfers, heats and works integrated beside them, and its voltages come from the node potentials.

Nothing here makes a published value. `accuracy_study.py` compares.
"""

from fractions import Fraction

import numpy

BITS = 420

N_A = Fraction("6.02214076e23")
E_CHARGE = Fraction("1.602176634e-19")
K_B = Fraction("1.380649e-23")


# An exponential and a logarithm of a fraction, by integers


def exp(q):
    """e^q for a fraction q, to about BITS bits."""
    if q < 0:
        return 1 / exp(-q)
    halvings = max(0, q.numerator.bit_length() - q.denominator.bit_length() + 1) + 16
    guard = BITS + 2 * halvings + 64
    one = 1 << guard
    r = (q.numerator << guard) // (q.denominator << halvings)
    total, term, n = one, one, 1
    while term:
        term = (term * r >> guard) // n
        total += term
        n += 1
    for _ in range(halvings):
        total = total * total >> guard
    return Fraction(total, one)


def _atanh_series(t):
    """2 atanh(t) for a fraction abs(t) <= 1/3, to about BITS bits of its own size."""
    if t == 0:
        return Fraction(0)
    if t < 0:
        return -_atanh_series(-t)
    small = max(0, t.denominator.bit_length() - t.numerator.bit_length())
    guard = BITS + small + 64
    x = (t.numerator << guard) // t.denominator
    square = x * x >> guard
    total, power, n = 0, x, 1
    while power:
        total += power // n
        power = power * square >> guard
        n += 2
    return Fraction(2 * total, 1 << guard)


def ln(q):
    """The natural logarithm of a positive fraction, to about BITS bits."""
    if q <= 0:
        raise ValueError("ln of a number that is not positive")
    k = q.numerator.bit_length() - q.denominator.bit_length()
    m = q / Fraction(2) ** k
    while m > Fraction(4, 3):
        m /= 2
        k += 1
    while m < Fraction(2, 3):
        m *= 2
        k -= 1
    return _atanh_series((m - 1) / (m + 1)) + k * _atanh_series(Fraction(1, 3))


class Dual:
    """A value and its derivative in one direction."""

    __slots__ = ("value", "slope")

    def __init__(self, value, slope=0):
        self.value, self.slope = Fraction(value), Fraction(slope)

    @staticmethod
    def of(other):
        return other if isinstance(other, Dual) else Dual(other)

    def __add__(self, other):
        other = Dual.of(other)
        return Dual(self.value + other.value, self.slope + other.slope)

    __radd__ = __add__

    def __neg__(self):
        return Dual(-self.value, -self.slope)

    def __sub__(self, other):
        return self + (-Dual.of(other))

    def __rsub__(self, other):
        return Dual.of(other) + (-self)

    def __mul__(self, other):
        other = Dual.of(other)
        return Dual(self.value * other.value, self.slope * other.value + self.value * other.slope)

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = Dual.of(other)
        quotient = self.value / other.value
        return Dual(quotient, (self.slope - quotient * other.slope) / other.value)

    def __rtruediv__(self, other):
        return Dual.of(other) / self

    def __pow__(self, n):
        n = int(n)
        result = Dual(1)
        for _ in range(abs(n)):
            result = result * self
        return result if n >= 0 else 1 / result


def dual_exp(q):
    q = Dual.of(q)
    value = exp(q.value)
    return Dual(value, value * q.slope)


# The kernel states


def _pump(values):
    """(J, forward) with any of c_N, c_P, V_NP a dual number."""
    v = values
    n, z = int(v["n"]), int(v["z"])
    c_N, c_P, V = v["c_N"], v["c_P"], v["V"]
    beta = E_CHARGE / (K_B * v["T"])
    role = c_N**n / (c_N**n + v["K_role"] ** n)
    forward = v["capacity"] * v["availability"] * role * v["atp"] / (v["atp"] + v["K_atp"])
    # e^gap as the product of its parts: the fuel's, the gradient's, the voltage's
    ratio = v["adp"] * v["pi"] / v["atp"] * (c_P / c_N) ** n
    backward = forward * ratio * dual_exp(v["mu"] - n * z * beta * V)
    return forward - backward, forward


def pump_outputs(state):
    """The same outputs as `forms.pump_outputs`, in fractions."""
    f = {key: Fraction(value) for key, value in state.items() if key not in ("tag", "z", "n")}
    base = {
        "n": state["n"],
        "z": state["z"],
        "T": f["temperature_K"],
        "c_N": Dual(f["c_N_mM"]),
        "c_P": Dual(f["c_P_mM"]),
        "V": Dual(f["V_NP_V"]),
        "K_role": f["K_role_mM"],
        "K_atp": f["K_ATP_mM"],
        "atp": f["atp_mM"],
        "adp": f["adp_mM"],
        "pi": f["pi_mM"],
        "mu": f["mu_adp_RT"] + f["mu_pi_RT"] - f["mu_atp_RT"],
        "capacity": f["capacity_fmol_per_s"],
        "availability": f["availability"],
    }
    n, z, T = state["n"], state["z"], f["temperature_K"]
    RT = N_A * K_B * T
    beta = E_CHARGE / (K_B * T)
    J, forward = _pump(base)
    fuel = base["mu"] + ln(base["adp"] * base["pi"] / base["atp"])
    # the moves: n ions leave N, n arrive at P
    gap = fuel + n * (ln(f["c_P_mM"]) - ln(f["c_N_mM"])) + n * z * beta * (0 - f["V_NP_V"])
    # S without the capacity and the availability, which may be zero
    _unused, unit_forward = _pump({**base, "capacity": Fraction(1), "availability": Fraction(1)})
    out = {
        "x": gap,
        "x_fuel": fuel,
        "S": unit_forward.value,
        "J_plus_fmol_per_s": forward.value,
        "J_fmol_per_s": J.value,
        "heat_rate_pJ_per_s": -RT * gap * J.value / 1000,
        "work_rate_pJ_per_s": -RT * fuel * J.value / 1000,
        "current_N_to_P_A": E_CHARGE * N_A * n * z * J.value / 10**15,
        "dJ_dV_NP_fmol_per_s_per_V": _pump({**base, "V": Dual(f["V_NP_V"], 1)})[0].slope,
        "dJ_dn_N_per_s": _pump({**base, "c_N": Dual(f["c_N_mM"], 1 / f["volume_N_pL"])})[0].slope,
        "dJ_dn_P_per_s": _pump({**base, "c_P": Dual(f["c_P_mM"], 1 / f["volume_P_pL"])})[0].slope,
        "move_N_fmol_per_s": -n * J.value,
        "move_P_fmol_per_s": n * J.value,
        "in_domain": -80 <= gap <= 80,
    }
    names = ("J_at_V_stall_minus_1e-6_V_fmol_per_s", "J_at_V_stall_fmol_per_s", "J_at_V_stall_plus_1e-6_V_fmol_per_s")
    if z == 0:
        out["V_stall_V"] = None
        out.update({name: None for name in names})
        out["near_V_stall"] = None
        return out
    V_stall = f["V_NP_V"] + gap / (n * z * beta)  # x falls by n z beta per volt
    out["V_stall_V"] = V_stall
    offsets = (Fraction(-1, 10**6), Fraction(0), Fraction(1, 10**6))
    for name, offset in zip(names, offsets):
        out[name] = _pump({**base, "V": Dual(V_stall + offset)})[0].value
    voltages = [Fraction(_nearest_double(V_stall + offset)) for offset in offsets]
    out["near_V_stall"] = {
        "V_NP_V": voltages,
        "J_fmol_per_s": [_pump({**base, "V": Dual(V)})[0].value for V in voltages],
    }
    return out


def _nearest_double(q):
    """The double nearest a fraction (Python rounds an integer division once)."""
    return q.numerator / q.denominator


def _exchanger(values):
    """(J, forward, backward) with any of the concentrations or the voltage a dual number."""
    v = values
    beta = E_CHARGE / (K_B * v["T"])
    half = dual_exp(beta * v["V"] / 2)
    inside, outside = v["Na_N"] / v["K_Na"], v["Na_P"] / v["K_Na"]
    ca_in, ca_out = v["Ca_N"] / v["K_Ca"], v["Ca_P"] / v["K_Ca"]
    occupancy = (1 + inside**3 + outside**3) * (1 + ca_in + ca_out)
    scale = v["capacity"] * v["availability"]
    forward = scale * (outside**3 * ca_in / half) / occupancy
    backward = scale * (inside**3 * ca_out * half) / occupancy
    return forward - backward, forward, backward


def exchanger_outputs(state):
    """The same outputs as `forms.exchanger_outputs`, in fractions."""
    f = {key: Fraction(value) for key, value in state.items() if key != "tag"}
    base = {
        "T": f["temperature_K"],
        "Na_N": Dual(f["Na_N_mM"]),
        "Na_P": Dual(f["Na_P_mM"]),
        "Ca_N": Dual(f["Ca_N_mM"]),
        "Ca_P": Dual(f["Ca_P_mM"]),
        "V": Dual(f["V_NP_V"]),
        "K_Na": f["K_Na_mM"],
        "K_Ca": f["K_Ca_mM"],
        "capacity": f["capacity_fmol_per_s"],
        "availability": f["availability"],
    }
    T = f["temperature_K"]
    RT = N_A * K_B * T
    beta = E_CHARGE / (K_B * T)
    J, _forward, _backward = _exchanger(base)
    _J, unit_forward, _b = _exchanger({**base, "capacity": Fraction(1), "availability": Fraction(1)})
    # the moves: 3 Na gained at N and lost at P, 1 Ca lost at N and gained at P, phi_N = V, phi_P = 0
    phi = beta * f["V_NP_V"]
    gap = 3 * (ln(f["Na_N_mM"]) + phi) - 3 * ln(f["Na_P_mM"]) - (ln(f["Ca_N_mM"]) + 2 * phi) + ln(f["Ca_P_mM"])
    out = {
        "x": gap,
        "S": unit_forward.value,
        "J_fmol_per_s": J.value,
        "heat_rate_pJ_per_s": -RT * gap * J.value / 1000,
        # the charge that leaves N per cycle: -(3 x 1 - 1 x 2)
        "current_N_to_P_A": -(3 * 1 - 1 * 2) * E_CHARGE * N_A * J.value / 10**15,
        "dJ_dV_NP_fmol_per_s_per_V": _exchanger({**base, "V": Dual(f["V_NP_V"], 1)})[0].slope,
        "in_domain": gap <= 80,
    }
    for row, volume in (("Na_N", "N"), ("Na_P", "P"), ("Ca_N", "N"), ("Ca_P", "P")):
        seeded = {**base, row: Dual(f[f"{row}_mM"], 1 / f[f"volume_{volume}_pL"])}
        out[f"dJ_dn_{row}_per_s"] = _exchanger(seeded)[0].slope
    V_rev = f["V_NP_V"] - gap / beta
    out["V_rev_V"] = V_rev
    offsets = (Fraction(-1, 10**6), Fraction(0), Fraction(1, 10**6))
    names = ("J_at_V_rev_minus_1e-6_V_fmol_per_s", "J_at_V_rev_fmol_per_s", "J_at_V_rev_plus_1e-6_V_fmol_per_s")
    for name, offset in zip(names, offsets):
        out[name] = _exchanger({**base, "V": Dual(V_rev + offset)})[0].value
    voltages = [Fraction(_nearest_double(V_rev + offset)) for offset in offsets]
    out["near_V_rev"] = {
        "V_NP_V": voltages,
        "J_fmol_per_s": [_exchanger({**base, "V": Dual(V)})[0].value for V in voltages],
    }
    return out


def _symport(c_N, c_P, stoichiometry, scale):
    """J as a ratio of products of concentrations: no exponential and no logarithm in it."""
    inside, outside = Dual(1), Dual(1)
    for species, nu in stoichiometry.items():
        inside = inside * c_N[species] ** nu
        outside = outside * c_P[species] ** nu
    return scale * (outside - inside) / (outside + inside)


def symport_outputs(state, law):
    """The same outputs as `forms.symport_outputs`, in fractions."""
    stoichiometry = {species: nu for species, _valence, nu in law}
    c_N = {s: Dual(Fraction(state["c_N_mM"][s])) for s in stoichiometry}
    c_P = {s: Dual(Fraction(state["c_P_mM"][s])) for s in stoichiometry}
    V_N, V_P = Fraction(state["volume_N_pL"]), Fraction(state["volume_P_pL"])
    T = Fraction(state["temperature_K"])
    scale = Fraction(state["capacity_fmol_per_s"]) * Fraction(state["availability"])
    J = _symport(c_N, c_P, stoichiometry, scale).value
    # the moves and the potentials they see; the valences add to nothing, so any phi cancels
    phi = E_CHARGE / (K_B * T) * Fraction(state["V_NP_V"])
    gap = sum(nu * (ln(c_N[s].value) + valence * phi - ln(c_P[s].value)) for s, valence, nu in law)
    out = {
        "x": gap,
        "J_fmol_per_s": J,
        "heat_rate_pJ_per_s": -N_A * K_B * T * gap * J / 1000,
        "one_way_rates_sum_fmol_per_s": scale,
        "dJ_dn_N_per_s": {},
        "dJ_dn_P_per_s": {},
        "moves_N_fmol_per_s": {s: nu * J for s, nu in stoichiometry.items()},
        "moves_P_fmol_per_s": {s: -nu * J for s, nu in stoichiometry.items()},
        "with_V_NP_changed": {
            "V_NP_V": [Fraction(state["V_NP_V"]) + Fraction(1, 10), -Fraction(state["V_NP_V"])],
            "J_fmol_per_s": [J, J],
        },
        "in_domain": gap <= 80,
    }
    for s in stoichiometry:
        seeded = {**c_N, s: Dual(c_N[s].value, 1 / V_N)}
        out["dJ_dn_N_per_s"][s] = _symport(seeded, c_P, stoichiometry, scale).slope
        seeded = {**c_P, s: Dual(c_P[s].value, 1 / V_P)}
        out["dJ_dn_P_per_s"][s] = _symport(c_N, seeded, stoichiometry, scale).slope
    return out


# The store world's rates at t = 0, in fractions


def _one_way(one_way, gap, RT):
    """(J, heat rate) from the forward one-way rate and the free energy per unit over RT."""
    J = one_way * (1 - exp(gap))
    return J, -RT * gap * J / 1000


def _power(base, exponent):
    return exp(exponent * ln(base))


def initial_rates(inputs):
    """(rates, heat rates, condition factors, dV_m/dt, dV_b/dt) of the base world at t = 0, keyed as `World` names movers.

    A constant-field transfer, the release's too, is positive here from the cell to the far node.
    """
    w = inputs["store_world"]
    T = Fraction(w["temperature_K"])
    RT, beta = N_A * K_B * T, E_CHARGE / (K_B * T)
    c = {
        (node, s): Fraction(n) / Fraction(part["volume_pL"])
        for node, part in w["nodes"].items()
        for s, n in part["amounts_fmol"].items()
    }
    z = w["valence"]
    V_m = Fraction(w["patches"]["plasma"]["initial_voltage_V"])
    V_b = Fraction(w["patches"]["bounding"]["initial_voltage_V"])
    phi = {"cell": V_m, "store": V_m - V_b, "outside": Fraction(0)}
    patch_of = {"outside": "plasma", "store": "bounding"}
    rates, heats = {}, {}

    def level(node, s):
        return ln(c[node, s]) + z[s] * beta * phi[node]

    def field(name, s, far, permeability, opening=Fraction(1)):
        psi = z[s] * beta * (phi["cell"] - phi[far])
        leaving = psi / (1 - exp(-psi)) if psi else Fraction(1)
        area = Fraction(w["patches"][patch_of[far]]["area_m2"])
        one_way = 10**15 * area * Fraction(permeability) * opening * c["cell", s] * leaving
        rates[name, s], heats[name, s] = _one_way(one_way, level(far, s) - level("cell", s), RT)

    factors = {}
    for name, condition in w["conditions"].items():
        factor = Fraction(1)
        for read in condition["reads"]:
            ratio = _power(
                c[condition["node"], read["species"]] / Fraction(read["half_saturation_mM"]),
                Fraction(read["hill_coefficient"]),
            )
            factor *= ratio / (1 + ratio) if read["form"] == "activation" else 1 / (1 + ratio)
        factors[name] = factor
    for s, P in w["patches"]["plasma"]["permeability_m_per_s"].items():
        field("plasma_permeability", s, "outside", P)
    for s, P in w["patches"]["bounding"]["permeability_m_per_s"].items():
        field("bounding_permeability", s, "store", P)
    routes = w["calcium_routes"]
    field("plasma_leak", "Ca", "outside", routes["plasma_leak"]["permeability_m_per_s"])
    field("store_leak", "Ca", "store", routes["store_leak"]["permeability_m_per_s"])
    opening = factors["release_ip3"] * factors["release_calcium"]
    field("release", "Ca", "store", routes["release"]["permeability_m_per_s"], opening)
    channel = w["calcium_channel"]
    gates = Fraction(channel["abundance"]) * Fraction(channel["initial_m"]) ** 2 * Fraction(channel["initial_h"])
    field("calcium_channel", "Ca", "outside", channel["max_permeability_m_per_s"], gates)
    for name, far in (("plasma_pump", "outside"), ("store_pump", "store")):
        pump = w["pumps"][name]
        out = pump_outputs({
            "tag": name, "z": z["Ca"], "n": pump["stoichiometry"], "temperature_K": T,
            "c_N_mM": c["cell", "Ca"], "c_P_mM": c[far, "Ca"],
            "atp_mM": c["cell", "ATP"], "adp_mM": c["cell", "ADP"], "pi_mM": c["cell", "Pi"],
            "mu_atp_RT": w["fuel_potentials_RT"]["ATP"], "mu_adp_RT": w["fuel_potentials_RT"]["ADP"],
            "mu_pi_RT": w["fuel_potentials_RT"]["Pi"], "K_role_mM": pump["K_role_mM"], "K_ATP_mM": pump["K_ATP_mM"],
            "capacity_fmol_per_s": pump["capacity_fmol_per_s"], "availability": 1, "V_NP_V": phi["cell"] - phi[far],
            "volume_N_pL": 1, "volume_P_pL": 1,
        })
        rates[name, "cycles"], heats[name, "cycles"] = out["J_fmol_per_s"], out["heat_rate_pJ_per_s"]
    x = w["exchanger"]
    out = exchanger_outputs({
        "tag": "exchanger", "temperature_K": T, "Na_N_mM": c["cell", "Na"], "Na_P_mM": c["outside", "Na"],
        "Ca_N_mM": c["cell", "Ca"], "Ca_P_mM": c["outside", "Ca"], "V_NP_V": V_m,
        "capacity_fmol_per_s": x["capacity_fmol_per_s"], "availability": 1, "K_Na_mM": x["K_Na_mM"],
        "K_Ca_mM": x["K_Ca_mM"], "volume_N_pL": 1, "volume_P_pL": 1,
    })
    rates["exchanger", "cycles"], heats["exchanger", "cycles"] = out["J_fmol_per_s"], out["heat_rate_pJ_per_s"]
    mu = {s: Fraction(m) for s, m in w["buffers"]["standard_mu_RT"].items()}
    for reaction in w["buffers"]["reactions"]:
        for site in w["buffers"]["sites"]:
            one_way = Fraction(w["nodes"][site]["volume_pL"]) * Fraction(reaction["forward_rate_per_s"])
            gap = Fraction(0)
            for s, k in reaction["reactants"].items():
                one_way *= c[site, s] ** k
                gap -= k * (ln(c[site, s]) + mu[s])
            for s, k in reaction["products"].items():
                gap += k * (ln(c[site, s]) + mu[s])
            rates[reaction["id"], site], heats[reaction["id"], site] = _one_way(one_way, gap, RT)
    # the charge that crosses each patch from the cell (fmol of unit charge per second)
    across = {"outside": Fraction(0), "store": Fraction(0)}
    for (name, s), J in rates.items():
        if name in ("plasma_permeability", "plasma_leak", "calcium_channel"):
            across["outside"] += z[s] * J
        elif name in ("bounding_permeability", "store_leak", "release"):
            across["store"] += z[s] * J
    across["outside"] += 2 * w["pumps"]["plasma_pump"]["stoichiometry"] * rates["plasma_pump", "cycles"]
    across["store"] += 2 * w["pumps"]["store_pump"]["stoichiometry"] * rates["store_pump", "cycles"]
    across["outside"] -= rates["exchanger", "cycles"]
    coulomb = N_A * E_CHARGE / 10**15
    dV_m = -coulomb * across["outside"] / Fraction(w["patches"]["plasma"]["capacitance_F"])
    dV_b = -coulomb * across["store"] / Fraction(w["patches"]["bounding"]["capacitance_F"])
    return rates, heats, factors, dV_m, dV_b


# The store world in doubles


class World:
    """The store world from the moves of its movers. Amounts are kept as changes, so that small ones keep their digits."""

    def __init__(self, inputs, variant, control=None):
        w = inputs["store_world"]
        factor = self._raised(control)
        self.no_pump_voltage = control == "pump_without_voltage"
        self.release_turned = control == "release_sign"
        self.buffers = variant == "store_world"
        T = float(w["temperature_K"])
        self.RT = float(N_A * K_B) * T
        self.beta = float(E_CHARGE / K_B) / T
        self.rows = [(node, s) for node in w["nodes"] for s in w["nodes"][node]["amounts_fmol"]]
        self.at = {row: i for i, row in enumerate(self.rows)}
        self.n0 = numpy.array([float(w["nodes"][node]["amounts_fmol"][s]) for node, s in self.rows])
        self.volume = numpy.array([float(w["nodes"][node]["volume_pL"]) for node, _s in self.rows])
        self.z = numpy.array([float(w["valence"][s]) for _node, s in self.rows])
        mu = {**w["buffers"]["standard_mu_RT"], **w["fuel_potentials_RT"]}
        self.mu = numpy.array([float(mu.get(s, 0.0)) for _node, s in self.rows])
        self.node_of_row = numpy.array([("cell", "store", "outside").index(node) for node, _s in self.rows])
        self.C_m = float(w["patches"]["plasma"]["capacitance_F"]) * factor("plasma capacitance")
        self.C_b = float(w["patches"]["bounding"]["capacitance_F"]) * factor("bounding capacitance")
        self.V0 = (
            float(w["patches"]["plasma"]["initial_voltage_V"]),
            float(w["variants"][variant]["bounding_initial_voltage_V"]),
        )
        self.coulomb = float(E_CHARGE * N_A) * 1e-15
        self.gates0 = (float(w["calcium_channel"]["initial_m"]), float(w["calcium_channel"]["initial_h"]))
        self.channel = w["calcium_channel"]
        reads = w["conditions"]
        self.K_ip3 = float(reads["release_ip3"]["reads"][0]["half_saturation_mM"]) * factor("release_ip3 half_saturation")
        self.N_ip3 = float(reads["release_ip3"]["reads"][0]["hill_coefficient"])
        on, off = reads["release_calcium"]["reads"]
        self.K_on = float(on["half_saturation_mM"]) * factor("release_calcium activation half_saturation")
        self.N_on, self.K_off, self.N_off = (
            float(on["hill_coefficient"]), float(off["half_saturation_mM"]), float(off["hill_coefficient"]),
        )
        self.movers = self._movers(w, factor)
        self.moves = numpy.zeros((len(self.movers), len(self.rows)))
        for i, mover in enumerate(self.movers):
            for row, units in mover["moves"].items():
                self.moves[i, self.at[row]] += units
        self.fuel = numpy.array([mover.get("fuel", 0.0) for mover in self.movers])

    @staticmethod
    def _raised(control):
        prefix = "constants_one_percent: "
        chosen = control[len(prefix):] if control and control.startswith(prefix) else None
        return lambda name: 1.01 if name == chosen else 1.0

    def _movers(self, w, factor):
        cell, store, outside = "cell", "store", "outside"
        unit = 1e15
        A_m, A_b = float(w["patches"]["plasma"]["area_m2"]), float(w["patches"]["bounding"]["area_m2"])
        movers = []

        def field(name, label, species, far, scale, kind):
            movers.append({"name": (name, label), "kind": kind, "scale": scale, "species": species, "far": far,
                           "moves": {(cell, species): -1.0, (far, species): 1.0}})

        for species, P in w["patches"]["plasma"]["permeability_m_per_s"].items():
            field("plasma_permeability", species, species, outside,
                  unit * A_m * P * factor(f"plasma permeability {species}"), "field")
        for species, P in w["patches"]["bounding"]["permeability_m_per_s"].items():
            field("bounding_permeability", species, species, store,
                  unit * A_b * P * factor(f"bounding permeability {species}"), "field")
        routes = {name: float(r["permeability_m_per_s"]) * factor(f"{name} permeability")
                  for name, r in w["calcium_routes"].items()}
        field("plasma_leak", "Ca", "Ca", outside, unit * A_m * routes["plasma_leak"], "field")
        field("store_leak", "Ca", "Ca", store, unit * A_b * routes["store_leak"], "field")
        field("release", "Ca", "Ca", store, unit * A_b * routes["release"], "release")
        P_channel = float(self.channel["max_permeability_m_per_s"]) * factor("channel max_permeability")
        field("calcium_channel", "Ca", "Ca", outside,
              unit * A_m * P_channel * float(self.channel["abundance"]), "channel")
        fuel_mu = w["fuel_potentials_RT"]
        atp, adp, pi = (self.n0[self.at[cell, s]] / self.volume[self.at[cell, s]] for s in ("ATP", "ADP", "Pi"))
        fuel = fuel_mu["ADP"] + fuel_mu["Pi"] - fuel_mu["ATP"] + numpy.log(adp) + numpy.log(pi) - numpy.log(atp)
        for name, far in (("plasma_pump", outside), ("store_pump", store)):
            pump = w["pumps"][name]
            n = pump["stoichiometry"]
            movers.append({
                "name": (name, "cycles"), "kind": "pump", "n": n, "K": float(pump["K_role_mM"]), "far": far,
                "scale": float(pump["capacity_fmol_per_s"]) * factor(f"{name} capacity") * atp / (atp + pump["K_ATP_mM"]),
                "fuel": fuel, "moves": {(cell, "Ca"): -float(n), (far, "Ca"): float(n)},
            })
        x = w["exchanger"]
        movers.append({
            "name": ("exchanger", "cycles"), "kind": "exchanger", "far": outside,
            "scale": float(x["capacity_fmol_per_s"]) * factor("exchanger capacity"),
            "K_Na": float(x["K_Na_mM"]), "K_Ca": float(x["K_Ca_mM"]),
            "moves": {(cell, "Na"): 3.0, (outside, "Na"): -3.0, (cell, "Ca"): -1.0, (outside, "Ca"): 1.0},
        })
        for reaction in w["buffers"]["reactions"]:
            for site in w["buffers"]["sites"]:
                moves = {(site, s): -float(k) for s, k in reaction["reactants"].items()}
                moves.update({(site, s): float(k) for s, k in reaction["products"].items()})
                movers.append({
                    "name": (reaction["id"], site), "kind": "reaction",
                    "scale": float(w["nodes"][site]["volume_pL"]) * float(reaction["forward_rate_per_s"])
                    * factor(f"{reaction['id']} forward_rate") * (1.0 if self.buffers else 0.0),
                    "moves": moves, "reads": [self.at[site, s] for s in reaction["reactants"]],
                })
        return movers

    @property
    def size(self):
        return len(self.rows) + 2 + 2 * len(self.movers) + 2

    def split(self, y):
        R, M = len(self.rows), len(self.movers)
        return y[:R], y[R:R + 2], y[R + 2:R + 2 + M], y[R + 2 + M:R + 2 + 2 * M], y[R + 2 + 2 * M:]

    def initial(self):
        y = numpy.zeros(self.size)
        y[len(self.rows):len(self.rows) + 2] = self.gates0
        return y

    def potentials(self, change):
        """(phi_cell, phi_store, phi_outside) from the charge each node has gained."""
        gained = numpy.zeros(3)
        numpy.add.at(gained, self.node_of_row, self.coulomb * self.z * change)
        V_m = self.V0[0] + (gained[0] + gained[1]) / self.C_m
        V_b = self.V0[1] - gained[1] / self.C_b
        return numpy.array([V_m, V_m - V_b, 0.0])

    def rates(self, change, gates, phi=None, opening=None):
        """(transfers, gates, heats, works, forward one-way rates, gaps); `phi` and the release's `opening` may be held."""
        c = (self.n0 + change) / self.volume
        if phi is None:
            phi = self.potentials(change)
        level = numpy.log(c) + self.mu + self.beta * self.z * phi[self.node_of_row]
        if self.no_pump_voltage:
            uncharged = numpy.log(c) + self.mu
        forward = numpy.empty(len(self.movers))
        ca = c[self.at["cell", "Ca"]]
        psi_m, psi_b = self.beta * phi[0], self.beta * (phi[0] - phi[1])
        m, h = gates
        gap = self.moves @ level + self.fuel
        for i, mover in enumerate(self.movers):
            kind = mover["kind"]
            if kind in ("field", "release", "channel"):
                row = self.at["cell", mover["species"]]
                w = self.z[row] * (psi_m if mover["far"] == "outside" else psi_b)
                one_way = mover["scale"] * c[row] * (w / -numpy.expm1(-w) if w != 0.0 else 1.0)
                if kind == "release":
                    one_way *= self.opening(c) if opening is None else opening
                elif kind == "channel":
                    one_way *= m * m * h
                forward[i] = one_way
            elif kind == "pump":
                forward[i] = mover["scale"] * ca ** mover["n"] / (ca ** mover["n"] + mover["K"] ** mover["n"])
                if self.no_pump_voltage:
                    gap[i] = self.moves[i] @ uncharged + self.fuel[i]
            elif kind == "exchanger":
                a, b = (c[self.at[node, "Na"]] / mover["K_Na"] for node in ("cell", "outside"))
                inside, outside = (c[self.at[node, "Ca"]] / mover["K_Ca"] for node in ("cell", "outside"))
                forward[i] = (
                    mover["scale"] * numpy.exp(3 * numpy.log(b) + numpy.log(inside) - psi_m / 2)
                    / ((1 + a**3 + b**3) * (1 + inside + outside))
                )
            else:
                forward[i] = mover["scale"] * numpy.prod(c[mover["reads"]])
        J = -forward * numpy.expm1(gap)
        heat = -1e-3 * self.RT * gap * J
        if self.release_turned:
            turned = [mover["name"][0] for mover in self.movers].index("release")
            J[turned], heat[turned] = -J[turned], -heat[turned]
        work = numpy.array([-1e-3 * self.RT * f * j for f, j, mover in zip(self.fuel, J, self.movers) if "fuel" in mover])
        return J, self.gate_rates(phi[0], m, h), heat, work, forward, gap

    def opening(self, c):
        """The release's opening, from fractions of occupied sites."""
        ca, ip3 = c[self.at["cell", "Ca"]], c[self.at["cell", "IP3"]]
        bound = ip3**self.N_ip3 / (ip3**self.N_ip3 + self.K_ip3**self.N_ip3)
        bound *= ca**self.N_on / (ca**self.N_on + self.K_on**self.N_on)
        return bound * self.K_off**self.N_off / (ca**self.N_off + self.K_off**self.N_off)

    @staticmethod
    def gate_rates(V, m, h):
        u = V - 0.010
        logistic = lambda s: 0.5 * (1.0 + numpy.tanh(s / 2))  # 1/(1 + e^-s)
        tau_m = 5e-3 + 20e-3 * logistic(-(u + 0.025) / 5e-3)
        tau_h = 20e-3 + 50e-3 * logistic(-(u + 0.040) / 7e-3)
        return numpy.array([
            (logistic((u + 0.030) / 6e-3) - m) / tau_m,
            (logistic(-(u + 0.080) / 6.4e-3) - h) / tau_h,
        ])

    def derivative(self, _t, y):
        change, gates, _J, _Q, _W = self.split(y)
        J, gate_rates, heat, work, _forward, _gap = self.rates(change, gates)
        return numpy.concatenate([J @ self.moves, gate_rates, J, heat, work])

    def observables(self, y):
        """Flat {path: double} with the paths of `accuracy_study.flatten`, at one time."""
        change, gates, J, Q, W = self.split(y)
        out = {}
        for row, d in zip(self.rows, change):
            out[("amount_changes_fmol",) + row] = d
        gained = numpy.zeros(3)
        numpy.add.at(gained, self.node_of_row, self.coulomb * self.z * change)
        out[("V_m_change_V",)] = (gained[0] + gained[1]) / self.C_m
        out[("V_b_change_V",)] = -gained[1] / self.C_b
        out[("m",)], out[("h",)] = gates
        totals = {}
        for mover, j, q in zip(self.movers, J, Q):
            name, label = mover["name"]
            out["transfers_fmol", name, label] = -j if name == "release" else j
            out["heats_pJ", name, label] = q
            totals[name] = totals.get(name, 0.0) + q
        for name in ("plasma_permeability", "bounding_permeability", "bind_first", "bind_second"):
            out["heats_pJ", name, "total"] = totals[name]
        for mover, w in zip([mv for mv in self.movers if "fuel" in mv], W):
            out["works_pJ", mover["name"][0]] = w
        dV_m, dV_b = out[("V_m_change_V",)], out[("V_b_change_V",)]
        out[("capacitor_energy_change_pJ",)] = 1e12 * (
            self.C_m * dV_m * (self.V0[0] + dV_m / 2) + self.C_b * dV_b * (self.V0[1] + dV_b / 2)
        )
        # the change of n (ln c - 1 + mu), without the loss of digits of a difference of two large sums
        grown = numpy.log1p(change / self.n0)
        chemical = (change * (numpy.log(self.n0 / self.volume) + self.mu) + (self.n0 + change) * grown - change).sum()
        out[("free_energy_change_pJ",)] = 1e-3 * self.RT * chemical + out[("capacitor_energy_change_pJ",)]
        out[("heat_total_pJ",)] = float(numpy.sum(Q))
        out[("work_total_pJ",)] = float(numpy.sum(W))
        return out
