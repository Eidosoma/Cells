"""Tier-1 smoke of local_species_reactions@1 at milestone 1, the contract fit (D152 version 1).

docs/SHARED_INVENTORY_REACTIONS_DESIGN.md §1.4, §2.1-§2.5, §3.3, §4.5, §4.6 and §10.4 (C1). Host
side, no compile, on the canonical enzyme network (validation/tissue/species_reactions_fixtures):
* the registration and the contract's declarations; the field map (one owner per row: @3 owns both
  amount fields and the operator writes them, booked in its own accumulators); the energy roles
  (heat and work fields in the flows and the dissipation check; the standard-potential term and the
  magnitudes in neither);
* the definition round trip; every law parameter bound per world as a layout array and every
  multiplier a control (per-site overrides), with identities and parameters outside the batch
  signature and the static network in it;
* idleness: no routes, statically idle; every multiplier zero, the start state selected bitwise (a
  planted -0.0 kept); milestone 1 refuses a step with a positive multiplier;
* the ledger terms against @3's own balances: a hand-built consistent booking (c0 != 1, mu° != 0, a
  mixed cell and a driven outside node) closes the material ledgers exactly and the energy ledger at
  rounding, and three misbookings (the heat's sign, a dropped standard term, one accumulator) fail
  the ledger each touches; the operator's domain refuses its own misbookings;
* the stationary analysis' refusal, and the energy-guard statement in the docstring.
"""

import copy
import re
from decimal import Decimal, getcontext
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.models.operators import OPERATORS, species_reactions
from cells.models.operators.contract import check_declarations
from cells.models.registry import get_model
from validation.tissue import species_reactions_fixtures as rfx

getcontext().prec = 50
R_SI = Decimal("6.02214076e23") * Decimal("1.380649e-23")  # N_A k_B, exact (SI 2019).
RT_PJ = Decimal("1e-3") * R_SI * Decimal("310")  # pJ/fmol at the fixtures' 310 K.
LAW = species_reactions.LAW_ID
OWN = tuple(species_reactions.STATE_AXES)


@pytest.fixture(scope="module")
def bound():
    spec = parse_spec(rfx.enzyme_network(c0=0.5))
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return spec, model, model.operators[0], state, p


def row(spec, name):
    return list(spec.model.species_ids).index(name)


# ------------------------------------------------------------------ the contract


def test_the_operator_is_registered_with_its_declarations():
    op = OPERATORS[LAW]
    assert type(op) is species_reactions.LocalSpeciesReactions
    check_declarations(type(op))
    assert op.SPLIT and op.RK4 == "split" and not op.EVENT and not op.PROCESS
    assert op.HEAT_FIELDS == (
        "reaction_dissipated_energy_pJ",
        "reaction_outside_dissipated_energy_pJ",
    )
    assert op.WORK_FIELDS == ("reaction_work_pJ", "reaction_outside_work_pJ")
    assert op.CONFLICTS_VIEW == (
        "volume",
        "extracellular_volume",
        "active",
        "outside_active",
        "extracellular_amount_reference",
    )
    assert dict(op.ENTITY_WRITES) == {
        "amount_increment": ("reaction_produced_fmol", "reaction_consumed_fmol"),
        "extracellular_amount_increment": (
            "reaction_outside_produced_fmol",
            "reaction_outside_consumed_fmol",
        ),
    }
    for name in ("VIEW_FIELDS", "CONTROL_FACTORS", "REPLACES", "ACCEPTS_WRITES", "EVENT_REPLACES"):
        assert not getattr(op, name), name
    assert op.CONTROL_FIELDS == ("reaction_multiplier",)
    assert op.EXPERIMENT_KEYS == ("reaction_controls",)


def test_the_field_map_gives_one_owner_per_row(bound):
    spec, model, _, _, _ = bound
    fields = model.field_owners(spec)
    for name in ("amount_increment", "extracellular_amount_increment"):
        assert fields["state"][name] == {"owner": "inner", "writers": [LAW]}
    for name in OWN:
        assert fields["state"][name] == {"owner": LAW, "writers": []}
    for name in species_reactions.LAYOUT_FIELDS:
        assert fields["layout"][name] == LAW
    assert fields["control"]["reaction_multiplier"] == LAW
    assert fields["views"] == {}
    assert {k: v for k, v in fields["observations"].items() if v == [LAW]} == {
        k: [LAW] for k in OWN
    }


