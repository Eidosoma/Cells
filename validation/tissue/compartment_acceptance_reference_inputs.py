"""The registered input file of FR-1's code-blind references (cells.operator.cell_owned_compartments@1 with
exchange@1: the closed-compartment acceptance, exchange's first judged acceptance).

The FR references agent writes FR-1's references (docs/CLOSED_COMPARTMENT_DESIGN.md §6.2) from that
design's Appendix A and this file alone, never reading src/cells, the operators or their tests. So
the file holds each reference world's physical parameters, initial amounts, rates in Appendix A's
symbols, schedules and record times, read from the protocol's world builders
(validation/tissue/compartment_acceptance_fixtures: their declared definitions, never the operators'
code), with the SI constants and Appendix A's forms and conventions in words.

    python -m validation.tissue.compartment_acceptance_reference_inputs OUT_JSON

The registered copy is validation/closed_compartment/reference_inputs.json; a tier-1 test checks
that it equals what this module writes from today's builders, so the references and the judged
worlds stay the same worlds.
"""

import json
import sys
from pathlib import Path

from validation.tissue import compartment_acceptance_fixtures as af
from validation.tissue import secreted_species_fixtures as fx

KIND = "FR-1 closed-compartment acceptance: reference inputs"
REGISTERED = Path(__file__).resolve().parents[1] / "closed_compartment" / "reference_inputs.json"
CONSTANTS = dict(
    avogadro_per_mol=6.02214076e23,
    elementary_charge_C=1.602176634e-19,
    boltzmann_J_per_K=1.380649e-23,
    faraday_C_per_mol="avogadro_per_mol x elementary_charge_C (exact SI)",
    gas_constant_J_per_mol_K="avogadro_per_mol x boltzmann_J_per_K (exact SI)",
)
UNITS = dict(amount="fmol", volume="pL", concentration="mM (fmol/pL)", time="s", length="m",
             area="m^2", rate="1/s", flux="fmol/s", velocity="m/s", capacitance="F",
             charge="C", potential="V", energy="pJ")


def _nodes(raw):
    """Every finite node's volume and initial S (and P where declared) amounts (fmol)."""
    m = raw["model"]
    out = {}
    for n in [*m["cells"], *(c for c in m["extracellular"] if not c.get("reservoir"))]:
        amounts = {s: n["initial_amount_fmol"][s] for s in ("S", "P") if s in
                   n["initial_amount_fmol"]}
        out[n["id"]] = dict(volume_pL=n["volume_pL"], initial_fmol=amounts)
    return out


def _routes(raw):
    """Exchange's routes in Appendix A's symbols: export first_order k_e (1/s); export flux J
    (fmol/s); import first_order kappa = 1e15 k_u A / V of the node it leaves (1/s); import
    saturable a = A V_max (fmol/s) and b = K_M V of the node it leaves (fmol)."""
    m, x = raw["model"], raw["experiment"]
    block = next(op for op in m["operators"] if op["law"] == fx.EXCHANGE)
    patches = {p["id"]: p for p in m["membranes"]}
    volumes = {n["id"]: n["volume_pL"] for n in [*m["cells"], *m["extracellular"]]}
    controls = {c["route_id"]: c["schedule"] for c in x["exchange_controls"]}
    out = []
    for route in block["routes"]:
        patch = patches[route["patch"]]
        source = patch["inside"] if route["direction"] == "export" else patch["outside"]
        target = patch["outside"] if route["direction"] == "export" else patch["inside"]
        schedule = []
        for change in controls[route["id"]]:
            entry = dict(time_s=change["time"])
            if route["law"] == "flux":
                entry["J_fmol_per_s"] = change["rate"]
            elif route["direction"] == "export":
                entry["k_e_per_s"] = change["rate"]
            elif route["law"] == "first_order":
                entry["kappa_per_s"] = (af.PL_PER_M3 * change["rate"] * patch["area_m2"]
                                        / volumes[source])
                entry["k_u_m_per_s"] = change["rate"]
            else:
                entry["a_fmol_per_s"] = patch["area_m2"] * change["rate"]
                entry["b_fmol"] = change["saturation_mM"] * volumes[source]
                entry["V_max_fmol_per_s_m2"] = change["rate"]
                entry["K_M_mM"] = change["saturation_mM"]
            schedule.append(entry)
        out.append(dict(id=route["id"], direction=route["direction"], law=route["law"],
                        source=source, target=target, patch=route["patch"],
                        patch_area_m2=patch["area_m2"], schedule=schedule))
    return out


def _world(raw, form, *, note=None, extra=None):
    out = dict(form=form, temperature_K=raw["model"]["temperature_K"],
               dt_s=raw["execution"]["dt"], solver=raw["execution"]["solver"],
               end_s=raw["experiment"]["end_time"], nodes=_nodes(raw), routes=_routes(raw),
               record_times_s=raw["experiment"]["observation_times"])
    if note:
        out["note"] = note
    return out | (extra or {})


def _clearance(raw):
    x = raw["experiment"]
    return {c["route_id"]: c["schedule"][0]["rate"] for c in x["turnover_controls"]}


def _reaction(raw):
    block = next(
        op
        for op in raw["model"]["operators"]
        if op["law"] == "cells.operator.local_species_reactions@1"
    )
    return {r["id"]: dict(rate_constant_per_s=r["rate_constant"], sites=r["sites"],
                          reactants=r["reactants"], products=r["products"])
            for r in block["reactions"]}


def _ladder(build):
    return {f"{dt:g}": _world(build(dt=dt), "A.3 and A.4") for dt in af.LADDER_S}


