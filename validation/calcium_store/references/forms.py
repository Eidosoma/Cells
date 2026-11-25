"""The closed forms of SPEC.md section 2, and the outputs SPEC.md section 5 asks of each kernel state.

Every function works on `decimal.Decimal` in the precision of the caller's context (see `working`) and returns Decimals.
Nothing is rounded to a double here. Units are SPEC.md's: fmol, pL, mM, m2, m/s, V, F, A, pJ, s, K; a current is in A.

Standard library only. The second derivation, in exact fractions, is `second_route.py`; it shares no code with this file.
"""

from decimal import (
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    ROUND_HALF_EVEN,
    localcontext,
)

ONE = Decimal(1)
ZERO = Decimal(0)
HALF = Decimal("0.5")

# The exact SI constants (2019).
AVOGADRO = Decimal("6.02214076e23")  # 1/mol
ELEMENTARY_CHARGE = Decimal("1.602176634e-19")  # C
BOLTZMANN = Decimal("1.380649e-23")  # J/K
FARADAY = Decimal("96485.3321233100184")  # N_A e in C/mol, exact
GAS_CONSTANT = Decimal("8.31446261815324")  # N_A k_B in J/(mol K), exact

FEMTO = Decimal("1e-15")  # mol per fmol
PICO_FROM_RATE = Decimal("1e-3")  # (fmol/s)(J/mol) to pJ/s
FLUX_UNITS = Decimal("1e15")  # (m2)(m/s)(mol/m3) to fmol/s


def working(digits):
    """A decimal context of `digits` digits, half-even, with wide exponents, for a `with` statement."""
    return localcontext(
        Context(
            prec=digits,
            rounding=ROUND_HALF_EVEN,
            Emin=-999999,
            Emax=999999,
            capitals=1,
            clamp=0,
            flags=[],
            traps=[InvalidOperation, DivisionByZero, Overflow],
        )
    )


def exact(number):
    """A number of `inputs.json` as a Decimal, without rounding: a double's own binary value, an int, or a Decimal."""
    return Decimal(number)


def expm1(x):
    """e^x - 1, in the context's precision also when x is small."""
    if x == 0:
        return ZERO
    with localcontext() as context:
        context.prec += max(0, -x.adjusted()) + 3
        value = x.exp() - 1
    return +value


def log1p(x):
    """ln(1 + x), in the context's precision also when x is small."""
    if x == 0:
        return ZERO
    with localcontext() as context:
        context.prec += max(0, -x.adjusted()) + 3
        value = (1 + x).ln()
    return +value


def bernoulli(x):
    """B(x) = x/(e^x - 1), B(0) = 1 (SPEC.md section 1)."""
    if x == 0:
        return ONE
    return x / expm1(x)


# 2.1 Constant-field flux


def constant_field(*, valence, temperature, voltage, area, permeability, opening, c_inside, c_outside):
    """(J, heat rate): J in fmol/s from the inside to the outside, heat in pJ/s."""
    rt = GAS_CONSTANT * temperature
    x = valence * FARADAY * voltage / rt
    flux = FLUX_UNITS * area * permeability * opening * (c_inside * bernoulli(-x) - c_outside * bernoulli(x))
    heat = PICO_FROM_RATE * flux * (rt * (c_inside / c_outside).ln() + valence * FARADAY * voltage)
    return flux, heat


def constant_field_slopes(*, valence, temperature, voltage, area, permeability, opening):
    """(dJ/dc_inside, dJ/dc_outside) in fmol/s per mM at a held voltage and opening."""
    x = valence * FARADAY * voltage / (GAS_CONSTANT * temperature)
    scale = FLUX_UNITS * area * permeability * opening
    return scale * bernoulli(-x), -scale * bernoulli(x)


# 2.2 The factors of a condition


def read_exponent(concentration, half_saturation, coefficient):
    """z = n (ln c - ln K)."""
    return coefficient * (concentration.ln() - half_saturation.ln())