def test_heat_and_work_are_flows_and_the_standard_term_is_not(bound):
    _, model, op, _, _ = bound
    flows = set(model.ENERGY_FLOW_FIELDS)
    assert set(op.HEAT_FIELDS) | set(op.WORK_FIELDS) <= flows
    assert set(op.HEAT_FIELDS) <= set(model.DISSIPATION_FIELDS)
    for name in (
        "reaction_standard_energy_pJ",
        "reaction_outside_standard_energy_pJ",
        "reaction_energy_magnitude_pJ",
        "reaction_outside_energy_magnitude_pJ",
        "reaction_extent_fmol",
    ):
        assert name not in flows and name not in model.DISSIPATION_FIELDS


# ------------------------------------------------------------------ definition and binding


def per_site_world():
    """The enzyme network with removal at both nodes, a reaction schedule and a site override."""
    raw = rfx.enzyme_network()
    block = raw["model"]["operators"][0]
    removal = next(r for r in block["reactions"] if r["id"] == "removal")
    removal["sites"] = {"cells": "all", "outside": ["ecs_0"]}
    raw["experiment"]["reaction_controls"] = [
        c for c in raw["experiment"]["reaction_controls"] if c["reaction_id"] != "removal"
    ] + [
        dict(
            reaction_id="removal",
            site=None,
            schedule=[dict(time=0.0, multiplier=1.0), dict(time=0.002, multiplier=0.5)],
        ),
        dict(
            reaction_id="removal",
            site="ecs_0",
            schedule=[dict(time=0.0, multiplier=0.0), dict(time=0.001, multiplier=2.0)],
        ),
    ]
    return raw


def test_the_definition_round_trips():
    for raw in (rfx.enzyme_network(c0=0.5), per_site_world()):
        spec = parse_spec(raw)
        assert parse_spec(cs.to_dict(spec)) == spec


def test_parameters_are_per_world_bindings_and_the_network_is_the_signature(bound):
    spec, model, op, _, p = bound
    names = list(spec.model.species_ids)
    assert np.asarray(p.reaction_rows).tolist() == [names.index(s) for s in "SECP"]
    assert np.asarray(p.reaction_route_law).tolist() == [0, 1, 2, 1, 1]
    assert np.asarray(p.reaction_route_outside).tolist() == [False, False, True, False, True]
    assert np.asarray(p.reaction_rate_constant).tolist() == [10.0, 1.0, 1.0, 1e-4, 0.5]
    assert np.asarray(p.reaction_saturation_mM).tolist() == [1.0, 1.0, 5e-4, 1.0, 1.0]
    assert np.asarray(p.reaction_standard_mu_RT).tolist() == [0.0, 0.0, -2.0, -1.0]
    assert float(p.reaction_standard_concentration_mM) == 0.5
    # E + S <-> C in the cell: alpha on E and S, beta on C; the catalyst E of the conversion.
    assert np.asarray(p.reaction_reactants)[:, 0].tolist() == [1.0, 1.0, 0.0, 0.0]
    assert np.asarray(p.reaction_products)[:, 0].tolist() == [0.0, 0.0, 1.0, 0.0]
    assert np.asarray(p.reaction_catalyst)[:, 2].tolist() == [0.0, 1.0, 0.0, 0.0]
    assert np.asarray(p.reaction_factor_kind).tolist() == [[0], [0], [0], [0], [2]]
    for name in ("reaction_rate_constant", "reaction_standard_mu_RT", "reaction_saturation_mM"):
        assert np.asarray(getattr(p, name)).dtype == np.float64
    # Another world's parameters (k, K_M, Hill, mu°, c0) and identities change only their bindings.
    raw = rfx.enzyme_network(c0=0.25, mu=(0.1, 0.2, -1.5, -0.5))
    block = raw["model"]["operators"][0]
    for reaction in block["reactions"]:
        for key in ("rate_constant", "forward_rate_per_s", "catalytic_rate_per_s"):
            if key in reaction:
                reaction[key] *= 1.7
        if "saturation_mM" in reaction:
            reaction["saturation_mM"] *= 3.0
        for factor in reaction["factors"]:
            factor.update(half_saturation_mM=2e-3, hill_coefficient=1.5)
    block["species"][0].update(catalogue=dict(catalogue="cells-proteins@0", entry="X"))
    block["species"][0]["evidence"] = "label_only"
    other = parse_spec(raw)
    assert get_model(other.model) is model
    assert model.batch_signature(other.model) == model.batch_signature(spec.model)
    _, q = model.initial_values(other)
    differ = {
        k
        for k in p._fields
        if np.asarray(getattr(p, k)).tobytes() != np.asarray(getattr(q, k)).tobytes()
    }
    assert differ == {
        "reaction_rate_constant",
        "reaction_saturation_mM",
        "reaction_factor_half_saturation_mM",
        "reaction_factor_coefficient",
        "reaction_standard_mu_RT",
        "reaction_standard_concentration_mM",
    }
    # A change of the network is a change of the signature.
    changed = rfx.enzyme_network()
    changed["model"]["operators"][0]["reactions"][1]["products"] = {"E": 1, "S": 1}
    assert model.batch_signature(parse_spec(changed).model) != model.batch_signature(spec.model)


