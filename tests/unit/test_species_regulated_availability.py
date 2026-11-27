"""Tier-1 smoke test of cells.operator.species_regulated_availability@1: the contract fit and every refusal.

docs/INVENTORY_COUPLING_DESIGN.md §1 (accepted 14 November 2026, rulings in §6.3). The registration
and round trip; every definition refusal of §1.11 with its message; and the operator's parts on the
bound seven-cell sheet in NumPy (no compile): the factors and their product, exactly 1 on untargeted
and switched-off elements; the exact two-state half-step; zero rates selecting the start state; the
event map (crossing record, writes, switches, counter, a stale write refused); static idleness
from the declaration alone; the summary's unrecorded final crossing; a non-finite factor refused;
a cell's prior condition, by a per-cell initial value or by a write at time 0 (FR-6, D162);
and the composition structure (every provider and closer of masks refused, §1.12). Version 1.1
(FR-65's coupling step, docs/TURNOVER_CHANGING_VOLUME_DESIGN.md §11): both versions beside water
by name, each read site's volume in NumPy and through the composite, the end check's reference
read, and the site source kept refused. The compiled runs are in the _runs and _bitwise files,
and the water door's in test_shared_inventory_volume.py.
"""

import copy
import re
from types import MappingProxyType, SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.operators import OPERATORS, species_common
from cells.operators import species_regulated_availability as sra
from cells.operators.contract import Read, check_declarations, factor_reads
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from validation.tissue import cell_replacement_fixtures as crfx
from validation.tissue import pump_water_fixtures as wfx
from validation.tissue import regulated_availability_fixtures as rf
from validation.tissue import secreted_species_fixtures as sfx
from validation.tissue import shared_inventory_fixtures as sif
from validation.tissue import site_occupancy_fixtures as ofx

LAW = sra.LAW_ID


def base(**kwargs):
    """A valid world: a Hill factor of R on junction_0's first side, and a state of Na in cell_0
    and cell_3 (junction_0's two cells) on junction_0, side both, with a basal level."""
    raw = rf.sheet(**kwargs)
    return rf.with_coupling(
        raw,
        species=["R", "Na"],
        states=[
            rf.state(
                "s",
                ["cell_0", "cell_3"],
                [("hill_activation", "Na", 12.0, 2.0)],
                on=5.0,
                off=1.0,
                initial=0.2,
                level=0.5,
            )
        ],
        couplings=[
            rf.hill_coupling(
                "c_r", "junction", ["junction_0"], "R", "hill_inhibition", 1e-3, 1.0, side="first"
            ),
            rf.coupling(
                "c_s",
                "junction",
                ["junction_0"],
                ("state", "s"),
                "state_complement",
                side="both",
                basal=0.25,
            ),
        ],
    )


def block(raw):
    return next(b for b in raw["model"]["operators"] if b["law"] == LAW)


def test_registered_with_its_declarations():
    op = OPERATORS[LAW]
    assert check_declarations(type(op)) is type(op)
    assert op.CONTROL_FACTORS == ("junction", "channel")
    assert op.EVENT and op.SPLIT and op.RK4 == "split"
    assert not op.ENTITY_WRITES and not op.LEDGERS and not op.HEAT_FIELDS and not op.WORK_FIELDS


def test_parses_and_round_trips():
    spec = parse_spec(base())
    again = parse_spec(cs.to_dict(spec))
    assert again.model.operators == spec.model.operators
    assert again.experiment.operators == spec.experiment.operators


def _edit(path_fn):
    def make():
        raw = base()
        path_fn(raw)
        return raw

    return make


def _coupling(raw, index=0):
    return block(raw)["couplings"][index]


def _state(raw):
    return block(raw)["states"][0]


def _add_species(count):
    def make():
        raw = rf.sheet()
        for k in range(count):
            raw = add_inventory_species(
                raw, f"Z{k}", trace_mM=1e-5, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
            )
        return rf.with_coupling(
            raw,
            species=["R"],
            couplings=[
                rf.hill_coupling(
                    "c", "junction", ["junction_0"], "R", "hill_activation", 1e-3, 1.0, side="first"
                )
            ],
        )

    return make


def _replaced(branch):
    """replacement@1 replaces cell_1 at 8 ms; a coupling on junction_1 (its contact), or a state
    declared in cell_1 whose coupling reads cell_0 only."""

    def make():
        raw = crfx.heredity_sheet(radius=1, disc=0, end_time=0.02)
        raw["experiment"]["observation_times"] = [0.0, 0.02]
        template = crfx.template_from_cell(raw, "cell_1", "T")
        rep = crfx.with_replacement(raw, [template], [(0.008, "cell_1", "T", "c1_new")])
        comp = add_inventory_species(
            cs.frozen_definition(rep),
            "R",
            trace_mM=1e-3,
            diffusivity_m2_per_s=1e-10,
            floor_fmol=1e-20,
        )
        if branch == "coupling":
            return rf.with_coupling(
                comp,
                species=["R"],
                couplings=[
                    rf.hill_coupling(
                        "c",
                        "junction",
                        ["junction_1"],
                        "R",
                        "hill_activation",
                        1e-3,
                        1.0,
                        side="first",
                    )
                ],
            )
        return rf.with_coupling(
            comp,
            species=["R"],
            states=[rf.frozen("s", ["cell_0", "cell_1"], 0.5)],
            couplings=[rf.fraction("c", "junction", ["junction_0"], "s", side="first")],
        )

    return make


def _watered():
    raw = crfx.heredity_sheet(radius=1, disc=0, end_time=0.02)
    raw["experiment"]["observation_times"] = [0.0, 0.02]
    raw = add_inventory_species(
        raw, "R", trace_mM=1e-3, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
    )
    comp = cs.frozen_definition(wfx.with_water(raw))
    return rf.with_coupling(
        comp,
        species=["R"],
        couplings=[
            rf.hill_coupling(
                "c", "junction", ["junction_0"], "R", "hill_activation", 1e-3, 1.0, side="first"
            )
        ],
    )


def _identity_mismatch():
    raw = base()
    block(raw)["species"][0]["catalogue"] = dict(catalogue="cells-proteins", entry="example")
    block(raw)["species"][0]["evidence"] = "label_only"
    return rf.with_turnover(raw, "cell_0", 1.0)


REFUSALS = {
    "unknown species": (
        _edit(lambda r: block(r)["species"].append(dict(id="Q", catalogue=None, evidence=None))),
        "does not declare",
    ),
    "charged instantaneous source": (
        _edit(lambda r: _coupling(r).update(source={"species": "Na"})),
        "charged species",
    ),
    "unlisted source": (_edit(lambda r: block(r)["species"].pop(0)), "not a listed species"),
    "other operator's control": (
        _edit(
            lambda r: _coupling(r)["target"].update(
                operator="cells.operator.scheduled_species_turnover@1"
            )
        ),
        "inner model's controls only",
    ),
    "leak control": (
        _edit(lambda r: _coupling(r)["target"].update(control="membrane")),
        "admitted targets",
    ),
    "side on a channel": (
        _edit(
            lambda r: _coupling(r)["target"].update(control="channel", ids=["kir_0"], side="first")
        ),
        "channel target takes no side",
    ),
    "unknown channel": (
        _edit(
            lambda r: _coupling(r)["target"].update(control="channel", ids=["kir_99"], side=None)
        ),
        "unknown channel",
    ),
    "state not in the channel's cell": (
        _edit(
            lambda r: _coupling(r, 1)["target"].update(control="channel", ids=["kir_1"], side=None)
        ),
        "is not declared",
    ),
    "unknown junction": (
        _edit(lambda r: _coupling(r)["target"].update(ids=["junction_99"])),
        "unknown junction",
    ),
    "element twice": (
        _edit(lambda r: _coupling(r)["target"].update(ids=["junction_0", "junction_0"])),
        "names an element twice",
    ),
    "junction side": (
        _edit(lambda r: _coupling(r)["target"].update(side="sender")),
        "side is one of",
    ),
    "species through a state law": (
        _edit(
            lambda r: block(r).update(
                couplings=[
                    rf.coupling(
                        "x",
                        "junction",
                        ["junction_0"],
                        ("species", "R"),
                        "state_fraction",
                        side="first",
                    )
                ]
            )
        ),
        "through a Hill law",
    ),
    "state through a Hill law": (
        _edit(
            lambda r: block(r).update(
                couplings=[
                    dict(
                        rf.coupling(
                            "x",
                            "junction",
                            ["junction_0"],
                            ("state", "s"),
                            "hill_activation",
                            side="first",
                        ),
                        half_saturation_mM=1.0,
                        hill_coefficient=1.0,
                    )
                ]
            )
        ),
        "through a state law",
    ),
    "half-saturation zero": (
        _edit(lambda r: _coupling(r).update(half_saturation_mM=0.0)),
        "positive",
    ),
    "coefficient negative": (
        _edit(lambda r: _coupling(r).update(hill_coefficient=-1.0)),
        "positive",
    ),
    "basal one": (_edit(lambda r: _coupling(r, 1).update(basal=1.0)), "[0, 1)"),
    "negative rate": (_edit(lambda r: _state(r).update(on_rate_per_s=-1.0)), "nonnegative"),
    "initial above one": (_edit(lambda r: _state(r).update(initial=1.5)), "initial value lies in"),
    "initial per cell above one": (
        _edit(lambda r: _state(r).update(initial={"cell_0": 0.2, "cell_3": 1.5})),
        "initial value in cell_3 lies in",
    ),
    "initial missing a cell": (
        _edit(lambda r: _state(r).update(initial={"cell_0": 0.2})),
        "names each of its cells once",
    ),
    "initial in another cell": (
        _edit(lambda r: _state(r).update(initial={"cell_0": 0.2, "cell_3": 0.2, "cell_5": 0.2})),
        "names each of its cells once",
    ),
    "level above one": (
        _edit(lambda r: _state(r).update(crossing_level=2.0)),
        "crossing level lies in",
    ),
    "state without input": (_edit(lambda r: _state(r).update(inputs=[])), "at least one input"),
    "state not in the target's cell": (
        _edit(lambda r: _state(r).update(cells=["cell_0"])),
        "is not declared",
    ),
    "rate limit": (
        _edit(lambda r: _state(r).update(on_rate_per_s=900.0, off_rate_per_s=200.0)),
        "dt (k_on + k_off)",
    ),
    "switch not from zero": (
        _edit(
            lambda r: r["experiment"]["coupling_controls"][0].update(
                schedule=[dict(time=0.005, enabled=1)]
            )
        ),
        "starts at 0",
    ),
    "switch value": (
        _edit(
            lambda r: r["experiment"]["coupling_controls"][0].update(
                schedule=[dict(time=0.0, enabled=0.5)]
            )
        ),
        "enabled (1) or not (0)",
    ),
    "missing switch schedule": (
        _edit(lambda r: r["experiment"]["coupling_controls"].pop()),
        "its schedule",
    ),
    "switch off the dt grid": (
        _edit(
            lambda r: r["experiment"]["coupling_controls"][0]["schedule"].append(
                dict(time=0.0055, enabled=0)
            )
        ),
        "on the clock's grid",
    ),
    "switch outside the horizon": (
        _edit(
            lambda r: r["experiment"]["coupling_controls"][0]["schedule"].append(
                dict(time=0.02, enabled=0)
            )
        ),
        "inside the horizon",
    ),
    "write off the dt grid": (
        _edit(
            lambda r: r["experiment"]["regulatory_writes"].append(
                dict(state_id="s", cell_id="cell_0", time=0.0055, value=0.5)
            )
        ),
        "on the clock's grid",
    ),
    "write outside the horizon": (
        _edit(
            lambda r: r["experiment"]["regulatory_writes"].append(
                dict(state_id="s", cell_id="cell_0", time=0.03, value=0.5)
            )
        ),
        "inside the horizon",
    ),
    "write at the horizon's end": (
        _edit(
            lambda r: r["experiment"]["regulatory_writes"].append(
                dict(state_id="s", cell_id="cell_0", time=0.02, value=0.5)
            )
        ),
        "0 <= t < end",
    ),
    "write above one": (
        _edit(
            lambda r: r["experiment"]["regulatory_writes"].append(
                dict(state_id="s", cell_id="cell_0", time=0.005, value=1.5)
            )
        ),
        "written value lies in",
    ),
    "two writes at one time": (
        _edit(
            lambda r: r["experiment"]["regulatory_writes"].extend(
                [dict(state_id="s", cell_id="cell_0", time=0.005, value=0.5)] * 2
            )
        ),
        "two writes",
    ),
    "write to an undeclared slot": (
        _edit(
            lambda r: r["experiment"]["regulatory_writes"].append(
                dict(state_id="s", cell_id="cell_5", time=0.005, value=0.5)
            )
        ),
        "undeclared state and cell",
    ),
    "unknown key": (_edit(lambda r: _coupling(r).update(gain=2.0)), "unknown="),
    "duplicate coupling": (
        _edit(lambda r: block(r)["couplings"].append(copy.deepcopy(_coupling(r)))),
        "unique",
    ),
    "duplicate state": (
        _edit(lambda r: block(r)["states"].append(copy.deepcopy(_state(r)))),
        "state IDs are unique",
    ),
    "species listed twice": (
        _edit(lambda r: block(r)["species"].append(copy.deepcopy(block(r)["species"][0]))),
        "lists a species twice",
    ),
    "identity mismatch": (_identity_mismatch, "another identity"),
    "species cap": (_add_species(12), "at most 16 species"),
    "replaced slot": (_replaced("coupling"), "coupling c targets junction_1"),
    "state on a replaced slot": (_replaced("state"), "state s is declared in cell_1"),
    "permeant instantaneous source": (
        _edit(lambda r: r["model"]["junctions"][1]["permeability_m_per_s"].update(R=1e-9)),
        "zero membrane, junction and channel permeability",
    ),
}

# ------------------------------------------------------------------ version 2's operator target
# B1′ (docs/INVENTORY_COUPLING_DESIGN.md §2.1; the lead's ruling C of 19 November 2026): @2 is @1
# plus operator targets, a Hill factor of R on D150's production of X0 in cell_0, declared before
# its target. Development, not judged.

