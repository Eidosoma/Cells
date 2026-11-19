"""The registered inputs of R-chain and R-clear: python -m validation.fr7.references.worlds
[--check]. Writes interface/inputs.json (or compares it with a fresh build).

Every lifetime, rate, amount and geometry here is this package's own synthetic choice, labelled
synthetic (D217): unit half-lives of 30, 60 and 120 s, maturation in m = 0 or 3 stages with a mean
delay m/kappa = 30 s, a template half-life of 20 s, and horizons of at least five unit half-lives
after the registered clearance row. The engine builds its worlds from these inputs, never from the
reference values.
"""

import argparse
import json
import math
import sys
from pathlib import Path

from validation.fr7.references import chain, clearance

HERE = Path(__file__).resolve().parent
INPUTS = HERE / "interface" / "inputs.json"

AVOGADRO = 6.02214076e23
CHARGE = 1.602176634e-19
BOLTZMANN = 1.380649e-23
LN2 = math.log(2.0)

DT = 1e-3
EPSILON_RESOLUTION = 1e-4
BASAL = 0.02
K_MM, HILL_N = 0.01, 2.0
TEMPLATE_HALF_LIFE = 20.0
NU = 4
ASSEMBLY = 0.02
MATURATION = 0.1  # kappa (1/s): mean delay m/kappa = 30 s at m = 3
STAGES = 3
N0 = 1.0e4
NP0 = 1.0e-4
DOSE_FMOL = 0.2  # c0 = 0.1 mM = 10 K in 2 pL
PULSE = [[0.0, 0.0], [5.0, 0.01], [25.0, 0.0]]  # fmol/s on [5, 25) s
SUPPLIED_PRECURSOR_HALF_LIFE = 300.0
SUPPLIED_NP = 4.0e-4

CELL = dict(
    note="R-cell's pump-free form: one cell, one patch facing a held bath at 0 V, "
         "constant-field leaks, and one gate-free channel population. Synthetic.",
    species=["Na", "K", "Cl"],
    valence=[1, 1, -1],
    bath_mM=[145.0, 5.0, 150.0],
    initial_mM=[12.0, 140.0, 30.0],
    volume_pL=2.0,
    patch_area_m2=4e-10,
    capacitance_F=4e-12,
    leak_permeability_m_s=[1e-10, 0.0, 0.0],
    leak_note="the cell's second permeant route: a Na leak on the patch; Cl is impermeant",
    population=dict(
        law="gate-free and K-selective (relative permeabilities Na 0, K 1, Cl 0), as "
            "kleak_always_open@1 is described in validation/coupling/REFERENCES_USAGE.md",
        permeability_m_s=2e-9,
        relative_permeability=[0.0, 1.0, 0.0],
        reference_density_per_um2=25.0,
        reference_density_per_m2=2.5e13,
        conductance="P N/rho_ref (m^3/s), the view's P a A with a = N/(A rho_ref); N = 1e4 "
                    "is a = 1 on the 400 um^2 patch",
    ),
)

BAND_RULES = dict(
    note="band(row) = bound(row) + max(rel * max(|x(row)|, floor * scale), abs), scale = max "
         "over the world's rows of |x|. The allowance is for a correct second-order engine at "
         "dt = 1 ms (see REFERENCES_USAGE.md, Bands).",
    template=dict(rel=1e-9, floor=1e-9, abs=0.0, quantities=["n_T_fmol"]),
    drive=dict(rel=4e-9, floor=1e-12, abs=0.0, quantities=["D"]),
    factor=dict(rel=1e-9, floor=1.0, abs=0.0, quantities=["F_T"]),
    chain=dict(rel=3e-7, floor=1e-2, abs=0.0,
               quantities=["n_P_fmol", "N_units", "PA_m3_s", "W_fmol", "R_units", "C_P_fmol"]),
    maturation=dict(rel=1e-6, floor=0.1, abs=0.0,
                    quantities=["M1_units", "M2_units", "M3_units"],
                    note="the maturing stages rise as t^(j-1) at an onset, where a split "
                         "scheme's relative error goes as (dt/t)^2: a wider band and a 10% "
                         "floor"),
    material_total=dict(rel=1e-9, floor=1.0, abs=0.0, quantities=["total_fmol"]),
    voltage=dict(rel=0.0, floor=0.0, abs=1e-6, quantities=["V_V"]),
    amounts=dict(rel=1e-6, floor=1.0, abs=0.0, quantities=["Na_fmol", "K_fmol"]),
)


def rows_for(horizon):
    return [0.0, 1.0, 2.0, 5.0] + [float(t) for t in range(10, int(horizon) + 1, 10)]


