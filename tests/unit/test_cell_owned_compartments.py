"""Tier-1 smoke test of cell_owned_compartments@1 and the contract's declarations (FR-1, D169).

docs/CLOSED_COMPARTMENT_DESIGN.md §1.4 to §1.6 and §4, in NumPy (no compile), on the silence world W
(validation/tissue/compartment_fixtures.loaded_compartment):
* the contract (§1.6, option (b), the lead's rulings): a DECLARATION_ONLY operator may define only
  contract.DECLARATION_MAY_DEFINE, fail closed: every other public attribute of Operator, data or
  method (parts, fields, step methods, schedule and definition-check hooks), is refused with its
  name, even restated at its default. The part-less operator with nothing at all (the contract
  test's `Nothing`) stays refused. A part-less owner whose every owned field is an accepted write is
  admitted, and one with an owned field nothing writes is refused. Every registered operator is
  admitted, as before;
* the declaration parses and round-trips, its refusals 1 to 7 fire with their reasons, and the
  summary carries the identity block. A label or reference changes no binding;
* the composite's structure check refuses the providers and closers of what the declaration reads
  as declared, in either order, and admits the operators of its list; the list fails closed.
"""

import copy
from types import SimpleNamespace

import pytest

from cells.core import pump_composite_spec as cs
from cells.core.specs import ConfigError, parse_spec
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.models.operators import OPERATORS
from cells.models.operators import compartments as comp
from cells.models.operators.contract import (
    DECLARATION_MAY_DEFINE,
    Operator,
    check_declarations,
    declaration_errors,
)
from cells.models.registry import get_model
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from validation.tissue import compartment_fixtures as cfx
from validation.tissue import secreted_species_fixtures as fx

LAW = cfx.LAW
END = 0.004


def w(**kwargs):
    return cfx.loaded_compartment(end=END, **kwargs)


def declared(raw, compartments):
    out = copy.deepcopy(raw)
    out["model"]["operators"][-1]["compartments"] = compartments
    return out


def node(raw, name):
    return next(c for c in raw["model"]["extracellular"] if c["id"] == name)


def patch(raw, name):
    return next(p for p in raw["model"]["membranes"] if p["id"] == name)


def two_cells(*, contacts, faces=(), junctions=()):
    """Two cells on the bath; cell_0's compartment ecs_0, a finite node ecs_1 beside cell_1."""
    raw = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0), ("ecs_1", 1.0)),
        contacts=contacts,
        faces=faces,
        junctions=junctions,
        end=0.01,
        concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=1e-6, ecs_1=5e-4),
    )
    return raw


# ------------------------------------------------------------------ the contract


class Minimal(Operator):
    LAW_ID = "minimal_declaration@1"
    DECLARATION_ONLY = True


def test_the_declaration_is_admitted_and_contributes_nothing():
    op = OPERATORS[LAW]
    assert type(op).DECLARATION_ONLY and declaration_errors(type(op)) == []
    assert check_declarations(type(op)) is type(op)
    assert check_declarations(Minimal) is Minimal
    for other in OPERATORS.values():  # Every registered operator, as before.
        assert check_declarations(type(other)) is type(other)


def test_the_operator_with_nothing_at_all_stays_refused():
    class Nothing(Operator):
        LAW_ID = "nothing@1"

    with pytest.raises(ValueError, match="contributes at least one part"):
        check_declarations(Nothing)


CONTRACT = sorted(n for n in dir(Operator) if not n.startswith("_"))
FORBIDDEN = [n for n in CONTRACT if n not in DECLARATION_MAY_DEFINE]


def test_the_check_covers_every_hook_the_lead_named():
    for name in ("inner_check_spec", "check_steps", "control_values", "schedule_times"):
        assert name in FORBIDDEN
    assert set(DECLARATION_MAY_DEFINE) <= set(CONTRACT)