LAW_V2 = sra.LAW_ID_V2
PRODUCTION = 2e-4  # fmol/s, X0's scheduled production in cell_0.


def routed(*, coupling_first=True, ranged=(0.0, 1.0), routes=None, states=(), inner=None):
    """The sheet with R and X0, @2 routing a Hill activation of R (K 1e-3 mM, n 2, basal 0.1) to
    the turnover's production of X0 in cell_0 (route make_x0), and that turnover. `inner`: an
    operating range for a second coupling, a step_view inhibition of R on junction_0's first
    side (its one route read in cell_0)."""
    raw = rf.sheet(extra=1)
    target = dict(
        operator=sfx.TURNOVER,
        control="turnover_rate",
        ids=["make_x0"],
        evaluation="target_half_steps",
        operating_range=list(ranged),
    )
    entry = rf.hill_coupling("c_x", "junction", ["junction_0"], "R", "hill_activation", 1e-3, 2.0)
    entry.update(target=target, basal=0.1)
    couplings = [entry]
    if inner is not None:
        view = rf.hill_coupling(
            "c_j", "junction", ["junction_0"], "R", "hill_inhibition", 1e-3, 1.0, side="first"
        )
        view["target"].update(evaluation="step_view", operating_range=list(inner))
        couplings.insert(0, view)
    raw = rf.with_coupling(raw, species=["R"], states=list(states), couplings=couplings)
    block(raw)["law"] = LAW_V2
    routes = routes or [("make_x0", "cell_0", "production", PRODUCTION)]
    turnover = dict(
        law=sfx.TURNOVER,
        species=rf.identities(["X0"]),
        routes=[dict(id=r, species="X0", node=n, kind=k) for r, n, k, _ in routes],
        templates=[],
    )
    operators = raw["model"]["operators"]
    operators.insert(len(operators) if coupling_first else 0, turnover)
    raw["experiment"]["turnover_controls"] = [
        dict(
            route_id=r,
            carrier_id=None if n.startswith("ecs") else n,
            schedule=[dict(time=0.0, rate=v)],
        )
        for r, n, _, v in routes
    ]
    return raw


def block_v2(raw):
    return next(b for b in raw["model"]["operators"] if b["law"] == LAW_V2)


def _edit_v2(path_fn, **kwargs):
    def make():
        raw = routed(**kwargs)
        path_fn(raw)
        return raw

    return make


def _target_v2(raw):
    return block_v2(raw)["couplings"][0]["target"]


STATE_INPUT = ("hill_activation", "R", 1e-3, 1.0)


def _from_state(raw):
    """The routed coupling reading state s's fraction in place of R's Hill factor."""
    entry = block_v2(raw)["couplings"][0]
    entry.update(source={"state": "s"}, law="state_fraction")
    for key in ("half_saturation_mM", "hill_coefficient"):
        del entry[key]


REFUSALS.update(
    {
        "v2 unroutable target": (
            _edit_v2(
                lambda r: _target_v2(r).update(
                    operator="cells.operator.scheduled_species_exchange@1"
                )
            ),
            "routable targets",
        ),
        "v2 operator target's evaluation": (
            _edit_v2(lambda r: _target_v2(r).update(evaluation="step_view")),
            "is evaluated at 'target_half_steps'",
        ),
        "v2 empty operating range": (
            _edit_v2(lambda r: _target_v2(r).update(operating_range=[1.0, 0.0])),
            "operating_range has low < high",
        ),
        "v2 unknown element": (
            _edit_v2(lambda r: _target_v2(r).update(ids=["make_nothing"])),
            "unknown element 'make_nothing'",
        ),
        "v2 target before its coupling": (
            lambda: routed(coupling_first=False),
            "which precedes it",
        ),
        "v2 inner target without its evaluation": (
            _edit_v2(
                lambda r: block_v2(r)["couplings"].append(
                    rf.hill_coupling(
                        "c_j",
                        "junction",
                        ["junction_0"],
                        "R",
                        "hill_inhibition",
                        1e-3,
                        1.0,
                        side="first",
                    )
                )
            ),
            f"{LAW_V2} target: missing=['evaluation', 'operating_range']",
        ),
        "v2 state source outside its cells": (
            _edit_v2(_from_state, states=[rf.state("s", ["cell_3"], [STATE_INPUT])]),
            "reads state s in cell_0, where it is not declared",
        ),
        "v2 state operating range above one": (
            _edit_v2(_from_state, states=[rf.state("s", ["cell_0"], [STATE_INPUT])], ranged=(0, 2)),
            "operating_range lies in [0, 1]",
        ),
    }
)


# ------------------------------------------------------------------ version 2's site source
# FR-24 (D244; the contract's R3): @2 reads a site population of cells.operator.site_occupancy@1 through its
# readable quantities. The world: D150's face-free cell with an outward population r0 on contact_0
# (cell_0, facing ecs_0) at theta0, and @2 routing its quantity to the turnover's production of X0
# in cell_0, declared after cells.operator.site_occupancy@1 and before the turnover. Development, not judged.

SITE_FRACTION = ("occupied_fraction", "site_fraction")


def site_routed(*, source=SITE_FRACTION, half=None, ranged=(0.0, 1.0), theta0=0.4, order=None):
    """source: (quantity, law); half: (half-saturation, Hill coefficient) for a Hill law; order:
    the operator blocks' order by law (default site occupancy, @2, the turnover)."""
    raw = ofx.face_free_sites([ofx.population("r0", theta0=theta0)])
    raw = add_inventory_species(
        raw, "X0", trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
    )
    quantity, law = source
    target = dict(
        operator=sfx.TURNOVER,
        control="turnover_rate",
        ids=["make_x0"],
        evaluation="target_half_steps",
        operating_range=list(ranged),
    )
    entry = dict(
        id="c_site",
        target=target,
        source={"site_population": "r0", "quantity": quantity},
        law=law,
        basal=0.1,
    )
    if half is not None:
        key = "half_saturation" if quantity == "occupied_fraction" else "half_saturation_mM"
        entry.update({key: half[0], "hill_coefficient": half[1]})
    raw = rf.with_coupling(raw, species=[], couplings=[entry])
    block(raw)["law"] = LAW_V2
    raw["model"]["operators"].append(
        dict(
            law=sfx.TURNOVER,
            species=rf.identities(["X0"]),
            routes=[dict(id="make_x0", species="X0", node="cell_0", kind="production")],
            templates=[],
        )
    )
    raw["experiment"]["turnover_controls"] = [
        dict(route_id="make_x0", carrier_id="cell_0", schedule=[dict(time=0.0, rate=PRODUCTION)])
    ]
    if order is not None:
        by_law = {b["law"]: b for b in raw["model"]["operators"]}
        raw["model"]["operators"] = [by_law[law] for law in order]
        keys = {
            ofx.LAW: ("site_controls",),
            LAW_V2: ("coupling_controls", "regulatory_writes"),
            sfx.TURNOVER: ("turnover_controls",),
        }
        for law, dropped in keys.items():
            if law not in order:
                for key in dropped:
                    del raw["experiment"][key]
    return raw


def site_inner(*, element="kir_0", theta0=0.3, law="site_complement"):
    """The sheet with an inward population r_in on cell_0's membrane_0 binding R from the cytosol
    (K_d 1e-3 mM, trace 5e-10 mM), and @2 routing its occupied fraction to `element`'s channel
    availability at the control view (step_view), basal 0.2."""
    raw = rf.sheet()
    population = ofx.population("r_in", patch="membrane_0", face="inside", theta0=theta0)
    population.update(ligand=rf.REGULATOR, association_rate_per_mM_per_s=1e3)
    raw = ofx.with_site_occupancy(
        raw, [population], ligands=[ofx.ligand(trace_mM=5e-10, species=rf.REGULATOR)]
    )
    target = dict(
        operator="inner",
        control="channel",
        ids=[element],
        side=None,
        evaluation="step_view",
        operating_range=[0.0, 1.0],
    )
    entry = dict(
        id="c_kir",
        target=target,
        source={"site_population": "r_in", "quantity": "occupied_fraction"},
        law=law,
        basal=0.2,
    )
    raw = rf.with_coupling(raw, species=[], couplings=[entry])
    block(raw)["law"] = LAW_V2
    return raw


def _site_entry(raw):
    return block_v2(raw)["couplings"][0]


def _site_edit(edit, **kwargs):
    def make():
        raw = site_routed(**kwargs)
        edit(_site_entry(raw))
        return raw

    return make


REFUSALS.update(
    {
        "v2 site: no site operator": (
            lambda: site_routed(order=(LAW_V2, sfx.TURNOVER)),
            "which the composition does not hold",
        ),
        "v2 site: the owner after the target": (
            lambda: site_routed(order=(LAW_V2, sfx.TURNOVER, ofx.LAW)),
            f"but {ofx.LAW} follows {sfx.TURNOVER}",
        ),
        "v2 site: an unknown population": (
            _site_edit(lambda e: e["source"].update(site_population="r9")),
            "unknown site population 'r9'",
        ),
        "v2 site: an unknown quantity": (
            _site_edit(lambda e: e["source"].update(quantity="occupied_fmol")),
            "site source reads one of occupied_fraction",
        ),
        "v2 site: a law that does not match": (
            _site_edit(lambda e: e["source"].update(quantity="occupied_mM")),
            "occupied_mM through one of hill_activation, hill_inhibition",
        ),
        "v2 site: a half-saturation in another unit": (
            _site_edit(
                lambda e: e.update(
                    law="hill_activation", half_saturation_mM=0.5, hill_coefficient=1
                )
            ),
            "its half-saturation is half_saturation, in the quantity's unit",
        ),
        "v2 site: a fraction's range above one": (
            lambda: site_routed(ranged=(0.0, 2.0)),
            "operating_range lies in [0, 1], the occupied fraction",
        ),
        "v2 site: a junction target": (
            lambda: _with_junction_target(site_inner()),
            "reads a site population onto a junction",
        ),
        "v2 site: a population in another cell": (
            lambda: site_inner(element="kir_1"),
            "a site source is read in its element's cell",
        ),
    }
)


def _with_junction_target(raw):
    _site_entry(raw)["target"].update(control="junction", ids=["junction_0"], side="first")
    return raw


def routed_replaced(**kwargs):
    """routed() with replacement@1 replacing cell_0 at 10 ms by a newcomer from template T (cell_0's
    declared state), whose production of X0 the turnover's template gives (D150's occupant rule):
    the routed element make_x0 sits in a replaced cell (FR-26's part C′)."""
    raw = routed(**kwargs)
    turnover = next(b for b in raw["model"]["operators"] if b["law"] == sfx.TURNOVER)
    turnover["templates"] = [dict(template_id="T", rates={"make_x0": PRODUCTION})]
    template = crfx.template_from_cell(raw, "cell_0", "T")  # With the cell's channel gates.
    return sfx.with_replacement(raw, [template], [(0.01, "cell_0", "T", "c0_new")])


REFUSALS.update(
    {
        "v2 C′: a state source in a replaced cell": (
            lambda: _with_state_source(
                routed_replaced(states=[rf.state("s", ["cell_0"], [STATE_INPUT])])
            ),
            "state s is declared in cell_0",
        ),
    }
)


def _with_state_source(raw):
    _from_state(raw)
    return raw


def test_version_2_routes_an_element_in_a_replaced_cell_from_a_species_source():
    """FR-26's part C′ (D244): @2 admits an operator target's element in a cell replacement@1
    replaces when its source is a species of that cell, since replacement swaps the cell's species
    and the factor then reads the newcomer's. (A site source there is admitted likewise, with
    cells.operator.site_occupant_replacement@1 resetting the population: the acceptance world.) Parse only."""
    spec = parse_spec(routed_replaced())
    declaration = next(d for o, d, _ in cs.entries(spec) if o.LAW_ID == LAW_V2)
    assert declaration.couplings[0].source_kind == "species"


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_refusals(case, monkeypatch):
    make, message = REFUSALS[case]
    if case == "species cap":  # Its call to the cap (1,024 since FR-43 / D315), set to 16 here.
        monkeypatch.setattr(species_common, "MAX_SPECIES", 16)
    with pytest.raises(ConfigError, match=None) as error:
        parse_spec(make())
    assert message in str(error.value), str(error.value)


# Operator lists with each provider or closer of a field it reads as declared (requirements first)
# and the reason. Since version 1.1 (FR-65's coupling step) it reads the cell volume current, so
# water and replacement@2 are its order and definition rows (test_version_1_1_beside_water_by_name),
# and the lumens meet it only through insertion's masks.
REFUSED = {
    "lumen@1": (
        (
            "cells.operator.membrane_entity_state@1",
            "cells.operator.scheduled_membrane_insertion@1",
            "cells.operator.restricted_cleft_lumen@1",
        ),
        "reads outside_active as declared, but cells.operator.scheduled_membrane_insertion@1",
    ),
    "lumen@2": (
        (
            "cells.operator.membrane_entity_state@1",
            "cells.operator.scheduled_membrane_insertion@2",
            "cells.operator.restricted_cleft_lumen@2",
        ),
        "reads outside_active as declared, but cells.operator.scheduled_membrane_insertion@2",
    ),
    "insertion@1": (
        ("cells.operator.membrane_entity_state@1", "cells.operator.scheduled_membrane_insertion@1"),
        "reads outside_active as declared",
    ),
    "insertion@2": (
        ("cells.operator.membrane_entity_state@1", "cells.operator.scheduled_membrane_insertion@2"),
        "reads outside_active as declared, but cells.operator.scheduled_membrane_insertion@2 closes it",
    ),
    "partition": (
        ("cells.operator.membrane_entity_state@1", "cells.operator.isopotential_partition@1"),
        "reads active as declared, but cells.operator.isopotential_partition@1 closes it",
    ),
    "bridge": (
        (
            "cells.operator.membrane_entity_state@1",
            "cells.operator.isopotential_partition@1",
            "cells.operator.cytoplasmic_bridge_closure@1",
        ),
        "reads active as declared, but cells.operator.isopotential_partition@1 closes it",
    ),
}
ADMITTED = (  # The note's §1.12 "composes" rows (replacement@1 on slots it does not replace).
    (),
    ("cells.operator.electrode_current_injection@1",),
    ("cells.operator.membrane_entity_state@1",),
    ("cells.operator.scheduled_cell_replacement@1",),
    ("cells.operator.scheduled_species_turnover@1",),
    ("cells.operator.scheduled_species_exchange@1",),
    ("cells.operator.scheduled_species_turnover@1", "cells.operator.scheduled_species_exchange@1"),
    ("cells.operator.local_species_reactions@1",),
    ("cells.operator.scheduled_species_turnover@1", "cells.operator.local_species_reactions@1"),
)


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_providers_and_closers_of_what_it_reads_as_declared_are_refused(name):
    laws, message = REFUSED[name]
    for order in ((*laws, LAW), (LAW, *laws)):
        errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order))
        assert any(e.startswith(LAW) and message in e for e in errors), (order, errors)


