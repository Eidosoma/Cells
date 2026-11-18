"""Cycle laws on a population: free energies, fluxes, rows, heat, work, charge and slopes.

Written from CORE_SEAMS_DESIGN §3.1–§3.4 and §16 (the contract), §19 (the rulings), and, for
the version-1 laws, COMPARTMENT_PH_TRANSFER_DESIGN §6 and R-fuel's statement of the neutral law
(validation/compartment_ph/REFERENCES_USAGE.md, "The laws"). No engine code is read.

**Free energy** (one authority): ΔG_m = Σ_{s,e} ν_{s,e,m} μ̃_{s,e}, μ̃ = μ° + RT ln(c/c°) + z F φ_e.

**Three law kinds:**
- ``diagram``: the law's kinetic diagram (``diagrams``); each declared Hill cycle κ has one-way
  fluxes per carrier j±_κ = Π±_κ Σ_κ/Σ. With the law's rate scale ω (1/s), S_κ = j⁺_κ/ω and a
  population of capacity k = N_carriers ω gives J±_κ = k a S_κ and J⁺ e^{ΔG/RT} = J⁻ exactly when
  the cycle satisfies Wegscheider's condition.
- ``factored``: S_m is a product of saturations [1 + (K/c)^h]^-1 (the version-1 laws' form), and
  J_m = k a S_m (1 − e^{ΔG_m/RT}), with J⁺ = k a S and J⁻ = J⁺ e^{ΔG/RT}.
- ``net_flow``: the fallback; each mode's net flux is Σ_t k_t (1 − exp(ΔG_t/RT + ε_t ψ)) over
  declared terms. No one-way fluxes.

**Host mapping.** A population lies on a patch with ends a (its cell) and b (the outside node),
V = φ_a − φ_b, and ``orientation`` says which host end is N.

**Units.** fmol, pL, mM, V, s, J/mol; energies pJ (1 fmol × 1 J/mol = 1e-3 pJ); current pA
(1 fmol e/s × F = F × 1e-3 pA); conductance pS (pA/V).
"""

from __future__ import annotations

from decimal import Decimal

from . import diagrams as D
from . import exact
from .exact import Dual, context, dec, dexp, dln

# --------------------------------------------------------------------------------------------
# States: host ends to law ends
# --------------------------------------------------------------------------------------------

def law_state(population: dict, host_state: dict) -> dict:
    """The law's N/P state from a host state {phi_V: {a, b}, c_mM: {a: {...}, b: {...}}}."""
    nend = population["orientation"]["N"]
    pend = "b" if nend == "a" else "a"
    return {"phi_V": {"N": host_state["phi_V"][nend], "P": host_state["phi_V"][pend]},
            "c_mM": {"N": host_state["c_mM"][nend], "P": host_state["c_mM"][pend]}}


def host_end(population: dict, end: str) -> str:
    nend = population["orientation"]["N"]
    return nend if end == "N" else ("b" if nend == "a" else "a")


# --------------------------------------------------------------------------------------------
# Kinetics per law kind
# --------------------------------------------------------------------------------------------

def saturation(terms: list, state: dict):
    """S = Π_t [1 + (K_t/c_t)^h_t]^-1 (the version-1 laws' S), with an optional planted offset."""
    with context():
        S = Decimal(1)
        for t in terms:
            c = state["c_mM"][t["end"]][t["species"]]
            c = c if isinstance(c, (Decimal, Dual)) else dec(c)
            S = S / (1 + (dec(t["K_mM"]) / c) ** int(t.get("hill", 1)))
        return S


def mode_fluxes(law: dict, registry: dict, state: dict, capacity, availability) -> dict:
    """Per mode: ΔG/RT, S, J⁺, J⁻ and J (fmol/s), with the diagram's details where it has one."""
    with context():
        k = dec(capacity) if not isinstance(capacity, (Decimal, Dual)) else capacity
        a = dec(availability)
        out = {}
        kind = law["kind"]
        if kind == "diagram":
            rates = D.edge_rates(law, state, registry)
            cyc = D.cycle_fluxes(law, rates, "trees")
            omega = dec(law["rate_scale_per_s"])
            for c in law["cycles"]:
                g = D.mode_dG_RT(c["nu"], registry, state)
                q = cyc[c["id"]]
                S = q["j_plus"] / omega
                jp = k * a * S
                jm = jp * dexp(g)           # §16: J⁻ = J⁺ e^{ΔG/RT} at the registry's potentials
                out[c["id"]] = {"dG_RT": g, "S": S, "J_plus": jp, "J_minus": jm,
                                "J": jp - jm, "J_scale": jp + jm,
                                "J_minus_diagram": k * a * q["j_minus"] / omega,
                                "Pi_plus": q["Pi_plus"], "Pi_minus": q["Pi_minus"],
                                "sigma_share": q["sigma_share"]}
            out["_rates"] = rates
            out["_p"] = cyc["_p"]
        elif kind == "factored":
            for m in law["modes"]:
                g = D.mode_dG_RT(m["nu"], registry, state)
                S = saturation(m["saturation"], state) - dec(m.get("planted_S_offset", 0.0))
                jp = k * a * S
                jm = jp * dexp(g)
                out[m["id"]] = {"dG_RT": g, "S": S, "J_plus": jp, "J_minus": jm, "J": jp - jm,
                                "J_scale": abs(jp) + abs(jm)}
        elif kind == "net_flow":
            ps = D.psi(state, registry["temperature_K"])
            for m in law["modes"]:
                g = D.mode_dG_RT(m["nu"], registry, state)
                J, scale = Decimal(0), Decimal(0)
                for t in m["flux_terms"]:
                    gt = D.mode_dG_RT(t["cycle_nu"], registry, state)
                    e = dexp(gt + dec(t.get("shift_psi", 0.0)) * ps)
                    kt = dec(t["capacity_fmol_per_s"])
                    J = J + kt * (1 - e)
                    scale = scale + abs(kt) * (1 + e)
                out[m["id"]] = {"dG_RT": g, "J": a * J, "J_scale": a * scale}
        else:
            raise ValueError(f"unknown law kind {kind!r}")
        return out


