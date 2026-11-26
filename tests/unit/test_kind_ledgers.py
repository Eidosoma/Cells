"""E's kind ledgers (docs/CORE_SEAMS_DESIGN.md §7.3; INNER_MODEL_V4_DESIGN §7.4 (p)), @3's part:
each declared kind's own ledgers, declared by its ledgers(declaration) hook and read once into
InnerStructure.kind_ledgers, follow @1's ten ledgers on every check path. Each is valued by the
kind's ledger_terms under its own name and bounded by its ledger_bounds at check time.

- A planted producer kind (tests.kind.producer@1) runs one reaction in a cell, ATP -> ADP + Pi at a
  declared rate, books its chemistry's heat, and declares the adenine moiety's ledger: the
  adenine weights (ATP 1, ADP 1) times its net production, held to zero within the rows' material
  tolerances. Its world runs with every ledger closing, the adenine one among them. The plant, its
  ADP count off by one (2 ADP per reaction), fails on "accounting failed: adenine", while its
  material, charge and energy ledgers close (its production record carries the wrong count).
  Both check paths hold it: the host's check of every row, and the device's row checks
  (WindowPolicy row_checks="device"), which decide the world's windows themselves. A composite
  takes the ledger from its inner model's lists, with no edit of its own, and runs with it; beside
  an operator with ledgers of its own, its device checks hold it too.
- A bound that is not finite fails its ledger, balanced or not (the fourth review's finding 2): a
  kind's own on the host and in the device's row checks, @1's and an operator's own on the host.
- Refused at the definition: a declared ledger the kind's ledger_terms does not value; a ledger
  or diagnostic named for one of @1's ten; a malformed hook result. The structure itself refuses
  an undeclared kind, two kinds unsorted or one kind twice, a repeated name, a name of @1's or of
  a ledger_terms role, and a malformed entry (F's review, 19 November 2026).
- Today's structures keep @1's own ledger objects, so their programs are unchanged.
"""

import dataclasses

import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.kinds import transporter
from cells.laws.electrochemistry import R
from cells.models import inner_laws, surface_pump, surface_pump_v3
from cells.numerics.species_sums import entity_sum, species_sum
from cells.registry import kind_registry
from cells.registry.models import get_model
from tests import kind_fixtures
from tests.unit.test_transporter_kind import held_world, scoped
from tests.window_row_check_fixtures import windows
from validation.tissue import bath_schedule_fixtures as bfx

PRODUCER_ID = "tests.kind.producer@1"
PRODUCER_KEY = "test_producer"
ADENINE = ("adenine", "adenine_moiety_error_fmol")


def _parse(entries, base):
    if set(entries) != {"cell", "rate_fmol_s", "adp"}:
        raise ConfigError("test_producer declares cell, rate_fmol_s and adp")
    if entries["cell"] not in [c.id for c in base.model.cells]:
        raise ConfigError("test_producer: unknown cell")
    return (entries["cell"], float(entries["rate_fmol_s"]), int(entries["adp"]))


def _to_dict(declaration):
    cell, rate, adp = declaration
    return dict(cell=cell, rate_fmol_s=rate, adp=adp)


def _initial(spec, declaration, layout):
    cell, rate, adp = declaration
    m, n = spec.model, spec.execution.capacity
    ids = list(m.species_ids)
    rates = np.zeros(n)
    rates[[c.id for c in m.cells].index(cell)] = rate
    nu, adenine = np.zeros(len(ids)), np.zeros(len(ids))
    nu[ids.index("ATP")], nu[ids.index("ADP")], nu[ids.index("Pi")] = -1.0, float(adp), 1.0
    adenine[ids.index("ATP")] = adenine[ids.index("ADP")] = 1.0
    state = dict(producer_extent=np.zeros(n), producer_dissipated_energy_pJ=np.zeros(n))
    return state, dict(producer_rate_fmol_s=rates, producer_nu=nu, producer_adenine=adenine)