def condition_factor(reads):
    """f = exp(sum of ln h) over the reads, each (concentration, half saturation, coefficient, form)."""
    total = ZERO
    for concentration, half_saturation, coefficient, form in reads:
        z = read_exponent(concentration, half_saturation, coefficient)
        if form == "activation":
            total -= log1p((-z).exp())
        elif form == "inhibition":
            total -= log1p(z.exp())
        else:
            raise ValueError(f"unknown form {form!r}")
    return total.exp()


def condition_log_slope(reads, species_is_read):
    """d ln f / d ln c for the reads of one species: n (1 - h) for activation, -n (1 - h) for inhibition."""
    total = ZERO
    for (concentration, half_saturation, coefficient, form), read in zip(reads, species_is_read):
        if not read:
            continue
        z = read_exponent(concentration, half_saturation, coefficient)
        if form == "activation":
            total += coefficient / (1 + z.exp())
        else:
            total -= coefficient / (1 + (-z).exp())
    return total


# 2.3 The gates of the calcium channel


def channel_gate_rates(voltage, m, h):
    """(dm/dt, dh/dt) in 1/s at the plasma patch's voltage."""
    u = voltage - Decimal("0.010")
    m_inf = 1 / (1 + (-(u + Decimal("0.030")) / Decimal("0.006")).exp())
    h_inf = 1 / (1 + ((u + Decimal("0.080")) / Decimal("0.0064")).exp())
    tau_m = Decimal("0.005") + Decimal("0.020") / (1 + ((u + Decimal("0.025")) / Decimal("0.005")).exp())
    tau_h = Decimal("0.020") + Decimal("0.050") / (1 + ((u + Decimal("0.040")) / Decimal("0.007")).exp())
    return (m_inf - m) / tau_m, (h_inf - h) / tau_h


# 2.4 The ATP-driven transporter


def fuel_affinity(*, atp, adp, pi, mu_atp, mu_adp, mu_pi):
    """x_fuel, with the activities over c0 = 1 mM."""
    return mu_adp + mu_pi - mu_atp + (adp * pi / atp).ln()


def pump_saturation(*, n, c_N, K_role, atp, K_atp):
    """S."""
    return 1 / ((1 + (K_role / c_N) ** n) * (1 + K_atp / atp))


def pump_cycle(
    *, temperature, z, n, c_N, c_P, atp, adp, pi, mu_atp, mu_adp, mu_pi, K_role, K_atp, capacity, availability, V_NP,
    with_voltage=True,
):
    """A dictionary of x, x_fuel, S, J_plus, J, heat rate and work rate. `with_voltage=False` is SPEC.md's control."""
    rt = GAS_CONSTANT * temperature
    x_fuel = fuel_affinity(atp=atp, adp=adp, pi=pi, mu_atp=mu_atp, mu_adp=mu_adp, mu_pi=mu_pi)
    x = x_fuel + n * (c_P / c_N).ln()
    if with_voltage:
        x -= n * z * FARADAY * V_NP / rt
    S = pump_saturation(n=n, c_N=c_N, K_role=K_role, atp=atp, K_atp=K_atp)
    J_plus = capacity * availability * S
    J = -J_plus * expm1(x)
    return {
        "x": x,
        "x_fuel": x_fuel,
        "S": S,
        "J_plus": J_plus,
        "J": J,
        "heat_rate": -PICO_FROM_RATE * rt * J * x,
        "work_rate": -PICO_FROM_RATE * rt * J * x_fuel,
    }


def pump_slopes(cycle, *, n, c_N, c_P, K_role):
    """(dJ/dc_N, dJ/dc_P) in fmol/s per mM at a held voltage, from a `pump_cycle` result."""
    back = cycle["J_plus"] * cycle["x"].exp()
    ratio = (K_role / c_N) ** n
    saturation = n * ratio / (c_N * (1 + ratio))
    return cycle["J"] * saturation + back * n / c_N, -back * n / c_P