def modes(law: dict) -> list:
    return law["cycles"] if law["kind"] == "diagram" else law["modes"]


# --------------------------------------------------------------------------------------------
# A population's rates on its host
# --------------------------------------------------------------------------------------------

def population_rates(law: dict, population: dict, registry: dict, host_state: dict) -> dict:
    """Rows per host end, heat, work (held rows), the stored rate (moved rows' standard part),
    the charge flux a → b and the current, with every mode's flux. Exact to 50 digits."""
    st = law_state(population, host_state)
    with context():
        RT = exact.RT_J_per_mol(registry["temperature_K"])
        c0 = dec(registry["standard_concentration_mM"])
        fl = mode_fluxes(law, registry, st, population["capacity_fmol_per_s"],
                         population.get("availability", 1.0))
        held = {(r[0], r[1]) for r in population.get("held_rows", [])}
        rows, supply = {}, {}
        heat, work, stored, charge_ab = Decimal(0), Decimal(0), Decimal(0), Decimal(0)
        for m in modes(law):
            J = fl[m["id"]]["J"]
            g = fl[m["id"]]["dG_RT"]
            heat = heat - J * g * RT
            held_nu = []
            nq_ab = 0
            for s, end, n in m["nu"]:
                sp = registry["species"][s]
                hend = host_end(population, end)
                key = f"{s}@{hend}"
                if (s, hend) in held:
                    held_nu.append((s, end, n))
                    supply[key] = supply.get(key, Decimal(0)) - int(n) * J
                    continue
                rows[key] = rows.get(key, Decimal(0)) + int(n) * J
                stored = stored + J * int(n) * (dec(sp["mu0_RT"]) * RT - RT * dln(c0))
                if hend == "b":
                    nq_ab += int(sp["valence"]) * int(n)
            if held_nu:
                work = work - J * D.mode_dG_RT(held_nu, registry, st) * RT
            charge_ab = charge_ab + nq_ab * J
        F = exact.F_C_per_mol()
        return {"modes": fl, "rows_fmol_per_s": rows, "held_supply_fmol_per_s": supply,
                "heat_pJ_per_s": heat / 1000, "work_pJ_per_s": work / 1000,
                "stored_standard_pJ_per_s": stored / 1000,
                "charge_a_to_b_fmol_per_s": charge_ab,
                "current_a_to_b_pA": charge_ab * F / 1000}


def population_total_JdG(law: dict, population: dict, registry: dict, host_state: dict):
    """The population guard's quantity Σ_m J_m ΔG_m (pJ/s), and each mode's term."""
    st = law_state(population, host_state)
    with context():
        RT = exact.RT_J_per_mol(registry["temperature_K"])
        fl = mode_fluxes(law, registry, st, population["capacity_fmol_per_s"],
                         population.get("availability", 1.0))
        terms = {m["id"]: fl[m["id"]]["J"] * fl[m["id"]]["dG_RT"] * RT / 1000 for m in modes(law)}
        return sum(terms.values(), Decimal(0)), terms


# --------------------------------------------------------------------------------------------
# Slopes, exactly (forward-mode duals) and by central differences (the internal check)
# --------------------------------------------------------------------------------------------

def _seeded(host_state: dict, what: tuple, h=None):
    """A copy of the host state with one input seeded as a Dual (or shifted by h)."""
    st = {"phi_V": dict(host_state["phi_V"]),
          "c_mM": {e: dict(v) for e, v in host_state["c_mM"].items()}}
    if what[0] == "V":
        va = dec(st["phi_V"]["a"])
        st["phi_V"]["a"] = Dual(va, 1) if h is None else va + h
        st["phi_V"]["b"] = dec(st["phi_V"]["b"])
    else:
        _, s, e = what
        c = dec(st["c_mM"][e][s])
        st["c_mM"][e][s] = Dual(c, 1) if h is None else c + h
    return st