@pytest.mark.parametrize("laws", ADMITTED, ids=lambda laws: "+".join(laws) or "alone")
def test_the_operators_version_1_composes_with_are_admitted(laws):
    for order in ((*laws, LAW), (LAW, *laws)):
        errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order))
        assert not [e for e in errors if LAW in e], (order, errors)


# ------------------------------------------------------------- the parts, in NumPy (no compile)


@pytest.fixture(scope="module")
def bound():
    spec = parse_spec(base())
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == LAW)
    return spec, model, op, state, p


def control(switch, count, value):
    return SimpleNamespace(
        coupling_switch=np.asarray(switch, dtype=float),
        regulatory_write_count=np.asarray(count, dtype=np.int64),
        regulatory_write_value=np.asarray(value, dtype=float),
    )


def _hill(x, k, n, law):
    act = x**n / (k**n + x**n)
    return act if law == "hill_activation" else 1.0 - act


def _concentration(spec, state, p, species, cell):
    row = list(spec.model.species_ids).index(species)
    col = [c.id for c in spec.model.cells].index(cell)
    amount = np.asarray(p.amount_reference)[row, col] + np.asarray(state.amount_increment)[row, col]
    return amount / np.asarray(p.volume)[col]


def test_factors_at_the_bound_state(bound):
    """junction_0 takes the product of its three routes in declared order (an inhibition of R on
    its first side, the complement of s on both sides with basal 1/4); every other junction 1."""
    spec, _, op, state, p = bound
    factors = op.control_factors(state, p, xp=np)
    assert set(factors) == {"junction"}
    junctions = [j.id for j in spec.model.junctions]
    j0 = junctions.index("junction_0")
    r = _hill(_concentration(spec, state, p, "R", "cell_0"), 1e-3, 1.0, "hill_inhibition")
    s = np.asarray(state.regulatory_state)
    assert list(s) == [0.2, 0.2]
    complement = 0.25 + 0.75 * (1.0 - 0.2)
    np.testing.assert_allclose(factors["junction"][j0], r * complement * complement, rtol=1e-14)
    others = np.delete(np.asarray(factors["junction"]), j0)
    assert np.all(others == 1.0)  # Untargeted elements select exactly 1.


def test_channel_factors_at_the_bound_state():
    """A state coupling on cell_0's Kir population: its factor is s there; every other channel 1,
    and the junction product is unchanged by the channel route."""
    raw = base()
    block(raw)["couplings"].append(
        rf.coupling("c_k", "channel", ["kir_0"], ("state", "s"), "state_fraction")
    )
    raw["experiment"]["coupling_controls"].append(
        dict(coupling_id="c_k", schedule=[dict(time=0.0, enabled=1)])
    )
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == LAW)
    factors = op.control_factors(state, p, xp=np)
    assert set(factors) == {"junction", "channel"}
    channels = [c.id for c in spec.model.channels]
    k = channels.index("kir_0")
    assert factors["channel"][k] == 0.2
    assert np.all(np.delete(np.asarray(factors["channel"]), k) == 1.0)
    plain = parse_spec(base())
    plain_state, plain_p = get_model(plain.model).initial_values(plain)
    reference = op.control_factors(plain_state, plain_p, xp=np)
    assert np.array_equal(factors["junction"], reference["junction"])


def test_the_half_step_is_the_exact_two_state_solution(bound):
    spec, _, op, state, p = bound
    h = 0.5
    new, valid = op.half_step(state, h, control([1, 1], [0, 0], [0, 0]), p, xp=np)
    assert bool(valid)
    for k, cell in enumerate(("cell_0", "cell_3")):
        u = _hill(_concentration(spec, state, p, "Na", cell), 12.0, 2.0, "hill_activation")
        lam = 5.0 * u + 1.0
        target = 5.0 * u / lam
        expected = target + (0.2 - target) * np.exp(-lam * h)
        np.testing.assert_allclose(new.regulatory_state[k], expected, rtol=1e-14)
        np.testing.assert_allclose(new.regulatory_input_integral[k], u * h, rtol=1e-14)
    # The amounts are read, never written.
    assert np.array_equal(new.amount_increment, state.amount_increment)


def test_zero_rates_select_the_start_state():
    raw = base()
    for entry in block(raw)["states"]:
        entry.update(on_rate_per_s=0.0, off_rate_per_s=0.0)
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == LAW)
    new, valid = op.half_step(state, 0.5, control([1, 1], [0, 0], [0, 0]), p, xp=np)
    assert bool(valid)
    assert new.regulatory_state.tobytes() == state.regulatory_state.tobytes()


def test_the_event_map(bound):
    """At a step start: the crossing record from the state before writes and the counter, then a
    due write, the switches copied, the counter advanced; a stale write count refuses the step."""
    _, _, op, state, p = bound
    lifted = state._replace(
        regulatory_state=np.asarray([0.6, 0.2]), coupling_step_count=np.asarray([7])
    )
    new, ok = op.event(lifted, control([0, 1], [0, 1], [0.0, 0.9]), p, xp=np)
    assert bool(ok)
    assert list(new.regulatory_crossing_step) == [7, -1]  # Level 0.5: crossed in cell_0 only.
    assert list(new.regulatory_state) == [0.6, 0.9]  # The write, after the record.
    assert list(new.regulatory_writes_applied) == [0, 1]
    assert list(new.coupling_enabled) == [0.0, 1.0]
    assert list(new.coupling_step_count) == [8]
    again, _ = op.event(new, control([0, 1], [0, 1], [0.0, 0.9]), p, xp=np)
    assert list(again.regulatory_crossing_step) == [7, 8]  # A record is kept once set.
    _, stale = op.event(state, control([1, 1], [0, 2], [0.0, 0.9]), p, xp=np)
    assert not bool(stale)


def test_switched_off_factors_are_exactly_one(bound):
    _, _, op, state, p = bound
    off = state._replace(coupling_enabled=np.zeros(2))
    factors = op.control_factors(off, p, xp=np)
    assert np.all(np.asarray(factors["junction"]) == 1.0)


def test_static_idleness_follows_the_declaration_only():
    for raw, idle in ((rf.with_coupling(rf.sheet()), True), (base(), False)):
        spec = parse_spec(raw)
        model = get_model(spec.model)
        _, p = model.initial_values(spec)
        op = next(o for o in model.operators if o.LAW_ID == LAW)
        assert op.statically_idle(p) is idle
        if idle:
            assert op.control_factors(None, p, xp=np) == {}


def test_the_summary_reports_an_unrecorded_final_crossing(bound):
    """A final row at or above a level with no record (no later step start ran the event map)."""
    spec, _, op, _, _ = bound
    _, declaration, schedule = next(e for e in cs.entries(spec) if e[0].LAW_ID == LAW)
    history = SimpleNamespace(
        regulatory_state=np.asarray([[0.2, 0.2], [0.6, 0.4]]),
        regulatory_crossing_step=np.asarray([[-1, -1], [-1, -1]], dtype=np.int64),
    )
    summary = op.summary(spec, declaration, schedule, history)
    assert summary["coupling_unrecorded_final_crossings"] == [["s", "cell_0"]]
    recorded = history.regulatory_crossing_step.copy()
    recorded[-1, 0] = 1
    history = history.__class__(
        regulatory_state=history.regulatory_state, regulatory_crossing_step=recorded
    )
    assert (
        op.summary(spec, declaration, schedule, history)["coupling_unrecorded_final_crossings"]
        == []
    )


def test_a_non_finite_factor_refuses_the_step(bound):
    _, _, op, state, p = bound
    assert bool(op.domain_valid(state, p, None, xp=np))
    rows = list(p.coupling_route_row)
    lost = np.asarray(state.amount_increment).copy()
    lost[rows[0], p.coupling_route_cell[0]] = (
        -2.0 * np.asarray(p.amount_reference)[rows[0], p.coupling_route_cell[0]]
    )
    with np.errstate(invalid="ignore"):  # The log of a negative amount: the case refused.
        assert not bool(op.domain_valid(state._replace(amount_increment=lost), p, None, xp=np))


def test_a_prior_condition_per_cell_and_by_a_write_at_time_zero():
    """A per-cell s0 binds per slot and round-trips (a number when every cell's is equal); a write
    at time 0 is no schedule change time, its count is in the control at 0, and the first step
    start's event map applies it after the crossing record."""
    raw = base()
    _state(raw).update(initial={"cell_0": 0.7, "cell_3": 0.2})
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == LAW)
    assert list(state.regulatory_state) == [0.7, 0.2]
    assert parse_spec(cs.to_dict(spec)).model.operators == spec.model.operators
    assert block(cs.to_dict(spec))["states"][0]["initial"] == {"cell_0": 0.7, "cell_3": 0.2}
    assert block(cs.to_dict(parse_spec(base())))["states"][0]["initial"] == 0.2

    raw = base()
    raw["experiment"]["regulatory_writes"].append(
        dict(state_id="s", cell_id="cell_0", time=0.0, value=0.7)
    )
    spec = parse_spec(raw)
    state, p = get_model(spec.model).initial_values(spec)
    _, _, schedule = next(e for e in cs.entries(spec) if e[0].LAW_ID == LAW)
    assert 0.0 not in op.schedule_times(schedule)
    c = cs.control_values(spec, [0.0])
    first = control(c.coupling_switch[0], c.regulatory_write_count[0], c.regulatory_write_value[0])
    assert list(first.regulatory_write_count) == [1, 0]
    lifted = state._replace(regulatory_state=np.asarray([0.6, 0.2]))
    new, ok = op.event(lifted, first, p, xp=np)
    assert bool(ok)
    assert list(new.regulatory_state) == [0.7, 0.2]
    assert list(new.regulatory_writes_applied) == [1, 0]
    assert list(new.regulatory_crossing_step) == [0, -1]  # From the state before the write.


def test_a_switch_change_mid_run_cuts_the_coupling():
    """§1.13's cut: a change of c_r's switch at 10 ms is a schedule change time; the control holds 1
    before it and 0 from it; the event map at that step start copies it, after which c_r's route
    gives exactly 1 and c_s's routes are unchanged."""
    raw = base()
    raw["experiment"]["coupling_controls"][0]["schedule"].append(dict(time=0.01, enabled=0))
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == LAW)
    _, _, schedule = next(e for e in cs.entries(spec) if e[0].LAW_ID == LAW)
    assert 0.01 in op.schedule_times(schedule)
    c = cs.control_values(spec, [0.0, 0.009, 0.01, 0.015])
    assert c.coupling_switch.tolist() == [[1, 1], [1, 1], [0, 1], [0, 1]]
    before = sra.route_factors(state, p, xp=np)
    at = control(c.coupling_switch[2], c.regulatory_write_count[2], c.regulatory_write_value[2])
    new, ok = op.event(state, at, p, xp=np)
    assert bool(ok) and list(new.coupling_enabled) == [0.0, 1.0]
    after = sra.route_factors(new, p, xp=np)
    for route, coupling in enumerate(np.asarray(p.coupling_route_coupling)):
        if coupling == 0:
            assert before[route] < 1.0 and after[route] == 1.0
        else:
            assert after[route] == before[route]


# ------------------------------------------------------------------ A7 and A9, at the definition


def _with_idle_operator(raw):
    raw["model"]["operators"].append(dict(law=LAW, species=[], states=[], couplings=[]))
    raw["experiment"]["coupling_controls"] = []
    raw["experiment"]["regulatory_writes"] = []
    return raw


def _lumen(version):
    from tests import membrane_insertion_fixtures as ifx

    raw = ifx.with_operators(ifx.cleft_cell(), ifx.furrow_insertion(onset=0.002))
    lumen = dict(
        law="cells.operator.restricted_cleft_lumen@1",
        lumens=[dict(node_id="cleft", source_id="bath_0", gap_width_m=2e-6)],
    )
    raw["model"]["operators"].append(lumen)
    if version == 2:
        later = {
            "cells.operator.scheduled_membrane_insertion@1": "cells.operator.scheduled_membrane_insertion@2",
            "cells.operator.restricted_cleft_lumen@1": "cells.operator.restricted_cleft_lumen@2",
        }
        for entry in raw["model"]["operators"]:
            entry["law"] = later.get(entry["law"], entry["law"])
    return _with_idle_operator(raw)


def _replacement_over_water():
    from cells.definitions.cell_replacement_spec import exact_event_times

    raw = crfx.heredity_sheet(1, 0, dt=1e-3, end_time=0.02)
    raw["experiment"]["observation_times"] = [0.0, 0.02]
    (t,) = exact_event_times((10,), 1e-3)
    template = crfx.template_from_cell(raw, "cell_1", "h")
    return _with_idle_operator(crfx.over_water(raw, [template], ((t, "cell_0", "h", "n1"),)))


SHARED_RULE = (  # species_common.check_volume_changers, by name (FR-43 / D315).
    "cells.operator.scheduled_cell_replacement@2 changes the volumes it reads; water is the one "
    "volume changer admitted beside it"
)
# A7 (docs/INVENTORY_COUPLING_DESIGN.md §4.4), amended in place for version 1.1 (FR-65's coupling
# step, docs/TURNOVER_CHANGING_VOLUME_DESIGN.md §11; disclosed there and in §8.4): water is the one
# volume changer admitted (its acceptance, the water door, is test_shared_inventory_volume.py's), so
# its case moved to test_version_1_1_beside_water_by_name; replacement@2 over water is refused by
# the shared rule, and the lumens by insertion's masks, each with its reason.
VOLUME_PROVIDERS = {
    "replacement@2 over water": (_replacement_over_water, SHARED_RULE),
    "lumen@1": (
        lambda: _lumen(1),
        "reads outside_active as declared, but cells.operator.scheduled_membrane_insertion@1 "
        "provides it",
    ),
    "lumen@2": (
        lambda: _lumen(2),
        "reads outside_active as declared, but cells.operator.scheduled_membrane_insertion@2 "
        "closes it",
    ),
}