def _world(horizon, template, units, precursor=None):
    precursor = precursor or dict(n0_fmol=NP0, supply_fmol_per_s=0.0, clearance_per_s=0.0,
                                  note="a finite pool: no supply, no clearance")
    return dict(
        synthetic=True,
        horizon_s=float(horizon),
        rows_s=rows_for(horizon),
        template=template,
        factor=dict(law="hill_activation", K_mM=K_MM, n=HILL_N, basal=BASAL,
                    source="the template's cytosolic concentration n_T/V (mM)",
                    target="the unit producer's rate k_a: consumption k_a F_T n_P"),
        precursor=precursor,
        units=units,
        cell_start=dict(initial_V=None),
    )


def _template(kind):
    k = LN2 / TEMPLATE_HALF_LIFE
    if kind == "dose":
        return dict(kind="dose", n0_fmol=DOSE_FMOL, clearance_per_s=k,
                    half_life_s=TEMPLATE_HALF_LIFE, production=[[0.0, 0.0]])
    if kind == "pulse":
        return dict(kind="production pulse", n0_fmol=0.0, clearance_per_s=k,
                    half_life_s=TEMPLATE_HALF_LIFE, production=PULSE)
    return dict(kind="none (the control: F_T = b throughout)", n0_fmol=0.0, clearance_per_s=k,
                half_life_s=TEMPLATE_HALF_LIFE, production=[[0.0, 0.0]])


def _units(stages, half_life, N_start=N0, M0=None):
    cu = chain.units_per_fmol(NU, AVOGADRO)
    return dict(nu=NU, units_per_fmol=cu, assembly_per_s=ASSEMBLY, stages=stages,
                maturation_per_s=MATURATION if stages else None,
                mean_maturation_delay_s=stages / MATURATION if stages else 0.0,
                removal_per_s=LN2 / half_life, half_life_s=float(half_life),
                N0=N_start, M0=list(M0) if M0 is not None else [0.0] * stages,
                removal_note="k_r acts on all of N, the declared N0 included; maturing units "
                             "are not removed")


def build_worlds():
    k_P = LN2 / SUPPLIED_PRECURSOR_HALF_LIFE
    kr60 = LN2 / 60.0
    cu = chain.units_per_fmol(NU, AVOGADRO)
    basal_flux = cu * ASSEMBLY * BASAL * SUPPLIED_NP  # units/s at the basal steady state
    supplied = dict(n0_fmol=SUPPLIED_NP, clearance_per_s=k_P,
                    supply_fmol_per_s=SUPPLIED_NP * (k_P + ASSEMBLY * BASAL),
                    half_life_s=SUPPLIED_PRECURSOR_HALF_LIFE,
                    note="supplied and cleared; the start is the chain's basal steady state "
                         "(F_T = b)")
    return {
        "W1_dose_m0_t30": _world(450, _template("dose"), _units(0, 30.0)),
        "W2_dose_m3_t60": _world(600, _template("dose"), _units(STAGES, 60.0)),
        "W3_pulse_m3_t120": _world(900, _template("pulse"), _units(STAGES, 120.0)),
        "W4_pulse_m0_t60": _world(600, _template("pulse"), _units(0, 60.0)),
        "W5_supplied_dose_m3_t60": _world(
            600, _template("dose"),
            _units(STAGES, 60.0, N_start=basal_flux / kr60,
                   M0=[basal_flux / MATURATION] * STAGES), supplied),
        "W6_no_template_m3_t60": _world(600, _template("none"), _units(STAGES, 60.0)),
    }


def build_cases():
    k_T = LN2 / TEMPLATE_HALF_LIFE
    return dict(
        note="R-clear's synthetic trajectories (clauses 3 to 5): exact by the matrix exponential "
             "of the cytosol-and-compartments linear system. Synthetic.",
        volume_pL=CELL["volume_pL"], K_mM=K_MM, n=HILL_N, basal=BASAL,
        clearance_per_s=k_T, rows_s=[float(t) for t in range(0, 1001, 10)],
        cases={
            "RC1_cytosol_dose": dict(n0_fmol=DOSE_FMOL, production=[[0.0, 0.0]],
                                     compartments={}),
            "RC2_releasing_compartment": dict(
                n0_fmol=DOSE_FMOL, production=[[0.0, 0.0]],
                compartments={"endosome": dict(n0_fmol=0.2, release=[[0.0, LN2 / 50.0]],
                                               degradation_per_s=0.0)}),
            "RC3_recrossing": dict(n0_fmol=0.0,
                                   production=[[0.0, 0.01], [10.0, 0.0], [400.0, 0.005],
                                               [410.0, 0.0]],
                                   compartments={}),
            "RC4_not_cleared": dict(n0_fmol=DOSE_FMOL, production=[[0.0, 2e-6]],
                                    compartments={}),
            "RC5_compartment_stops_releasing": dict(
                n0_fmol=DOSE_FMOL, production=[[0.0, 0.0]],
                compartments={"vesicle": dict(n0_fmol=0.2,
                                              release=[[0.0, LN2 / 100.0], [300.0, 0.0]],
                                              degradation_per_s=0.0)}),
            "RC6_no_template": dict(n0_fmol=0.0, production=[[0.0, 0.0]], compartments={}),
        },
        definitional={
            "RC7_threshold_equality": dict(
                note="a drive series given directly: one row equals epsilon exactly",
                rows_s=[0.0, 10.0, 20.0, 30.0, 40.0],
                D=[0.5, 1e-3, 2e-6, 1e-6, 5e-7]),
        },
    )


