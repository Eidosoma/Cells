"""R-loop's registered inputs, a dated addition to the interface:
python -m validation.fr7.references.loop_worlds [--check]. Writes interface/loop_inputs.json.

**The world.** It is the FR-7 lane's probe world (D231), from the input values the lead relayed:
EXPORT, numbers only, with every value the engine computed removed. The lead accepted these
choices: m = 0, b_T = 0.2, t_d = 260 s, a horizon of 560 s, dt = 1 ms and R-chain's row grid. The
user's ruling D233 scales the template's K and dose x5 together (K 0.05 mM, dose 0.5 mM).

**Computed here, as the lead asked:**
- the start: the closed loop's own steady state with no template and N = N0;
- s0, F_loop0, and the precursor's n_P0 and S_P;
- F*: the closed trajectory's own loop factor at t_d;
- the bound on |F*_engine - F*_reference|, which covers the engine's half-step lag in its applied
  factor.
"""

import argparse
import json
import sys
from pathlib import Path

from validation.fr7.references import design, loop, worlds

HERE = worlds.HERE
IFACE = HERE / "interface"
INPUTS = IFACE / "loop_inputs.json"
EXPORT = Path("/mnt/workspaces/Cells/fr7-references-20261119-01/r-loop-inputs/"
              "f4_world_inputs_for_references.json")
EXPORT_COPY = IFACE / "loop_world_export.json"  # the relayed input values, kept beside the inputs
REGISTERED = "2026-11-19"
# D233 (the user's ruling, option 2): the template's K and dose x5 together
TEMPLATE_K_MM, TEMPLATE_DOSE_MM = 0.05, 0.5
TEMPLATE_NOTE = (
    "D233: F4's template scales its half-saturation K and its dose together, x5 (K 0.05 mM, "
    "dose 0.5 mM; n, the 20 s half-life, b_T 0.2 and epsilon unchanged). Only c/K drives the "
    "cell, so F_T(t), t_clear (260 s) and every non-template row are unchanged; the template's "
    "tail crosses D150's mean-field floor (10^2 molecules in 7.5 fL) at 289.3 s instead of "
    "242.8 s, after the cut at t_d = 260 s, and clearance (D <= epsilon) comes at about 320 "
    "molecules, above the floor")

LOOP_BAND_RULES = dict(
    note="R-chain's rule, band = bound + max(rel max(|x|, floor scale), abs), at dt = 1 ms. The "
         "clamped arm's bands add the propagated F* allowance (loop_design.py).",
    template=dict(rel=1e-9, floor=1e-9, abs=0.0, quantities=["n_T_fmol"]),
    drive=dict(rel=4e-9, floor=1e-12, abs=0.0, quantities=["D"]),
    factor=dict(rel=1e-9, floor=1.0, abs=0.0, quantities=["F_T"]),
    chain=dict(rel=3e-7, floor=1e-2, abs=0.0,
               quantities=["n_P_fmol", "N_units", "PA_units_m3_s", "W_fmol", "R_units",
                           "C_P_fmol"]),
    material_total=dict(rel=1e-9, floor=1.0, abs=0.0, quantities=["total_fmol"]),
    regulator=dict(rel=0.0, floor=0.0, abs=1e-8, quantities=["s"]),
    voltage=dict(rel=0.0, floor=0.0, abs=1e-6, quantities=["V_V"]),
    amounts=dict(rel=1e-6, floor=1.0, abs=0.0, quantities=["Na_fmol", "K_fmol", "M_fmol"]),
    pump=dict(rel=1e-6, floor=1.0, abs=0.0, quantities=["pump_fmol_per_s"]),
)


def plant_variants(dt):
    """The closed arm's plants, and the clamped arm's confound (cut_at_one)."""
    V = loop.LoopVariant
    return {
        "nu_off_by_one": V("nu_off_by_one", nu_delta=1),
        "cu_without_1e-15": V("cu_without_1e-15", cu_per_mol=True),
        "maturation_stage_skipped": V("maturation_stage_skipped", stages_delta=-1),
        "removal_on_increment_only": V("removal_on_increment_only", removal_on_increment=True),
        "route_on_precursor_clearance": V("route_on_precursor_clearance",
                                          route_on_clearance=True),
        "factor_held_from_step_start": V("factor_held_from_step_start", factor_lag_s=0.5 * dt),
        "factor_from_amount": V("factor_from_amount", factor_from_amount=True),
        "releasing_compartment_left_out": V("releasing_compartment_left_out"),
        "route_state_fraction": V("route_state_fraction", route_state_fraction=True),
        "regulator_reads_amount": V("regulator_reads_amount", regulator_reads_amount=True),
        "regulator_quasi_steady": V("regulator_quasi_steady", regulator_quasi_steady=True),
        "pump_standard_state_1mM": V("pump_standard_state_1mM", pump_standard_mM=1.0),
        "cut_at_one": V("cut_at_one"),
    }


