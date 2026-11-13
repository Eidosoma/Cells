"""Compact worlds for isopotential_partition@1 (docs/CELL_DIVISION_S5_DESIGN.md §8.1).

Nominal values around one heredity cell (validation/tissue/surface_pump_v3_fixtures), built from
neither J1 input (the J2 bright line, §10.1). The parent is the heredity cell with its pump
removed: pumps on a dividing cell are later work. It keeps its Kir2.1 and NaV1.2 populations, so
the partition maps populations too. Daughter slots are written by core/partition_spec.add_division
(the anchor rule), and membrane_entity_state@1 declares every population.
"""

from cells.core import partition_spec as ps
from cells.core import pump_composite_spec as cs
from tests import membrane_insertion_fixtures as ifx
from validation.tissue import pump_water_fixtures as wfx

PARTITION = "isopotential_partition@1"
DT = 1e-3
EVENT = 0.002


def parent(*, end=0.004):
    """The heredity cell facing its held bath, without its pump (@3, raw)."""
    base = wfx.heredity_cell("H", dt=DT, end_time=end)
    base["experiment"]["observation_times"] = [0.0, end]
    for patch in base["model"]["membranes"]:
        patch["pump"] = None
    base["experiment"]["pump_controls"] = []
    return base


def divided(
    *,
    f=0.5,
    area_fraction=None,
    carriers=None,
    at=EVENT,
    end=0.004,
    events=True,
    second=None,
):
    """The parent, its two daughters (d1, d2) and the partition, as a composition (raw).

    second: a time for both daughters' own divisions (d1 -> g1, g2; d2 -> g3, g4), or None.
    """
    raw = cs.frozen_definition(parent(end=end))
    blocks = [
        ps.add_division(
            raw,
            division_id="first",
            parent="cell_0",
            daughters=("d1", "d2"),
            volume_fraction=f,
            area_fractions=None if area_fraction is None else {"membrane_0": area_fraction},
            mismatch_carriers=carriers,
        )
    ]
    if second is not None:
        for d, kids in (("d1", ("g1", "g2")), ("d2", ("g3", "g4"))):
            blocks.append(ps.add_division(raw, division_id=f"second_{d}", parent=d, daughters=kids))
    raw["model"]["operators"] = [ifx.membrane_state(raw), dict(law=PARTITION, divisions=blocks)]
    schedule = []
    if events:
        schedule.append(dict(division="first", time=at, carriers=["c1", "c2"]))
        if second is not None:
            schedule += [
                dict(division="second_d1", time=second, carriers=["c11", "c12"]),
                dict(division="second_d2", time=second, carriers=["c21", "c22"]),
            ]
    raw["experiment"]["partition_events"] = schedule
    return raw


def without_divisions(*, end=0.004):
    """The parent alone with an idle partition (no divisions) and membrane state."""
    raw = cs.frozen_definition(parent(end=end))
    raw["model"]["operators"] = [ifx.membrane_state(raw), dict(law=PARTITION, divisions=[])]
    raw["experiment"]["partition_events"] = []
    return raw


def without_partition(*, end=0.004):
    """The parent with membrane state only (the idle partition's comparison)."""
    raw = cs.frozen_definition(parent(end=end))
    raw["model"]["operators"] = [ifx.membrane_state(raw)]
    return raw