def pump_outputs(state):
    """Every output SPEC.md section 5 asks of one pump state."""
    s = {key: exact(value) for key, value in state.items() if key not in ("tag", "z", "n")}
    z, n = Decimal(state["z"]), Decimal(state["n"])
    rt = GAS_CONSTANT * s["temperature_K"]
    arguments = {
        "temperature": s["temperature_K"],
        "z": z,
        "n": n,
        "c_N": s["c_N_mM"],
        "c_P": s["c_P_mM"],
        "atp": s["atp_mM"],
        "adp": s["adp_mM"],
        "pi": s["pi_mM"],
        "mu_atp": s["mu_atp_RT"],
        "mu_adp": s["mu_adp_RT"],
        "mu_pi": s["mu_pi_RT"],
        "K_role": s["K_role_mM"],
        "K_atp": s["K_ATP_mM"],
        "capacity": s["capacity_fmol_per_s"],
        "availability": s["availability"],
    }
    cycle = pump_cycle(V_NP=s["V_NP_V"], **arguments)
    slope_N, slope_P = pump_slopes(cycle, n=n, c_N=s["c_N_mM"], c_P=s["c_P_mM"], K_role=s["K_role_mM"])
    outputs = {
        "x": cycle["x"],
        "x_fuel": cycle["x_fuel"],
        "S": cycle["S"],
        "J_plus_fmol_per_s": cycle["J_plus"],
        "J_fmol_per_s": cycle["J"],
        "heat_rate_pJ_per_s": cycle["heat_rate"],
        "work_rate_pJ_per_s": cycle["work_rate"],
        "current_N_to_P_A": FEMTO * FARADAY * n * z * cycle["J"],
        "dJ_dV_NP_fmol_per_s_per_V": cycle["J_plus"] * cycle["x"].exp() * n * z * FARADAY / rt,
        "dJ_dn_N_per_s": slope_N / s["volume_N_pL"],
        "dJ_dn_P_per_s": slope_P / s["volume_P_pL"],
        "move_N_fmol_per_s": -n * cycle["J"],
        "move_P_fmol_per_s": n * cycle["J"],
        "in_domain": abs(cycle["x"]) <= 80,
    }
    if z != 0:
        per_volt = n * z * FARADAY / rt
        V_stall = (cycle["x_fuel"] + n * (s["c_P_mM"] / s["c_N_mM"]).ln()) / per_volt
        outputs["V_stall_V"] = V_stall
        for name, offset in _OFFSETS:
            outputs[f"J_at_V_stall{name}_fmol_per_s"] = -cycle["J_plus"] * expm1(-per_volt * offset)
        outputs["near_V_stall"] = _at_doubles(V_stall, lambda V: pump_cycle(V_NP=V, **arguments)["J"])
    else:
        outputs["V_stall_V"] = None
        for name, _offset in _OFFSETS:
            outputs[f"J_at_V_stall{name}_fmol_per_s"] = None
        outputs["near_V_stall"] = None
    return outputs


_OFFSETS = (("_minus_1e-6_V", Decimal("-1e-6")), ("", ZERO), ("_plus_1e-6_V", Decimal("1e-6")))


def _at_doubles(voltage, rate):
    """The doubles nearest voltage - 1e-6, voltage and voltage + 1e-6 V, and the rate at each, taken exactly."""
    voltages = [Decimal(float(voltage + offset)) for _name, offset in _OFFSETS]
    return {"V_NP_V": voltages, "J_fmol_per_s": [rate(V) for V in voltages]}


# 2.5 The exchanger


