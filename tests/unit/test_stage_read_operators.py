"""Operators beside a stage read that stores totals, refused at the definition
(registry/species_registry.py, check_stage_read_rows): the second review's finding 3, verified, and
the lead's ruling, option (a), of 18 November 2026.

At a version-1 buffered node the proton row stores H_eq (free plus bound), and an operator reads
the stored row. So, beside a declared buffer read:
- an operator that names the buffered proton row (here a regulated availability's state input
  of H) would read H_eq/V as free h: refused;
- the water law's osmolyte sum counts the stored rows, so the bound protons count twice: refused;
- the lumen's fill sums the lumen's stored rows the same way, and the closure reads that outside
  node at its declared volume: refused where the read holds rows at an outside node.
The plants are the verifier's worlds (its three-cell and water cases), each with the same world
unbuffered as its admitted control, and for the lumen a buffered cleft (refused today first by the
insertion beside a declared kind) with the registry's rule tested directly. A read that rewrites
no row (the planted exchange kind's identity read) stores no totals, so water beside it is
admitted (the composite kinds' own world). Parse only, with nothing run.
"""

import copy
import math
from types import SimpleNamespace

import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.operators import restricted_lumen as lumen
from cells.registry import species_registry as registry
from tests import membrane_insertion_fixtures as fx
from validation.compartment_ph_engine import definitions as fr
from validation.tissue import pump_water_fixtures as water
from validation.tissue import regulated_availability_fixtures as rf
from validation.tissue import species_reactions_fixtures as rfx
from validation.tissue import surface_pump_v3_fixtures as fixtures

LN10 = math.log(10.0)
C0_MM, PK, PH, BATH_PH = 1000.0, 7.2, 7.2, 7.4


def h_mM(ph):
    return C0_MM * 10.0 ** (-ph)


def with_buffer_rows(raw, buffered_mM, *, extra_outside=None):
    """raw's @3 block with a proton row H and a two-form buffer row B (pK 7.2 at c0 = 1000 mM): at
    each node named in buffered_mM, B at that total and H at its proton equivalents at pH 7.2
    (their charge in the node's anchor); elsewhere H at the bath's pH with B at the same
    concentration, so the added pair is electroneutral there (a lumen's source must be). Every
    patch and face carries neither row."""
    m = raw["model"]
    m["species"] += [
        dict(id="H", valence=1, standard_mu_RT=0.0),
        dict(id="B", valence=-1, standard_mu_RT=0.0, protonated_standard_mu_RT=-PK * LN10),
    ]
    m["standard_concentration_mM"] = C0_MM
    h0, k = h_mM(PH), h_mM(PK)
    for node in (*m["cells"], *m["extracellular"]):
        b = buffered_mM.get(node["id"])
        h_row = h0 + b * h0 / (h0 + k) if b else h_mM(BATH_PH)
        b_row = b if b else h_row
        volume = node["volume_pL"]
        node["initial_amount_fmol"] |= dict(H=h_row * volume, B=b_row * volume)
        node["fixed_charge_equivalent_fmol"] -= h_row * volume - b_row * volume
    for patch in m["membranes"]:
        patch["permeability_m_per_s"] |= dict(H=0.0, B=0.0)
    for face in m.get("faces", ()):
        face["diffusivity_m2_per_s"] |= dict(H=0.0, B=0.0)
    raw["execution"]["material_balance_atol_fmol"] |= dict(H=1e-10, B=1e-10)
    return raw


def declare_buffer(raw, nodes):
    raw["model"]["stage_reads"] = [
        dict(read_id="cells.kind.rapid_proton_buffer@1", proton_row="H", buffers={n: ["B"] for n in nodes},
             k_on_per_mM_s={"B": 1e7})
    ]  # fmt: skip
    return raw


def quiet(raw):
    for group in ("membrane_controls", "channel_controls", "pump_controls"):
        for entry in raw["experiment"][group]:
            entry["schedule"] = [dict(time=0.0, availability=0.0)]
    return raw