@pytest.mark.parametrize("name", sorted(VOLUME_PROVIDERS))
def test_a7_volume_changers_but_water_are_refused_at_the_definition(name):
    make, reason = VOLUME_PROVIDERS[name]
    with pytest.raises(ConfigError) as error:
        parse_spec(make())
    assert reason in str(error.value), str(error.value)


def test_a9_a_batch_refuses_worlds_of_another_structure():
    from cells.execution.batch import BatchSpec, WorldSpec, parse_batch

    def batch(*raws):
        worlds = tuple(WorldSpec(i + 1, parse_spec(r)) for i, r in enumerate(raws))
        return parse_batch(BatchSpec(worlds, len(worlds), 10**6, 2**31).to_dict())

    first = rf.pair_world()
    varied = rf.pair_world(
        on=8.0,
        off=2.0,
        s0=(0.4, 0.1),
        level=0.3,
        half_saturation=2e-3,
        coefficient=2.0,
        basal=0.1,
        write=(0.005, 0.8),
        switch=(0.004, 0.01),
    )
    batch(first, varied)  # Parameters, s0, the level, the switch and the write are data.
    other_side = copy.deepcopy(first)
    block(other_side)["couplings"][0]["target"]["side"] = "second"
    other_law = copy.deepcopy(first)
    block(other_law)["couplings"][1]["law"] = "state_fraction"
    more_species = copy.deepcopy(first)
    block(more_species)["species"].append(dict(id="Na", catalogue=None, evidence=None))
    for other in (other_side, other_law, more_species):
        with pytest.raises(ConfigError, match="matching model array axes"):
            batch(first, other)


def test_the_field_map_records_each_factored_controls_chain_and_only_then():
    """Ruling 6, with the lead's rule of 14 November 2026: the `factors` entry appears only with a
    factor operator, so every other composition's field map (and its manifests) is unchanged."""
    inner = "cells.model.resolved_pump_tissue@3"
    replacement, bridge = (
        "cells.operator.scheduled_cell_replacement@1",
        "cells.operator.cytoplasmic_bridge_closure@1",
    )
    keys = {"state", "layout", "control", "views", "observations"}
    for laws in (
        (),
        ("cells.operator.ideal_osmosis_linear_compliance_water@1",),
        ("cells.operator.electrode_current_injection@1",),
        ("cells.operator.scheduled_species_turnover@1", "cells.operator.local_species_reactions@1"),
    ):
        assert set(pump_composite.implementation(inner, laws).FIELD_MAP) == keys, laws
    chains = {
        (replacement, LAW): {"junction": [replacement, LAW], "channel": [LAW]},
        (LAW, replacement): {"junction": [LAW, replacement], "channel": [LAW]},
        (replacement,): {"junction": [replacement]},
        (
            "cells.operator.membrane_entity_state@1",
            "cells.operator.isopotential_partition@1",
            bridge,
        ): {"junction": [bridge]},
    }
    for laws, chain in chains.items():
        field_map = pump_composite.implementation(inner, laws).FIELD_MAP
        assert set(field_map) == keys | {"factors"} and field_map["factors"] == chain, laws


def test_a_state_with_two_inputs_multiplies_an_activation_and_an_inhibition():
    """u = f_act(Na) f_inh(R) per cell (D152's rule: factors multiply), and the half-step is the
    exact solution with that u, against the Hill forms written out directly."""
    raw = base()
    _state(raw)["inputs"].append(
        dict(law="hill_inhibition", species="R", half_saturation_mM=1e-3, hill_coefficient=1.0)
    )
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == LAW)
    u = np.asarray(sra.state_inputs(state, p, xp=np))
    expected = []
    for cell in ("cell_0", "cell_3"):
        na = _concentration(spec, state, p, "Na", cell)
        r = _concentration(spec, state, p, "R", cell)
        expected.append(
            _hill(na, 12.0, 2.0, "hill_activation") * _hill(r, 1e-3, 1.0, "hill_inhibition")
        )
    np.testing.assert_allclose(u, expected, rtol=1e-14)
    new, valid = op.half_step(state, 0.5, control([1, 1], [0, 0], [0, 0]), p, xp=np)
    assert bool(valid)
    lam = 5.0 * np.asarray(expected) + 1.0
    target = 5.0 * np.asarray(expected) / lam
    np.testing.assert_allclose(
        new.regulatory_state, target + (0.2 - target) * np.exp(-lam * 0.5), rtol=1e-14
    )


def test_version_2_routes_a_production_rate_in_the_targets_half_steps(monkeypatch):
    """B1′ on @2 (development, not judged; its Hill reference is written out here): registered with
    its routes; parses and round trips; binds make_x0's one route. The factor F = b + (1 - b) f is
    the Hill law of R's concentration in cell_0, and the composite's half-step of the turnover is
    bitwise the half-step at the product rate. Switched off (the cut control), F is exactly 1 and
    the half-step is the scheduled one. Planted, each refused: R outside the declared operating
    range, which refuses the half-step only while the coupling is on; and an outside-node element
    (the turnover's elements planted at no cell), refused at the binding."""
    op = OPERATORS[LAW_V2]
    assert check_declarations(type(op)) is type(op)
    assert op.RATE_ROUTES == tuple(sra.OPERATOR_TABLES)
    assert op.LAYOUT_FIELDS[: len(sra.LAYOUT_FIELDS)] == sra.LAYOUT_FIELDS
    spec = parse_spec(routed())
    again = parse_spec(cs.to_dict(spec))
    assert again.model.operators == spec.model.operators
    assert again.experiment.operators == spec.experiment.operators
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    coupling = next(o for o in model.operators if o.LAW_ID == LAW_V2)
    turnover = next(o for o in model.operators if o.LAW_ID == sfx.TURNOVER)
    assert model.rate_routes == {turnover: ((coupling, "turnover_rate"),)}
    assert np.asarray(p.coupling_turnover_rate_routes).tolist() == [[0]]
    assert np.asarray(p.coupling_reaction_multiplier_routes).shape == (0, 0)
    assert coupling.declared_rate_routes(spec.model.operators[0]) == (
        (sfx.TURNOVER, "turnover_rate"),
    )
    c = _concentration(spec, state, p, "R", "cell_0")
    expected = 0.1 + 0.9 * _hill(c, 1e-3, 2.0, "hill_activation")
    factor, ok = coupling.rate_factors(state, p, sfx.TURNOVER, "turnover_rate", xp=np)
    assert bool(ok) and float(factor[0]) == pytest.approx(expected, rel=1e-14) and expected < 1
    values = cs.control_values(spec, [0.0])
    control = model.CONTROL_TYPE(*(v[0] for v in values))
    h = 0.5 * spec.execution.dt
    record = sra.SpeciesRegulatedAvailabilityV2.FACTOR_RECORD
    assert np.asarray(getattr(state, record)).tobytes() == np.asarray(factor).tobytes()  # Bound.
    routed_step, ok = model._half_step(turnover, state, h, control, p, xp=np)
    scheduled = control._replace(turnover_rate=control.turnover_rate * factor)
    by_hand, _ = turnover.half_step(state, h, scheduled, p, xp=np)
    assert bool(ok)
    _bitwise_but(routed_step, by_hand, record)
    assert np.asarray(getattr(routed_step, record)).tobytes() == np.asarray(factor).tobytes()
    off = state._replace(coupling_enabled=np.zeros_like(state.coupling_enabled))
    cut, ok = model._half_step(turnover, off, h, control, p, xp=np)
    plain, _ = turnover.half_step(off, h, control, p, xp=np)
    assert bool(ok)
    _bitwise_but(cut, plain, record)
    assert np.asarray(getattr(cut, record)).tolist() == [1.0]  # The factor applied: exactly 1.
    narrow = parse_spec(routed(ranged=(0.5, 1.0)))  # R at 1e-3 mM, below the range.
    model2 = get_model(narrow.model)
    state2, p2 = model2.initial_values(narrow)
    _, ok = model2._half_step(turnover, state2, h, control, p2, xp=np)
    assert not bool(ok)
    off2 = state2._replace(coupling_enabled=np.zeros_like(state2.coupling_enabled))
    _, ok = model2._half_step(turnover, off2, h, control, p2, xp=np)
    assert bool(ok)
    monkeypatch.setattr(
        type(turnover),
        "routable_elements",
        lambda self, d, f: tuple((r.id, None) for r in d.routes),
    )
    with pytest.raises(ConfigError, match="routes cell-side elements only"):
        parse_spec(routed())


def self_routed():
    """The independent Lean project's ramp world (lean/checks/regulated_availability.py,
    ramp_order, 20 November 2026): a 1 pL cell with S at 1 mM; the turnover produces S at 1 fmol/s
    (make_S) and Y at 1 fmol/s times @2's Hill activation of S (K 1 mM, n 1, basal 0) in the same
    cell (make_Y): a route whose source its own target moves."""
    raw = sfx.world(nodes=(), contacts=(), faces=(), trace_mM=1.0, dt=1 / 8, end=1.0)
    raw = add_inventory_species(
        raw, "Y", trace_mM=1.0, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
    )
    coupling = dict(
        id="reporter_gate",
        source=dict(species=sfx.SPECIES),
        law="hill_activation",
        basal=0.0,
        half_saturation_mM=1.0,
        hill_coefficient=1.0,
        target=dict(
            operator=sfx.TURNOVER,
            control="turnover_rate",
            ids=["make_Y"],
            evaluation="target_half_steps",
            operating_range=[1.0, 2.0],
        ),
    )
    raw = rf.with_coupling(raw, species=[sfx.SPECIES], couplings=[coupling])
    block(raw)["law"] = LAW_V2
    routes = [(r, "cell_0", "production") for r in ("make_S", "make_Y")]
    controls = [(r, "cell_0", [(0.0, 1.0)]) for r, _, _ in routes]
    raw = sfx.with_turnover(raw, routes, controls, species=rf.identities([sfx.SPECIES, "Y"]))
    next(r for r in raw["model"]["operators"][-1]["routes"] if r["id"] == "make_Y")["species"] = "Y"
    return parse_spec(raw)


def _autoregulated_transcription(monkeypatch):
    """The row cells.operator.templated_polymerisation@1 (FR-38's found defect, the lead's ruling of 22 November
    2026): A1 to 10 s with its coupling's source moved from X to R, transcription's own product,
    which R's loss and completions move inside each of transcription's half-steps; R starts at the
    Hill activation's K, 1e-8 mM. Before the operator declared half_step_rows the composite never
    saw the route as self-moved, so k_I's factor was a left-endpoint rule: order 1, as planted
    here. With it, the cumulative initiations converge at order 2. NumPy half-steps of the
    operator alone, about 3 s with the world's build, no world compiled."""
    from validation.gene_regulation import worlds

    raw = worlds.a1(end=10.0)
    (block,) = [op for op in raw["model"]["operators"] if op["law"] == LAW_V2]
    block["species"] = [dict(id="R", catalogue=None, evidence=None)]
    coupling = block["couplings"][0]
    coupling.update(source=dict(species="R"), half_saturation_mM=1e-8)
    coupling["target"]["operating_range"] = [0.0, 1e-6]
    raw["model"]["cells"][0]["initial_amount_fmol"]["R"] = 1e-8  # 1e-8 mM in its 1 pL.
    spec = parse_spec(raw)
    target = worlds.POLYMERISATION
    assert pump_composite.self_moved_targets(spec.model) == {target}
    model = get_model(spec.model)
    assert model.structure_key[3:] == (("midpoint", (target,)),)
    state, p = model.initial_values(spec)
    operator = next(o for o in model.operators if o.LAW_ID == target)
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))

    def orders(per_second):
        made = []
        for n in per_second:
            current = state
            for _ in range(20 * n):
                current, ok = model._half_step(operator, current, 1 / (2 * n), control, p, xp=np)
                assert bool(ok)
            made.append(float(np.asarray(current.poly_initiated_fmol)[0]))
        gaps = [abs(a - b) for a, b in zip(made, made[1:], strict=False)]
        return [np.log2(a / b) for a, b in zip(gaps, gaps[1:], strict=False)]

    assert min(orders((1, 2, 4, 8))) >= 1.9
    monkeypatch.setattr(model, "midpoint", frozenset())
    assert max(orders((1, 2, 4))) < 1.2


def _routed_release_fraction(monkeypatch):
    """The row cells.operator.templated_polymerisation@1's durable fraction (FR-38's routed p, the sheet's §9.4,
    source 3): R1 to 10 s at k_I = 0, its release's p = 0.75 routed by a Hill activation on R, the
    durable fate row that the release itself fills inside each of transcription's half-steps; R
    starts at the activation's K, 1e-10 mM, and rises about threefold, so p's factor u, between b =
    0.2 and 1, moves through the run. The composite evaluates u at the half-step's midpoint, so the
    cumulative durable releases converge at order 2, and u < 1 applies: the durable share of the
    releases lies below the scheduled p. Planted, the midpoint off: a left-endpoint rule, order 1.
    NumPy half-steps of the operator alone, about 3 s with the world's build, no world compiled."""
    from validation.gene_regulation import kernel, worlds

    raw = kernel.truncated(worlds.r1(0.75), 10.0)
    raw["model"]["operators"].insert(
        0,
        dict(
            law=LAW_V2,
            species=[dict(id="R", catalogue=None, evidence=None)],
            states=[],
            couplings=[
                dict(
                    id="c_release",
                    target=dict(
                        operator=worlds.POLYMERISATION,
                        control="polymerisation_release_fraction",
                        ids=[worlds.RELEASE],
                        evaluation="target_half_steps",
                        operating_range=[0.0, 1e-6],
                    ),
                    source={"species": "R"},
                    law="hill_activation",
                    half_saturation_mM=1e-10,
                    hill_coefficient=2.0,
                    basal=0.2,
                )
            ],
        ),
    )
    raw["experiment"].update(
        coupling_controls=[dict(coupling_id="c_release", schedule=[dict(time=0.0, enabled=1)])],
        regulatory_writes=[],
    )
    raw["model"]["cells"][0]["initial_amount_fmol"]["R"] = 1e-10  # 1e-10 mM in its 1 pL.
    spec = parse_spec(raw)
    target = worlds.POLYMERISATION
    assert pump_composite.self_moved_targets(spec.model) == {target}
    model = get_model(spec.model)
    assert model.structure_key[3:] == (("midpoint", (target,)),)
    state, p = model.initial_values(spec)
    operator = next(o for o in model.operators if o.LAW_ID == target)
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))

    def orders(per_second):
        made, share = [], None
        for n in per_second:
            current = state
            for _ in range(20 * n):
                current, ok = model._half_step(operator, current, 1 / (2 * n), control, p, xp=np)
                assert bool(ok)
            released = np.asarray(current.poly_hold_released_fmol)[0, 0]  # [fate]
            made.append(float(released[0]))
            share = float(released[0] / released.sum())
        gaps = [abs(a - b) for a, b in zip(made, made[1:], strict=False)]
        return [np.log2(a / b) for a, b in zip(gaps, gaps[1:], strict=False)], share

    found, share = orders((1, 2, 4, 8))
    assert min(found) >= 1.9 and 0.2 * 0.75 < share < 0.75  # p u, with u in (b, 1).
    monkeypatch.setattr(model, "midpoint", frozenset())
    assert max(orders((1, 2, 4))[0]) < 1.2


