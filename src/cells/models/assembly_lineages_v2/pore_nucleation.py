"""cells.assembly_hazard.pore_nucleation@1: line-tension nucleation of a pore under tension (FR-31, Phase A).

The declared laws are docs/VESICLE_PORES_LAWS.md, tagged `pores-laws-sheet-registered-2026-11-22`
(D287). This module holds the law's pure functions: the rate, its temperature slope and the
damping's temperature law. The hazard clock, the held tension and the fates are separate steps.

**The rate** (the sheet's §2 and §4). A vesicle of membrane area A at a held tension σ (N/m) and
temperature T (K) opens a pore, and so ruptures, at

    k_v = A · ν_A · σ^(1/2) · T^(−3/2) · exp(−E_A/(R·T)) · exp(−π·Γ²/(σ·k_B·T))

- This is Evans and Smith 2011's Kramers rate (their B.2.1), (σ_β·σ)^(1/2)/ζ·exp(−σ_β/σ) with
  σ_β = πΓ²/(k_B·T), taken per membrane area.
- The damping is the membrane's, ζ = 4π·η_m(T), with η_m(T) ∝ T·exp(E_A/(R·T)). E_A is DOPC's lipid
  lateral diffusion activation energy, through Saffman and Delbrück.
- ν_A gathers the site density, Γ, k_B^(−1/2), the 4π and η_m's scale. Its units are
  m⁻²·s⁻¹·(N/m)^(−1/2)·K^(3/2).

**The absolute scale** (the sheet's §7): η_m(T) = η₂₉₈·(T/298.15 K)·exp[(E_A/R)·(1/T − 1/298.15 K)],
with η₂₉₈ = 3 × 10⁻¹⁰ Pa·s·m. Only the event pair and the heat booked at opening read it.

**The declaration** (a world's `hazard`, the first law of cells.assembly_hazard@1; D148: a world
that declares none runs as before): {"law": "cells.assembly_hazard.pore_nucleation@1", "nu_A", "gamma_N",
"E_A_J_per_mol", "eta_298_Pa_s_m"}, each {value, provenance} (§0.2e rule 3), for one lipid
composition (D287). ν_A is in m⁻²·s⁻¹·(N/m)^(−1/2)·K^(3/2), Γ in N, E_A in J/mol, η₂₉₈ in Pa·s·m;
T is the world's temperature. Refused with it (Phase A; the lead's rulings of 22 November 2026):
- a world without cells.assembly_geometry.bilayer_geometry@1, so with no geometry or with FR-21's prescribed shell:
  the vesicle's area is the bilayer's, A = q·W/2;
- under a hold, any step that changes a membrane place's count (its net change, not the
  membrane's total): the area then stays fixed, so each vesicle's rate is constant through the
  hold (`phase_a_refusals`, which spec.parse's exact branch calls under a hold, and
  cells.assembly_representation.rate_equations@1's T2). With no hold the tension comes from F and such steps are admitted
  in both representations (OL6 S3 and S4; exact events carry the clock on the device,
  pore_device.py);
- a membrane or lumen species without a pool place to return to at a rupture (as §0.2c rule 8
  refuses it in a world that can lyse).
The experiment's hold and the cross-checks with it are tension_hold.py's (spec.parse).

**The rate at real area and tension** (`rate_at`, OL6 S3): the same closed form, traceable, for
cells.assembly_representation.rate_equations@1, whose vesicles have real areas and, with an osmotic lumen, a tension from F
(the design note's §3.5). It is 0 where σ ≤ 0 (a floppy vesicle), with the logarithms guarded so
that its gradient is finite on both sides.
"""

import math

from cells.definitions.specs import ConfigError, finite_number
from cells.models.assembly_lineages_v2 import BILAYER_GEOMETRY, MODEL_ID, PORE_NUCLEATION
from cells.models.assembly_lineages_v2.interfaces import AssemblyHazard
from cells.modules import Citation, CitedWork

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

