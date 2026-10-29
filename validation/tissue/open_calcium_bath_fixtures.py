"""New manufactured bath models with explicit real counterion ownership.

The five-ion model splits declared chloride into Cl/M in every physical volume.
Fixed background charges are unchanged. It is a distinct manufactured model,
never an equivalent trajectory of the accepted four-ion calcium/fuel inputs.
"""

from copy import deepcopy

from validation.tissue import open_calcium_fixtures as parent

FAMILIES = parent.FAMILIES
CASES = ("overlap", "single", "negative", "empty", "disabled", "init", "permuted", "cl_only")
MODEL_IDS = dict(
    calcium="resolved_open_calcium_bath_events@1",
    energy="resolved_open_calcium_energy_bath_events@1",
)
PARENT_IDS = parent.MODEL_IDS
DT, END = parent.DT, parent.END
EXTERIOR_POLICY = "scheduled_declared_ideal_chemical_and_fixed_voltage_reservoirs@1"
EXTRA = (
    "bath_events",
    "bath_site_ids",
    "enabled_Cl",
    "phase",
    "timing_policy",
    "controller_policy",
    "baseline_policy",
)


def static_definition(raw):
    value = deepcopy(raw)
    family = next(name for name, identity in MODEL_IDS.items() if identity == value["model"]["id"])
    value["model"]["id"] = PARENT_IDS[family]
    value["model"]["exterior_policy"] = "static_declared_ideal_chemical_and_voltage_reservoirs@1"
    for key in EXTRA:
        value["model"].pop(key)
    return value


def _split_chloride(raw):
    m, x = raw["model"], raw["execution"]
    ion = m["ionic"]
    ion["species"].append(dict(id="M", valence=-1))
    for row in (*ion["cells"], *ion["extracellular"]):
        half = 0.5 * row["initial_amount_fmol"]["Cl"]
        row["initial_amount_fmol"].update(Cl=half, M=half)
    for kind, key in (
        ("membranes", "permeability_m_per_s"),
        ("junctions", "permeability_m_per_s"),
        ("faces", "diffusivity_m2_per_s"),
    ):
        for row in ion[kind]:
            row[key]["M"] = row[key]["Cl"]
    for row in m["stores"]:
        store = row["model"]
        store["moieties"].append("M")
        for species in store["species"]:
            species["moieties"]["M"] = 0
        store["species"].append(
            dict(
                id="M",
                valence=-1,
                standard_mu_RT=0.0,
                moieties={key: int(key == "M") for key in store["moieties"]},
            )
        )
        for owner in store["compartments"]:
            half = 0.5 * owner["initial_amount_fmol"]["Cl"]
            owner["initial_amount_fmol"].update(Cl=half, M=half)
        store["membrane"]["permeability_m_per_s"]["M"] = store["membrane"]["permeability_m_per_s"][
            "Cl"
        ]
    for group in raw["experiment"]["store_controls"]:
        for row in group["controls"]:
            row["passive"]["M"] = row["passive"]["Cl"]
    x["material_balance_atol_fmol"]["M"] = x["material_balance_atol_fmol"]["Cl"]
    m["ionic_moiety_ceiling_fmol"] = {
        key: 1.5 * value for key, value in parent.ionic_totals(m).items()
    }


def definition(family="energy", case="overlap", *, padded=True, depleted=False):
    if family not in FAMILIES or case not in CASES:
        raise ValueError((family, case))
    raw = parent.definition(
        family, "permuted" if case == "permuted" else "mixed", padded=padded, depleted=depleted
    )
    if case != "cl_only":
        _split_chloride(raw)
    m, e = raw["model"], raw["experiment"]
    events = [
        dict(kind="K_env", on_s=0.25e-6, off_s=4e-6, change_s=1e-6, amplitude=0.04),
        dict(kind="Cl_env", on_s=1e-6, off_s=5e-6, change_s=1.5e-6, amplitude=0.005),
        dict(kind="Na_env", on_s=2e-6, off_s=6e-6, change_s=1e-6, amplitude=0.003),
    ]
    if case == "single":
        events = events[:1]
    elif case == "negative":
        events = events[:1]
        events[0]["amplitude"] = -0.04
    elif case == "empty":
        events = []
    elif case in ("disabled", "cl_only"):
        events = events[1:2]
    m.update(
        id=MODEL_IDS[family],
        exterior_policy=EXTERIOR_POLICY,
        bath_events=events,
        bath_site_ids=[row["id"] for row in m["ionic"]["extracellular"] if row["reservoir"]],
        enabled_Cl=case != "disabled",
        phase="INIT" if case == "init" else "SIM",
        timing_policy="phase_clock_rk_stage_native_logistic@1",
        controller_policy="explicit_ideal_reservoir_dose_voltage_compensation_work@1",
        baseline_policy="each_declared_reservoir_reference_concentration@1",
    )
    # Original held controls remain. Explicit unchanged carrier values make the
    # additional requested sample clocks accepted boundaries, never hidden splits.
    clocks = set(e["observation_times"]) | {i * DT for i in (4, 20, 40, 60, 80, 96, 112, 128)}
    carrier = e["membrane_controls"][0]
    previous = deepcopy(carrier["schedule"])
    carrier["schedule"] = [
        dict(
            time=time,
            availability=next(
                row["availability"] for row in reversed(previous) if row["time"] <= time
            ),
        )
        for time in sorted(clocks)
    ]
    e["observation_times"] = sorted(clocks)
    if case == "permuted":
        m["ionic"]["species"].reverse()
        m["bath_site_ids"].reverse()
    return raw