def exchanger_cycle(*, temperature, Na_N, Na_P, Ca_N, Ca_P, K_Na, K_Ca, capacity, availability, V_NP):
    """A dictionary of x, S, J, heat rate and the parts the slopes use."""
    rt = GAS_CONSTANT * temperature
    u = FARADAY * V_NP / rt
    a, b, c, d = Na_N / K_Na, Na_P / K_Na, Ca_N / K_Ca, Ca_P / K_Ca
    D = (1 + a**3 + b**3) * (1 + c + d)
    forward = b**3 * c * (-u / 2).exp()
    backward = a**3 * d * (u / 2).exp()
    J = capacity * availability * (forward - backward) / D
    x = 3 * (Na_N / Na_P).ln() + (Ca_P / Ca_N).ln() + u
    return {
        "x": x,
        "S": forward / D,
        "J": J,
        "heat_rate": -PICO_FROM_RATE * rt * J * x,
        "u": u,
        "parts": (a, b, c, d, D, forward, backward),
    }


def exchanger_slopes(cycle, *, K_Na, K_Ca, capacity, availability):
    """dJ/dc for Na_N, Na_P, Ca_N, Ca_P (fmol/s per mM), at a held voltage, from an `exchanger_cycle` result."""
    a, b, c, d, D, forward, backward = cycle["parts"]
    scale = capacity * availability
    sodium = 1 + a**3 + b**3
    calcium = 1 + c + d
    J = cycle["J"]
    half = (cycle["u"] / 2).exp()
    return {
        "Na_N": (-scale * 3 * a**2 * d * half / D - J * 3 * a**2 / sodium) / K_Na,
        "Na_P": (scale * 3 * b**2 * c / half / D - J * 3 * b**2 / sodium) / K_Na,
        "Ca_N": (scale * b**3 / half / D - J / calcium) / K_Ca,
        "Ca_P": (-scale * a**3 * half / D - J / calcium) / K_Ca,
    }


def exchanger_outputs(state):
    """Every output SPEC.md section 5 asks of one exchanger state."""
    s = {key: exact(value) for key, value in state.items() if key != "tag"}
    rt = GAS_CONSTANT * s["temperature_K"]
    arguments = {
        "temperature": s["temperature_K"],
        "Na_N": s["Na_N_mM"],
        "Na_P": s["Na_P_mM"],
        "Ca_N": s["Ca_N_mM"],
        "Ca_P": s["Ca_P_mM"],
        "K_Na": s["K_Na_mM"],
        "K_Ca": s["K_Ca_mM"],
        "capacity": s["capacity_fmol_per_s"],
        "availability": s["availability"],
    }
    cycle = exchanger_cycle(V_NP=s["V_NP_V"], **arguments)
    slopes = exchanger_slopes(
        cycle,
        K_Na=s["K_Na_mM"],
        K_Ca=s["K_Ca_mM"],
        capacity=s["capacity_fmol_per_s"],
        availability=s["availability"],
    )
    scale = s["capacity_fmol_per_s"] * s["availability"]
    _a, b, c, _d, D, forward, backward = cycle["parts"]
    outputs = {
        "x": cycle["x"],
        "S": cycle["S"],
        "J_fmol_per_s": cycle["J"],
        "heat_rate_pJ_per_s": cycle["heat_rate"],
        "current_N_to_P_A": -FEMTO * FARADAY * cycle["J"],
        "dJ_dV_NP_fmol_per_s_per_V": -scale * HALF * (forward + backward) / D * FARADAY / rt,
        "dJ_dn_Na_N_per_s": slopes["Na_N"] / s["volume_N_pL"],
        "dJ_dn_Na_P_per_s": slopes["Na_P"] / s["volume_P_pL"],
        "dJ_dn_Ca_N_per_s": slopes["Ca_N"] / s["volume_N_pL"],
        "dJ_dn_Ca_P_per_s": slopes["Ca_P"] / s["volume_P_pL"],
        "in_domain": cycle["x"] <= 80,
    }
    u_rev = -(3 * (s["Na_N_mM"] / s["Na_P_mM"]).ln() + (s["Ca_P_mM"] / s["Ca_N_mM"]).ln())
    outputs["V_rev_V"] = u_rev * rt / FARADAY
    for name, offset in _OFFSETS:
        du = FARADAY * offset / rt
        S = b**3 * c * (-(u_rev + du) / 2).exp() / D
        outputs[f"J_at_V_rev{name}_fmol_per_s"] = -scale * S * expm1(du)
    outputs["near_V_rev"] = _at_doubles(outputs["V_rev_V"], lambda V: exchanger_cycle(V_NP=V, **arguments)["J"])
    return outputs