def applicability(world, plant):
    if plant == "maturation_stage_skipped" and world.m_declared == 0:
        return "no maturation stage to skip (m = 0)"
    if plant == "cu_without_1e-15":
        return ("not integrated: its units are about 1e15 times the reference's, a Na short "
                "that floods the 7.5 fL cell; R-chain shows its power")
    if plant == "releasing_compartment_left_out":
        return "the loop's world has no releasing compartment"
    return None


def from_export(e):
    """The loop block's declared part, mapped from the export (no computed value)."""
    cell, sp = e["cell"], e["cell"]["species"]
    pop, prod, prec = e["units"]["population"], e["units"]["producer"], e["units"]["precursor"]
    kpop, pump, reg = cell["K_population"], e["pump"], e["regulator_and_route"]
    tp, prot = e["template"], e["protocol"]
    if [a for a, _ in pump["availability"]] != [0.0]:
        raise ValueError("the pump's availability schedule is not a constant")
    return dict(
        registered=REGISTERED,
        source=("the FR-7 lane's export of the probe world, input values only, relayed by the "
                "lead: interface/loop_world_export.json"),
        synthetic=e["synthetic"],
        setting=dict(e["setting"]),
        cell=dict(
            species=list(sp), valence=list(cell["valence"]),
            bath_mM=[cell["bath"]["mM"][s] for s in sp], volume_pL=cell["volume_pL"],
            patch_area_m2=cell["patch"]["area_m2"], capacitance_F=cell["patch"]["capacitance_F"],
            leak_permeability_m_s=[cell["patch"]["leak_permeability_m_per_s"][s] for s in sp],
            temperature_K=cell["temperature_K"],
            fixed_populations=[dict(
                id=kpop["id"], law=kpop["law"], permeability_m_s=kpop["permeability_m_per_s"],
                relative_permeability=[1.0 if s == "K" else 0.0 for s in sp],
                units=kpop["units"], reference_density_per_m2=kpop["reference_density_per_m2"])],
            fixed_charge_fmol=cell["fixed_charge_equivalent_fmol"],
            initial_amounts_fmol=[cell["state_H_scaled"]["amounts_fmol"][s] for s in sp],
            initial_note="state H scaled: where the steady-state settle begins, not the start"),
        pump=dict(law=pump["law"], capacity_fmol_cycles_per_s=pump["capacity_fmol_cycles_per_s"],
                  capacity_mol_per_s=pump["capacity_fmol_cycles_per_s"] * 1e-15,
                  km_na_mM=pump["km_na_mM"], km_k_mM=pump["km_k_mM"],
                  km_atp_mM=pump["km_atp_mM"], atp_mM=pump["fuel"]["atp_mM"],
                  adp_mM=pump["fuel"]["adp_mM"], pi_mM=pump["fuel"]["pi_mM"],
                  deltaG0_J_per_mol=pump["fuel"]["delta_g0_J_per_mol"],
                  standard_state_mM=pump["fuel"]["standard_state_mM"],
                  availability=pump["availability"][0][1],
                  fuel="maintained reservoirs (held pools), declared with the standard state"),
        units=dict(id=pop["id"], law=pop["law"], permeability_m_s=pop["permeability_m_per_s"],
                   relative_permeability=[1.0 if s == "Na" else 0.0 for s in sp],
                   reference_density_per_m2=pop["reference_density_per_m2"], N0=pop["N0"],
                   phi=e["setting"]["phi"], producer_law=prod["law"], nu=prod["nu"],
                   units_per_fmol=prod["units_per_fmol"],
                   assembly_per_s=prod["assembly_rate_per_s"],
                   stages=prod["stages"], maturation_per_s=prod["maturation_per_s"],
                   removal_per_s=prod["removal_per_s"], half_life_s=prod["unit_half_life_s"]),
        precursor=dict(clearance_per_s=prec["clearance_per_s"], regime=prec["regime"]),
        regulator=dict(law=reg["state"]["law"], K_mM=reg["state"]["K_mM"], n=reg["state"]["n"],
                       k_on_per_s=reg["state"]["k_on_per_s"],
                       k_off_per_s=reg["state"]["k_off_per_s"],
                       route=dict(law=reg["route"]["law"], basal=reg["route"]["basal"],
                                  target=reg["route"]["target"]),
                       with_the_template=reg["with_the_template"]),
        template=dict(n0_fmol=TEMPLATE_DOSE_MM * cell["volume_pL"], dose_mM=TEMPLATE_DOSE_MM,
                      clearance_per_s=tp["clearance_per_s"], half_life_s=tp["half_life_s"],
                      production=tp["production"],
                      factor=dict(tp["factor"], K_mM=TEMPLATE_K_MM),
                      operating_range_mM=tp["operating_range_mM"],
                      scale=dict(ruling="D233", K_mM=TEMPLATE_K_MM, dose_mM=TEMPLATE_DOSE_MM,
                                 export_K_mM=tp["factor"]["K_mM"],
                                 export_dose_mM=tp["dose_mM"], note=TEMPLATE_NOTE)),
        horizon_s=prot["horizon_s"], rows_s=list(prot["rows_s"]), dt_s=prot["dt_s"],
        arms=dict(t_d_s=prot["t_d_s"], cut_control=prot["cut_control"]),
    )


