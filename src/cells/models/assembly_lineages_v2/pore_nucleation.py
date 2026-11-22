"""cells.pore_nucleation@1: line-tension nucleation of a pore under tension (FR-31, Phase A).

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
"""

import math

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


def dlog_rate_dt(sigma_n_per_m, temperature_k, gamma_n, e_a_j_per_mol):
    """∂ln k/∂T = E_A/(R·T²) + σ_β/(σ·T) − 3/(2T), per K (the sheet's §8, for s_T)."""
    t = temperature_k
    return (e_a_j_per_mol / (R * t * t) + sigma_beta(gamma_n, t) / (sigma_n_per_m * t)
            - 1.5 / t)  # fmt: skip


def eta_m(temperature_k, e_a_j_per_mol, eta_298=ETA_298_PA_S_M):
    """η_m(T), the membrane's surface viscosity (Pa·s·m), on the declared absolute scale."""
    t = temperature_k
    return eta_298 * (t / T_REF_K) * math.exp(e_a_j_per_mol / R * (1.0 / t - 1.0 / T_REF_K))


def collapse_rate(sigma_n_per_m, temperature_k, gamma_n, e_a_j_per_mol, eta_298=ETA_298_PA_S_M):
    """P = (σ_β·σ)^(1/2)/ζ, with ζ = 4π·η_m(T): the event pair's reverse rate (s⁻¹; the sheet's
    §7)."""
    zeta = 4.0 * math.pi * eta_m(temperature_k, e_a_j_per_mol, eta_298)
    return math.sqrt(sigma_beta(gamma_n, temperature_k) * sigma_n_per_m) / zeta
