"""FR-7 item 3's mapper: a U2 world with a compartment that releases template (D217's clause 4).

D217's first acceptance includes, in the clearance criterion, every compartment that can still
release template. R-clear (validation/fr7/references/, registered code-blind and tagged
fr7-references-registered-2026-11-19) holds that clause's synthetic cases RC2 (a releasing
compartment) and RC5 (a compartment that stops releasing). Until 20 November 2026 no U2 world
admitted a compartment, so R-clear's compartment plant had power on no engine run. The lead's
rulings of that day admit one (the engine head 1ec77911). This module declares the two worlds,
registered in compartment_registration.json before any engine output of either:
* C2, RC2's case: an endosome holding 0.2 fmol of template, releasing it into the cytosol at
  ln 2/50 per second from time 0;
* C5, RC5's case: a vesicle holding 0.2 fmol, releasing at ln 2/100 per second until 300 s, then
  sealed (its release rate 0 from 300 s).

Each is R-chain's W2 world (chain_mapper: three maturation stages, units' half-life 60 s, a finite
precursor), whose template and factor blocks equal the cases' cytosol block (asserted here), with:
* a compartment of the cell (cell_owned_compartments@1, through unit_turnover_fixtures): a finite
  outside node bounded by one patch that no species crosses, its content neutral at a zero charge
  anchor, the owner's ion concentrations, the case's template amount, and the precursor at the
  trace;
* the release, scheduled_species_exchange@1's first-order import on the bounding patch, whose rate
  constant out of the node is kappa = k_u A 1e15 / V_o: k_u is declared from the case's release
  rate (unit_turnover_fixtures.release_velocity). It reads the patch area current (D191), which
  nothing changes here, so it reads the declared area bit for bit. Declared after the producer
  (C2's order rule);
* the cases' rows (every 10 s to 1000 s), at the declared step of 1 ms.

The compartment's volume, the bounding patch's area and capacitance and the owner's ion
concentrations in it are layout choices, not physics: the template's release depends on them only
through kappa, which is the case's, and no ion crosses the bounding patch. A case's degradation
inside the compartment would be turnover's clearance at its node; RC2's and RC5's is zero, so none
is declared.

The template's tail is chain_mapper's: D150's exact first-order clearance in the cell, with no
floor, clamp or reset. The release is exact within each exchange stage. Synthetic throughout
(D217). Development, not judged, until the registered comparison runs from main.
"""

from validation.fr7 import chain_mapper as cm
from validation.fr7 import unit_turnover_fixtures as ufx

BASE = "W2_dose_m3_t60"
CASES = {
    "C2": "RC2_releasing_compartment",
    "C5": "RC5_compartment_stops_releasing",
}
COMPARTMENT, NODE, PATCH, RELEASE = ufx.COMPARTMENT, ufx.NODE, ufx.BOUNDING, ufx.RELEASE
VOLUME_pL, AREA_m2, CAPACITANCE_F = ufx.NODE_pL, ufx.BOUNDING_m2, ufx.BOUNDING_F


def case_of(inp, world):
    """R-clear's registered inputs of world `world`'s case (inputs.json, clearance_cases)."""
    return inp["clearance_cases"]["cases"][CASES[world]]


def the_compartment(inp, world):
    """(name, its block) of the case's one compartment."""
    compartments = case_of(inp, world)["compartments"]
    if len(compartments) != 1:
        raise ValueError(f"{world}: the mapper declares one compartment per case")
    return next(iter(compartments.items()))


def check_base(inp, world):
    """The base world's template and factor blocks equal the case's cytosol block: the case's
    trajectories are then the base world's template with its compartment added."""
    w, cases = inp["worlds"][BASE], inp["clearance_cases"]
    case = case_of(inp, world)
    template, factor = w["template"], w["factor"]
    pairs = {
        "dose (fmol)": (template["n0_fmol"], case["n0_fmol"]),
        "production": (template["production"], case["production"]),
        "clearance (1/s)": (template["clearance_per_s"], cases["clearance_per_s"]),
        "K (mM)": (factor["K_mM"], cases["K_mM"]),
        "n": (factor["n"], cases["n"]),
        "basal": (factor["basal"], cases["basal"]),
        "volume (pL)": (inp["cell"]["volume_pL"], cases["volume_pL"]),
    }
    differ = {k: v for k, v in pairs.items() if v[0] != v[1]}
    if differ:
        raise ValueError(f"{world}: {BASE}'s blocks differ from {CASES[world]}'s: {differ}")
    if factor["law"] != "hill_activation":
        raise ValueError(f"{world}: the case's drive is a Hill activation")


def release_changes(inp, world):
    """[(time, k_u in m/s), ...]: the case's release schedule as exchange's uptake velocity."""
    _, block = the_compartment(inp, world)
    return [
        (float(t), ufx.release_velocity(rate, volume_pL=VOLUME_pL, area_m2=AREA_m2))
        for t, rate in block["release"]
    ]


def definition(inp, world, *, dt=None, end=None, rows=None):
    """The engine's definition of world `world` (C2 or C5) of the registered inputs `inp`, run with
    the declared step (or dt) to the cases' last row (or end), observed at the cases' rows (or
    `rows`)."""
    check_base(inp, world)
    name, block = the_compartment(inp, world)
    if block["degradation_per_s"] != 0.0:
        raise ValueError(f"{world}: {name} degrades its template; this mapper declares none")
    grid = inp["clearance_cases"]["rows_s"]
    end = grid[-1] if end is None else end
    rows = [t for t in (grid if rows is None else rows) if t <= end]
    raw = cm.definition(inp, BASE, dt=dt, end=end, rows=rows)
    raw = ufx.with_compartment(
        raw,
        owner=cm.CELL,
        volume_pL=VOLUME_pL,
        area_m2=AREA_m2,
        capacitance_F=CAPACITANCE_F,
        amounts_fmol={cm.TEMPLATE: block["n0_fmol"], cm.PRECURSOR: cm.TRACE_mM * VOLUME_pL},
        label=f"synthetic {name}, R-clear's {CASES[world]}",
    )
    return ufx.with_release(raw, release_changes(inp, world), species=cm.TEMPLATE, owner=cm.CELL)
