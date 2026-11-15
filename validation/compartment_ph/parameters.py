"""The generic parameters of FR-4's and FR-5's first acceptance worlds, in one place.

docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §13 (generic; no study's names). Every derived quantity the
worlds, the dt study and the references use is computed here from the declared values, so the
three read one source. Representation: a lumped population of N identical compartments as one
node (§1), with N x volume, area, capacitance and transporter capacity.
"""

import math
from dataclasses import dataclass, field, replace

F = 6.02214076e23 * 1.602176634e-19  # as cells.processes.electrochemistry
R = 6.02214076e23 * 1.380649e-23
N_A = 6.02214076e23
C0_mM = 1000.0
LN10 = math.log(10.0)


def sphere(radius_m):
    """(volume pL, area m^2) of a sphere."""
    return 4.0 / 3.0 * math.pi * radius_m**3 * 1e15, 4.0 * math.pi * radius_m**2


def h_from_ph(ph):
    return C0_mM * 10.0 ** (-ph)


@dataclass(frozen=True)
class Buffer:
    """One buffer species: its registry entry is (mu_HB - mu_B)/RT = -pK ln 10, mu_H = 0."""

    name: str
    pk: float
    total_mM: float
    base_valence: int = -1
    k_on_per_mM_s: float = 1e7  # for the envelope check and the kinetic reference only

    @property
    def mu_acid_minus_base_RT(self):
        return -self.pk * LN10

    @property
    def k_mM(self):
        return C0_mM * math.exp(self.mu_acid_minus_base_RT)


@dataclass(frozen=True)
class World:
    """FR-4 §13.1's world; FR-5's (§13.2) adds the damage and the cargo."""

    temperature_K: float = 310.0
    owner_radius_m: float = 10e-6
    member_radius_m: float = 250e-9
    members: int = 1000
    specific_capacitance_F_m2: float = 0.01
    bath_mM: dict = field(default_factory=lambda: dict(Na=145.0, K=5.0, Cl=110.0, pH=7.4))
    cytosol_mM: dict = field(default_factory=lambda: dict(Na=10.0, K=140.0, Cl=10.0, pH=7.2))
    lumen_mM: dict = field(default_factory=lambda: dict(Na=10.0, K=140.0, Cl=10.0, pH=7.2))
    cytosol_buffer: Buffer = Buffer("B_c", 7.2, 50.0)
    lumen_buffer: Buffer = Buffer("B_L", 6.0, 40.0)
    fuel_mM: dict = field(default_factory=lambda: dict(ATP=3.0, ADP=0.3, Pi=3.0))
    delta_g0_prime_J_mol: float = -30500.0
    fuel_ph_band: float = 0.05
    pump_n: int = 2
    pump_cycles_per_member_s: float = 5000.0
    km_proton_mM: float = 1e-4
    km_atp_mM: float = 0.1
    proton_leak_m_s: float = 6e-7
    counterion_k_m_s: float = 5e-10
    end_s: float = 900.0
    standard_concentration_mM: float = 1000.0  # the registry's c0 (one authority)
    trace_mM: float = 1e-9  # a row that does not apply at a node is this declared trace
    trace_floor_fmol: float = 1e-18  # its declared material floor (the registry's background)
    dt_s: float = 1e-3

    # --- derived -------------------------------------------------------------------------------
    @property
    def owner(self):
        return sphere(self.owner_radius_m)

    @property
    def lumen_volume_pL(self):
        return self.members * sphere(self.member_radius_m)[0]

    @property
    def patch_area_m2(self):
        return self.members * sphere(self.member_radius_m)[1]

    @property
    def patch_capacitance_F(self):
        return self.specific_capacitance_F_m2 * self.patch_area_m2

    @property
    def pump_capacity_fmol_s(self):
        return self.pump_cycles_per_member_s * self.members / N_A * 1e15

    def proton_equivalents_fmol(self, ph, buffer, volume_pL):
        """H_eq = V (h + B h / (h + K)) at the declared start pH."""
        h = h_from_ph(ph)
        return volume_pL * (h + buffer.total_mM * h / (h + buffer.k_mM))

    def counterion_rate_per_s(self, dt_s=None):
        """Max-side dt x G/C_b of the K+ counterion (the world declares its dt with it)."""
        c = max(self.cytosol_mM["K"], self.lumen_mM["K"])
        g = F * F / (R * self.temperature_K) * self.counterion_k_m_s * self.patch_area_m2 * c
        return g / self.patch_capacitance_F * (dt_s or self.dt_s)

    def held_fuel_drive_J_mol(self):
        f = self.fuel_mM
        return self.delta_g0_prime_J_mol + R * self.temperature_K * math.log(
            f["ADP"] * f["Pi"] / (f["ATP"] * C0_mM))

    def control(self):
        """The negative control: the counterion route removed (P_K = 0)."""
        return replace(self, counterion_k_m_s=0.0)


@dataclass(frozen=True)
class DamageWorld:
    """FR-5 §13.2 (revised after the references' R-transfer runs): two arms on FR-4's state.

    - Arm T, the condition: X crosses while the lumen is acidic and stops when a proton-only
      damage raises the lumen's pH above pH50 (no cargo pore), then resumes after resealing.
    - Arm R, the release: X is held in the lumen by a slow gated route until damage opens a cargo
      pore and a proton pore, giving a release burst; resealing lets the pump re-acidify.
    The start is FR-4's engine checkpoint at 1800 s (steady state), passed to the references as
    tr.Start. X's budget: 1e-3 of the lumen's initial X at every record, for the lumen's X and
    the gated route's cumulative transfer; each control must differ by at least 10 x the budget.
    """

    arm: str = "R"
    base: World = World()
    start_checkpoint_s: float = 1800.0  # FR-4's run to steady state; FR-5's t = 0
    horizon_s: float = 400.0
    cargo_lumen_mM: float = 1.0
    cargo_cytosol_mM: float = 1e-4  # a resolved start, not a trace
    cargo_transfer_m_s: float = 1e-10
    ph50: float = 5.5
    ph_slope: float = 4.0
    injury_rate_per_s: float = 1.0
    injury_window_s: tuple = (100.0, 160.0)
    resealing_rate_per_s: float = 0.05
    pore_proton_m_s: float = 1e-5  # explicit at 1 ms: max-side dt x G/C_b = 0.029 at pH 5.1
    pore_cargo_m_s: float = 1e-6
    x_budget_fraction: float = 1e-3  # of the lumen's initial X
    control_margin: float = 10.0  # each control's effect >= this x the budget
    ionic_pores: bool = False  # refused in version 1, until the implicit patch (§9)


ARM_T = DamageWorld(arm="T", cargo_transfer_m_s=1e-9, injury_window_s=(60.0, 120.0),
                    pore_cargo_m_s=0.0)
ARM_R = DamageWorld(arm="R")