@pytest.mark.parametrize(
    "target",
    [
        "cells.operator.scheduled_species_turnover@1",
        "cells.operator.templated_polymerisation@1",
        "cells.operator.templated_polymerisation@1-release_fraction",
    ],
)
def test_version_2_evaluates_a_route_its_target_moves_at_the_half_steps_midpoint(
    monkeypatch, target
):
    """A route whose source its own target moves (the independent Lean project's finding: first
    order, a gain of 0.58928135 fmol at 8 steps against 1 - ln(3/2)): the composite evaluates its
    factor at the target half-step's midpoint, from a predictor over h/2 (pump_composite's
    self_moved_targets and _half_step). NumPy half-steps of the turnover alone (S and Y are moved
    by nothing else), under 1 s, no world compiled. Four refinements of the one-second ramp
    converge at order at least 1.9; the record holds the midpoint's factor; the S route keeps its
    booking; a composition without such a route (routed) keeps its key. Planted: the midpoint off,
    order 1. The second row is _autoregulated_transcription's, the third
    _routed_release_fraction's."""
    if target == "cells.operator.templated_polymerisation@1":
        return _autoregulated_transcription(monkeypatch)
    if target == "cells.operator.templated_polymerisation@1-release_fraction":
        return _routed_release_fraction(monkeypatch)
    spec = parse_spec(routed())
    assert pump_composite.self_moved_targets(spec.model) == frozenset()
    assert get_model(spec.model).structure_key[3:] == ()
    spec = self_routed()
    assert pump_composite.self_moved_targets(spec.model) == {sfx.TURNOVER}
    model = get_model(spec.model)
    assert model.structure_key[3:] == (("midpoint", (sfx.TURNOVER,)),)
    state, p = model.initial_values(spec)
    turnover = next(o for o in model.operators if o.LAW_ID == sfx.TURNOVER)
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))
    s, y = (list(spec.model.species_ids).index(k) for k in (sfx.SPECIES, "Y"))
    record = sra.SpeciesRegulatedAvailabilityV2.FACTOR_RECORD
    h = 1 / 16
    first, ok = model._half_step(turnover, state, h, control, p, xp=np)
    c_mid = 1.0 + h / 2  # mM: S after the predictor's h/2 at 1 fmol/s in 1 pL.
    assert bool(ok) and float(np.asarray(getattr(first, record))[0]) == c_mid / (1.0 + c_mid)
    assert float(np.asarray(first.amount_increment)[s, 0]) == h  # make_S, as without a route.

    def gains(steps):
        out = []
        for n in steps:
            current = state
            for _ in range(2 * n):
                current, ok = model._half_step(turnover, current, 1 / (2 * n), control, p, xp=np)
                assert bool(ok)
            assert float(np.asarray(current.amount_increment)[s, 0]) == 1.0
            out.append(float(np.asarray(current.amount_increment)[y, 0]))
        return out

    exact = 1.0 - np.log1p(0.5)
    errors = [abs(g - exact) for g in gains((8, 16, 32, 64))]
    orders = [np.log2(a / b) for a, b in zip(errors, errors[1:], strict=False)]
    assert min(orders) >= 1.9, orders
    # Beside a site route (the operators owner's review): site_routed's turnover, made self-moved
    # by a second route of X0, which it produces, onto the same make_x0. The predictor moves X0,
    # never the site's pools, so the site route's factor applied at the midpoint is bitwise
    # 0.1 + 0.9 theta of the state the half-step receives.
    mixed = site_routed()
    block_v2(mixed)["species"] = rf.identities(["X0"])
    target = dict(
        operator=sfx.TURNOVER,
        control="turnover_rate",
        ids=["make_x0"],
        evaluation="target_half_steps",
        operating_range=[0.0, 1e6],
    )
    block_v2(mixed)["couplings"].append(
        dict(
            id="c_x0",
            source=dict(species="X0"),
            law="hill_activation",
            basal=0.0,
            half_saturation_mM=1e-9,
            hill_coefficient=1.0,
            target=target,
        )
    )
    mixed["experiment"]["coupling_controls"].append(
        dict(coupling_id="c_x0", schedule=[dict(time=0.0, enabled=1)])
    )
    mixed = parse_spec(mixed)
    assert pump_composite.self_moved_targets(mixed.model) == {sfx.TURNOVER}
    model2 = get_model(mixed.model)
    state2, p2 = model2.initial_values(mixed)
    turnover2 = next(o for o in model2.operators if o.LAW_ID == sfx.TURNOVER)
    control2 = model2.CONTROL_TYPE(*(v[0] for v in cs.control_values(mixed, [0.0])))
    stepped, ok = model2._half_step(turnover2, state2, mixed.execution.dt / 2, control2, p2, xp=np)
    v2 = next(d for d in mixed.model.operators if d.law == LAW_V2)
    keys = [k[0] for k in sra.route_keys(mixed, v2)]
    applied = np.asarray(getattr(stepped, record))
    assert bool(ok) and float(applied[keys.index("c_site")]) == 0.1 + 0.9 * float(
        _theta(state2, p2)[0]
    )
    monkeypatch.setattr(model, "midpoint", frozenset())
    planted = [abs(g - exact) for g in gains((8, 16))]
    assert np.log2(planted[0] / planted[1]) < 1.2


def _bitwise_but(a, b, skipped):
    """Every field of two states bitwise equal but `skipped`."""
    for name in type(a)._fields:
        if name != skipped:
            assert np.asarray(getattr(a, name)).tobytes() == np.asarray(getattr(b, name)).tobytes()


def test_version_2_holds_and_records_each_factor_where_it_is_applied(monkeypatch):
    """R4 and the exact record (the lead's freeze rulings of 19 November 2026; development, not
    judged). A step_view target's operating range is held at the control view, where its factor is
    evaluated, for an enabled coupling only. The composite records each route's factor where it
    is applied: a step_view route at the control view, an operator route at its target's
    half-step, every other route kept. Planted: R outside the step_view range, refused by the
    control view's check and so by the composite's whole step (NumPy, @3's step stubbed, since
    the check precedes it), and admitted switched off."""
    spec = parse_spec(routed(inner=(0.0, 1.0)))
    assert parse_spec(cs.to_dict(spec)).model.operators == spec.model.operators
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    coupling = next(o for o in model.operators if o.LAW_ID == LAW_V2)
    turnover = next(o for o in model.operators if o.LAW_ID == sfx.TURNOVER)
    assert sra.route_keys(spec, spec.model.operators[0]) == (
        ("c_j", "junction_0", "cell_0"),
        ("c_x", "make_x0", "cell_0"),
    )
    assert np.asarray(p.coupling_route_low).tolist() == [0.0, 0.0]
    assert bool(coupling.factor_valid(state, p, xp=np))
    record = coupling.FACTOR_RECORD
    values = sra.route_factors(state, p, xp=np)
    planted = state._replace(**{record: np.full(2, 0.5)})  # A record to be overwritten in part.
    checked, viewed = model._control_factor_checks(planted, p, xp=np)
    assert bool(checked)
    assert np.asarray(getattr(viewed, record)).tolist() == [float(values[0]), 0.5]
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))
    h = 0.5 * spec.execution.dt
    stepped, ok = model._half_step(turnover, planted, h, control, p, xp=np)
    assert bool(ok) and np.asarray(getattr(stepped, record)).tolist() == [0.5, float(values[1])]
    narrow = parse_spec(routed(inner=(0.5, 1.0)))  # R at 1e-3 mM, below the step_view range.
    model2 = get_model(narrow.model)
    state2, p2 = model2.initial_values(narrow)
    coupling2 = next(o for o in model2.operators if o.LAW_ID == LAW_V2)
    assert not bool(coupling2.factor_valid(state2, p2, xp=np))
    control2 = model2.CONTROL_TYPE(*(v[0] for v in cs.control_values(narrow, [0.0])))
    monkeypatch.setattr(model2.inner, "checked_step", lambda s, dt, c, q, active: (s, True))
    _, ok = model2.split_step(state2, narrow.execution.dt, control2, p2, xp=np)
    assert not bool(ok)
    off_schedule = control2._replace(coupling_switch=np.zeros_like(control2.coupling_switch))
    _, ok = model2.split_step(state2, narrow.execution.dt, off_schedule, p2, xp=np)
    assert bool(ok)  # The same stubbed step admitted with every coupling switched off.
    off = np.asarray(state2.coupling_enabled).copy()
    off[0] = 0.0  # c_j switched off: its range is not held.
    assert bool(coupling2.factor_valid(state2._replace(coupling_enabled=off), p2, xp=np))


class _ControlViewReader(sra.SpeciesRegulatedAvailabilityV2):
    """R2′, planted: @2 with current reads of channel_abundance and volume at the control view
    only (no split read, so it is no door S reader); each of its factor hooks keeps the view it is
    given."""

    SCOPED_READS = MappingProxyType(
        {"channel_abundance": Read("current", "inner"), "volume": Read("current", "inner")}
    )
    VIEW_READS = ("channel_abundance", "volume")

    def __init__(self):
        self.seen = []

    def control_factors(self, state, p, *, xp, view=None, quantities=None):
        self.seen.append(("control_factors", view))
        return super().control_factors(state, p, xp=xp, view=view)

    def factor_valid(self, state, p, *, xp, view=None, quantities=None):
        self.seen.append(("factor_valid", view))
        return super().factor_valid(state, p, xp=xp, view=view)

    def factor_record(self, state, p, target, field, *, xp, view=None, quantities=None):
        self.seen.append(("factor_record", view))
        return super().factor_record(state, p, target, field, xp=xp, view=view)

    def rate_factors(self, state, p, target, field, *, xp, quantities=None, view=None):
        self.seen.append(("rate_factors", view))
        return super().rate_factors(state, p, target, field, xp=xp, view=view)


def _planted_reading(raw):
    """(spec, the composition with @2 replaced by the planted reader, the reader, state, control,
    p): a composition built directly, so no definition check runs."""
    spec = parse_spec(raw)
    model = get_model(spec.model)
    planted = _ControlViewReader()
    reading = pump_composite.Composition(
        model.inner, tuple(planted if o.LAW_ID == LAW_V2 else o for o in model.operators)
    )
    state, p = reading.initial_values(spec)
    control = reading.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))
    return spec, reading, planted, state, control, p


def test_a_factor_operator_reads_the_control_view_per_field_where_it_changes():
    """R2′ (FR-65's coupling step, docs/TURNOVER_CHANGING_VOLUME_DESIGN.md §11.3; R2 is FR-7's
    request): a factor operator's current reads at stage inner reach its three control-view hooks
    as a ViewFunction that carries only the fields some operator changes (C1 per field), and no
    view where none is changed; a routed half-step passes the source its reader view only where it
    reads current at the split (the planted reader does not). Without a changer, the routed world
    of turnover's production gives every hook view None; in A1's swelling cell, the hooks at the
    control view get a view of the volume alone, whose volume is the full view's. Planted: the
    declaration-based rule, which passes channel_abundance with no changer. Host only, about 3 s."""
    spec = parse_spec(routed(inner=(0.0, 1.0)))
    assert get_model(spec.model).factor_fields == {}  # channel_abundance: no changer here.
    declared = {o: factor_reads(o) for o in get_model(spec.model).factors if factor_reads(o)}
    assert {o.LAW_ID: f for o, f in declared.items()} == {LAW_V2: ("channel_abundance", "volume")}
    swelling = sif.swelling_a1(coupling=True, dt=0.01, end=1.0, every=0.5)
    unit = "cells.operator.templated_polymerisation@1"
    for raw, carried, routed_law in (
        (routed(inner=(0.0, 1.0)), None, sfx.TURNOVER),
        (swelling, ("volume",), unit),
    ):
        spec, reading, planted, state, control, p = _planted_reading(raw)
        assert reading.factor_fields == ({} if carried is None else {planted: carried})
        reading.control_view(control, state, p, xp=np)
        reading._control_factor_checks(state, p, xp=np)
        target = next(o for o in reading.operators if o.LAW_ID == routed_law)
        reading._half_step(target, state, 0.5 * spec.execution.dt, control, p, xp=np)
        hooks = [name for name, _ in planted.seen]
        assert hooks[:3] == ["control_factors", "factor_valid", "factor_record"], hooks
        assert set(hooks[3:]) == {"rate_factors", "factor_record"}, hooks  # Its routed calls.
        for name, view in planted.seen[3:]:
            assert view is None, name  # Not a door S reader: the routed half-step passes none.
        full = reading.view(p, state, xp=np)
        for name, view in planted.seen[:3]:
            if carried is None:
                assert view is None, name
            else:
                assert view.fields == carried, name
                assert np.array_equal(view(state).volume, full.volume), name