def three_cells(*, buffered):
    """The verifier's three-cell plant: heredity cells D with 50, 10 and 0 mM of B at free pH 7.2
    (the first two declared under the buffer read when `buffered`), and a regulated availability
    with two Hill-activation inputs of H in every cell."""
    kind = fixtures.HEREDITY_STATES["D"][:4]
    raw = copy.deepcopy(fixtures.heredity_cells([kind] * 3, dt=1e-3, end_time=0.01))
    cells = [c["id"] for c in raw["model"]["cells"]]
    raw = quiet(with_buffer_rows(raw, {cells[0]: 50.0, cells[1]: 10.0}))
    if buffered:
        declare_buffer(raw, cells[:2])
    raw = cs.frozen_definition(raw)
    states = [
        rf.state("s_free", "all", [("hill_activation", "H", h_mM(PH), 1.0)], on=10.0, off=10.0),
        rf.state("s_hi", "all", [("hill_activation", "H", 20.0, 1.0)], on=10.0, off=10.0),
    ]
    return rf.with_coupling(raw, species=["H"], states=states)


def reactions_with_proton_counter_ion(*, buffered):
    """FR-15 S1: the three-cell plant's world with cells.operator.local_species_reactions@1 making a trace anion X
    with H as its counter-ion (0 -> X + H in cell_0), H flagged counter_ion: beside the buffer read,
    the network names the stored proton row, so check_stage_read_rows refuses it (no new code)."""
    kind = fixtures.HEREDITY_STATES["D"][:4]
    raw = copy.deepcopy(fixtures.heredity_cells([kind] * 3, dt=1e-3, end_time=0.01))
    cells = [c["id"] for c in raw["model"]["cells"]]
    raw = quiet(with_buffer_rows(raw, {cells[0]: 50.0, cells[1]: 10.0}))
    if buffered:
        declare_buffer(raw, cells[:2])
    raw = rfx.with_charged_trace(cs.frozen_definition(raw), "X", -1)
    listed = [rfx.species("X"), dict(rfx.species("H"), counter_ion=True)]
    make = rfx.mass_action("make", {"cells": [cells[0]]}, {}, {"X": 1, "H": 1}, 1e-6)
    # c0 the world's 1000 mM, so H's mu°/RT agrees with the species registry's (one authority).
    return rfx.with_reactions(raw, listed, [make], [("make", None, [(0.0, 1.0)])], c0=C0_MM)


def two_cells_with_water(*, buffered):
    """The verifier's water plant: two heredity cells D with 50 mM of B at free pH 7.2 (the first
    declared under the buffer read when `buffered`), osmotic water on."""
    kind = fixtures.HEREDITY_STATES["D"][:4]
    raw = copy.deepcopy(fixtures.heredity_cells([kind] * 2, dt=1e-3, end_time=0.01))
    cells = [c["id"] for c in raw["model"]["cells"]]
    raw = quiet(with_buffer_rows(raw, {cells[0]: 50.0, cells[1]: 50.0}))
    if buffered:
        declare_buffer(raw, cells[:1])
    return cs.frozen_definition(water.with_water(raw))


def buffered_cleft(*, buffered):
    """The membrane-insertion cleft cell with cells.operator.restricted_cleft_lumen@1 filling its cleft from the
    bath, the cleft (a finite outside node) holding 50 mM of B, declared under the buffer read when
    `buffered`."""
    base = with_buffer_rows(fx.cleft_cell(), {"cleft": 50.0})
    if buffered:
        declare_buffer(base, ["cleft"])
    raw = fx.with_operators(base, fx.furrow_insertion(rate=1e-11, onset=0.002))
    raw["model"]["operators"].append(
        dict(law=lumen.LAW_ID, lumens=[dict(node_id="cleft", source_id="bath_0", gap_width_m=2e-6)])
    )
    return raw