def test_multipliers_are_controls_with_site_overrides():
    spec = parse_spec(per_site_world())
    model = get_model(spec.model)
    op = model.operators[0]
    routes = spec.model.operators[0].routes
    names = [(r.reaction, r.node) for r in routes]
    assert names[-2:] == [("removal", "cell_0"), ("removal", "ecs_0")]
    times = [0.0, 0.001, 0.002, 0.003]
    values = np.asarray(control_values(spec, times).reaction_multiplier)
    assert values.shape == (4, len(routes))
    assert values[:, -2].tolist() == [1.0, 1.0, 0.5, 0.5]  # The reaction's schedule.
    assert values[:, -1].tolist() == [0.0, 2.0, 2.0, 2.0]  # The site's own.
    assert np.all(values[:, :-2] == 1.0)
    assert sorted(op.schedule_times(spec.experiment.operators[0].data)) == sorted(
        [0.0] * 4 + [0.0, 0.002, 0.0, 0.001]
    )


def test_the_summary_reports_each_routes_parameters_under_their_law_names(bound):
    """The lead's ruling Q8: law-specific names and units per route; one internal rate array."""
    spec, _, op, _, _ = bound
    summary = op.summary(spec, spec.model.operators[0], None, None)
    routes = summary["reaction_routes"]
    assert [(r["reaction"], r["site"]) for r in routes] == [
        ("binding", "cell_0"),
        ("catalysis", "cell_0"),
        ("conversion", "ecs_0"),
        ("supply", "cell_0"),
        ("removal", "ecs_0"),
    ]
    by = {r["reaction"]: r for r in routes}
    assert by["binding"]["parameters"] == {"forward_rate_per_s": 10.0}
    assert by["binding"]["units"] == {"forward_rate_per_s": "1/s"}
    assert by["catalysis"]["units"] == {"rate_constant": "1/s"}  # First order.
    assert by["supply"]["units"] == {"rate_constant": "mM/s"}  # Zeroth order.
    assert by["conversion"]["parameters"] == {
        "catalytic_rate_per_s": 1.0,
        "saturation_mM": 5e-4,
        "catalyst": "E",
    }
    assert by["conversion"]["units"] == {"catalytic_rate_per_s": "1/s", "saturation_mM": "mM"}
    assert by["removal"]["factors"] == [
        dict(law="hill_inhibition", species="S", half_saturation_mM=1e-3, hill_coefficient=2.0)
    ]
    assert summary["reaction_species"]["C"] == dict(
        catalogue=None, evidence=None, moieties={"X": 1, "Y": 1}, standard_mu_RT=-2.0
    )
    assert summary["reaction_network"]["supply"]["kind"] == "source"
    assert summary["reaction_standard_concentration_mM"] == 0.5
    raw = rfx.enzyme_network()
    conversion = next(
        r for r in raw["model"]["operators"][0]["reactions"] if r["id"] == "conversion"
    )
    conversion.update(catalyst=None, max_rate_mM_per_s=2e-3)
    del conversion["catalytic_rate_per_s"]
    plain = parse_spec(raw)
    entry = get_model(plain.model).operators[0].summary(plain, plain.model.operators[0], None, None)
    (uncatalysed,) = [r for r in entry["reaction_routes"] if r["reaction"] == "conversion"]
    assert uncatalysed["parameters"] == {"max_rate_mM_per_s": 2e-3, "saturation_mM": 5e-4}
    assert uncatalysed["units"] == {"max_rate_mM_per_s": "mM/s", "saturation_mM": "mM"}


# ------------------------------------------------------------------ idleness


def control(p, values):
    return SimpleNamespace(reaction_multiplier=np.asarray(values, dtype=float))