K_B = 1.380649e-23  # J/K, exact (SI 2019)
N_A = 6.02214076e23  # 1/mol, exact (SI 2019)
R = K_B * N_A  # J/(mol K)
T_REF_K = 298.15  # the absolute scale's reference temperature (the sheet's §7)
ETA_298_PA_S_M = 3e-10  # η₂₉₈, declared (the sheet's §7; Fitzgerald et al. 2023's 2–4 × 10⁻¹⁰)


def sigma_beta(gamma_n, temperature_k):
    """σ_β = πΓ²/(k_B·T), the thermal tension scale (N/m)."""
    return math.pi * gamma_n**2 / (K_B * temperature_k)


def log_rate_per_area(sigma_n_per_m, temperature_k, log_nu_a, gamma_n, e_a_j_per_mol):
    """ln j(σ, T): the hazard per membrane area (ln of m⁻²·s⁻¹)."""
    if not (sigma_n_per_m > 0 and temperature_k > 0):
        raise ValueError("The rate needs a positive tension and temperature")
    return (
        log_nu_a
        + 0.5 * math.log(sigma_n_per_m)
        - 1.5 * math.log(temperature_k)
        - e_a_j_per_mol / (R * temperature_k)
        - math.pi * gamma_n**2 / (sigma_n_per_m * K_B * temperature_k)
    )


def log_rate(area_m2, sigma_n_per_m, temperature_k, log_nu_a, gamma_n, e_a_j_per_mol):
    """ln k_v = ln A + ln j: the vesicle's hazard (ln of s⁻¹)."""
    return math.log(area_m2) + log_rate_per_area(
        sigma_n_per_m, temperature_k, log_nu_a, gamma_n, e_a_j_per_mol
    )


def rate_at(area_m2, sigma_n_per_m, temperature_k, log_nu_a, gamma_n, e_a_j_per_mol, xp):
    """k_v (1/s) at real areas and tensions (arrays, traceable): exp of log_rate's closed form where
    σ > 0 and A > 0, and 0 elsewhere, each logarithm taken at 1 there (the double-where form)."""
    t = temperature_k
    live = (sigma_n_per_m > 0) & (area_m2 > 0)
    sigma = xp.where(live, sigma_n_per_m, 1.0)
    area = xp.where(live, area_m2, 1.0)
    log_k = xp.log(area) + (
        log_nu_a
        + 0.5 * xp.log(sigma)
        - 1.5 * math.log(t)
        - e_a_j_per_mol / (R * t)
        - math.pi * gamma_n**2 / (sigma * K_B * t)
    )
    return xp.where(live, xp.exp(log_k), 0.0)


def dlog_rate_dt(sigma_n_per_m, temperature_k, gamma_n, e_a_j_per_mol):
    """∂ln k/∂T = E_A/(R·T²) + σ_β/(σ·T) − 3/(2T), per K (the sheet's §8, for s_T)."""
    t = temperature_k
    return (e_a_j_per_mol / (R * t * t) + sigma_beta(gamma_n, t) / (sigma_n_per_m * t)
            - 1.5 / t)  # fmt: skip


def eta_m(temperature_k, e_a_j_per_mol, eta_298=ETA_298_PA_S_M):
    """η_m(T), the membrane's surface viscosity (Pa·s·m), on the declared absolute scale."""
    t = temperature_k
    return eta_298 * (t / T_REF_K) * math.exp(e_a_j_per_mol / R * (1.0 / t - 1.0 / T_REF_K))


def log_site_density(log_nu_a, gamma_n, e_a_j_per_mol, eta_298=ETA_298_PA_S_M):
    """ln n_s (n_s per m²), the sheet's §7 closed form, which no temperature enters:
    n_s = 4π·η₂₉₈·ν_A·exp(−E_A/(R·298.15 K)) / (π^(1/2)·Γ·k_B^(−1/2)·298.15 K)."""
    return (math.log(4.0 * math.pi * eta_298) + log_nu_a - e_a_j_per_mol / (R * T_REF_K)
            - 0.5 * math.log(math.pi) - math.log(gamma_n) + 0.5 * math.log(K_B)
            - math.log(T_REF_K))  # fmt: skip