@pytest.mark.parametrize(
    "world, message",
    [
        (three_cells, r"species H is held by the stage read of cells.kind.rapid_proton_buffer@1 at "
                      r"cell_0: cells.operator.species_regulated_availability@1 names or moves it"),
        (two_cells_with_water, r"cells.operator.ideal_osmosis_linear_compliance_water@1 sums every stored row as "
                               "free particles"),
        (reactions_with_proton_counter_ion,
         r"species H is held by the stage read of cells.kind.rapid_proton_buffer@1 at cell_0: "
         r"cells.operator.local_species_reactions@1 names or moves it"),  # FR-15 S1: B4's proton as counter-ion.
    ],
    ids=["regulated_availability", "water", "proton_counter_ion"],
)  # fmt: skip
def test_an_operator_beside_a_stored_total_is_refused_and_the_unbuffered_control_admitted(
    world, message
):
    """Composite worlds with operators beside version 1's read, whose stage rows carry the read's
    law as a third item (P1's selector): the check reads each row's (species, node), so it
    refuses with the row's species and node. Unpacking a whole three-item row would raise a
    ValueError here instead."""
    parse_spec(world(buffered=False))  # The control: the same world with no buffer read.
    with pytest.raises(ConfigError, match=message):
        parse_spec(world(buffered=True))


def test_water_beside_a_read_that_rewrites_no_row_is_admitted():
    """The planted exchange kind's stage read is the identity, and its stage_rows name no row, so
    it stores no totals and water beside it counts nothing twice: admitted. This is the composite
    kinds' world (tests/unit/test_pump_composite_kinds.py), which 3de621a4's rule refused. Water
    beside the buffer read, which rewrites rows, stays refused."""
    from cells.registry import kind_registry
    from tests import kind_fixtures as kf
    from tests.unit.test_pump_composite_kinds import RATE, world

    assert kf.EXCHANGE.stage_read is not None and kf.EXCHANGE.stage_rows(None) == ()
    with kind_registry.scope(kf.registry()):
        parse_spec(cs.frozen_definition(water.with_water(kf.declare(world(), rate=RATE))))
    with pytest.raises(ConfigError, match="sums every stored row as free particles"):
        parse_spec(two_cells_with_water(buffered=True))  # Beside the closure: still refused.


def test_the_lumen_fill_beside_a_buffered_outside_node_is_refused(monkeypatch):
    """The lumen's fill needs the membrane insertion, which today is refused beside any declared
    kind until kinds declare partition roles, so the buffered cleft is refused first by the
    insertion (shown, with the unbuffered cleft admitted). The registry's own rule stands behind
    it, tested directly: a lumen fill beside FR-4's buffer read, which holds rows at its lumen (an
    outside node), is refused; beside the read at the cell alone it is admitted (the control)."""
    parse_spec(buffered_cleft(buffered=False))
    with pytest.raises(
        ConfigError,
        match=r"cells.operator.scheduled_membrane_insertion@1 .* beside declared kinds|cells.operator.restricted_cleft_lumen@1's",
    ):
        parse_spec(buffered_cleft(buffered=True))

    def v1(cell_only):
        raw = fr.development_world(fr.fr4_world())
        if cell_only:
            read = raw["model"]["stage_reads"][0]
            read["buffers"] = {fr.CELL: ["B_c"]}
            read["k_on_per_mM_s"] = {"B_c": read["k_on_per_mM_s"]["B_c"]}
        return parse_spec(raw).model

    cell_only, both = v1(cell_only=True), v1(cell_only=False)  # Parsed before any patch.
    fill = SimpleNamespace(LAW_ID=lumen.LAW_ID, PROCESS=False, species_identities=lambda _: ())
    spec = SimpleNamespace(model=SimpleNamespace(operators=()))
    monkeypatch.setattr(registry, "_entries", lambda _: ((fill, None),))
    monkeypatch.setattr(registry, "_inner_model", lambda _: cell_only)
    registry.check_stage_read_rows(spec)
    monkeypatch.setattr(registry, "_inner_model", lambda _: both)
    with pytest.raises(
        ConfigError, match=rf"cells.operator.restricted_cleft_lumen@1's fill .* outside node {fr.LUMEN}"
    ):
        registry.check_stage_read_rows(spec)


