"""The mechanical check of PART2.md section 15: none of either part's declared numbers is here.

    exclusions2.py [SPEC]   the numbers of inputs_rehearsal_part2.json and of the legacy steps,
                            against those of SPEC/inputs.json and SPEC/inputs_part2.json (and the
                            captured steps of both legacy files), by category; SPEC is the spec
                            folder, or a copy of it at the criteria's commit

A category holds every declared number of its kind: volumes, amounts, permeabilities (and
diffusivities), rates (every rate, capacity, constant of a law, metabolite, abundance, gate,
threshold, Hill and standard-potential value, temperature), geometry (areas, lengths, capacitances,
charges, voltages), seeds, times (compared times, horizons, restarts) and steps (the retry's too). A
number matches another at 1e-12 relative. The exemptions are listed and each has its reason.
`exclusions2.py` exits 1 on any other match.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_inputs2 as m  # noqa: E402
import rules2  # noqa: E402

TRIVIAL = {0.0, 1.0, -1.0}  # Structural: a schedule's level, an absent route, 1 mM.
EXEMPT = {
    ("temperature", 298.15): "both channel laws admit this temperature only",
    ("stoichiometry", -3.0): "the Na/K pump's ions are the law's",
    ("stoichiometry", 2.0): "the Na/K pump's ions and the reactions' are the laws'",
}
CATEGORY = {
    "volume_pL": "volumes", "pool_volume_L": "volumes",
    "initial_amount_fmol": "amounts", "fixed_charge_equivalent_fmol": "amounts",
    "initial_free_trimers": "amounts",
    "permeability_m_per_s": "permeabilities", "max_permeability_m_per_s": "permeabilities",
    "diffusivity_m2_per_s": "permeabilities",
    "capacity_fmol_per_s": "rates", "km_na_mM": "rates", "km_k_mM": "rates", "km_atp_mM": "rates",
    "km_ca_mM": "rates", "atp_mM": "rates", "adp_mM": "rates", "pi_mM": "rates",
    "delta_g0_J_per_mol": "rates", "delta_g0_at_1M_J_per_mol": "rates", "k_on_M_inv_s": "rates",
    "k_close_s_inv": "rates", "k_off_s_inv": "rates", "k_fragment_dissolve_s_inv": "rates",
    "abundance": "rates", "initial_gate": "rates", "m": "rates", "h": "rates",
    "threshold_voltage_V": "rates", "minimum_open_fraction": "rates",
    "forward_rate_per_s": "rates", "standard_mu_RT": "rates", "activation_mM": "rates",
    "inhibition_mM": "rates", "activation_n": "hill", "inhibition_n": "hill",
    "fuel_standard_mu_RT": "rates", "material_tolerance_fmol": "rates",
    "temperature_K": "temperature",
    "area_m2": "geometry", "length_m": "geometry", "capacitance_F": "geometry",
    "initial_charge_C": "geometry", "initial_voltage_V": "geometry",
    "stoichiometry": "stoichiometry", "reactants": "stoichiometry", "products": "stoichiometry",
    "end_s": "times", "end_time_s": "times", "final_s": "times", "potential_times_s": "times",
    "summary_times_s": "times", "first_s": "times", "last_s": "times", "spacing_s": "times",
    "step_s": "steps", "seeds": "seeds",
}  # fmt: skip
LEFT_OUT = (
    "scales", "amount_refs", "closure_share", "closure_terms_V", "closure_terms", "p",
    "calcium_controls", "coupling", "harness",
)  # fmt: skip
KEYED = {"Na", "K", "Cl", "Ca", "B", "CaB", "Ca2B", "IP3", "IP3_buffer", "IP3_bound", "ATP", "ADP",
         "Pi"}  # fmt: skip


def add(out, category, value):
    if not isinstance(value, bool) and isinstance(value, (int, float)):
        out.setdefault(category, set()).add(float(value))


def walk(value, key, out):
    if key == "controls":
        for family in value.values():
            if isinstance(family, dict):
                for s in family.values():
                    for point in s:
                        add(out, "times", point[0])
        return
    if isinstance(value, dict):
        for k, v in value.items():
            if k not in LEFT_OUT:
                walk(v, key if k in KEYED and key in CATEGORY else k, out)
    elif isinstance(value, list):
        for v in value:
            walk(v, key, out)
    elif key in CATEGORY:
        add(out, CATEGORY[key], value)


def numbers(inputs):
    out = {}
    for world in inputs["worlds"].values():
        walk(world, "", out)
    for r in inputs["runs"]:
        add(out, "steps", r["step_s"])
        for t in re.findall(r"restart at ([0-9.eE+-]+)", r.get("variant") or ""):
            add(out, "times", float(t))
        for item in r.get("declared_change") or []:
            if "path" in item:
                walk(item["value"], item["path"][-1], out)
    return out


def close(a, b):
    return a == b or abs(a - b) <= 1e-12 * max(abs(a), abs(b))


def main(spec):
    folder = {}
    for f in ("inputs.json", "inputs_part2.json"):
        for category, values in numbers(json.loads((spec / f).read_text())).items():
            folder.setdefault(category, set()).update(values)
    for f in ("legacy_part1.json", "legacy_part2.json"):
        for w in json.loads((spec / f).read_text())["worlds"].values():
            folder["steps"].update(w.get("captured_steps_s") or [])
    folder["steps"] |= {3.125e-06, 1.5625e-06}
    folder["times"] |= {7.3e-05, 3.713e-03}  # The captured off-grid observations.
    mine = numbers(json.loads((m.HERE / "inputs_rehearsal_part2.json").read_text()))
    for name, w in m.WORLDS.items():
        for k in (1, 2, 4):
            add(mine, "steps", w["legacy"] / k)
        add(mine, "steps", m.retry_step(name))
        add(mine, "times", w.get("off_grid"))
    bad, exempt, counts = [], [], {}
    for category, values in sorted(mine.items()):
        counts[category] = len(values)
        for v in sorted(values):
            if v in TRIVIAL:
                continue
            for u in folder.get(category, ()):
                if close(v, u):
                    if (category, u) in EXEMPT or category == "stoichiometry":
                        exempt.append(
                            (category, v, EXEMPT.get((category, u), "the laws' stoichiometry"))
                        )
                    else:
                        bad.append((category, v, u))
                    break
    print("numbers checked by category:", counts)
    for e in sorted(set(exempt)):
        print("  exempt", *e)
    for b in bad:
        print("  MATCH", *b)
    print("no other match" if not bad else f"{len(bad)} matches")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else rules2.SPEC))