@pytest.mark.parametrize("name", FORBIDDEN)
def test_a_declaration_that_defines_anything_else_of_the_contract_is_refused(name):
    """Fail closed: data or method, even at its default value, anything below Operator outside
    DECLARATION_MAY_DEFINE is refused, with its name."""
    value = (lambda self, *a, **k: None) if callable(getattr(Operator, name)) else ("x",)
    marked = type("Marked", (Minimal,), {name: value})
    with pytest.raises(ValueError, match=rf"a declaration contributes nothing.* {name}\b"):
        check_declarations(marked)
    same = type("Same", (Minimal,), {name: getattr(Operator, name)})
    if not callable(getattr(Operator, name)):  # Restating a default is still a definition.
        with pytest.raises(ValueError, match=rf" {name}\b"):
            check_declarations(same)


def test_a_declaration_may_define_what_a_declaration_needs():
    allowed = {
        "CONFLICTS_VIEW": ("volume",),
        "REQUIRES": (),
        "parse": lambda self, raw, base, inner: None,
        "to_dict": lambda self, declaration, base: {},
        "check_definition": lambda self, spec, declaration, schedule, model: None,
        "initial_values": lambda self, *a: ({}, {}),
        "summary": lambda self, *a: {},
    }
    declared = type("Declared", (Minimal,), allowed)
    assert check_declarations(declared) is declared


def test_a_part_less_owner_of_accepted_writes_only_is_admitted():
    class Owner(Operator):
        LAW_ID = "accepted_owner@1"
        STATE_AXES = {"held_fmol": ["cell_slot"]}
        LEDGERS = ("held",)
        LEDGER_DIAGNOSTICS = ("held_error_fmol",)
        ACCEPTS_WRITES = {"held_fmol": ("held",)}

    class Stranded(Owner):
        LAW_ID = "stranded_owner@1"
        STATE_AXES = {"held_fmol": ["cell_slot"], "stuck_fmol": ["cell_slot"]}

    assert check_declarations(Owner) is Owner
    with pytest.raises(ValueError, match="contributes at least one part"):
        check_declarations(Stranded)


# ------------------------------------------------------------------ the declaration


def test_the_declaration_parses_round_trips_and_names_its_compartments():
    spec = parse_spec(w())
    assert [d.law for d in spec.model.operators] == ["scheduled_species_exchange@1", LAW]
    declaration = spec.model.operators[-1]
    assert declaration.compartments == (
        comp.Compartment(
            "lys_0", "ecs_0", "contact_0", "cell_0", "lumen", False, "lysosome pool", None
        ),
    )
    assert parse_spec(cs.to_dict(spec)) == spec
    op = OPERATORS[LAW]
    summary = op.summary(spec, declaration, (), None)
    assert summary["compartments"] == [
        dict(
            id="lys_0",
            owner=dict(cell="cell_0", slot=0, carrier="cell_0"),
            role="lumen",
            role_declared=False,
            storage=dict(kind="outside_node", node="ecs_0", slot=1),
            membrane=dict(
                patch="contact_0",
                slot=1,
                inside=dict(kind="cell", id="cell_0", slot=0),
                outside=dict(kind="compartment", id="lys_0"),
                voltage="inside minus outside: V_b = phi_owner - phi_compartment",
            ),
            label="lysosome pool",
            reference=None,
        )
    ]
    model = get_model(spec.model)
    assert (
        model.STATE_TYPE._fields
        == get_model(parse_spec(w(declared=False)).model).STATE_TYPE._fields
    )