def _site_model(raw):
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    coupling = next(o for o in model.operators if o.LAW_ID == LAW_V2)
    return spec, model, state, p, coupling


def _theta(state, p):
    bound = np.asarray(p.site_bound_anchor_fmol) + np.asarray(state.site_bound_increment_fmol)
    free = np.asarray(p.site_free_anchor_fmol) + np.asarray(state.site_free_increment_fmol)
    return bound / (bound + free)


def test_version_2_routes_a_site_populations_quantity_in_the_targets_half_steps():
    """FR-24 on @2 (development, not judged), in NumPy with no world compiled (about 2 s): the
    turnover's production of X0 in cell_0 routed from r0's occupied fraction (site_fraction, basal
    0.1), read through cells.operator.site_occupancy@1's readable quantities (R3). The factor is
    0.1 + 0.9 theta at the bound state and its record's start; the routed half-step is bitwise the
    half-step at the product rate; at another occupancy the factor and the half-step change;
    switched off the factor is exactly 1; the site half-step keeps its bits whether the coupling is
    on, off or absent (a one-way read); a theta outside the declared range refuses the half-step
    only while on. A Hill law of B / V, of an empty site (activation gives the basal level,
    inhibition 1, in NumPy and compiled), and a capacity source reported constant."""
    op = OPERATORS[LAW_V2]
    assert op.QUANTITY_READS == {
        sra.SITE_LAW: ("site_occupied_fraction", "site_occupied_fmol", "site_capacity_fmol")
    }
    spec, model, state, p, coupling = _site_model(site_routed())
    again = parse_spec(cs.to_dict(spec))
    assert again.model.operators == spec.model.operators
    declaration = next(d for o, d, _ in cs.entries(spec) if o.LAW_ID == LAW_V2)
    assert coupling.declared_quantity_reads(declaration) == (
        (sra.SITE_LAW, "site_occupied_fraction", sfx.TURNOVER),
    )
    assert np.asarray(p.coupling_route_site).tolist() == [0]
    assert np.asarray(p.coupling_route_law).tolist() == [sra.SITE_FRACTION]
    turnover = next(o for o in model.operators if o.LAW_ID == sfx.TURNOVER)
    sites = next(o for o in model.operators if o.LAW_ID == ofx.LAW)
    quantities = model.quantity_reader(coupling, p, xp=np)
    theta = _theta(state, p)[0]
    factor, ok = coupling.rate_factors(
        state, p, sfx.TURNOVER, "turnover_rate", xp=np, quantities=quantities
    )
    assert bool(ok) and float(factor[0]) == 0.1 + 0.9 * theta and theta == pytest.approx(0.4)
    record = sra.SpeciesRegulatedAvailabilityV2.FACTOR_RECORD
    assert np.asarray(getattr(state, record)).tobytes() == np.asarray(factor).tobytes()  # Bound.
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))
    h = 0.5 * spec.execution.dt
    routed_step, ok = model._half_step(turnover, state, h, control, p, xp=np)
    scheduled = control._replace(turnover_rate=control.turnover_rate * factor)
    by_hand, _ = turnover.half_step(state, h, scheduled, p, xp=np)
    assert bool(ok)
    _bitwise_but(routed_step, by_hand, record)
    moved = np.asarray(p.site_free_anchor_fmol) * 0.5  # Half the free sites bound.
    other = state._replace(
        site_bound_increment_fmol=np.asarray(state.site_bound_increment_fmol) + moved,
        site_free_increment_fmol=np.asarray(state.site_free_increment_fmol) - moved,
    )
    factor2, _ = coupling.rate_factors(
        other, p, sfx.TURNOVER, "turnover_rate", xp=np, quantities=quantities
    )
    assert float(factor2[0]) == 0.1 + 0.9 * _theta(other, p)[0] and factor2[0] > factor[0]
    step2, _ = model._half_step(turnover, other, h, control, p, xp=np)
    assert not np.array_equal(step2.amount_increment, routed_step.amount_increment)
    off = state._replace(coupling_enabled=np.zeros_like(state.coupling_enabled))
    cut, ok = model._half_step(turnover, off, h, control, p, xp=np)
    plain, _ = turnover.half_step(off, h, control, p, xp=np)
    assert bool(ok)
    _bitwise_but(cut, plain, record)
    assert np.asarray(getattr(cut, record)).tolist() == [1.0]
    absent = parse_spec(site_routed(order=(ofx.LAW, sfx.TURNOVER)))
    absent_model = get_model(absent.model)
    absent_state, absent_p = absent_model.initial_values(absent)
    values = cs.control_values(absent, [0.0])
    absent_control = absent_model.CONTROL_TYPE(*(v[0] for v in values))
    site_steps = [model._half_step(sites, s, h, control, p, xp=np)[0] for s in (state, off)] + [
        absent_model._half_step(sites, absent_state, h, absent_control, absent_p, xp=np)[0]
    ]
    for name in ofx_state_fields():
        on_bits, off_bits, absent_bits = (
            np.asarray(getattr(s, name)).tobytes() for s in site_steps
        )
        assert on_bits == off_bits == absent_bits, name
    narrow = parse_spec(site_routed(ranged=(0.5, 1.0)))  # theta 0.4, below the range.
    model3 = get_model(narrow.model)
    state3, p3 = model3.initial_values(narrow)
    _, ok = model3._half_step(turnover, state3, h, control, p3, xp=np)
    assert not bool(ok)
    off3 = state3._replace(coupling_enabled=np.zeros_like(state3.coupling_enabled))
    assert bool(model3._half_step(turnover, off3, h, control, p3, xp=np)[1])
    # A Hill law of B / V (mM in cell_0, at its declared volume), and of an empty site.
    for theta0, law, expected_empty in (
        (0.4, "hill_activation", None),
        (0.0, "hill_activation", 0.1),
        (0.0, "hill_inhibition", 1.0),
    ):  # noqa: E501
        raw = site_routed(
            source=("occupied_mM", law), half=(1e-9, 2.0), theta0=theta0, ranged=(0, 1)
        )
        spec4, model4, state4, p4, coupling4 = _site_model(raw)
        reader = model4.quantity_reader(coupling4, p4, xp=np)
        f4, _ = coupling4.rate_factors(
            state4, p4, sfx.TURNOVER, "turnover_rate", xp=np, quantities=reader
        )
        cell = [c.id for c in spec4.model.cells].index("cell_0")
        bound = np.asarray(p4.site_bound_anchor_fmol)[0]
        x = bound / np.asarray(p4.volume)[cell]
        if expected_empty is None:
            assert float(f4[0]) == pytest.approx(0.1 + 0.9 * _hill(x, 1e-9, 2.0, law), rel=1e-14)
        else:
            assert x == 0.0 and float(f4[0]) == expected_empty
            source = sra.site_route_sources(reader(state4), p4, xp=np)
            compiled = jax.jit(
                lambda s, st, pp: sra.with_site_factors(jnp.ones(1), st, pp, s, xp=jnp)
            )
            assert float(np.asarray(compiled(source, state4, p4))[0]) == expected_empty
    capacity = parse_spec(
        site_routed(source=("capacity_mM", "hill_activation"), half=(1e-9, 1.0), ranged=(0, 1))
    )  # noqa: E501
    declaration = next(d for o, d, _ in cs.entries(capacity) if o.LAW_ID == LAW_V2)
    summary = op.summary(capacity, declaration, None, SimpleNamespace())
    assert summary["coupling_constant_sources"] == {"c_site": sra.CONSTANT_CAPACITY}
    assert summary["coupling_targets"]["c_site"]["source"] == {
        "site_population": "r0",
        "quantity": "capacity_mM",
    }


def ofx_state_fields():
    return tuple(OPERATORS[ofx.LAW].STATE_AXES)


def test_version_2_reads_a_site_population_on_a_channel_at_the_control_view():
    """FR-24's inner target (development, not judged; NumPy, no world compiled): kir_0's
    availability factor at the control view is 0.2 + 0.8 (1 - theta) of r_in, an inward population
    binding R in cell_0, and every other channel's 1, through the composite's control view, which
    passes @2 its quantities (R3); the range check holds there."""
    spec, model, state, p, coupling = _site_model(site_inner())
    reader = model.quantity_reader(coupling, p, xp=np)
    theta = _theta(state, p)[0]
    factors = coupling.control_factors(state, p, xp=np, quantities=reader)
    channels = [c.id for c in spec.model.channels]
    k = channels.index("kir_0")
    assert float(factors["channel"][k]) == 0.2 + 0.8 * (1.0 - theta)
    assert np.all(np.delete(np.asarray(factors["channel"]), k) == 1.0)
    assert bool(coupling.factor_valid(state, p, xp=np, quantities=reader))
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))
    effective = model.control_view(control, state, p, xp=np)
    scheduled = np.asarray(model.inner.inner_control(control).channel)
    assert float(np.asarray(effective.channel)[k]) == float(scheduled[k] * factors["channel"][k])


def test_version_2_reads_the_newcomers_occupancy_after_its_reset():
    """FR-26's exact reads (D244; the lead's ruling: the reads-stay-exact branch, NumPy). cell_0,
    holding r0 (theta0 0.4) and the routed production of X0, is replaced at 10 ms; W resets r0 to
    its newcomer's template occupancy 0.8. W has only an event part, and events run before every
    split part's first half, so at the step leaving t_e the routed factor is the newcomer's,
    0.1 + 0.9 theta(after the events), from the target's first half on (a writer with a split part
    would need R3's order check extended to writers)."""
    raw = site_routed(theta0=0.4)
    turnover = next(b for b in raw["model"]["operators"] if b["law"] == sfx.TURNOVER)
    turnover["templates"] = [dict(template_id="T", rates={"make_x0": PRODUCTION})]
    raw = sfx.with_replacement(
        raw, [sfx.template(raw, "cell_0", "T")], [(0.01, "cell_0", "T", "n")]
    )
    raw = ofx.with_occupant(raw, {"T": {"r0": (0.8, 1.0, None)}})
    spec, model, state, p, coupling = _site_model(raw)
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.01])))
    after = state
    for op in model.events:
        after, ok = op.event(after, control, p, xp=np)
        assert ok is None or bool(ok)
    reader = model.quantity_reader(coupling, p, xp=np)
    theta = _theta(after, p)[0]
    assert theta == pytest.approx(0.8, rel=1e-15) and _theta(state, p)[0] == pytest.approx(0.4)
    factor, ok = coupling.rate_factors(
        after, p, sfx.TURNOVER, "turnover_rate", xp=np, quantities=reader
    )
    assert bool(ok) and float(factor[0]) == 0.1 + 0.9 * theta


def receptor_routed(theta0, enabled=1):
    """The tester's receptor-controlled reaction (D264 finding 1): the face-free world's cell_0
    holds X0 at 1e-3 mM, and D152's convert X0 -> P (mass action, k 0.2/s) in cell_0 is routed by
    @2 from the receptor r0's occupied fraction (site_fraction, basal 0); r0's binding is off, so
    its theta holds at theta0. enabled: the coupling's switch."""
    from validation.tissue import species_reactions_fixtures as rfx

    raw = ofx.face_free_sites(
        [ofx.population("r0", theta0=theta0)], controls={("r0", "binding"): [(0.0, 0.0)]}
    )
    for name, profile in (("X0", {"cell_0": 1e-3}), ("P", None)):
        raw = add_inventory_species(
            raw, name, trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20,
            concentrations_mM=profile,
        )  # fmt: skip
    species = [rfx.species("X0", moieties={"Q": 1}), rfx.species("P", moieties={"Q": 1}, mu=-1.0)]
    reaction = rfx.mass_action("convert", {"cells": ["cell_0"]}, {"X0": 1}, {"P": 1}, 0.2)
    raw = rfx.with_reactions(raw, species, [reaction], [("convert", None, [(0.0, 1.0)])])
    target = dict(
        operator="cells.operator.local_species_reactions@1",
        control="reaction_multiplier",
        ids=["convert"],
        evaluation="target_half_steps",
        operating_range=[0.0, 1.0],
    )
    entry = dict(id="receptor", target=target, law="site_fraction", basal=0.0,
                 source={"site_population": "r0", "quantity": "occupied_fraction"})  # fmt: skip
    raw = rf.with_coupling(
        raw, species=[], couplings=[entry], switches={"receptor": [(0.0, enabled)]}
    )
    block(raw)["law"] = LAW_V2
    rank = {ofx.LAW: 0, LAW_V2: 1, "cells.operator.local_species_reactions@1": 2}
    raw["model"]["operators"].sort(key=lambda b: rank.get(b["law"], -1))
    return raw


def test_a_routed_targets_exported_rate_is_the_rate_its_step_runs_at(monkeypatch):
    """D264 finding 1 (a tester's report; host only, about 1 s). A receptor-routed reaction's
    exported rate (reaction_rate_fmol_per_s) read 0.000200 fmol/s in all three controls, where its
    product accumulated at 0, 0.000080 and 0.000200: the observer took the scheduled multiplier,
    not the routed one. The composite now observes a routed target with its routes' factors at the
    row's state (pump_composite's observe_history). In each control the exported rate at t = 0
    is k n theta-factor, and it equals the product one target half-step makes, per second (to
    the step's own depletion). Planted, the routes left out of the observer: the empty receptor
    exports the unrouted 0.000200 again. Turnover and the unit producer observe their state only,
    and @3's channels are observed at the control view, so they need no change."""
    k, n = 0.2, 1e-3  # 1/s; fmol, X0 in cell_0 (1e-3 mM in 1 pL).
    h = 1e-6
    for theta0, enabled, factor in ((0.0, 1, 0.0), (0.4, 1, 0.4), (0.4, 0, 1.0)):
        spec = parse_spec(receptor_routed(theta0, enabled))
        model = get_model(spec.model)
        state, p = model.initial_values(spec)
        history = type(state)(*(np.asarray(v)[None] for v in state))
        observed = model.observe_history(np.array([0.0]), history, p, np.array([0.0]), spec)
        exported = float(np.asarray(observed.reaction_rate_fmol_per_s)[0, 0])
        assert exported == pytest.approx(k * n * factor, rel=1e-12, abs=1e-30), theta0
        reactions = next(
            o for o in model.operators if o.LAW_ID == "cells.operator.local_species_reactions@1"
        )
        control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))
        stepped, ok = model._half_step(reactions, state, h, control, p, xp=np)
        row = list(spec.model.species_ids).index("P")
        made = float(np.asarray(stepped.reaction_produced_fmol)[row, 0]) / h
        assert bool(ok) and made == pytest.approx(exported, rel=1e-6, abs=1e-30), theta0
    spec = parse_spec(receptor_routed(0.0))
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    monkeypatch.setattr(model, "rate_routes", {})
    history = type(state)(*(np.asarray(v)[None] for v in state))
    observed = model.observe_history(np.array([0.0]), history, p, np.array([0.0]), spec)
    assert float(np.asarray(observed.reaction_rate_fmol_per_s)[0, 0]) == pytest.approx(k * n)


