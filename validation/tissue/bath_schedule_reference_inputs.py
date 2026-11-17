"""The registered input file of fr10-dose-schedule-v1's code-blind references.

The FR references agent writes R-faces, R-ion and R-records (validation/tissue/
bath_schedule_protocol.json: references) from docs/BATH_SCHEDULE_DESIGN.md's Appendix A and this
file alone, never reading src/cells, the operator or its tests. So the file holds each reference
world's physical parameters, initial state, schedule and record times, read from the protocol's
world builders (validation/tissue/bath_schedule_fixtures: their declared definitions, never the
operator's code), with the SI constants and Appendix A's forms and conventions in words.

    python -m validation.tissue.bath_schedule_reference_inputs OUT_JSON

The registered copy is validation/bath_schedule/reference_inputs.json; a tier-1 test checks that it
equals what this module writes from today's builders, so the references and the judged worlds stay
the same worlds.
"""

import json
import sys
from pathlib import Path

from validation.tissue import bath_schedule_fixtures as bfx
from validation.tissue import secreted_species_fixtures as fx

KIND = "fr10-dose-schedule-v1 reference inputs"
REGISTERED = Path(__file__).resolve().parents[1] / "bath_schedule" / "reference_inputs.json"
CONSTANTS = dict(
    avogadro_per_mol=6.02214076e23,
    elementary_charge_C=1.602176634e-19,
    boltzmann_J_per_K=1.380649e-23,
    faraday_C_per_mol="avogadro_per_mol x elementary_charge_C (exact SI)",
    gas_constant_J_per_mol_K="avogadro_per_mol x boltzmann_J_per_K (exact SI)",
)
UNITS = dict(
    amount="fmol", volume="pL", concentration="mM (fmol/pL)", time="s", length="m", area="m^2",
    diffusivity="m^2/s", permeability="m/s", capacitance="F", charge="C", potential="V",
    energy="pJ",
)


def _schedule(raw, species_by_unit):
    """The schedule as (time, {species: concentration mM after the event}) at each scheduled bath:
    the declared composition plus the offsets times the units' counts."""
    m = raw["model"]
    block = next(op for op in m["operators"] if op["law"] == bfx.LAW)
    out = {}
    for bath in block["baths"]:
        node = next(n for n in m["extracellular"] if n["id"] == bath)
        declared = {s: a / node["volume_pL"] for s, a in node["initial_amount_fmol"].items()}
        steps = []
        for event in raw["experiment"]["bath_composition_events"]:
            if bath not in event["baths"]:
                continue
            c = dict(declared)
            for unit, mM in event["formula_units_mM"].items():
                for species, count in species_by_unit[unit].items():
                    c[species] = c[species] + mM * count
            steps.append(dict(time_s=event["time"], concentration_mM=c))
        out[bath] = dict(volume_pL=node["volume_pL"], declared_mM=declared, events=steps)
    return out


def _chain_inputs():
    raw = bfx.chain_world()
    m = raw["model"]
    s = fx.SPECIES
    nodes = {
        n["id"]: dict(volume_pL=n["volume_pL"], S_mM=n["initial_amount_fmol"][s] / n["volume_pL"])
        for n in m["extracellular"] if not n.get("reservoir")
    }
    faces = [
        dict(id=f["id"], between=[f["sender"], f["receiver"]], area_m2=f["area_m2"],
             length_m=f["length_m"], S_diffusivity_m2_per_s=f["diffusivity_m2_per_s"][s])
        for f in m["faces"]
    ]
    return dict(
        world="W1 (B1, Appendix A.2): the neutral species S on a face chain; its two cells are "
              "inert (S impermeant at every patch)",
        species="S, neutral",
        finite_nodes=nodes,
        faces=faces,
        bath=_schedule(raw, bfx.CARGO)["bath"],
        record_times_s=raw["experiment"]["observation_times"],
        returns="each finite node's S amount (fmol) at every record time",
        dt_ladder_s=[1e-3, 5e-4, 2.5e-4, 1.25e-4],
        note="the engine runs this world at each dt of the ladder; the reference is the exact "
             "solution, independent of dt",
    )