def test_two_compartments_in_one_cell_stay_distinct_in_the_identity_map():
    """ARCHITECTURE.md's modular core (D174): the host-side map keeps two compartments of one
    owner distinct, each with its own storage slot and its own oriented bounding membrane."""
    raw = fx.world(
        cells=(("cell_0", 1.0),),
        nodes=(("ecs_0", 1.0), ("ecs_1", 0.5)),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_0", "ecs_1")),
        faces=(),
        end=END,
        concentrations_mM=dict(cell_0=1e-3, ecs_0=1e-6, ecs_1=1e-6),
    )
    raw = cfx.with_compartments(
        raw,
        [
            cfx.compartment(label="lysosome pool"),
            cfx.compartment(
                cid="gran_0",
                node="ecs_1",
                patch="contact_1",
                label="secretory granules",
                role="granule lumen",
            ),
        ],
    )
    spec = parse_spec(raw)
    entries = comp.identity_map(spec.model, spec.model.operators[-1])
    assert [e["id"] for e in entries] == ["lys_0", "gran_0"]
    assert [(e["role"], e["role_declared"]) for e in entries] == [
        ("lumen", False),
        ("granule lumen", True),
    ]
    assert [e["storage"]["node"] for e in entries] == ["ecs_0", "ecs_1"]
    assert {e["owner"]["cell"] for e in entries} == {"cell_0"}
    assert [e["storage"]["slot"] for e in entries] == [1, 2]
    assert [e["membrane"]["patch"] for e in entries] == ["contact_0", "contact_1"]
    assert [e["membrane"]["outside"]["id"] for e in entries] == ["lys_0", "gran_0"]
    assert all(e["membrane"]["inside"] == dict(kind="cell", id="cell_0", slot=0) for e in entries)
    assert OPERATORS[LAW].summary(spec, spec.model.operators[-1], (), None)["compartments"] == list(
        entries
    )


def test_a_label_or_a_reference_changes_no_binding():
    plain = cfx.bindings(w())
    for label, reference in (("secretory granules", None), (None, "GO:0005764")):
        other = cfx.bindings(declared(w(), [cfx.compartment(label=label, reference=reference)]))
        assert cfx.same_bindings(plain, other) == []
    for cid, role in (("lys_9", None), ("lys_0", "lysosome lumen")):  # Metadata too.
        other = cfx.bindings(declared(w(), [cfx.compartment(cid=cid, role=role)]))
        assert cfx.same_bindings(plain, other) == []


def test_a_declared_role_round_trips_and_the_default_is_recorded():
    spec = parse_spec(declared(w(), [cfx.compartment(role="lysosome lumen")]))
    assert parse_spec(cs.to_dict(spec)) == spec
    entry = comp.identity_map(spec.model, spec.model.operators[-1])[0]
    assert (entry["role"], entry["role_declared"]) == ("lysosome lumen", True)
    plain = parse_spec(w())
    assert "role" not in cs.to_dict(plain)["model"]["operators"][-1]["compartments"][0]
    summary = OPERATORS[LAW].summary(plain, plain.model.operators[-1], (), None)
    assert summary["compartments_role_default"] == "lumen"
    assert summary["compartments"][0]["role_declared"] is False


def closed_world(gauge):
    raw = w()
    node(raw, "bath")["reservoir"] = False
    raw["model"]["closure"]["gauge_reference"] = gauge
    return raw


def faced_world():
    raw = fx.world(
        cells=(("cell_0", 1.0),),
        nodes=(("ecs_0", 1.0),),
        contacts=(("contact_0", "cell_0", "ecs_0"),),
        faces=(("face_0", "ecs_0", "bath", 1e-10, 1e-5),),
        end=END,
        concentrations_mM=dict(cell_0=1e-3, ecs_0=1e-6),
    )
    return cfx.with_compartments(raw, [cfx.compartment()])


def shared_node():
    raw = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0),),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_0")),
        faces=(),
        end=END,
        concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=1e-6),
    )
    return cfx.with_compartments(raw, [cfx.compartment()])