def build():
    eps = clearance.epsilon_computation(BASAL, EPSILON_RESOLUTION)["epsilon"]
    inputs = dict(
        kind="cells.fr7_reference_inputs@1",
        registered="2026-11-19",
        synthetic="every lifetime, rate, amount and geometry is this package's own synthetic "
                  "choice, labelled synthetic (D217)",
        units=dict(amount="fmol", volume="pL", concentration="mM", time="s", potential="V",
                   permeability="m/s", area="m^2", capacitance="F", units="count",
                   conductance="m^3/s (permeability x area)"),
        constants=dict(avogadro_per_mol=AVOGADRO, elementary_charge_C=CHARGE,
                       boltzmann_J_per_K=BOLTZMANN, faraday_C_per_mol=AVOGADRO * CHARGE,
                       gas_J_per_mol_K=AVOGADRO * BOLTZMANN, temperature_K=310.0,
                       note="exact SI (2019); F = N_A e and R = N_A k_B"),
        step=dict(dt_s=DT, note="the declared step: bands and the held factor's plant are "
                                "evaluated at dt = 1 ms"),
        clearance=dict(
            drive="D = (F_T(c*) - b)/(1 - b) = c*^n/(K^n + c*^n), "
                  "c* = (cytosolic n_T + sum over releasing compartments of n_T)/V",
            epsilon=eps, resolution_relative=EPSILON_RESOLUTION,
            resolution_note="a constant drive of epsilon moves the steady-state units, and so "
                            "the conductance, by less than this relative amount",
            operating_range_mM=[0.0, 1.0],
            operating_range_amendment=(
                "Amended 19 November 2026, before any engine output, at the lead's direction: "
                "[1e-7, 1] mM became [0, 1] mM. B1' refuses a routed half-step whose source "
                "leaves its declared range, and the template falls below 1e-7 mM inside the "
                "horizons (from 398.63 s in the dose worlds and 414.21 s in the pulse worlds; "
                "W6 has none from the start). The mean-field floor of about 10^2 molecules per "
                "cell is a stated limit, not a refusal (clearance.json, operating_range)."),
            rule="the fall-back rule over each world's saved rows (clearance.t_clear)"),
        power=dict(margin=3.0, note="a plant has power on a compared row when it moves the row "
                                    "by at least 3 bands"),
        band_rules=BAND_RULES,
        cell=CELL,
        worlds=build_worlds(),
        clearance_cases=build_cases(),
    )
    for name, w in inputs["worlds"].items():
        world = chain.World(inputs, name)
        mM = CELL["initial_mM"]
        w["cell_start"]["initial_V"] = chain.zero_current_potential(world, world.N_start, mM)
        w["cell_start"]["note"] = ("the zero-current potential of the declared start (leak and "
                                   "population at N0); the charge is C V0 and the background "
                                   "follows")
        w["cell_start"]["initial_amounts_fmol"] = [x * CELL["volume_pL"] for x in mM]
        charge = CELL["capacitance_F"] * w["cell_start"]["initial_V"] / (
            inputs["constants"]["faraday_C_per_mol"] * chain.FMOL)
        w["cell_start"]["background_fmol"] = charge - math.fsum(
            z * n for z, n in zip(CELL["valence"], w["cell_start"]["initial_amounts_fmol"],
                                  strict=True))
    return inputs


def text():
    return json.dumps(build(), indent=1) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    fresh = text()
    if args.check:
        same = INPUTS.read_text() == fresh
        print("inputs: equal" if same else "inputs: DIFFER")
        return 0 if same else 1
    INPUTS.write_text(fresh)
    print(f"wrote {INPUTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