def _ion_inputs():
    raw = bfx.ion_world()
    m = raw["model"]
    cell = m["cells"][0]
    wall = next(p for p in m["membranes"] if p["id"] == "wall_cell_0")
    return dict(
        world="W2 (B2, Appendix A.3): one passive cell on the held bath, K permeant only",
        temperature_K=m["temperature_K"],
        species={sp["id"]: sp["valence"] for sp in m["species"]},
        cell=dict(volume_pL=cell["volume_pL"], amounts_fmol=cell["initial_amount_fmol"],
                  initial_charge_C=cell["initial_charge_C"]),
        wall=dict(area_m2=wall["area_m2"], capacitance_F=wall["capacitance_F"],
                  permeability_m_per_s=wall["permeability_m_per_s"]),
        bath=_schedule(raw, bfx.SALTS)["bath"],
        bath_potential_V=0.0,
        record_times_s=raw["experiment"]["observation_times"],
        returns="V_m (the cell's potential less the bath's, V) and the cell's Na, K and Cl "
                "(fmol) at every record time, and the zero-current potential at the composition "
                "after the event",
        initial_state="V_m(0) = initial_charge_C / capacitance_F: the cell at rest at E_K of the "
                      "declared bath",
        dt_ladder_s=[1e-3, 5e-4, 2.5e-4, 1.25e-4],
    )


def _records_inputs():
    worlds = {}
    for name, raw, units in (("W1", bfx.chain_world(), bfx.CARGO),
                             ("W2", bfx.ion_world(), bfx.SALTS),
                             ("W3", bfx.ledger_world(), bfx.CARGO)):
        worlds[name] = dict(temperature_K=raw["model"]["temperature_K"],
                            valence={sp["id"]: sp["valence"] for sp in raw["model"]["species"]},
                            baths=_schedule(raw, units))
    return dict(
        world="every event of W1, W2 and W3 (B4, Appendix A.4 and A.5)",
        worlds=worlds,
        returns="at each event: the dose dn_s = V_b (c_after - c_before) (fmol), dG_b, the "
                "free-energy change of the bath's content at its declared volume (pJ, design "
                "§2.2's expression), and the step's charge F sum_s z_s dn_s (C, zero in exact "
                "arithmetic); and the reconciliation K(t) of §2.3 and A.5 (pJ) as a function of "
                "the record times and the cumulative supply S_s at them, an input at run time "
                "(the generator passes the engine's W3 supply series; the convention above)",
    )


def inputs():
    return dict(
        kind=KIND,
        protocol="fr10-dose-schedule-v1 (validation/tissue/bath_schedule_protocol.json)",
        forms="docs/BATH_SCHEDULE_DESIGN.md, Appendix A (A.1 to A.5)",
        units=UNITS,
        constants=CONSTANTS,
        conventions=[
            "an event at t_e sets the bath's composition for t >= t_e (right-continuous)",
            "node amounts and V_m are continuous at an event; they are what the references "
            "return at the record times",
            "a face's conductance is kappa = 1e15 D A / L (pL/s), so its flux is kappa (c_a - c_b) "
            "in fmol/s with c in mM",
            "the constant-field flux is outward positive; V_m is the cell less the bath",
            "the constants above are exact SI values (F = N_A e, R = N_A k_B, so RT/F = k_B T/e); "
            "Appendix A's printed RT = 2.577 pJ/fmol and F = 96485.33 C/mol are rounded for "
            "reading, and the references use the values here (delta_G_b is judged within 1e-12 "
            "relative)",
            "S_s(t), the cumulative supply, is the amount the bath has supplied to the tissue "
            "since t = 0 (fmol, positive out of the bath)",
        ],
        R_faces=_chain_inputs(),
        R_ion=_ion_inputs(),
        R_records=_records_inputs(),
    )


def write(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(inputs(), indent=1, sort_keys=False) + "\n")
    return path


def main(argv):
    if len(argv) != 1:
        raise SystemExit(__doc__)
    print(write(argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