def collapse_rate(sigma_n_per_m, temperature_k, gamma_n, e_a_j_per_mol, eta_298=ETA_298_PA_S_M):
    """P = (σ_β·σ)^(1/2)/ζ, with ζ = 4π·η_m(T): the event pair's reverse rate (s⁻¹; the sheet's
    §7)."""
    zeta = 4.0 * math.pi * eta_m(temperature_k, e_a_j_per_mol, eta_298)
    return math.sqrt(sigma_beta(gamma_n, temperature_k) * sigma_n_per_m) / zeta


# ------------------------------------------------------------------ the world's declaration

KEYS = ("nu_A", "gamma_N", "E_A_J_per_mol", "eta_298_Pa_s_m")  # beside `law`
UNITS = {
    "nu_A": "m^-2 s^-1 (N/m)^(-1/2) K^(3/2)",
    "gamma_N": "N",
    "E_A_J_per_mol": "J/mol",
    "eta_298_Pa_s_m": "Pa s m",
}


def _value(raw, name):
    if not isinstance(raw, dict) or set(raw) != {"value", "provenance"}:
        raise ConfigError(f"world: hazard: {name} is {{value, provenance}} (§0.2e rule 3)")
    if not isinstance(raw["provenance"], str) or not raw["provenance"]:
        raise ConfigError(f"world: hazard: {name}'s provenance is stated ('unsourced' if so)")
    value = finite_number(raw["value"], f"world: hazard: {name}", positive=True)
    return value, raw["provenance"]


def membrane_changes(world):
    """[(step, place)] of every step that changes a membrane place's count (its net change)."""
    out = []
    by_name = {p.name: p for p in world.places}
    for step in world.steps:
        net = {}
        for name, count in step.reactants:
            net[name] = net.get(name, 0) - count
        for name, count in step.products:
            net[name] = net.get(name, 0) + count
        out += [(step.id, n) for n, c in net.items() if c and by_name[n].phase == "membrane"]
    return out


def parse_data(raw, world):
    """The world's hazard block (spec.py calls it last, after the geometry and the population)."""
    if not isinstance(raw, dict) or raw.get("law") != PORE_NUCLEATION:
        raise ConfigError(f"world: hazard names its law, {PORE_NUCLEATION}")
    if set(raw) != {"law", *KEYS}:
        raise ConfigError(
            f"world: hazard: {PORE_NUCLEATION} declares {', '.join(KEYS)}, each {{value, "
            f"provenance}}; missing={sorted(set(KEYS) - set(raw))}, "
            f"unknown={sorted(set(raw) - {'law', *KEYS})}"
        )
    if world.geometry is None or world.geometry[0] != BILAYER_GEOMETRY:
        raise ConfigError(
            f"world: hazard: {PORE_NUCLEATION} reads the vesicle's area from its bilayer, A = q W "
            f"/ 2, so the world declares {BILAYER_GEOMETRY}"
            + ("; a prescribed shell has no tension (FR-21)" if world.geometry is not None else "")
        )
    pool = {p.species for p in world.places if p.phase == "pool"}
    homeless = sorted({p.species for p in world.places if p.phase in ("membrane", "lumen")} - pool)
    if homeless:
        raise ConfigError(
            "world: hazard: a pore's rupture is a lysis, so every membrane and lumen species has a "
            f"pool place to return to; {', '.join(homeless)} has none (§0.2c rule 8)"
        )
    return {name: _value(raw[name], name) for name in KEYS}


def phase_a_refusals(world):
    """Exact events' refusal of a pore world whose areas change (spec.parse's exact branch, right
    after the world parses, where parse_data refused it before OL6 S3): the host clock's rate is
    constant through a hold only while no step changes a membrane place's count."""
    changed = membrane_changes(world)
    if changed:
        step, place = changed[0]
        raise ConfigError(
            f"world: hazard: step {step} changes {place}'s count. Phase A holds each vesicle's "
            "area fixed, so its rate is constant through a hold: a world that declares the pore "
            "law declares no step that changes a membrane place's count (the lead's ruling of 22 "
            "November 2026)"
        )