def inputs():
    c11 = {}
    for law in af.C11_LAWS:
        for solver in (af.ARS, af.RK4):
            form = "A.2" if law.endswith("export") else ("A.5" if law.startswith("saturable")
                                                         else "A.3 with a = 0")
            c11[f"{law} {'ARS' if solver == af.ARS else 'RK4'}"] = _world(
                af.from_trace(law, solver), form + " and A.10")
    lw = af.load_and_degrade()
    lr = af.load_and_react()
    return dict(
        kind=KIND,
        protocol="FR-1's protocol (validation/tissue/compartment_acceptance_protocol.json, to be "
                 "registered after these references)",
        forms="docs/CLOSED_COMPARTMENT_DESIGN.md, Appendix A (A.1 to A.10)",
        units=UNITS,
        constants=CONSTANTS,
        conventions=[
            "the constants above are exact SI values (F = N_A e, R = N_A k_B); Appendix A's "
            "printed RT = 2.577 pJ/fmol and F = 96485.33 C/mol are rounded for reading, and the "
            "references use the values here",
            "c = n / V, with n in fmol, V in pL and c in mM; 1e15 converts m^3 to pL",
            "c = the owner cell's cytosol (cell_0), o = the compartment's node (ecs_0), e = the "
            "extracellular node ecs_e (C8 only); every node's initial S (and P) is listed, the "
            "trace included, and nothing else changes S in these worlds",
            "a route's schedule holds its rate from each time on; every schedule here starts at "
            "t = 0 and does not change",
            "records are the amounts at the record times, t = 0 included",
            "A.4's step: a half-step of length h = dt/2 is S(h) = E(h/2) I(h) E(h/2), and one "
            "step of the engine is S(dt/2) twice; no world here declares a saturable route beside "
            "the first-order pair, so A.4's stage plan is S(h) as written",
        ],
        R_closed=dict(
            world="C3, C4 and C5 at the declared 1 ms (A.2, A.3, A.5): the closed forms",
            worlds=dict(
                C3_flux=_world(af.flux_loading(), "A.2, the flux law"),
                C3_first_order=_world(af.first_order_loading(), "A.2, the first-order law"),
                C4_two_way=_world(af.two_way(), "A.3"),
                C5_saturable=_world(af.saturable_release(), "A.5"),
            ),
            returns="each node's S (fmol) at every record time, and for C4 x_eq = b/(a + b); each "
                    "with a floor (the same values a second way: another method, or a tighter "
                    "setting where the form is solved numerically, as A.5's implicit equation)",
        ),
        R_step_map=dict(
            world="C4 at each rung of the ladder (A.4): the palindrome's step map, iterated",
            worlds=_ladder(af.two_way),
            returns="at each rung: the step map's fixed point x* = alpha(1 - beta)/(1 - alpha^2 "
                    "beta), x = n_c / N iterated from x(0) and the cytosol's and compartment's S "
                    "(fmol) at every record time, and the splitting term, the fixed point's "
                    "relative displacement x*/x_eq - 1, beside -a(a + 2b) dt^2 / 96 "
                    "(docs/CLOSED_COMPARTMENT_DESIGN.md §2.3); with a floor (the map iterated a "
                    "second way)",
        ),
        R_linear=dict(
            world="C6, C7 and C8 (A.6, A.7, A.8): the declared linear systems by their matrix "
                  "exponentials",
            worlds=dict(
                C6_load_and_degrade=_world(lw, "A.6", extra=dict(
                    clearance_per_s=_clearance(lw),
                    clearance_node=af.NODE)),
                C7_load_and_react=_world(lr, "A.7", extra=dict(reactions=_reaction(lr))),
                C8_uptake_path=_world(af.uptake_path(), "A.8"),
            ),
            returns="each node's S (and C7's P at the compartment) (fmol) at every record time; "
                    "C6's cleared amount (the integral of k n_o); C7's moiety S + P; each with a "
                    "floor (a second method, such as an eigendecomposition beside the matrix "
                    "exponential)",
        ),
        R_capacitor=dict(
            world="A.9: a cell (node i), its held bath (phi_b = 0) and its compartment (node j)",
            network=dict(C_pm_F=fx.WALL_C_F, C_b_F=fx.CONTACT_C_F, phi_b_V=0.0,
                         note="C_pm is the owner's wall patch on the held bath; C_b the bounding "
                              "patch"),
            returns="V_b = phi_i - phi_j and V_pm = phi_i - phi_b as functions of the charges "
                    "q_i and q_j (C), by a dense solve of its own; the generator passes the "
                    "engine's recorded charges",
        ),
        R_energy=dict(
            world="A.10: G = RT sum_nodes n (ln(n/V) - 1) (pJ, c in mM)",
            worlds={**c11, "C6_load_and_degrade": _world(
                lw, "A.6 and A.10", note="the loading with clearance: its S leaves the two "
                "nodes (sum dn != 0), so a dropped -1 or another standard state in G shows here "
                "(the references' power finding, ruled 17 November 2026)", extra=dict(
                    clearance_per_s=_clearance(lw), clearance_node=af.NODE))},
            returns="for C3, C4, C5 (R_closed's worlds) and each world here: the free-energy "
                    "change of the nodes each law touches, along the reference trajectory at "
                    "every record time (pJ), and G as a function of amounts and volumes; for each "
                    "C11 world also each node's S (fmol) at every record time (its law's closed "
                    "form from the trace); for C6 the change of both nodes' G along A.6's "
                    "trajectory, which the loading's and the clearance's work together book; each "
                    "with a floor",
        ),
    )


def write(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(inputs(), indent=1) + "\n")
    return path


def main(argv):
    if len(argv) != 1:
        raise SystemExit(__doc__)
    print(write(argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