def slopes(law: dict, population: dict, registry: dict, host_state: dict,
           volumes_pL: dict) -> dict:
    """∂J_m/∂V (fmol/(s V)), the population's conductance ∂I/∂V (pS) and each moved row's
    material slopes ∂(row rate)/∂n_row and max_m |ν ∂J_m/∂n_row| (1/s), exactly."""
    with context():
        F = exact.F_C_per_mol()
        out = {"dJ_dV": {}, "material": {}}
        d = population_rates(law, population, registry, _seeded(host_state, ("V",)))
        G = Decimal(0)
        for m in modes(law):
            J = d["modes"][m["id"]]["J"]
            out["dJ_dV"][m["id"]] = exact.slope(J)
        G = exact.slope(d["charge_a_to_b_fmol_per_s"]) * F / 1000
        out["conductance_pS"] = G
        held = {(r[0], r[1]) for r in population.get("held_rows", [])}
        moved = set()
        for m in modes(law):
            for s, end, _n in m["nu"]:
                he = host_end(population, end)
                if (s, he) not in held:
                    moved.add((s, he))
        for s, he in sorted(moved):
            dd = population_rates(law, population, registry, _seeded(host_state, ("c", s, he)))
            vol = dec(volumes_pL[he])
            row = exact.slope(dd["rows_fmol_per_s"][f"{s}@{he}"]) / vol
            mx = Decimal(0)
            for m in modes(law):
                for s2, end2, n2 in m["nu"]:
                    if s2 == s and host_end(population, end2) == he:
                        mx = max(mx, abs(int(n2) * exact.slope(dd["modes"][m["id"]]["J"]) / vol))
            out["material"][f"{s}@{he}"] = {"row_self_slope_per_s": row,
                                              "max_mode_slope_per_s": mx}
        return out


def slopes_by_differences(law: dict, population: dict, registry: dict, host_state: dict,
                          volumes_pL: dict, rel=Decimal("1e-22")) -> dict:
    """The same slopes by central differences in decimals (the internal second method)."""
    with context():
        F = exact.F_C_per_mol()
        out = {"dJ_dV": {}, "material": {}}
        h = rel
        up = population_rates(law, population, registry, _seeded(host_state, ("V",), h))
        dn = population_rates(law, population, registry, _seeded(host_state, ("V",), -h))
        for m in modes(law):
            dJ = up["modes"][m["id"]]["J"] - dn["modes"][m["id"]]["J"]
            out["dJ_dV"][m["id"]] = dJ / (2 * h)
        out["conductance_pS"] = ((up["charge_a_to_b_fmol_per_s"] - dn["charge_a_to_b_fmol_per_s"]) /
                                 (2 * h)) * F / 1000
        held = {(r[0], r[1]) for r in population.get("held_rows", [])}
        moved = set()
        for m in modes(law):
            for s, end, _n in m["nu"]:
                he = host_end(population, end)
                if (s, he) not in held:
                    moved.add((s, he))
        for s, he in sorted(moved):
            c = dec(host_state["c_mM"][he][s])
            hc = c * rel
            u = population_rates(law, population, registry, _seeded(host_state, ("c", s, he), hc))
            w = population_rates(law, population, registry, _seeded(host_state, ("c", s, he), -hc))
            vol = dec(volumes_pL[he])
            key = f"{s}@{he}"
            out["material"][key] = {"row_self_slope_per_s":
                                    (u["rows_fmol_per_s"][key] - w["rows_fmol_per_s"][key]) /
                                    (2 * hc) / vol}
        return out


# --------------------------------------------------------------------------------------------
# Parse-time checks: charge, moieties and the derived transported charge
# --------------------------------------------------------------------------------------------

def parse_checks(mode_nu: list, registry: dict) -> dict:
    """Σ_e Σ_s z ν (must be 0), each declared moiety's Σ content × ν (must be 0), and
    n_q = Σ_s z ν at P (derived, never declared)."""
    species = registry["species"]
    charge = sum(int(species[s]["valence"]) * int(n) for s, _e, n in mode_nu)
    moieties = {}
    for name, content in registry.get("moieties", {}).items():
        moieties[name] = sum(int(content.get(s, 0)) * int(n) for s, _e, n in mode_nu)
    nq = sum(int(species[s]["valence"]) * int(n) for s, e, n in mode_nu if e == "P")
    ok = charge == 0 and all(v == 0 for v in moieties.values())
    return {"charge_sum": charge, "moiety_sums": moieties, "n_q": nq, "admitted": ok}


def stoichiometry_matches_diagram(law: dict) -> dict:
    """For each declared cycle: whether its ν equals the ν its rates' orders imply."""
    out = {}
    for c in law.get("cycles", []):
        implied = D.implied_stoichiometry(law, c)
        declared = {(s, e): int(n) for s, e, n in c["nu"] if int(n) != 0}
        out[c["id"]] = implied == declared
    return out