def _rates(state, potentials, control, p, *, xp):
    """The reaction's rate in each active cell, its node changes, and its heat: the ideal
    chemical free energy it releases, -RT sum(nu ln c) per fmol (no standard parts are declared)."""
    rate = xp.where(p.active, p.producer_rate_fmol_s, 0.0)
    ci, co = kind_fixtures._potentials(state, p, xp=xp)
    drive = species_sum(p.producer_nu[:, None] * xp.log(ci), xp=xp)  # [cell]
    heat = -1e-3 * R * p.temperature * drive * rate  # pJ/s
    return kind_registry.KindRates(
        cell=p.producer_nu[:, None] * rate[None, :],
        outside=xp.zeros_like(co),
        derivatives=dict(producer_extent=rate, producer_dissipated_energy_pJ=heat),
        heat_pJ_s=heat,
        work_pJ_s=xp.zeros(()),
    )


def _ledger_terms(state, p, *, xp):
    nodes = p.producer_nu[:, None] * state.producer_extent[None, :]  # [species, cell]
    produced = entity_sum(nodes, axis=1, xp=xp)
    return dict(
        cell=nodes,
        produced=produced,
        heat_pJ=state.producer_dissipated_energy_pJ,
        adenine=species_sum(p.producer_adenine * produced, xp=xp),  # The moiety: sum w x produced.
    )


def _ledger_bounds(row, p, tol, steps, *, xp):
    """The adenine ledger's bound: the rows' material tolerances, weighted as the moiety is."""
    return (species_sum(p.producer_adenine * tol, xp=xp),)


def _domain(state, p, *, xp):
    return xp.all(xp.isfinite(state.producer_extent)) & xp.all(
        xp.isfinite(state.producer_dissipated_energy_pJ)
    )


def _moved_rows(declaration):
    cell, _, _ = declaration
    return (("ATP", cell), ("ADP", cell), ("Pi", cell))


PRODUCER = kind_registry.Kind(
    kind_id=PRODUCER_ID,
    model_key=PRODUCER_KEY,
    state_axes=(
        ("producer_extent", ("cell_slot",)),
        ("producer_dissipated_energy_pJ", ("cell_slot",)),
    ),
    layout_fields=("producer_rate_fmol_s", "producer_nu", "producer_adenine"),
    parse=_parse,
    to_dict=_to_dict,
    structure_entry=lambda declaration: (),
    initial=_initial,
    control_values=lambda spec, declaration, times: {},
    rates=_rates,
    ledger_terms=_ledger_terms,
    domain=_domain,
    moved_rows=_moved_rows,
    ledgers=lambda declaration: (ADENINE,),
    ledger_bounds=_ledger_bounds,
)


def world(*, adp=1, rate=1e-3):
    """The held world without its transporter, the producer reacting in cell_0."""
    raw = held_world()
    m = raw["model"]
    del m[transporter.MODEL_KEY]
    m[PRODUCER_KEY] = dict(cell="cell_0", rate_fmol_s=rate, adp=adp)
    return raw


def nonfinite_bound(value):
    """PRODUCER with its adenine bound planted at value, +inf or NaN (the fourth review's
    finding 2)."""

    def bounds(row, p, tol, steps, *, xp):
        return (_ledger_bounds(row, p, tol, steps, xp=xp)[0] * 0.0 + value,)

    return dataclasses.replace(PRODUCER, ledger_bounds=bounds)