def build(export):
    lp = from_export(export)
    if lp["units"]["units_per_fmol"] != round(loop.units_per_fmol(
            lp["units"]["nu"], export["constants"]["avogadro_per_mol"]), 0):
        raise ValueError("the export's c_u is not N_A 1e-15/nu")
    inputs = dict(
        kind="cells.fr7_reference_loop_inputs@1",
        registered=REGISTERED,
        constants={k: export["constants"][k] for k in ("avogadro_per_mol", "faraday_C_per_mol",
                                                        "gas_J_per_mol_K")},
        step=dict(dt_s=lp["dt_s"]),
        clearance=dict(epsilon=json.loads(worlds.INPUTS.read_text())["clearance"]["epsilon"],
                       drive="R-clear's: D = c^n/(K^n + c^n), c = n_T/V"),
        power=dict(margin=3.0),
        loop_band_rules=LOOP_BAND_RULES,
        loop=lp,
    )
    start, report = loop.steady_start(inputs)
    lp["start"] = start
    lp["start_report"] = report
    # F*: the closed trajectory's own loop factor at t_d, and its allowance
    world = loop.LoopWorld(inputs)
    t_d, dt = lp["arms"]["t_d_s"], lp["dt_s"]
    recs, _ = loop.simulate(world, lp["rows_s"], rtol=1e-12)  # the design's own integration
    r = recs[lp["rows_s"].index(t_d)]
    F_star = r["F_loop"]
    ds = world.k_on * r["u"] * (1.0 - r["s"]) - world.k_off * r["s"]
    s_band = LOOP_BAND_RULES["regulator"]["abs"]
    lp["arms"].update(
        F_star=F_star, ds_dt_at_t_d_per_s=ds,
        F_star_bound=abs(ds) * dt + s_band,
        F_star_bound_note=("|F*_engine - F*_reference| <= |ds/dt(t_d)| dt + the s band: a full "
                           "step's lag (twice the half step the engine's applied factor can lag) "
                           "plus the engine's allowed error in s"))
    return inputs


def text(export):
    return json.dumps(build(export), indent=1) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    export = json.loads(EXPORT_COPY.read_text())
    fresh = text(export)
    if args.check:
        # computed values (the start, F*) to 1e-9 relative: their last bits move between
        # environments (design.py's note); declared values and text exactly
        problems = []
        design._close(json.loads(fresh), json.loads(INPUTS.read_text()), INPUTS.name, problems,
                      rtol=1e-9)
        print(f"loop inputs: {len(problems)} differences")
        for p in problems[:20]:
            print("  ", p)
        return 1 if problems else 0
    INPUTS.write_text(fresh)
    print(f"wrote {INPUTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