def _clamp_world(source):
    """FR-34's maintained twin example (validation/channel_readouts/example.py, a composite:
    kir_0 and leak_1, the same count on one patch), both scheduled at availability 1, with leak_1
    held at a factor of 0.5 by `source`: "write", cells.operator.species_regulated_availability@1 (a Hill
    activation of R at its own concentration, exactly 0.5); "door", the routing door (a planted
    factor source, 0.5)."""
    from tests import kind_fixtures as kf
    from validation.channel_readouts import example

    raw = example.world()
    for entry in raw["experiment"]["channel_controls"]:
        if entry["channel_id"] == example.HALF:
            entry["schedule"] = [dict(time=0.0, availability=1.0)]
    if source == "write":
        raw = add_inventory_species(
            raw, rf.REGULATOR, trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20,
            concentrations_mM={"cell_0": 1e-3},
        )  # fmt: skip
        entry = rf.hill_coupling(
            "hold", "channel", [example.HALF], rf.REGULATOR, "hill_activation", 1e-3, 1.0
        )
        return rf.with_coupling(raw, species=[rf.REGULATOR], couplings=[entry])
    raw = kf.declare_routing(raw, factors={"f_a": 0.5})
    channel = next(c for c in raw["model"]["channels"] if c["id"] == example.HALF)
    channel["factors"] = ["f_a"]
    return raw


@pytest.mark.parametrize("source", ("write", "door"))
def test_a_composites_clamped_current_runs_at_its_effective_availability(source):
    """D265 finding 1 (a fourth review; host only, about 1 s each): in a composite, a channel
    population's current at a declared voltage is the composite's clamped_channel_flux, which
    hands @3 the control and layout views the step runs at (clamp_inputs). leak_1 is held at a
    factor of 0.5 by an @1 write or by the routing door, kir_0 at 1, the same count:
    - at the cell's own voltage the clamped flux is the recorded channel_flux_fmol_s, bit for bit;
    - at -50 mV leak_1's current is exactly half of kir_0's;
    - for the write, @3's helper given the stored control and layout (the reviewer's path, 11.10328
      pA for 5.55164) loses the factor: leak_1's current equals kir_0's."""
    from cells.models import surface_pump_v3 as v3
    from cells.registry import kind_registry
    from tests import kind_fixtures as kf
    from validation.channel_readouts import example

    with kind_registry.scope(kf.registry(kf.factor_source())):
        spec = parse_spec(_clamp_world(source))
        model = get_model(spec.model)
        state, p = model.initial_values(spec)
        control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))
        history = type(state)(*(np.asarray(v)[None] for v in state))
        observed = model.observe_history(np.array([0.0]), history, p, np.array([0.0]), spec)
        own = np.asarray(observed.membrane_voltage_V)[0]
        flux, _ = model.clamped_channel_flux(state, control, p, own)
        assert np.array_equal(flux, np.asarray(observed.channel_flux_fmol_s)[0])
        ids = [c.id for c in spec.model.channels]
        full, half = ids.index(example.FULL), ids.index(example.HALF)
        _, current = model.clamped_channel_flux(state, control, p, -0.05)
        assert current[full] != 0 and current[half] == 0.5 * current[full]
        if source == "write":
            inner = model.inner
            stored = v3.clamped_channel_flux(
                inner.inner_state(state), inner.inner_control(control), inner.inner_layout(p),
                -0.05, xp=np, structure=inner.structure,
            )[1]  # fmt: skip
            assert stored[half] == stored[full] == 2 * current[half]


def test_a_composites_clamped_kinds_are_the_steps_own_rates():
    """D265 finding 1's check of the kinds (host only, about 2 s): in a composite with kinds
    (crossrev's FR-4 declared world: passive routes, the rapid proton buffer, transporters), the
    composite's clamped_kind at each route's own patch voltage is the step's own passive flux
    (the composite readouts' passive_transferred derivative), bit for bit."""
    from cells.kinds import passive_routes
    from validation.tissue import composite_crossrev as crossrev

    spec = parse_spec(crossrev._worlds("kinds", all_steps=False)["fr4_declared"])
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))
    values = model.readouts(state, control, p, xp=np)
    potentials = np.asarray(values.ionic.field.potential_V)
    _, _, view = model.clamp_inputs(state, control, p)
    volts = (
        potentials[np.asarray(view.passive_inside)] - potentials[np.asarray(view.passive_outside)]
    )
    flux, _ = model.clamped_kind(passive_routes.clamped_flux, state, control, p, volts)
    assert np.any(flux != 0)
    assert np.array_equal(flux, np.asarray(values.derivative.passive_transferred))


# ------------------------------------------------------------------ version 1.1: beside water
# FR-65's coupling step (docs/TURNOVER_CHANGING_VOLUME_DESIGN.md §11; D402): the cell volume is
# read current wherever a factor or a state is evaluated, beside water declared first. Each read
# site has its row here or in test_shared_inventory_volume.py (§11.8's table).

WATER = "cells.operator.ideal_osmosis_linear_compliance_water@1"


def _coupling_first(raw):
    """raw with the coupling's block moved to the front, before water."""
    ops = raw["model"]["operators"]
    block = next(o for o in ops if o["law"] in (LAW, LAW_V2))
    raw["model"]["operators"] = [block, *(o for o in ops if o is not block)]
    return raw


# FR-65's coupling step beside FR-50 phase 2 (D327): @3's own one-way records beside the coupling
# and water are refused by name until a world qualifies the three (check_one_way_records).
RECORDS_RULE = (
    "@3's own one_way records (one_way_records) beside the coupling and "
    f"{WATER}, a changer of the cell volume, are refused until a world qualifies the three together"
)


def _recorded(raw, entity, entity_id, species):
    """raw with @3's own one-way records (FR-50 phase 2) on one entity and species."""
    out = copy.deepcopy(raw)
    out["model"]["one_way_records"] = [dict(entity=entity, id=entity_id, species=[species])]
    return out


def _as_v2(raw):
    """raw with its idle coupling block under version 2's law (its definition check is its own)."""
    for entry in raw["model"]["operators"]:
        if entry["law"] == LAW:
            entry["law"] = LAW_V2
    return raw


def _a5pp_swelling():
    from validation.tissue import a5pp_acceptance_fixtures as a5pp

    return sif.with_water_first(a5pp.registered_world())


BESIDE_WATER = {  # (builder, the refusal's words, or None for an admission)
    "@1: an instantaneous Hill on a junction (A7's water world)": (_watered, None),
    "@1: a state on two cells' populations (A5'')": (_a5pp_swelling, None),
    "@1: the pair world": (lambda: sif.with_water_first(rf.pair_world()), None),
    "@1: the water door": (lambda: sif.water_door(version=1), None),
    "@2: the water door, beside the network and turnover": (sif.water_door, None),
    "@2: A1, beside turnover and the gene unit": (
        lambda: sif.swelling_a1(coupling=True, end=60.0),
        None,
    ),
    "@2: arm B, labelled": (lambda: sif.swelling_arm_b("p=0.55 returned"), None),
    "@2: beside the symport": (lambda: sif.companion_world("symport", coupling=True), None),
    "@2: beside the bath schedule": (
        lambda: sif.companion_world("bath schedule", coupling=True),
        None,
    ),
    "@1: declared before water": (
        lambda: _coupling_first(_watered()),
        f"{LAW} reads the view volume at stage split before {WATER} changes it there",
    ),
    "@2: declared before water": (
        lambda: _coupling_first(sif.swelling_a1(coupling=True, end=60.0)),
        f"{LAW_V2} reads the view volume at stage split before {WATER} changes it there",
    ),
    "@1: beside replacement@2 over water": (_replacement_over_water, SHARED_RULE),
    "@2: beside replacement@2 over water": (lambda: _as_v2(_replacement_over_water()), SHARED_RULE),
    "@1: A7's water world, with @3's own one-way records": (
        lambda: _recorded(_watered(), "junction", "junction_0", "Na"),
        RECORDS_RULE,
    ),
    "@2: the water door, with @3's own one-way records": (
        lambda: _recorded(sif.water_door(), "channel", sif.DOOR_CHANNEL, "K"),
        RECORDS_RULE,
    ),
}


@pytest.mark.parametrize("name", sorted(BESIDE_WATER))
def test_version_1_1_beside_water_by_name(name, monkeypatch):
    """FR-65's coupling step, §11.8 row 1, host side, about 0.1 to 3 s a world (parse only, nothing
    compiled): both versions beside water declared first, alone and beside the network, turnover,
    the gene unit, labels, the symport and the bath schedule; refused in the engine's words when
    declared before water (C2's order rule) and beside replacement@2 (the shared volume rule).
    Planted: version 1.0's declarations (the shared static-tissue list, no volume read) put back
    on both versions, every admitted world is refused with "reads volume as declared"."""
    build, words = BESIDE_WATER[name]
    if words is not None:
        with pytest.raises(ConfigError, match=re.escape(words)):
            parse_spec(build())
        return
    parse_spec(build())
    for cls, reads in (
        (sra.SpeciesRegulatedAvailability, ()),
        (sra.SpeciesRegulatedAvailabilityV2, ("channel_abundance",)),
    ):
        monkeypatch.setattr(cls, "CONFLICTS_VIEW", species_common.CONFLICTS_VIEW)
        monkeypatch.setattr(cls, "VIEW_READS", reads)
        monkeypatch.setattr(
            cls, "SCOPED_READS", MappingProxyType({k: Read("current", "inner") for k in reads})
        )
    pump_composite._implementation.cache_clear()  # Compositions are cached per operator list.
    try:
        with pytest.raises(ConfigError, match=r"availability@[12] reads volume as declared"):
            parse_spec(build())
    finally:
        monkeypatch.undo()
        pump_composite._implementation.cache_clear()


def _hill(x, k, n, law):
    """x^n / (K^n + x^n) (activation) or K^n / (K^n + x^n) (inhibition), written plainly."""
    a = (np.asarray(x, dtype=float) / k) ** n
    return a / (1.0 + a) if law in ("hill_activation", 1) else 1.0 / (1.0 + a)


def _closed_factors(state, p, volume):
    """[route] F = b + (1 - b) f of every route at `volume` [cell], written plainly from the
    layout: a species route's Hill law of n/V, a state route's s or 1 - s; 1 switched off."""
    law = np.asarray(p.coupling_route_law)
    rows, cells = np.asarray(p.coupling_route_row), np.asarray(p.coupling_route_cell)
    amount = (
        np.asarray(p.amount_reference)[rows, cells]
        + np.asarray(state.amount_increment)[rows, cells]
    )
    x = amount / np.asarray(volume)[cells]
    k, n = np.asarray(p.coupling_route_half_saturation_mM), np.asarray(p.coupling_route_coefficient)
    states = np.asarray(state.regulatory_state)
    s = states[np.asarray(p.coupling_route_slot)] if states.size else np.zeros(law.shape)
    f = np.where(
        law == 1,
        _hill(x, k, n, 1),
        np.where(law == 2, _hill(x, k, n, 2), np.where(law == 3, s, 1.0 - s)),
    )
    b = np.asarray(p.coupling_route_basal)
    on = np.asarray(state.coupling_enabled)[np.asarray(p.coupling_route_coupling)] > 0
    return np.where(on, b + (1.0 - b) * f, 1.0)


def _swollen(state, p, scale):
    """state with water's cell increment set by hand, V = scale V0 in every cell."""
    return state._replace(volume_increment_pL=(scale - 1.0) * np.asarray(p.volume))


def test_version_1_1_kernels_read_the_volume_they_are_given(bound):
    """§11.8 row 2, NumPy (no compile), about 1 s: route_factors and state_inputs read a species
    source's concentration at the volume they are given, here 1.3 V0, against the closed forms at
    n/V; range_valid refuses a source inside its range at V0 and outside it at a shrunken V.
    Planted: the declared volume (no volume given), which misses each."""
    _, _, _, state, p = bound
    volume = 1.3 * np.asarray(p.volume)
    got = np.asarray(sra.route_factors(state, p, xp=np, volume=volume))
    want = _closed_factors(state, p, volume)
    assert np.allclose(got, want, rtol=1e-13, atol=0.0), (got, want)
    declared = np.asarray(sra.route_factors(state, p, xp=np))
    assert not np.allclose(declared, want, rtol=1e-6, atol=0.0)  # The plant misses.
    rows = np.asarray(p.regulatory_input_row)
    cells = np.asarray(p.regulatory_slot_cell)[:, None]
    amount = (
        np.asarray(p.amount_reference)[rows, cells]
        + np.asarray(state.amount_increment)[rows, cells]
    )
    x = amount / volume[np.asarray(p.regulatory_slot_cell)][:, None]
    kind = np.asarray(p.regulatory_input_kind)
    factors = np.where(
        kind == 1,
        _hill(x, p.regulatory_input_half_saturation_mM, p.regulatory_input_coefficient, 1),
        np.where(
            kind == 2,
            _hill(x, p.regulatory_input_half_saturation_mM, p.regulatory_input_coefficient, 2),
            1.0,
        ),
    )
    u = np.asarray(sra.state_inputs(state, p, xp=np, volume=volume))
    assert np.allclose(u, factors.prod(axis=1), rtol=1e-13, atol=0.0)
    assert not np.allclose(sra.state_inputs(state, p, xp=np), u, rtol=1e-6, atol=0.0)
    spec = parse_spec(routed())
    routed_state, routed_p = get_model(spec.model).initial_values(spec)
    law, row, cell = (np.asarray(getattr(routed_p, k)) for k in (
        "coupling_route_law", "coupling_route_row", "coupling_route_cell"))  # fmt: skip
    c0 = (
        np.asarray(routed_p.amount_reference)[row, cell]
        + np.asarray(routed_state.amount_increment)[row, cell]
    ) / np.asarray(routed_p.volume)[cell]
    tight = routed_p._replace(coupling_route_high=1.05 * c0)  # V0 inside, V0 / 1.1 outside.
    used = np.ones(law.shape[0], dtype=bool)
    shrunk = np.asarray(routed_p.volume) / 1.1
    assert bool(sra.range_valid(routed_state, tight, used, xp=np))
    assert not bool(sra.range_valid(routed_state, tight, used, xp=np, volume=shrunk))