def test_a_kind_declared_ledger_closes_in_a_run_and_its_off_by_one_plant_fails(monkeypatch):
    assert kind_registry.declaration_errors(PRODUCER) == []
    with scoped(PRODUCER):
        spec = parse_spec(world())
        model = get_model(spec.model)
        assert model.structure.kind_ledgers == ((PRODUCER_ID, (ADENINE,)),)
        assert model.LEDGERS == (*surface_pump.LEDGERS, "adenine")
        assert model.DEVICE_CHECKS == ("domain", *surface_pump.LEDGERS, "adenine", "dissipation")
        result = run(spec)  # Every ledger closes, the adenine one among them.
        assert result.diagnostics["max_adenine_moiety_error_fmol"] <= 1e-12
        final = result.final.state
        assert float(np.asarray(final.producer_extent)[0]) > 0.0
        # Planted: two ADP per reaction. Its records carry the count, so material, charge and
        # energy close; only the moiety does not.
        with pytest.raises(NumericalError, match="accounting failed: adenine"):
            run(parse_spec(world(adp=2)))
    # A bound that is not finite fails its ledger, balanced or not (the fourth review's finding
    # 2), on the start row without a compile: the kind's own (+inf, NaN) on the host and in the
    # device's row checks, and @1's own (NaN) on the host.
    for value in (np.inf, np.nan):
        with scoped(nonfinite_bound(value)):
            spec = parse_spec(world())
            model = get_model(spec.model)
            state, p = model.initial_values(spec)
            with pytest.raises(NumericalError, match="accounting failed: adenine"):
                model.check_values(state, spec)
            constants = model.device_check_constants(spec)
            failed, _ = model.device_checks(state, state, p, constants, 0)
            assert bool(np.asarray(failed)[model.DEVICE_CHECKS.index("adenine")])
    with scoped(PRODUCER):
        spec = parse_spec(world())
        model = get_model(spec.model)
        state, _ = model.initial_values(spec)
        lists = surface_pump_v3.ledger_lists(model.structure)  # The one the host check reads.
        real, work = lists.ledger_limits, surface_pump.LEDGERS.index("metabolic_work")

        def nan_work(*args, **kwargs):  # @1's metabolic-work bound, planted NaN.
            flows, bounds = real(*args, **kwargs)
            return flows, (*bounds[:work], np.nan, *bounds[work + 1 :])

        monkeypatch.setattr(lists, "ledger_limits", nan_work)
        with pytest.raises(NumericalError, match="accounting failed: metabolic_work"):
            model.check_values(state, spec)


def composite_world(*, adp=1):
    """world() in a composite beside an idle scheduled bath, an operator with ledgers of its own:
    its device checks split the magnitudes between @3's ten and the operator's (the fourth
    review's finding 1)."""
    raw = cs.frozen_definition(world(adp=adp))
    return bfx.with_bath_schedule(raw, ["bath_0"], {"Yu": {"Y": 1}}, [])


@pytest.mark.parametrize("make", [world, composite_world], ids=["@3", "composite"])
def test_the_device_row_checks_hold_the_kind_ledger_too(make):
    with scoped(PRODUCER):
        spec = parse_spec(make())
        model = get_model(spec.model)
        if getattr(model, "own_ledger_operators", ()):  # The split, on distinct magnitudes.
            state, p = model.initial_values(spec)
            ((op,), inner) = model.own_ledger_operators, model.inner_magnitudes(state, p)
            planted = tuple(float(k + 1) for k in range(len(op.LEDGERS)))
            tol = np.asarray(spec.execution.material_balance_atol_fmol)
            magnitudes = (*inner, *planted)
            _, bounds = model.ledger_limits(state, p, tol, 0.0, steps=7, magnitudes=magnitudes)
            assert len(inner) < len(model.inner.LEDGERS)  # The adenine ledger has no magnitude.
            assert bounds[len(model.inner.LEDGERS) :] == op.own_bounds(planted, 7)
            # An operator's own bound that is not finite fails its ledger on the host (the fourth
            # review's finding 2); the device leaves it (row_checks states the gap).
            with pytest.MonkeyPatch.context() as patch:
                infinite = (np.inf,) * len(op.LEDGERS)
                patch.setattr(type(op), "own_bounds", lambda self, magnitudes, steps: infinite)
                with pytest.raises(NumericalError, match="Bath schedule accounting failed"):
                    model.check_values(state, spec)
        device = windows(spec, 4, "device")
        assert any(w.row_checks.decided_by == "device" for w in device)
        for window in device:
            assert window.diagnostics["max_adenine_moiety_error_fmol"] <= 1e-12
        with pytest.raises(NumericalError, match="accounting failed: adenine"):
            windows(parse_spec(make(adp=2)), 4, "device")