def injected_fr4(carrier):
    """FR-4's development world as a composite, with an electrode at its buffered cell carrying
    its current by `carrier` (the binding owner's planted injection, runs/injection-01: carried by
    H+, the energy ledger refuses the run; carried by K+, it closes)."""
    raw = cs.frozen_definition(fr.development_world(fr.fr4_world()))
    raw["model"].setdefault("operators", []).append(
        dict(law="cells.operator.electrode_current_injection@1",
             electrodes=[dict(cell_id=fr.CELL, carriers={carrier: 1.0})])
    )  # fmt: skip
    raw["experiment"]["injection_controls"] = [
        dict(cell_id=fr.CELL, schedule=[dict(time=0.0, current_A=2e-12)])
    ]
    return raw


def test_an_injection_carried_by_a_held_species_is_refused_at_definition():
    """The current injection names its carriers (NamedRow, no identity claim), so an injection
    carried by H+ into a buffered cell is refused at the definition, as every mover of a held row
    is, where the run would refuse at its energy ledger. The K+-carried control is admitted."""
    parse_spec(injected_fr4("K"))
    with pytest.raises(
        ConfigError,
        match=r"species H is held by the stage read of cells.kind.rapid_proton_buffer@1 at cell_0: "
        "cells.operator.electrode_current_injection@1 names or moves it",
    ):
        parse_spec(injected_fr4("H"))


def injection_worlds():
    """Existing worlds with the injection: its own test world (K and M carriers, a heredity cell),
    the same composed with a regulated availability reading K, and FR-4's K-carried composite."""
    from tests.unit.test_current_injection_runs import definition

    alone = definition([(0, 1e-12)])
    coupled = copy.deepcopy(alone)
    cell = coupled["model"]["cells"][0]["id"]
    coupled = rf.with_coupling(
        coupled, species=["K"],
        states=[rf.state("s", [cell], [("hill_activation", "K", 140.0, 4.0)], on=20.0, off=5.0,
                         initial=0.5)],
    )  # fmt: skip
    return [parse_spec(alone), parse_spec(coupled), parse_spec(injected_fr4("K"))]


def test_the_injections_named_carriers_change_no_identity_and_meet_the_two_form_check(
    monkeypatch,
):
    """The three effects of the injection's named carriers, on existing worlds:
    - every species' resolved identity, and its source, is the same as with no names at all: a
      NamedRow sets none, and check_identities compares none;
    - check_two_form_rows passes: the carriers are ions;
    - planted: a carrier that is a two-form row is refused by check_two_form_rows, naming the
      injection, so the check does see the carriers."""
    from cells.operators import current_injection

    for spec in injection_worlds():
        named = registry.identities(spec)
        monkeypatch.setattr(
            current_injection.ElectrodeCurrentInjection, "species_identities", lambda s, d: ()
        )
        assert registry.identities(spec) == named
        monkeypatch.undo()
        registry.check_two_form_rows(spec)
        ops = [op for op, d in registry._entries(spec) if op.LAW_ID == current_injection.LAW_ID]
        assert ops and all(
            isinstance(item, registry.NamedRow)
            for op, d in registry._entries(spec)
            if op.LAW_ID == current_injection.LAW_ID
            for item in registry.operator_identities(op, d)
        )
    with pytest.raises(
        ConfigError, match=r"species B_c has two forms .*: cells.operator.electrode_current_injection@1 names it"
    ):
        parse_spec(injected_fr4("B_c"))
