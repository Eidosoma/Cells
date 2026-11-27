"""FR-64's shift kinds as closed forms in 50-digit decimal arithmetic, written from the design
note's formulas (docs/FR64_VOLTAGE_SHIFT_DESIGN.md §1, §3.5, §3.6 and §4.2), never from the
engine's kernels. This module imports nothing from cells.

This is an independent reference for the host rows of
tests/unit/test_surface_pump_v3_populations.py. FR-64 has no registered comparison: the kinds are
proved as engine arithmetic (D361).

- **The reversal** (Nernst 1889): E = (R T/(z F)) ln(c_o/c_i). Its slope at one end is
  |dE/dc| = R T/(|z| F c).
- **The pH:** pH = -log10(h / 1000 mM), with h the free proton concentration in mM.
- **The pH shift:** dV = sigma (pH - pH_ref), with sigma in V per pH unit. Its slope in h is
  |d(dV)/dh| = |sigma|/(h ln 10).
- **The constants** are exact by the 2019 SI.
"""

from decimal import Decimal as D
from decimal import localcontext

PRECISION = 50
F = D("6.02214076e23") * D("1.602176634e-19")
R = D("6.02214076e23") * D("1.380649e-23")
PH_REFERENCE_MM = D(1000)


def _d(value):
    """A Decimal as it is, a decimal string as written, or a binary64 as its exact value."""
    if isinstance(value, D):
        return value
    return D(value) if isinstance(value, str) else D(float(value))


def reversal(inside_mM, outside_mM, valence, temperature_K):
    """E (V) of an ion of this valence."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ratio = _d(outside_mM) / _d(inside_mM)
        return R * _d(temperature_K) / (D(valence) * F) * ratio.ln()


def reversal_slope(concentration_mM, valence, temperature_K):
    """|dE/dc| (V/mM) at one end."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return R * _d(temperature_K) / (abs(D(valence)) * F * _d(concentration_mM))


def ph(h_mM):
    """pH of a free proton concentration (mM)."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return -(_d(h_mM) / PH_REFERENCE_MM).log10()


def ph_shift(h_mM, shift_V_per_ph, reference_ph):
    """dV (V) = sigma (pH - pH_ref)."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return _d(shift_V_per_ph) * (ph(h_mM) - _d(reference_ph))


def ph_slope(h_mM, shift_V_per_ph):
    """|d(dV)/dh| (V/mM) = |sigma|/(h ln 10)."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return abs(_d(shift_V_per_ph)) / (_d(h_mM) * D(10).ln())


def bernoulli(x):
    """B(x) = x/(e^x - 1), with B(0) = 1."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        x = _d(x)
        return D(1) if x == 0 else x / (x.exp() - 1)


def unblocked(v_ref, temperature_K, blocker_mM, modes):
    """FR-51's law at V_ref (V): (sum_k w_k K_k/(c_B + K_k)) / (sum_k w_k), with
    K_k = K_k(0) exp(m_k F V_ref/(R T)); modes ((w, K(0) in mM, m_k the signed steepness), ...)."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        scale = F / (R * _d(temperature_K)) * _d(v_ref)
        c_b, num, den = _d(blocker_mM), D(0), D(0)
        for weight, k0, steepness in modes:
            k = _d(k0) * (_d(steepness) * scale).exp()
            num, den = num + _d(weight) * k / (c_b + k), den + _d(weight)
        return num / den


def pair_one_way(raw, population, cell_ph):
    """(forward, backward) (fmol/s) of one of D327's pair's populations (validation/fr64/worlds.py):
    g c_in B(-x) and g c_out B(x) at V = E_K, with g = 1e15 P r a A o u v from the world's declared
    values. o is the declared gates' product (1 for a gate-free law). u is FR-51's law at the
    block's V_ref = E_K - sigma (pH_cell - pH_ref), sigma and pH_ref from its declared pH shift
    and the cell's pH as given (the world sets B4's free h there), or 1 without a block."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        m = raw["model"]
        temperature = _d(m["temperature_K"])
        c_in = _d(m["cells"][0]["initial_amount_fmol"]["K"]) / _d(m["cells"][0]["volume_pL"])
        bath = m["extracellular"][0]
        c_out = _d(bath["initial_amount_fmol"]["K"]) / _d(bath["volume_pL"])
        e_k = R * temperature / F * (c_out / c_in).ln()
        x = F * e_k / (R * temperature)
        entry = next(c for c in m["channels"] if c["id"] == population)
        area = _d(m["membranes"][0]["area_m2"])
        g = D("1e15") * _d(entry["max_permeability_m_per_s"]) * _d(entry["abundance"]) * area
        g *= _d(entry["permeant_ions"][0]["relative_permeability"])
        for gate in entry["initial_gate"]:
            g *= _d(gate)
        block = entry.get("block")
        if block is not None:
            side = 1 if block["blocker"]["side"] == "outside" else -1
            z_b = block["blocker"]["valence"]
            modes = [
                (mode["weight"], mode["k0_mM"],
                 side * (1 if z_b > 0 else -1) * abs(z_b) * _d(mode["electrical_distance"]))
                for mode in block["modes"]
            ]  # fmt: skip
            shift = entry["voltage_shift"]["block"]["ph"]
            dv = _d(shift["shift_V_per_ph"]) * (_d(cell_ph) - _d(shift["reference_ph"]))
            g *= unblocked(e_k - dv, temperature, block["blocker"]["concentration_mM"], modes)
        return g * c_in * bernoulli(-x), g * c_out * bernoulli(x)