def test_a_composite_takes_the_kind_ledger_from_its_inner_model():
    raw = cs.frozen_definition(world())
    electrode = dict(cell_id="cell_0", carriers={"K": 1.0})
    raw["model"].setdefault("operators", []).append(
        dict(law="cells.operator.electrode_current_injection@1", electrodes=[electrode])
    )
    raw["experiment"]["injection_controls"] = [
        dict(cell_id="cell_0", schedule=[dict(time=0.0, current_A=1e-13)])
    ]
    with scoped(PRODUCER):
        spec = parse_spec(raw)
        model = get_model(spec.model)
        assert model.inner.LEDGERS == (*surface_pump.LEDGERS, "adenine")
        assert model.LEDGERS[: len(model.inner.LEDGERS)] == model.inner.LEDGERS
        result = run(spec)
        assert result.diagnostics["max_adenine_moiety_error_fmol"] <= 1e-12


def test_a_declared_ledger_its_terms_do_not_value_is_refused():
    def without(state, p, *, xp):
        terms = _ledger_terms(state, p, xp=xp)
        del terms["adenine"]
        return terms

    with scoped(dataclasses.replace(PRODUCER, ledger_terms=without)):
        with pytest.raises(ConfigError, match=r"values none of its declared ledgers \['adenine'\]"):
            parse_spec(world())


def test_a_ledger_or_diagnostic_named_for_one_of_todays_ten_is_refused():
    for pair in (("energy", "producer_energy_error_pJ"), ("adenine", "energy_balance_error_pJ")):
        planted = dataclasses.replace(PRODUCER, ledgers=lambda declaration, pair=pair: (pair,))
        with scoped(planted):
            with pytest.raises(ConfigError, match="take names of @1's ledgers or diagnostics"):
                parse_spec(world())


def test_a_malformed_ledgers_result_is_refused_naming_the_kind():
    planted = dataclasses.replace(PRODUCER, ledgers=lambda declaration: ["adenine"])
    with scoped(planted):
        with pytest.raises(ConfigError, match=r"Kind tests.kind.producer@1's ledgers are refused"):
            parse_spec(world())


def test_the_structure_refuses_entries_that_are_not_declared_sorted_distinct_named_ledgers():
    raw = kind_fixtures.declare_carrier(world(), species="K")  # Two kinds: the carrier too.
    with scoped(PRODUCER, kind_fixtures.carrier()):
        structure = surface_pump_v3.structure(parse_spec(raw).model)
    assert [kind_id for kind_id, _ in structure.kinds] == [kind_fixtures.CARRIER_ID, PRODUCER_ID]
    assert structure.kind_ledgers == ((PRODUCER_ID, (ADENINE,)),)  # At most one per kind.
    other = (kind_fixtures.CARRIER_ID, (("b", "b_error"),))
    for planted, reason in (
        (((PRODUCER_ID, (ADENINE,)), other), "sorted, one entry per kind"),  # Two kinds, unsorted.
        (((PRODUCER_ID, (ADENINE,)), (PRODUCER_ID, (("b", "b_error"),))), "sorted, one entry"),
        (((PRODUCER_ID, (("heat_pJ", "heat_error"),)),), "ledger_terms' roles"),
        (
            ((PRODUCER_ID, (ADENINE,)), ("tests.kind.undeclared@1", (("b", "b_error"),))),
            "not a declared",
        ),
        (((PRODUCER_ID, (ADENINE, ADENINE)),), "named twice"),
        (((PRODUCER_ID, (("local", "x_error"),)),), "one of @1's ledgers or diagnostics"),
        ([(PRODUCER_ID, (ADENINE,))], "entries of names"),
        (((PRODUCER_ID, ()),), "entries of names"),
    ):
        with pytest.raises(ValueError, match=reason):
            dataclasses.replace(structure, kind_ledgers=planted)
    assert inner_laws.kind_ledger_errors((), ()) == []
    assert dataclasses.replace(
        structure, kind_ledgers=(other, (PRODUCER_ID, (ADENINE,)))
    )  # Sorted.


def test_todays_structures_keep_todays_ledger_objects():
    with scoped():  # The transporter, which declares no ledger of its own.
        plain = surface_pump_v3.structure(parse_spec(held_world()).model)
    assert plain.kinds and plain.kind_ledgers == ()
    for structure in (None, plain):
        lists = surface_pump_v3.ledger_lists(structure)
        assert lists.LEDGERS is surface_pump.LEDGERS
        assert lists.ledger_limits is surface_pump.ledger_limits
        assert lists.DEVICE_CHECKS is surface_pump.DEVICE_CHECKS
