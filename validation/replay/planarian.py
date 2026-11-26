"""The interim planarian loop (FR-11; docs/LOOPING_REPLAY_DESIGN.md §4): a builder.

World: a seven-cell patch of the heredity sheet (validation/stationary/worlds.py: hexagon(1) and
e07_sheet_definition), seven heredity cells each facing its own held bath, joined by the E07-v1
voltage-gated junctions. Every cell is written in state H, an exact declared steady state of the
cell (validation/tissue/surface_pump_v3_fixtures.heredity_cells) and, with no junction voltage, of
the sheet: the run starts at rest, with no pattern to settle first.

Drive (the lead's ruling 3, §9): cells.operator.electrode_current_injection@1 into the centre cell, a
charge-balanced square wave (+I for the first half of each period, -I for the second), so the
injected amounts net to zero over a period. Its carriers are a 3 M KCl filling's proportion with M
as this world's anion. The amplitude keeps every cell far below its switching voltage (H at about
-80 mV, the unstable state U at about -39 mV), so the loop shows a cell held in its written state
under a slow drive, and the drive spreads to the ring over the junctions (junction voltages appear
only through it, so their sign convention is checked on data).

The run covers SETTLE periods and one more; only the last period's rows are observed and saved, so
the view's first observed row is at t0 = SETTLE T and its last at t0 + T. The writer measures the
closure there and labels the run a loop only within TOLERANCE.

Engine models: cells.model.resolved_pump_composite@1 over cells.model.resolved_pump_tissue@3, with the heredity cell's laws
(cells.channel.nav1p2_m3h_regularized@1, cells.channel.kir2p1_mh2@1, the Na/K pump cells.cycle.nak_atp_mass_action_positive@1, membranes
and junctions cells.route.constant_field@1, the junction gate cells.junction.junction_voltage_relaxation@1), and
cells.operator.electrode_current_injection@1. An illustration (D175): no verdict, not registered.

The amplitude, settling periods and tolerance are provisional until the first development run
(the package's own probe) shows the closure and the cells' voltage range.
"""

import math
from dataclasses import dataclass

from cells.definitions import pump_composite_spec as cs
from cells.records import run_view
from validation.stationary import worlds
from validation.tissue import surface_pump_v3_fixtures as fixtures

NAME = "planarian"
DT = 1e-3  # s; the heredity sheet's step (e07_sheet_definition's default).
PERIOD_S = 2.0  # 0.5 Hz (§4).
EVERY_S = 0.02  # The observed cadence: 101 rows over the loop.
CURRENT_A = 2e-12  # Provisional: a few mV at the centre (six junctions), far from U.
SETTLE = 4  # Provisional: periods run before the observed one.
TOLERANCE = 1e-4  # Provisional: the largest closure the package accepts.
CARRIERS = {"K": 0.4912, "M": 0.5088}  # A 3 M KCl filling's proportion; M is the anion here.
SPACING_UM = 9.25  # Centre to centre: the W225 sheet's cell spacing (resolved_scale_world).
WINDOW_STEPS = 500
# The records the package keeps (about 0.4 MB at 101 rows): what the loop shows and the totals its
# reader differences for the rates (cells/run_view.LOOP_TOTALS), with the injection's own.
FIELDS = (
    "amount",
    "cell_potential_V",
    "membrane_voltage_V",
    "junction_voltage_V",
    "channel_gate",
    "junction_gate",
    "membrane_transferred",
    "channel_transferred",
    "pump_cycles",
    "junction_transferred",
    "membrane_flux_fmol_s",
    "channel_flux_fmol_s",
    "junction_flux_fmol_s",
    "pump_cycle_rate_fmol_s",
    "injection_supplied_fmol",
    "injection_removed_fmol",
    "injection_charge_C",
)


@dataclass(frozen=True)
class Package:
    """What the driver writes: the definition, the view's request and the windows' size."""

    name: str
    definition: dict
    request: run_view.Request
    window_steps: int


def _steps(seconds):
    steps = round(seconds / DT)
    if not math.isclose(steps * DT, seconds, rel_tol=1e-12, abs_tol=0.0):
        raise ValueError(f"{seconds} s is not a whole number of {DT} s steps")
    return steps


def geometry(cells):
    """The patch as pointy-top hexagons in the plane, at the sheet's spacing (prescribed)."""
    radius = SPACING_UM / math.sqrt(3)
    vertices, faces = [], []
    for q, r in cells:
        x = SPACING_UM * (q + r / 2)
        y = SPACING_UM * math.sqrt(3) / 2 * r
        faces.append(list(range(len(vertices), len(vertices) + 6)))
        for k in range(6):
            angle = math.radians(30 + 60 * k)
            vertices.append([x + radius * math.cos(angle), y + radius * math.sin(angle)])
    return run_view.Geometry(
        unit="um",
        dimensions=2,
        sets={"cell": {"kind": "polygons", "vertices": vertices, "faces": faces}},
        source="validation/replay/planarian.py: hexagon(1) in axial coordinates at the W225 "
        "sheet's cell spacing",
    )


def package(
    *,
    current_A=CURRENT_A,
    settle=SETTLE,
    tolerance=TOLERANCE,
    period_s=PERIOD_S,
    every_s=EVERY_S,
):
    """The planarian loop's definition and view request (module docstring)."""
    period, every = _steps(period_s), _steps(every_s)
    if period % 2 or period % every:
        raise ValueError("A period is an even number of steps and a whole number of rows")
    cells, edges = worlds.hexagon(1)
    centre = next(i for i, c in enumerate(cells) if worlds.ring(c) == 0)
    states = [fixtures.HEREDITY_STATES["H"][:4]] * len(cells)
    end = (settle + 1) * period
    raw = cs.frozen_definition(worlds.e07_sheet_definition(states, edges, dt=DT, end_time=end * DT))
    cell = f"cell_{centre}"
    raw["model"]["operators"] = [
        dict(
            law="cells.operator.electrode_current_injection@1",
            electrodes=[dict(cell_id=cell, carriers=dict(CARRIERS))],
        )
    ]
    schedule = []
    for p in range(settle + 1):
        schedule.append(dict(time=p * period * DT, current_A=float(current_A)))
        schedule.append(dict(time=(p * period + period // 2) * DT, current_A=-float(current_A)))
    raw["experiment"]["injection_controls"] = [dict(cell_id=cell, schedule=schedule)]
    first = settle * period
    raw["experiment"]["observation_times"] = [
        (first + j) * DT for j in range(0, period + 1, every)
    ]
    labels = {
        "id": f"{NAME}-loop",
        "experiment": "fr11-looping-replay",
        "arm": NAME,
        "label": "interim planarian loop: a seven-cell heredity sheet patch under a subthreshold "
        "current train into its centre cell (illustration, no verdict)",
    }
    request = run_view.Request(
        labels,
        geometry=geometry(cells),
        recording=run_view.Recording(fields=FIELDS),
        loop=run_view.Loop(NAME, cell, period * DT, float(tolerance)),
    )
    return Package(NAME, raw, request, WINDOW_STEPS)