def data_to_dict(data):
    return {"law": PORE_NUCLEATION, **{
        name: {"value": data[name][0], "provenance": data[name][1]} for name in KEYS
    }}  # fmt: skip


def parameters(world):
    """(ln ν_A, Γ, E_A, η₂₉₈) of a world that declares the law."""
    data = world.hazard[1]
    return (math.log(data["nu_A"][0]), data["gamma_N"][0], data["E_A_J_per_mol"][0],
            data["eta_298_Pa_s_m"][0])  # fmt: skip


FORMULAS = {
    "rate": "k_v = A nu_A sigma^(1/2) T^(-3/2) exp(-E_A/(R T)) exp(-pi Gamma^2/(sigma k_B T)) "
    "(1/s): A = q W / 2 the vesicle's area (m^2), sigma the held tension (N/m), T the world's "
    "temperature (K), R = N_A k_B",
    "barrier": "E(r) = 2 pi r Gamma - pi r^2 sigma; r_c = Gamma/sigma; E_c = pi Gamma^2/sigma; "
    "sigma_beta = pi Gamma^2/(k_B T)",
    "damping": "zeta = 4 pi eta_m(T), eta_m(T) = eta_298 (T/298.15 K) exp[(E_A/R)(1/T - "
    "1/298.15 K)]",
    "pair": "the reverse P = (sigma_beta sigma)^(1/2)/zeta, the collapse of a critical pore; "
    "ln(k_v/P) = ln(A n_s) - sigma_beta/sigma = -(dF - w)/k_BT, with dF = 2 pi r_c Gamma - k_BT "
    "ln(A n_s) and w = sigma pi r_c^2, the hold's work",
    "site_density": "n_s = 4 pi eta_298 nu_A exp(-E_A/(R 298.15 K)) / (pi^(1/2) Gamma "
    "k_B^(-1/2) 298.15 K)",
    "clock": "each vesicle's H(t) = integral of k_v dt and threshold E = -ln u, u from the pore "
    "stream (domain 7, the vesicle's key, counter its pore draws from 0); it fires when H reaches "
    "E (Anderson 2007)",
    "domain": "a hold with sigma > sigma_beta/4 is refused (sigma_beta >> sigma)",
}

LAW = law_registry.BUILTIN.register(
    AssemblyHazard(
        "cells.assembly_hazard.pore_nucleation@1",
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/VESICLE_PORES_LAWS.md, tagged pores-laws-sheet-registered-2026-11-22 (§1-§5, "
            "§7; D287), from Evans and Smith (2011), New J Phys 13:095010, Appendix B.2",
            "Kramers' overdamped escape over the cavitation barrier, their (B.2.1), taken per "
            "membrane area (Freeman, Wang and Weaver 1994) and damped by the membrane's surface "
            "viscosity, whose temperature law is DOPC's lateral diffusion (Filippov, Oradd and "
            "Lindblom 2003, through Saffman and Delbruck 1975)",
            "no numbers taken: every parameter is the world's, with its provenance",
            (
                "per membrane area at a site density, where Evans and Smith's rate is per "
                "nucleation site (D287)",
                "the line tension is constant in temperature: no measured law was found (§4)",
                "the logarithm in Saffman and Delbruck's mobility is neglected (§4)",
                "a vesicle's first rupture is its first opening: declared, uncited (§2)",
            ),
            (
                CitedWork(
                    ("E. Evans", "B. A. Smith"),
                    2011,
                    "Kinetics of hole nucleation in biomembrane rupture",
                    doi="10.1088/1367-2630/13/9/095010",
                ),
            ),
        ),
        test="tests/unit/test_assembly_lineages_v2_pores.py::test_the_rate_is_the_sheets_closed_form",
        energy_role="passive",
        energy_source=None,
        reads=("tension", "area", "temperature"),
        stream="pore",
        outcome="lysis",
        data=KEYS,
        parse_data=parse_data,
        data_to_dict=data_to_dict,
        formulas=FORMULAS,
    )
)
assert LAW.law_id == PORE_NUCLEATION