def test_zero_multipliers_select_the_start_state_bitwise(bound):
    """Structural at milestone 1 (the half-step is the skeleton); the same test bites at
    milestone 2, where the half-step computes a new state and selects it by multiplier."""
    _, _, op, state, p = bound
    planted = state._replace(amount_increment=state.amount_increment.copy())
    planted.amount_increment[0, 0] = -0.0  # An added 0.0 would flip it.
    idle, ok = op.half_step(planted, 0.5, control(p, np.zeros(5)), p, xp=np)
    assert ok
    for a, b in zip(idle, planted, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()
    assert not op.statically_idle(p)


def test_milestone_1_refuses_an_active_step(bound):
    _, _, op, state, p = bound
    for k in range(5):
        values = np.zeros(5)
        values[k] = 1.0
        moved, ok = op.half_step(state, 0.5, control(p, values), p, xp=np)
        assert not ok
        assert all(
            np.asarray(a).tobytes() == np.asarray(b).tobytes()
            for a, b in zip(moved, state, strict=True)
        )


def test_no_routes_is_statically_idle():
    raw = rfx.enzyme_network()
    raw["model"]["operators"][0]["reactions"] = []
    raw["experiment"]["reaction_controls"] = []
    spec = parse_spec(raw)
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    assert model.operators[0].statically_idle(p)
    assert np.asarray(control_values(spec, [0.0]).reaction_multiplier).shape == (1, 0)


# ------------------------------------------------------------------ ledgers against @3's balances


def chemical(n, dn, volume):
    """The exact change of RT n (ln(n/V) - 1) from n to n + dn, pJ (50 digits)."""
    n, dn, volume = (Decimal(float(x)) for x in (n, dn, volume))

    def g(x):
        return RT_PJ * x * ((x / volume).ln() - 1)

    return g(n + dn) - g(n)


def change(spec, moves, reference, volume, index, standard):
    """(chemical, standard) dG of `moves` {species: fmol} at one node (Decimal)."""
    chem = sum(
        chemical(reference[row(spec, s), index], dn, volume[index]) for s, dn in moves.items()
    )
    return chem, sum(standard[s] * Decimal(dn) for s, dn in moves.items())


def booking(spec, state, p):
    """A consistent booking by hand. In the cell, a mixed node: C -> E + S (the passive binding
    in reverse, downhill, 1e-6 fmol) and 0 -> S (the driven supply, 2e-7 fmol), with H the
    binding's own -dG and W = dG + H. At ecs_0, a driven node: S -> P (3e-7 fmol), W = dG.
    Returns the booked state, each node's (chemical, standard) dG and the heat (Decimal)."""
    mu = dict(S=Decimal(0), E=Decimal(0), C=Decimal(-2), P=Decimal(-1))
    standard = {s: RT_PJ * (mu[s] - Decimal("0.5").ln()) for s in mu}  # mu°' at c0 = 0.5 mM.
    delta, supply, conversion = 1e-6, 2e-7, 3e-7
    moves = dict(
        cell=dict(C=-delta, E=delta, S=delta + supply), outside=dict(S=-conversion, P=conversion)
    )
    ecs = [c.id for c in spec.model.extracellular].index("ecs_0")
    s = state._replace(**{k: np.array(getattr(state, k), copy=True) for k in state._fields})
    nodes = dict(
        cell=(0, s.amount_increment, p.amount_reference, p.volume, "reaction_"),
        outside=(
            ecs,
            s.extracellular_amount_increment,
            p.extracellular_amount_reference,
            p.extracellular_volume,
            "reaction_outside_",
        ),
    )
    terms = {}
    for where, (index, increment, reference, volume, prefix) in nodes.items():
        for name, dn in moves[where].items():
            r = row(spec, name)
            increment[r, index] = dn
            getattr(s, prefix + ("produced_fmol" if dn > 0 else "consumed_fmol"))[r, index] = abs(
                dn
            )
        terms[where] = change(spec, moves[where], reference, volume, index, standard)
        getattr(s, prefix + "standard_energy_pJ")[index] = float(terms[where][1])
        getattr(s, prefix + "energy_magnitude_pJ")[index] = float(sum(abs(t) for t in terms[where]))
    binding = change(
        spec, dict(C=-delta, E=delta, S=delta), p.amount_reference, p.volume, 0, standard
    )
    heat = -sum(binding)
    assert heat > 0
    s.reaction_dissipated_energy_pJ[0] = float(heat)
    s.reaction_work_pJ[0] = float(sum(terms["cell"]) + heat)
    s.reaction_outside_work_pJ[ecs] = float(sum(terms["outside"]))
    return s, terms, heat


def test_a_consistent_booking_closes_every_ledger_against_the_balances(bound):
    spec, model, _, state, p = bound
    s, terms, heat = booking(spec, state, p)
    b = model.balances(s, p)
    for name in ("local", "outside", "total"):
        assert np.max(np.abs(b[name])) == 0.0, name
    total = sum(abs(t) for pair in terms.values() for t in pair) + 2 * abs(heat)
    assert abs(b["energy"]) <= 1e-15 * float(total)
    diagnostics = model.check_values(s, spec, steps=[1])
    assert diagnostics["max_energy_balance_error_pJ"] <= 1e-15 * float(total)


def test_misbookings_fail_the_ledger_they_touch(bound):
    spec, model, _, state, p = bound
    s, terms, heat = booking(spec, state, p)
    standard = float(terms["cell"][1])
    flipped = s._replace(reaction_dissipated_energy_pJ=-s.reaction_dissipated_energy_pJ)
    assert np.isclose(model.balances(flipped, p)["energy"], -2 * float(heat), rtol=1e-12)
    dropped = s._replace(reaction_standard_energy_pJ=np.zeros_like(s.reaction_standard_energy_pJ))
    assert np.isclose(model.balances(dropped, p)["energy"], -standard, rtol=1e-12)
    for wrong in (flipped, dropped):
        with pytest.raises(NumericalError):
            model.check_values(wrong, spec, steps=[1])
    # One accumulator misbooked far below the ions' floor (1e-10 fmol) and far above the species'
    # (1e-20 fmol) fails the species' row of the local ledger alone.
    S = row(spec, "S")
    produced = s.reaction_produced_fmol.copy()
    produced[S, 0] += 1e-16
    misbooked = s._replace(reaction_produced_fmol=produced)
    local = model.balances(misbooked, p)["local"]
    assert abs(local[S, 0]) > 1e-17 and np.max(np.abs(np.delete(local, S, axis=0))) == 0.0
    with pytest.raises(NumericalError, match="local"):
        model.check_values(misbooked, spec, steps=[1])


def test_the_domain_refuses_its_own_misbookings(bound):
    spec, model, op, state, p = bound
    assert op.domain_valid(state, p, None, xp=np)
    E, Na = row(spec, "E"), row(spec, "Na")
    cases = dict(
        negative_produced=("reaction_produced_fmol", (E, 0), -1e-18),
        negative_heat=("reaction_outside_dissipated_energy_pJ", (1,), -1e-18),
        ion_row=("reaction_consumed_fmol", (Na, 0), 1e-18),
        held_bath=("reaction_outside_work_pJ", (0,), 1e-18),  # The bath (outside slot 0).
        driven_extent=("reaction_extent_fmol", (1,), -1e-18),
        non_finite=("reaction_work_pJ", (0,), np.nan),
    )
    for name, (field, index, value) in cases.items():
        array = np.array(getattr(state, field), copy=True)
        array[index] = value
        assert not op.domain_valid(state._replace(**{field: array}), p, None, xp=np), name
    passive = np.array(state.reaction_extent_fmol, copy=True)
    passive[0] = -1e-18  # A passive route's extent is signed.
    assert op.domain_valid(state._replace(reaction_extent_fmol=passive), p, None, xp=np)


# ------------------------------------------------------------------ refusals and statements


def test_the_stationary_analysis_does_not_admit_the_composite():
    from cells.analysis import stationary

    with pytest.raises(ConfigError, match="not resolved_pump_composite@1"):
        stationary.problem(parse_spec(rfx.enzyme_network()))


def test_the_energy_guard_statement_is_in_the_docstring():
    def normalized(text):
        return re.sub(r"\s+", " ", text)

    assert "ENERGY_GUARD_STATEMENT holds for these bookings" in normalized(
        species_reactions.__doc__
    )
    statement = normalized(species_reactions.ENERGY_GUARD_STATEMENT)
    assert "face-free species-only world" in statement and "NumPy ΔG test per law" in statement


def test_padding_and_copies_do_not_change_the_contract():
    raw = rfx.enzyme_network()
    raw["execution"]["capacity"] += 1
    raw["execution"]["extracellular_capacity"] += 1
    spec = parse_spec(copy.deepcopy(raw))
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    assert state.reaction_produced_fmol.shape == (len(spec.model.species_ids), 2)
    assert state.reaction_outside_work_pJ.shape == (3,)
    op = model.operators[0]
    assert op.domain_valid(state, p, None, xp=np)
    work = np.array(state.reaction_work_pJ, copy=True)
    work[1] = 1e-18  # The padded cell slot.
    assert not op.domain_valid(state._replace(reaction_work_pJ=work), p, None, xp=np)