# 2.6 The symports


def symport_cycle(*, temperature, stoichiometry, c_N, c_P, capacity, availability, V_NP):
    """A dictionary of x, J, heat rate. `V_NP` is an argument so that it can be changed; the law does not read it."""
    del V_NP
    rt = GAS_CONSTANT * temperature
    x = sum((nu * (c_N[s] / c_P[s]).ln() for s, nu in stoichiometry.items()), ZERO)
    ex = x.exp()
    J = -capacity * availability * expm1(x) / (1 + ex)
    return {"x": x, "J": J, "heat_rate": -PICO_FROM_RATE * rt * J * x}


def symport_outputs(state, law):
    """Every output SPEC.md section 5 asks of one symport state. `law` lists (species, valence, stoichiometry)."""
    stoichiometry = {species: Decimal(nu) for species, _valence, nu in law}
    if sum(valence * nu for _species, valence, nu in law) != 0:
        raise ValueError("a symport of SPEC.md moves no net charge")
    c_N = {s: exact(state["c_N_mM"][s]) for s in stoichiometry}
    c_P = {s: exact(state["c_P_mM"][s]) for s in stoichiometry}
    volume_N, volume_P = exact(state["volume_N_pL"]), exact(state["volume_P_pL"])
    V_NP = exact(state["V_NP_V"])
    arguments = {
        "temperature": exact(state["temperature_K"]),
        "stoichiometry": stoichiometry,
        "c_N": c_N,
        "c_P": c_P,
        "capacity": exact(state["capacity_fmol_per_s"]),
        "availability": exact(state["availability"]),
    }
    cycle = symport_cycle(V_NP=V_NP, **arguments)
    total = arguments["capacity"] * arguments["availability"]
    ex = cycle["x"].exp()
    dJ_dx = -2 * total * ex / (1 + ex) ** 2
    changed = [V_NP + Decimal("0.1"), -V_NP]
    return {
        "x": cycle["x"],
        "J_fmol_per_s": cycle["J"],
        "heat_rate_pJ_per_s": cycle["heat_rate"],
        "one_way_rates_sum_fmol_per_s": total,
        "dJ_dn_N_per_s": {s: dJ_dx * nu / (c_N[s] * volume_N) for s, nu in stoichiometry.items()},
        "dJ_dn_P_per_s": {s: -dJ_dx * nu / (c_P[s] * volume_P) for s, nu in stoichiometry.items()},
        "moves_N_fmol_per_s": {s: nu * cycle["J"] for s, nu in stoichiometry.items()},
        "moves_P_fmol_per_s": {s: -nu * cycle["J"] for s, nu in stoichiometry.items()},
        "with_V_NP_changed": {
            "V_NP_V": changed,
            "J_fmol_per_s": [symport_cycle(V_NP=V, **arguments)["J"] for V in changed],
        },
        "in_domain": cycle["x"] <= 80,
    }


# 2.7 The buffers


def reaction(*, temperature, volume, rate_constant, reactants, products, delta_mu):
    """(r, heat rate): r in fmol/s forward, heat in pJ/s; reactants and products are lists of activities (over 1 mM)."""
    forward, backward = ONE, ONE
    for activity in reactants:
        forward *= activity
    for activity in products:
        backward *= activity
    r = volume * rate_constant * (forward - delta_mu.exp() * backward)
    heat = PICO_FROM_RATE * GAS_CONSTANT * temperature * r * ((forward / backward).ln() - delta_mu)
    return r, heat