def misowned():
    raw = two_cells(contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_1")))
    return cfx.with_compartments(raw, [cfx.compartment(owner="cell_1")])


def permeable():
    raw = w()
    patch(raw, "contact_0")["permeability_m_per_s"]["K"] = 1e-9
    return raw


def channelled():
    """A K leak channel population on the bounding patch (refusal 4's channel branch)."""
    raw = w()
    raw["model"]["channels"] = [
        dict(
            id="leak_0",
            membrane_id="contact_0",
            kinetic_law="kleak_always_open@1",
            max_permeability_m_per_s=1e-9,
            abundance=1.0,
            initial_gate=[],
            permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
        )
    ]
    raw["experiment"]["channel_controls"] = [
        dict(channel_id="leak_0", schedule=[dict(time=0.0, availability=1.0)])
    ]
    raw["execution"]["channel_capacity"] = 1
    return raw


def pumped():
    """A Na/K pump on the bounding patch (refusal 4's pump branch)."""
    raw = w()
    bounding = next(p for p in raw["model"]["membranes"] if p["id"] == "contact_0")
    bounding["pump"] = dict(
        id="pump_c",
        law="nak_atp_mass_action_positive@1",
        roles=dict(sodium="Na", potassium="K"),
        stoichiometry=dict(Na=-3, K=2),
        capacity_fmol_per_s=1e-3,
        km_na_mM=12.0,
        km_k_mM=0.2,
        km_atp_mM=0.5,
        metabolism=dict(
            kind="maintained_chemical_reservoirs@1",
            atp_mM=1.5,
            adp_mM=0.1,
            pi_mM=0.1,
            delta_g0_J_per_mol=-37000.0,
        ),
    )
    raw["experiment"]["pump_controls"] = [
        dict(pump_id="pump_c", schedule=[dict(time=0.0, availability=1.0)])
    ]
    return raw


def charged():
    raw = w()
    lumen = node(raw, "ecs_0")
    lumen["fixed_charge_equivalent_fmol"] += 1e-8
    valence = {s["id"]: s["valence"] for s in raw["model"]["species"]}
    net = lumen["fixed_charge_equivalent_fmol"] + sum(
        valence[s] * n for s, n in lumen["initial_amount_fmol"].items()
    )
    lumen["initial_charge_C"] = CHARGE_PER_FMOL * net
    return raw


REFUSALS = {
    "an undeclared node": (
        lambda: declared(w(), [cfx.compartment(node="nowhere")]),
        "is not a declared outside node",
    ),
    "a held bath": (
        lambda: declared(w(), [cfx.compartment(node="bath", patch="wall_cell_0")]),
        "is a held bath",
    ),
    "the gauge": (lambda: closed_world("ecs_0"), "is the gauge"),
    "a node named by a face": (faced_world, "is named by the face 'face_0'"),
    "an undeclared patch": (
        lambda: declared(w(), [cfx.compartment(patch="nope")]),
        "is not declared",
    ),
    "a patch that does not face the node": (
        lambda: declared(w(), [cfx.compartment(patch="wall_cell_0")]),
        "is bounded by exactly one patch",
    ),
    "a node faced by two patches": (shared_node, "is bounded by exactly one patch"),
    "an owner that is not a cell": (
        lambda: declared(w(), [cfx.compartment(owner="bath")]),
        "is not a cell",
    ),
    "a patch on another cell": (misowned, "not on its declared owner 'cell_1'"),
    "two compartments on one node": (
        lambda: declared(w(), [cfx.compartment(), cfx.compartment(cid="lys_1", label="again")]),
        "one compartment per node",
    ),
    "an ion route on the bounding patch": (
        permeable,
        "carries an ion route, a nonzero constant-field permeability, in a world that declares "
        "no kind",
    ),
    "a pump on the bounding patch": (
        pumped,
        "carries an ion route version 1.1 refuses there, pump_c",
    ),
    "an ID that is its node's": (
        lambda: declared(w(), [cfx.compartment(cid="ecs_0")]),
        "collides with an ID the world already declares",
    ),
    "an ID that is a cell's": (
        lambda: declared(w(), [cfx.compartment(cid="cell_0")]),
        "collides with an ID the world already declares",
    ),
    "an ID that is a species'": (
        lambda: declared(w(), [cfx.compartment(cid="S")]),
        "collides with an ID the world already declares",
    ),
    "an ID declared twice": (
        lambda: declared(w(), [cfx.compartment(), cfx.compartment(node="nowhere")]),
        "is declared twice",
    ),
    "an empty role": (lambda: declared(w(), [cfx.compartment(role="")]), "a short string"),
    "a role with spaces around it": (
        lambda: declared(w(), [cfx.compartment(role=" lumen")]),
        "a short string",
    ),
    "a role too long": (lambda: declared(w(), [cfx.compartment(role="x" * 41)]), "a short string"),
    "a role that is not a string": (
        lambda: declared(w(), [cfx.compartment(role=5)]),
        "a short string",
    ),
    "a channel population on the bounding patch": (
        channelled,
        "carries an ion route version 1.1 refuses there, leak_0",
    ),
    "a charge anchor": (charged, "nonzero charge anchor"),
    "no held bath in the owner's component": (lambda: closed_world("bath"), "with no held bath"),
    "an empty label": (
        lambda: declared(w(), [cfx.compartment(label=" ")]),
        "null or a non-empty string",
    ),
    "a numeric reference": (
        lambda: declared(w(), [cfx.compartment(reference=5)]),
        "null or a non-empty string",
    ),
}


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_definition_refusals(name):
    build, message = REFUSALS[name]
    with pytest.raises(ConfigError, match=message):
        parse_spec(build())


def test_refusal_4_admits_the_known_kinds_and_fails_closed_on_any_other():
    """Refusal 4, version 1.1 (docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.1): FR-4's declared world, in
    the composite's form, is admitted with its proton pump (cells.transporter@1), its proton leak
    (cells.passive_routes@1) and its K+ permeability on the bounding patch, and B4's stage read; a
    compartment in a world declaring a kind refusal 4 does not know is refused (fails closed). A
    permeability in a world without kinds stays refused (REFUSALS), as do pumps and channels."""
    from cells.core import kind_registry
    from tests import kind_fixtures
    from validation.compartment_ph_engine import definitions as defs

    spec = parse_spec(defs.declared_world(defs.fr4_world()))
    bounding = next(p for p in spec.model.membranes if p.id == defs.BOUNDING)
    assert any(v > 0 for v in bounding.permeability_m_per_s)  # The K+ counterion.
    assert {k for k, _ in spec.model.kinds} == {*comp.ROUTE_KINDS, *comp.READ_KINDS}
    populations = dict(spec.model.kinds)["cells.transporter@1"]
    routes = dict(spec.model.kinds)["cells.passive_routes@1"]
    assert {t.patch for t in populations} == {r.host for r in routes} == {defs.BOUNDING}
    with kind_registry.scope(kind_fixtures.registry()):
        with pytest.raises(ConfigError, match="which refusal 4 does not know"):
            parse_spec(kind_fixtures.declare(w(), species="S"))


STIFF_DT = 1e-4  # RK4's largest step (surface_tissue.check_steps).
STIFF_STEPS = 20


def stiff_fr4(solver=None, *, operator=True):
    """FR-4's world at STIFF_DT with its bounding patch's K+ permeability scaled 1e4: the lumen's
    row at about 2.5e5 1/s, so dt x rate = 25 (the core's review of refusal 4 version 1.1). The
    declared world (the composite with FR-1's operator), or the development world without it."""
    from validation.compartment_ph_engine import definitions as defs

    world = defs.declared_world if operator else defs.development_world
    raw = world(defs.fr4_world())
    end = STIFF_STEPS * STIFF_DT
    raw["execution"].update(dt=STIFF_DT, max_steps=2 * STIFF_STEPS)
    if solver is not None:
        raw["execution"]["solver"] = solver
    raw["experiment"].update(end_time=end, observation_times=[0.0, end])
    patch(raw, defs.BOUNDING)["permeability_m_per_s"]["K"] *= 1e4
    return raw


def test_refusal_4_admits_routes_beside_a_compartment_only_with_an_imex_tableau():
    """Refusal 4, version 1.1, admits kinds and @3's permeability on a bounding patch only with an
    IMEX tableau (docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.1; the core's review): an RK4 step runs
    neither the per-stage rule nor B7's and the kinds' definition-time terms. The review's probe:
    FR-4's declared world with the stiff K+ permeability is admitted under IMEX, whose step checks
    then refuse it as before, and refused under RK4, where it used to pass its step checks."""
    import dataclasses

    import numpy as np

    from validation.compartment_ph_engine import definitions as defs

    spec = parse_spec(stiff_fr4())  # FR-4's own IMEX solver.
    assert spec.execution.solver != comp.RK4_SOLVER
    with pytest.raises(ConfigError, match="IMEX step exceeds the explicit-rate stability bound"):
        get_model(spec.model).bind_step_checks(spec)(np.full(STIFF_STEPS, STIFF_DT))
    with pytest.raises(ConfigError, match="declared with kinds in a world that steps with RK4"):
        parse_spec(stiff_fr4(comp.RK4_SOLVER))
    # The operator's own rule, on @3's parsed base under each solver.
    base = parse_spec(stiff_fr4(operator=False))
    block = defs.fr4_world()["model"]["operators"][0]
    assert comp.parse_declaration(block, base).compartments[0].node == defs.LUMEN
    rk4 = dataclasses.replace(
        base, execution=dataclasses.replace(base.execution, solver=comp.RK4_SOLVER)
    )
    with pytest.raises(ConfigError, match="version 1's refusal stands"):
        comp.parse_declaration(block, rk4)


def test_refusal_4s_premise_the_stage_rule_holds_a_permeability_at_the_compartments_node(
    monkeypatch,
):
    """Refusal 4's premise (§3.4.1; the core's review, finding 3): with kinds declared, @3's
    per-stage rule (surface_pump_v3.membrane_rate) counts @3's own constant-field permeability at
    the compartment's free node, so an IMEX step at dt G_b / C_b > 1 is refused there. FR-4's world
    with its K+ permeability scaled k, at its own 1 ms: at k = 60 the lumen's row from the K+ route
    alone is about 1.5 / dt while the owner's whole row stays under 1 / dt (the cells-only rate
    would have passed the step), and the step is refused by the stage bound; at k = 20 (about 0.5)
    it is accepted. The declared world (with the operator) is admitted at both."""
    import numpy as np

    from cells.core.surface_pump_v3_spec import control_values
    from cells.models import surface_pump_v3
    from cells.processes.electrochemistry import F, R
    from validation.compartment_ph_engine import definitions as defs

    def scaled(k, world):
        raw = world(defs.fr4_world())
        patch(raw, defs.BOUNDING)["permeability_m_per_s"]["K"] *= k
        return raw

    for k, accepted in ((20, True), (60, False)):
        parse_spec(scaled(k, defs.declared_world))  # Refusal 4 admits it (kinds, IMEX).
        spec = parse_spec(scaled(k, defs.development_world))  # The same @3 world and kinds.
        impl = get_model(spec.model)
        state, p = impl.initial_values(spec)
        control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
        dt = spec.execution.dt
        b = [m.id for m in spec.model.membranes].index(defs.BOUNDING)
        cell, node = int(p.membrane_cell[b]), int(p.membrane_outside[b])
        assert bool(surface_pump_v3.free_outside_nodes(p, xp=np)[node])  # The lumen is free.
        row = spec.model.species_ids.index("K")
        c_in = p.amount_reference[row, cell] / p.volume[cell]
        c_out = p.extracellular_amount_reference[row, node] / p.extracellular_volume[node]
        slope = F * F / (R * spec.model.temperature_K)  # @3's constant-field slope factor.
        g_k = slope * p.membrane_permeability[row, b] * max(c_in, c_out) * p.membrane_area[b]
        node_rate = g_k / p.membrane_capacitance[b]  # The K+ route alone, at the lumen (1/s).
        assert (dt * node_rate > 1.0) == (not accepted), (k, dt * node_rate)
        rate = float(impl.membrane_rate(state, control, p, xp=np))
        cells_only = float(surface_pump_v3.membrane_rate(state, control, p, xp=np))
        assert rate >= node_rate and dt * cells_only < 1.0, (k, rate, cells_only)
        _, valid = impl.imex_step(state, dt, control, p, xp=np)
        assert bool(valid) == accepted, (k, dt * rate)
        if not accepted:  # The stage bound is what refuses it.
            monkeypatch.setattr(surface_pump_v3, "EXPLICIT_STEP_BOUND", np.inf)
            assert bool(impl.imex_step(state, dt, control, p, xp=np)[1])
            monkeypatch.undo()


def replaced(events):
    raw = two_cells(
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_1")),
        faces=(("face_1", "ecs_1", "bath", 1e-10, 1e-5),),
        junctions=(("junction_0", "cell_0", "cell_1"),),
    )
    template = fx.template(raw, "cell_1", "T", s_mM=1e-3)
    raw = fx.with_replacement(raw, [template], events)
    return cfx.with_compartments(raw, [cfx.compartment()])


def test_replacement_composes_away_from_owners_and_never_on_or_from_one():
    parse_spec(replaced([(0.005, "cell_1", "T", "c1_new")]))
    with pytest.raises(ConfigError, match="schedules an event on 'cell_0'"):
        parse_spec(replaced([(0.005, "cell_0", "T", "c0_new")]))
    with pytest.raises(ConfigError, match="names 'cell_0', which owns a compartment, as a donor"):
        parse_spec(replaced([(0.005, "cell_1", None, "c1_new", "cell_0")]))


def test_the_admitted_list_fails_closed(monkeypatch):
    class Newcomer(Operator):
        LAW_ID = "a_future_operator@1"
        EVENT = True

    monkeypatch.setitem(OPERATORS, Newcomer.LAW_ID, Newcomer())
    spec = parse_spec(w())
    model = SimpleNamespace(operators=(*spec.model.operators, SimpleNamespace(law=Newcomer.LAW_ID)))
    experiment = SimpleNamespace(operators=(*spec.experiment.operators, SimpleNamespace(data=())))
    fake = SimpleNamespace(model=model, experiment=experiment)
    with pytest.raises(ConfigError, match="a_future_operator@1 is not on its admitted list"):
        comp.check_definition(fake, spec.model.operators[-1])
    assert set(comp.ADMITTED) <= set(OPERATORS)


# ------------------------------------------------------------------ the structure check

STATE, WATER = "membrane_entity_state@1", "ideal_osmosis_linear_compliance_water@1"
STRUCTURE_REFUSED = {
    "water": ((WATER,), WATER),
    "membrane state": ((STATE,), STATE),
    "insertion@1": ((STATE, "scheduled_membrane_insertion@1"), "scheduled_membrane_insertion@1"),
    "insertion@2": ((STATE, "scheduled_membrane_insertion@2"), "scheduled_membrane_insertion@2"),
    "the partition": ((STATE, "isopotential_partition@1"), "isopotential_partition@1"),
    "lumen@1": (
        (STATE, "scheduled_membrane_insertion@1", "restricted_cleft_lumen@1"),
        "restricted_cleft_lumen@1",
    ),
    "lumen@2": (
        (STATE, "scheduled_membrane_insertion@2", "restricted_cleft_lumen@2"),
        "restricted_cleft_lumen@2",
    ),
    "replacement@2, over water": ((WATER, "scheduled_cell_replacement@2"), WATER),
    "the symport, over water": ((WATER, "k_anion_symport_mass_action@1"), WATER),
}
STRUCTURE_ADMITTED = (
    ("scheduled_species_exchange@1",),
    ("scheduled_species_turnover@1",),
    ("scheduled_species_turnover@1", "scheduled_species_exchange@1"),
    ("local_species_reactions@1",),
    ("species_regulated_availability@1",),
    ("electrode_current_injection@1",),
    ("scheduled_cell_replacement@1",),
    ("scheduled_bath_composition@1",),
)


@pytest.mark.parametrize("name", sorted(STRUCTURE_REFUSED))
def test_the_structure_check_refuses_providers_and_closers_of_what_it_reads(name):
    laws, culprit = STRUCTURE_REFUSED[name]
    for order in ((*laws, LAW), (LAW, *laws)):
        errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order))
        assert any(e.startswith(LAW + " reads") and f"but {culprit} " in e for e in errors), (
            order,
            errors,
        )


@pytest.mark.parametrize("laws", STRUCTURE_ADMITTED, ids="+".join)
def test_the_structure_check_admits_the_operators_it_composes_with(laws):
    for order in ((*laws, LAW), (LAW, *laws)):
        assert pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order)) == []