def test_version_1_1_the_end_check_reads_the_declared_volume_with_the_same_outcome(bound):
    """§11.8 row 3, NumPy, about 1 s: factors_valid, the end's validity check (rate_checks and
    domain_valid), keeps the declared volume as a reference read (C3): a factor lies in [0, 1] at
    every finite positive volume, so its outcome is the same at V and at V0 for the amounts 0,
    1e-30, 1, 1e30, inf, NaN and -1. Planted: a volume-dependent check in its place (range_valid,
    at a range that V0 keeps and V leaves) changes the outcome."""
    _, _, _, state, p = bound
    route = int(np.flatnonzero(np.asarray(p.coupling_route_law) == 2)[0])  # c_r: R's inhibition.
    row, cell = int(p.coupling_route_row[route]), int(p.coupling_route_cell[route])
    for scale in (0.7, 1.3):
        volume = scale * np.asarray(p.volume)
        for amount in (0.0, 1e-30, 1.0, 1e30, np.inf, np.nan, -1.0):
            increment = np.asarray(state.amount_increment).copy()
            increment[row, cell] = amount - float(np.asarray(p.amount_reference)[row, cell])
            at = state._replace(amount_increment=increment)
            with np.errstate(all="ignore"):
                declared = bool(sra.factors_valid(at, p, xp=np))
                f = np.asarray(sra.route_factors(at, p, xp=np, volume=volume))
            current = bool(np.all(np.isfinite(f) & (f >= 0) & (f <= 1)))
            assert declared == current, (scale, amount)
    spec = parse_spec(routed())
    routed_state, routed_p = get_model(spec.model).initial_values(spec)
    row, cell = (np.asarray(getattr(routed_p, k)) for k in ("coupling_route_row",
                                                           "coupling_route_cell"))  # fmt: skip
    c0 = (
        np.asarray(routed_p.amount_reference)[row, cell]
        + np.asarray(routed_state.amount_increment)[row, cell]
    ) / np.asarray(routed_p.volume)[cell]
    tight = routed_p._replace(coupling_route_low=0.9 * c0)
    used = np.ones(row.shape[0], dtype=bool)
    at_v0 = bool(sra.range_valid(routed_state, tight, used, xp=np))
    at_v = bool(sra.range_valid(routed_state, tight, used, xp=np, volume=1.3 * routed_p.volume))
    assert at_v0 != at_v  # A volume-dependent check would change the outcome.


def _door(raw, scale=1.3):
    """(spec, model, the coupling, state at V = scale V0, control, p) of a bound world."""
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))
    coupling = next(o for o in model.operators if o.LAW_ID in (LAW, LAW_V2))
    return spec, model, coupling, _swollen(state, p, scale), control, p


def test_version_1_1_the_composite_passes_the_current_volume_to_every_read_site(monkeypatch):
    """§11.8 row 4, NumPy through the composite (no compile), about 5 s. In the water door's world
    (sif.water_door) at V = 1.3 V0, set by hand, each of these equals its closed form at n/V: the
    control view's channel availability; factor_valid at a range that n/V leaves and n/V0 keeps;
    the inner routes' record; the routed rates of turnover and of the network, with their validity
    at such a range (no observation column holds a routed turnover or gene-unit rate, so this row
    is their exact check), and the gene unit's in A1's world; the self-moved route's factor at the
    midpoint's predictor; one state half-step; the observed coupling_factor. In A7's water world
    (@1, a junction) with its two cells' volumes set apart, the junction's factor for each side.
    Without a changer (A5''), the coupling receives no view of the volume, and beside membrane
    state (a population world) the view carries channel_abundance alone. Planted, each missing
    its identity: the view withheld at the control view, at the routed half-step and at the
    split; and today's declaration-based R2, which A5'''s composition would answer with a view."""
    spec, model, coupling, state, control, p = _door(sif.water_door())
    v = np.asarray(p.volume) + np.asarray(state.volume_increment_pL)
    want = _closed_factors(state, p, v)  # inst, gate, make, bind, self.
    # The control view: the population's availability is its schedule times inst and gate.
    effective = model.control_view(control, state, p, xp=np)
    assert np.isclose(effective.channel[0], control.channel[0] * want[0] * want[1], rtol=1e-13)
    # The inner routes' record, and factor_valid at a range V leaves and V0 keeps.
    _, recorded = model._control_factor_checks(state, p, xp=np)
    assert np.allclose(np.asarray(recorded.coupling_applied_factor)[:2], want[:2], rtol=1e-13)
    row, cell = int(p.coupling_route_row[0]), int(p.coupling_route_cell[0])
    n_r = float(np.asarray(p.amount_reference)[row, cell] + state.amount_increment[row, cell])
    low = np.asarray(p.coupling_route_low).copy()
    low[[0, 2]] = 0.9 * n_r / float(p.volume[cell])  # inst's and make's: V0 keeps, V leaves.
    tight = p._replace(coupling_route_low=low)
    checked, _ = model._control_factor_checks(state, tight, xp=np)
    assert not bool(checked)
    ops = {o.LAW_ID: o for o in model.operators}
    turnover, network = ops[sfx.TURNOVER], ops["cells.operator.local_species_reactions@1"]
    routed_control, valid, _ = model._routed_control(
        turnover, model.rate_routes[turnover], state, control, p, xp=np
    )
    rates = np.asarray(routed_control.turnover_rate)
    assert np.isclose(rates[0], control.turnover_rate[0] * want[2] * want[4], rtol=1e-13)
    assert rates[1] == control.turnover_rate[1]  # clear_s: no route.
    _, refused, _ = model._routed_control(
        turnover, model.rate_routes[turnover], state, control, tight, xp=np
    )
    assert bool(valid) and not bool(refused)
    multiplied, _, _ = model._routed_control(
        network, model.rate_routes[network], state, control, p, xp=np
    )
    assert np.isclose(
        multiplied.reaction_multiplier[0], control.reaction_multiplier[0] * want[3], rtol=1e-13
    )
    # The self-moved route at the midpoint: S after turnover's predictor over h / 4 of the step
    # (half of a half-step), from the routed rate at the half-step's start.
    h = 0.5 * spec.execution.dt
    assert sfx.TURNOVER in model.midpoint
    moved, _ = model._half_step(turnover, state, h, control, p, xp=np)
    s_row = list(spec.model.species_ids).index(sif.fx.SPECIES)
    n_s = float(p.amount_reference[s_row, 0] + state.amount_increment[s_row, 0])
    make, clear = float(rates[0]), float(control.turnover_rate[1])
    n_mid = n_s * np.exp(-clear * h / 2) - make * np.expm1(-clear * h / 2) / clear
    b = float(p.coupling_route_basal[4])
    k, n = float(p.coupling_route_half_saturation_mM[4]), float(p.coupling_route_coefficient[4])
    self_mid = b + (1 - b) * _hill(n_mid / v[0], k, n, 2)
    assert np.isclose(np.asarray(moved.coupling_applied_factor)[4], self_mid, rtol=1e-12)
    # One state half-step: s' = s + (k_on u (1 - s) - k_off s) h phi(lambda h), u at n_R / V.
    stepped, _ = model._half_step(coupling, state, h, control, p, xp=np)
    s0 = float(state.regulatory_state[0])
    u = float(_hill(n_r / v[0], p.regulatory_input_half_saturation_mM[0, 0],
                    p.regulatory_input_coefficient[0, 0], 1))  # fmt: skip
    k_on, k_off = float(p.regulatory_on_rate[0]), float(p.regulatory_off_rate[0])
    lam = k_on * u + k_off
    s1 = s0 + (k_on * u * (1 - s0) - k_off * s0) * h * (-np.expm1(-lam * h) / (lam * h))
    assert np.isclose(float(stepped.regulatory_state[0]), s1, rtol=1e-13)
    # The observed factors, at the row's view.
    observed = coupling.observe(None, state, control, p, model.view(p, state, xp=np), model, spec)
    assert np.allclose(observed["coupling_factor"], want, rtol=1e-13)
    # The planted withheld views, each of which misses.
    monkeypatch.setattr(model, "_factor_views", lambda p, *, xp: {})
    plain = model.control_view(control, state, p, xp=np)
    assert not np.isclose(plain.channel[0], effective.channel[0], rtol=1e-6)
    monkeypatch.undo()
    monkeypatch.setattr(model, "_routed_view", lambda source, p, *, xp: {})
    lagged, _, _ = model._routed_control(
        turnover, model.rate_routes[turnover], state, control, p, xp=np
    )
    assert not np.isclose(lagged.turnover_rate[0], rates[0], rtol=1e-6)
    monkeypatch.undo()
    monkeypatch.setattr(model, "_passes_view", lambda op: False)
    stale, _ = model._half_step(coupling, state, h, control, p, xp=np)
    assert not np.isclose(float(stale.regulatory_state[0]), s1, rtol=1e-9)
    monkeypatch.undo()
    # The gene unit's routed initiation in A1's world.
    spec, model, coupling, state, control, p = _door(sif.swelling_a1(coupling=True, end=60.0))
    v = np.asarray(p.volume) + np.asarray(state.volume_increment_pL)
    want = _closed_factors(state, p, v)
    unit = next(o for o in model.operators if o.LAW_ID == sif.gw.POLYMERISATION)
    initiated, _, _ = model._routed_control(unit, model.rate_routes[unit], state, control, p, xp=np)
    field = "polymerisation_initiation_rate"
    declaration = next(d for o, d, _ in cs.entries(spec) if o is unit)
    tx = [e for e, _ in unit.routable_elements(declaration, field)].index("tx")
    ratio = np.asarray(getattr(initiated, field))[tx] / np.asarray(getattr(control, field))[tx]
    assert np.isclose(ratio, want[0], rtol=1e-13)
    # A7's water world (@1): the junction's factor for each side, its two cells set apart.
    for side in ("first", "second", "both"):
        raw = _watered()
        block(raw)["couplings"][0]["target"]["side"] = side
        spec, model, coupling, state, control, p = _door(raw, scale=1.0)
        junction = next(j for j in spec.model.junctions if j.id == "junction_0")
        ids = [c.id for c in spec.model.cells]
        first, second = ids.index(junction.sender), ids.index(junction.receiver)
        increment = np.zeros_like(np.asarray(p.volume))
        increment[first], increment[second] = 0.3 * p.volume[first], -0.2 * p.volume[second]
        state = state._replace(volume_increment_pL=increment)
        v = np.asarray(p.volume) + increment
        route = p.coupling_route_cell  # One route per cell the side names.
        factors = _closed_factors(state, p, v)
        expected = float(np.prod(factors))
        assert [int(c) for c in route] == {"first": [first], "second": [second],
                                           "both": [first, second]}[side]  # fmt: skip
        got = model.control_view(control, state, p, xp=np).junction[0] / control.junction[0]
        assert np.isclose(got, expected, rtol=1e-13), side
        assert not np.isclose(got, float(np.prod(_closed_factors(state, p, p.volume))), rtol=1e-6)
    # No view without a changer, and per field beside membrane state.
    from tests.unit import test_regulated_availability_population as population

    for raw, fields in ((_a5pp_swelling_free(), {}),
                        (population.world(), {LAW_V2: ("channel_abundance",)})):  # fmt: skip
        model = get_model(parse_spec(raw).model)
        assert {o.LAW_ID: f for o, f in model.factor_fields.items()} == fields
        assert not [o for o in model.view_readers if o.LAW_ID in (LAW, LAW_V2)]
    declared = {o.LAW_ID: factor_reads(o) for o in model.factors if factor_reads(o)}
    assert declared != {o.LAW_ID: f for o, f in model.factor_fields.items()}  # The plant.


def _a5pp_swelling_free():
    """A5''s registered world as judged: no water, so no changer of the volume."""
    from validation.tissue import a5pp_acceptance_fixtures as a5pp

    return a5pp.registered_world()


def test_a_site_source_stays_refused_beside_water(monkeypatch):
    """The lead's ruling 2 (D402): a site source in mM reads B / V at the declared volume (D244's
    Q2, the user's answer), so beside water it stays refused: today by site occupancy's own fixed
    volume read, and by name in the coupling (check_site_volume) should that read change. Planted:
    site occupancy's volume reads lifted in process, the coupling's own refusal answers. Host only,
    about 1 s."""
    base = site_routed(source=("occupied_mM", "hill_activation"), half=(1e-3, 1.0), ranged=(0, 1e3))
    species = tuple(entry["id"] for entry in base["model"]["species"])
    raw = sif.with_water_first(base, keep=species)  # Its ligand undiluted, above its trace.
    with pytest.raises(ConfigError, match=re.escape(sra.SITE_LAW) + " reads volume as declared"):
        parse_spec(copy.deepcopy(raw))
    site = type(OPERATORS[sra.SITE_LAW])
    monkeypatch.setattr(
        site,
        "CONFLICTS_VIEW",
        tuple(k for k in site.CONFLICTS_VIEW if k not in ("volume", "extracellular_volume")),
    )
    kept = {k: v for k, v in site.SCOPED_READS.items() if k != "extracellular_volume"}
    monkeypatch.setattr(site, "SCOPED_READS", kept)
    pump_composite._implementation.cache_clear()
    try:
        words = r"reads a site population's occupied_mM at the declared volume"
        with pytest.raises(ConfigError, match=words):
            parse_spec(copy.deepcopy(raw))
    finally:
        monkeypatch.undo()
        pump_composite._implementation.cache_clear()
