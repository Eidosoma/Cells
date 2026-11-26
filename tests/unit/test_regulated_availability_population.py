"""cells.operator.species_regulated_availability@2's population source (FR-7's part (b); development, not judged).

docs/ABUNDANCE_TO_FUNCTION_DESIGN.md §6.2 and D218: a coupling reads a channel population's density
rho = a rho_ref (units per µm²). Here a is @3's current channel_abundance, read in the coupling's
reader view at the control view (contract R2), and rho_ref is the population's reference density
declared in cells.operator.membrane_entity_state@1. The world is FR-7's leak cell (validation/fr7/
unit_turnover_fixtures.cell): one cell holding the gate-free K populations kir_0 and leak_1, each
at 10 units per µm² of reference density. In it, c_pop reads kir_0 onto leak_1's availability.
Every value is synthetic.

Host rows (no compile, a few seconds):
* parsing, binding and the round trip;
* each refusal, D218's self-source among them, and @1 refusing a population source with its
  message unchanged;
* the factor against an independent b + (1 - b) Hill(a rho_ref) at planted views, rho = 0
  included, and its operating range;
* the static switch: without a population route no hook calls the view, and with one a hook given
  no view refuses;
* the constant-source report.

One compiled program serves four arms of 30 steps at 1 ms, set by controls alone. Its structure is
the unit producer writing kir_0 on its direct route.
* **Varying arm (the producer on):** two checks against the independent evaluation, both within
  1e-13. The observed factor is compared at each row's units. Each step's applied record is
  compared at the control view's state, which is the row before advanced half a step by the
  producer's closed form.
* **Constant arm (the producer at zero rates):** P1's form. Bit for bit, it gives @3's step and
  observations of the same structure with the coupling switched off and leak_1 scheduled at the
  recorded product. It is non-vacuous: it differs from leak_1 at its unscaled schedule.

About 25 s, so tier 2 (D224: the four arms share one compiled world).
"""

import copy
from decimal import Decimal, localcontext
from types import SimpleNamespace

import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.runner import run
from cells.operators import species_regulated_availability as sra
from cells.registry.models import get_model
from validation.fr7 import unit_turnover_fixtures as fx
from validation.tissue import regulated_availability_fixtures as rf

SOURCE, TARGET = "kir_0", fx.SECOND
K, HILL, BASAL, RANGE = 12.0, 2.0, 0.2, (0.0, 100.0)  # Units per µm²; synthetic.
PER_UM2 = 1e-12  # The test's own conversion: one µm² is 1e-12 m².


def coupling(source=SOURCE, ids=(TARGET,), *, law="hill_activation", control="channel", **change):
    """c_pop: a Hill law of `source`'s density on `ids` (an inner step_view target)."""
    entry = dict(
        id="c_pop",
        target=dict(
            operator="inner",
            control=control,
            ids=list(ids),
            side=None,
            evaluation="step_view",
            operating_range=list(RANGE),
        ),
        source={"population": source},
        law=law,
        half_saturation_per_um2=K,
        hill_coefficient=HILL,
        basal=BASAL,
    )
    entry.update(change)
    return entry


def with_coupling(raw, entries, *, law=sra.LAW_ID_V2, enabled=1, species=()):
    """raw with the coupling operator's block last and each coupling switched as `enabled`."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(
        dict(law=law, species=list(species), states=[], couplings=list(entries))
    )
    out["experiment"]["coupling_controls"] = [
        dict(coupling_id=e["id"], schedule=[dict(time=0.0, enabled=enabled)]) for e in entries
    ]
    out["experiment"]["regulatory_writes"] = []
    return out


def world(entry=None, *, end=0.005, raw=None):
    return with_coupling(fx.cell(end=end) if raw is None else raw, [entry or coupling()])


def bound(raw):
    """(spec, composite, state, layout, the coupling operator, its declaration and schedule)."""
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op, declaration, schedule = next(
        e for e in cs.entries(spec) if e[0].LAW_ID in (sra.LAW_ID, sra.LAW_ID_V2)
    )
    return spec, model, state, p, op, declaration, schedule


def planted(a, other=0.5):
    """A reader view whose channel_abundance is [a (kir_0), other (leak_1)]."""
    return lambda state: SimpleNamespace(channel_abundance=np.asarray([a, other]))


def independent(rho, *, law="hill_activation", k=K, n=HILL, b=BASAL):
    """b + (1 - b) f, f = rho^n / (rho^n + K^n) (activation) or K^n / (rho^n + K^n), in Decimal."""
    with localcontext() as context:
        context.prec = 50
        r, kk, nn, bb = (Decimal(repr(float(v))) for v in (rho, k, n, b))
        if r == 0:
            f = Decimal(0) if law == "hill_activation" else Decimal(1)
        else:
            x = (r.ln() * nn).exp()
            y = (kk.ln() * nn).exp()
            f = (x if law == "hill_activation" else y) / (x + y)
        return bb + (1 - bb) * f


def close(got, want, rel=1e-13):
    return abs(Decimal(repr(float(got))) - want) <= Decimal(repr(rel)) * abs(want)


# ------------------------------------------------------------------ parsing and binding


def test_parses_binds_and_round_trips():
    spec, model, state, p, op, declaration, _ = bound(world())
    (c,) = declaration.couplings
    assert type(c) is sra.PopulationCoupling and c.source_kind == "population"
    assert (c.source, c.half_saturation_per_um2, c.hill_coefficient, c.basal) == (
        SOURCE,
        K,
        HILL,
        BASAL,
    )
    assert parse_spec(cs.to_dict(spec)).model.operators == spec.model.operators
    assert np.asarray(p.coupling_route_law).tolist() == [sra.POPULATION_LAWS["hill_activation"]]
    assert np.asarray(p.coupling_route_population).tolist() == [0]
    assert np.asarray(p.coupling_population_channel).tolist() == [0]  # kir_0's slot.
    assert np.asarray(p.coupling_population_reference_density_per_um2).tolist() == [
        fx.DENSITY * PER_UM2
    ]
    assert np.asarray(p.coupling_channel_routes).tolist() == [[-1], [0]]  # On leak_1 only.
    assert {o.LAW_ID: f for o, f in model.factor_fields.items()} == {
        sra.LAW_ID_V2: ("channel_abundance",)
    }
    a0 = next(ch.abundance for ch in spec.model.channels if ch.id == SOURCE)
    assert close(state.coupling_applied_factor[0], independent(a0 * fx.DENSITY * PER_UM2))


def _sheet(entry):
    """The seven-cell sheet (a junction, a Kir population per cell), for the locality and
    junction refusals, which parsing raises before any binding."""
    return with_coupling(rf.sheet(end=0.002), [entry])


REFUSALS = {
    "self-source (D218)": (
        lambda: world(coupling(ids=(SOURCE, TARGET))),
        "kir_0's own abundance onto its availability",
    ),
    "a count": (
        lambda: world(
            {
                **{k: v for k, v in coupling().items() if k != "half_saturation_per_um2"},
                "half_saturation_units": 3.0,
            }
        ),
        "a count would make the factor depend on the host's size",
    ),
    "a concentration": (
        lambda: world(
            {
                **{k: v for k, v in coupling().items() if k != "half_saturation_per_um2"},
                "half_saturation_mM": 1e-3,
            }
        ),
        "through half_saturation_mM",
    ),
    "another cell's population": (
        lambda: _sheet(coupling(source="kir_0", ids=("kir_3",))),
        "a population source is read in its target's cell",
    ),
    "a junction target": (
        lambda: _sheet(
            coupling(
                source="kir_0",
                ids=("junction_0",),
                control="junction",
                target=dict(
                    operator="inner",
                    control="junction",
                    ids=["junction_0"],
                    side="first",
                    evaluation="step_view",
                    operating_range=list(RANGE),
                ),
            )
        ),
        "reads a population onto a junction",
    ),
    "an operator target": (
        lambda: world(
            coupling(
                target=dict(
                    operator=fx.LAW,
                    control="unit_assembly_rate",
                    ids=["kir_units"],
                    evaluation="target_half_steps",
                    operating_range=list(RANGE),
                )
            )
        ),
        "reads a population onto an operator target",
    ),
    "an unknown population": (lambda: world(coupling(source="nav_9")), "unknown population"),
    "a state law": (lambda: world(coupling(law="state_fraction")), "through a Hill law"),
    "K = 0": (lambda: world(coupling(half_saturation_per_um2=0.0)), "half_saturation_per_um2"),
    "n = 0": (lambda: world(coupling(hill_coefficient=0.0)), "hill_coefficient"),
    "a negative range": (
        lambda: world(
            coupling(
                target={**coupling()["target"], "operating_range": [-1.0, 10.0]},
            )
        ),
        "operating_range bound",
    ),
    "no membrane state": (
        lambda: world(raw=_without_membrane_state(fx.cell(end=0.005))),
        "a population source needs cells.operator.membrane_entity_state@1",
    ),
    "@1": (
        lambda: with_coupling(fx.cell(end=0.005), [_v1(coupling())], law=sra.LAW_ID),
        "coupling c_pop's source is {'species': id} or {'state': id}",
    ),
}


def _without_membrane_state(raw):
    out = copy.deepcopy(raw)
    out["model"]["operators"] = [o for o in out["model"]["operators"] if o["law"] != fx.STATE]
    return out


def _v1(entry):
    """@1's form of the coupling: its inner target without evaluation or range, and its
    half-saturation in mM, so that @1 reaches its source rule."""
    target = {
        k: v for k, v in entry["target"].items() if k not in ("evaluation", "operating_range")
    }
    out = {k: v for k, v in entry.items() if k != "half_saturation_per_um2"}
    return {**out, "target": target, "half_saturation_mM": 1e-3}


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_each_refusal(name):
    make, words = REFUSALS[name]
    with pytest.raises(ConfigError) as caught:
        parse_spec(make())
    assert words in str(caught.value), str(caught.value)
    if name != "@1":
        assert sra.LAW_ID_V2 in str(caught.value) or name == "a negative range"


def test_an_in_step_writer_of_units_or_area_is_refused(monkeypatch):
    """The held factor is exact only while units and area change in half-steps and event maps,
    so an in-step process writing either is refused (planted; no registered operator has one)."""
    spec, _, _, _, _, declaration, _ = bound(world())
    real = list(cs.entries(spec))
    for field in sra.UNIT_FIELDS:
        stub = SimpleNamespace(LAW_ID="cells.operator.stub@1", PROCESS=True, ENTITY_WRITES={field: ("x",)})
        monkeypatch.setattr(
            sra.composite_spec, "entries", lambda s, stub=stub: [*real, (stub, 0, 0)]
        )
        with pytest.raises(ConfigError, match=f"cells.operator.stub@1's in-step process writes {field}"):
            sra.check_population_sources(spec, declaration)
        quiet = SimpleNamespace(LAW_ID="cells.operator.stub@1", PROCESS=False, ENTITY_WRITES={field: ("x",)})
        monkeypatch.setattr(sra.composite_spec, "entries", lambda s, q=quiet: [*real, (q, 0, 0)])
        sra.check_population_sources(spec, declaration)  # A half-step writer is admitted.


# ------------------------------------------------------------------ the factor


@pytest.mark.parametrize("law", ["hill_activation", "hill_inhibition"])
def test_the_factor_is_b_plus_one_minus_b_hill_of_the_density(law):
    """At planted views of kir_0's abundance a (rho = 0 included), control_factors gives leak_1
    b + (1 - b) Hill(a rho_ref) and kir_0 exactly 1, and factor_record the same values with the
    route evaluated there; factor_valid holds rho to the declared range, and a switched-off
    coupling gives exactly 1 and is not checked."""
    _, _, state, p, op, _, _ = bound(world(coupling(law=law)))
    for a in (0.0, 0.05, 0.3, 1.0, 1.2, 4.0):
        view = planted(a)
        rho = a * fx.DENSITY * PER_UM2
        with np.errstate(divide="ignore"):
            factors = op.control_factors(state, p, xp=np, view=view)
            values, used = op.factor_record(state, p, None, None, xp=np, view=view)
        want = independent(rho, law=law)
        assert factors["channel"][0] == 1.0 and close(factors["channel"][1], want, 2e-15), a
        assert values[0] == factors["channel"][1] and used.tolist() == [True]
        if a == 0.0 and law == "hill_activation":
            assert factors["channel"][1] == BASAL  # f = 0 exactly at rho = 0.
        with np.errstate(divide="ignore"):
            assert bool(op.factor_valid(state, p, xp=np, view=view))
    assert not bool(op.factor_valid(state, p, xp=np, view=planted(10.5)))  # rho = 105 > 100.
    off = state._replace(coupling_enabled=np.zeros(1))
    assert bool(op.factor_valid(off, p, xp=np, view=planted(10.5)))
    assert op.control_factors(off, p, xp=np, view=planted(10.5))["channel"].tolist() == [1.0, 1.0]


def _raising(state):
    raise AssertionError("the view was called")


def test_without_a_population_route_no_hook_calls_the_view(monkeypatch):
    """The static switch: an @2 world with only a species route never calls the reader view, in
    the hooks or through the composite, so no other @2 program changes. With a population route,
    a hook given no view refuses."""
    species = coupling(source=None)
    del species["half_saturation_per_um2"]
    species.update(source={"species": fx.PRECURSOR}, half_saturation_mM=1e-4)
    raw = with_coupling(fx.cell(end=0.005), [species], species=fx.identity())
    spec, model, state, p, op, _, _ = bound(raw)
    assert not sra.has_population(p)
    op.control_factors(state, p, xp=np, view=_raising)
    op.factor_valid(state, p, xp=np, view=_raising)
    op.factor_record(state, p, None, None, xp=np, view=_raising)
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))
    with monkeypatch.context() as patched:  # The composite is shared: undone before the next.
        patched.setattr(model, "_reader_view_of", lambda *args, **kwargs: _raising(None))
        model.control_view(control, state, p, xp=np)
        model._control_factor_checks(state, p, xp=np)
    _, _, state, p, op, _, _ = bound(world())
    for call in (
        lambda: op.control_factors(state, p, xp=np),
        lambda: op.factor_valid(state, p, xp=np),
        lambda: op.factor_record(state, p, None, None, xp=np),
    ):
        with pytest.raises(ValueError, match="none was passed"):
            call()


def test_a_source_no_declared_writer_changes_is_reported_constant():
    """The summary reports a constant source, and the writers of units or area otherwise."""
    spec, _, _, _, op, declaration, schedule = bound(world())
    out = op.summary(spec, declaration, schedule, SimpleNamespace())
    assert out["coupling_constant_sources"] == {"c_pop": sra.CONSTANT_SOURCE}
    target = out["coupling_targets"]["c_pop"]
    assert target["half_saturation_per_um2"] == K and "half_saturation_mM" not in target
    assert target["operating_range_per_um2"] == list(RANGE) and target["source_writers"] == []
    spec, _, _, _, op, declaration, schedule = bound(structure(0.0, 0.0, enabled=1))
    out = op.summary(spec, declaration, schedule, SimpleNamespace())
    assert out["coupling_constant_sources"] == {}
    assert out["coupling_targets"]["c_pop"]["source_writers"] == [fx.LAW]


# ------------------------------------------------------------------ one compiled world

STEPS, DT, HELD = 30, 1e-3, 0.75  # leak_1's scheduled availability, under the factor.
RATES = (50.0, 5.0)  # k_a, k_r (1/s), synthetic: kir_0 roughly doubles in 30 ms.
NU = 4


def structure(k_a, k_r, *, enabled, held=HELD):
    """The one compiled structure: the producer on kir_0's direct route at (k_a, k_r), c_pop
    switched on or off, leak_1 held at `held`."""
    raw = fx.cell(end=STEPS * DT, dt=DT)
    raw = fx.with_producer(
        raw, [fx.route("kir_units", SOURCE, nu=NU)], {"kir_units": [(0.0, k_a, k_r)]}
    )
    raw = with_coupling(raw, [coupling()], enabled=enabled)
    return rf.schedule_channel(raw, TARGET, held)


_runs = {}


def arm(name):
    if name not in _runs:
        if name == "scheduled":  # P1's form: the recorded product, the coupling off.
            product = float(np.float64(HELD) * np.float64(constant_factor()))
            raw = structure(0.0, 0.0, enabled=0, held=product)
        else:
            raw = dict(
                varying=lambda: structure(*RATES, enabled=1),
                constant=lambda: structure(0.0, 0.0, enabled=1),
                unscaled=lambda: structure(0.0, 0.0, enabled=0),
            )[name]()
        spec = parse_spec(raw)
        _runs[name] = (spec, run(spec))
    return _runs[name]


def constant_factor():
    _, result = arm("constant")
    record = np.asarray(result.history.coupling_applied_factor)[:, 0]
    assert np.all(record == record[0])  # One value on every row.
    return record[0]


def declared(spec):
    """(a0, A0 in m^2, the precursor's species row) of kir_0 and its patch, from the definition."""
    channel = next(c for c in spec.model.channels if c.id == SOURCE)
    area = next(m.area_m2 for m in spec.model.membranes if m.id == channel.membrane_id)
    return channel.abundance, area, list(spec.model.species_ids).index(fx.PRECURSOR)


def test_a_constant_source_is_its_scheduled_availability_bitwise():
    spec, _ = arm("constant")
    a0, _, _ = declared(spec)
    assert close(constant_factor(), independent(a0 * fx.DENSITY * PER_UM2))
    fields, columns = rf.differing(arm("constant")[1], arm("scheduled")[1])
    assert not fields and not columns, dict(state_fields=fields, observation_columns=columns)
    fields, _ = rf.differing(arm("constant")[1], arm("unscaled")[1])
    assert fields  # Non-vacuous: the factor reaches @3's step.


def test_a_varying_source_is_read_current_at_the_control_view():
    spec, result = arm("varying")
    a0, area, row = declared(spec)
    _, p = get_model(spec.model).initial_values(spec)
    reference = np.asarray(p.amount_reference)[row, 0]
    history = result.history
    units = [
        Decimal(repr(a0 * area * fx.DENSITY)) + Decimal(repr(float(dn)))
        for dn in np.asarray(history.population_abundance_increment)[:, 0]
    ]
    amounts = [
        Decimal(repr(float(reference))) + Decimal(repr(float(x)))
        for x in np.asarray(history.amount_increment)[:, row, 0]
    ]
    per_um2 = Decimal(repr(PER_UM2)) / Decimal(repr(area))
    observed = np.asarray(result.observations.coupling_factor)[:, 0]
    assert len(observed) == len(units) == STEPS + 1
    for k, n in enumerate(units):  # The observed factor at each row's own units.
        assert close(observed[k], independent(n * per_um2)), k
    applied = np.asarray(history.coupling_applied_factor)[:, 0]
    for k in range(1, STEPS + 1):  # The applied factor at the control view of step k.
        assert close(applied[k], independent(half_step(units[k - 1], amounts[k - 1]) * per_um2)), k
    assert applied[-1] - applied[1] > 0.1  # Non-vacuous: the source moved.


def half_step(units, amount):
    """kir_0's units after the producer's first half-step from a row: the direct route's closed
    form, dN/dt = c k_a n - k_r N with dn/dt = -k_a n, over h = dt / 2 (c = N_A 1e-15 / nu units
    per fmol)."""
    with localcontext() as context:
        context.prec = 50
        k_a, k_r = (Decimal(repr(v)) for v in RATES)
        h = Decimal(repr(DT)) / 2
        c = Decimal("6.02214076e23") * Decimal("1e-15") / NU
        decay_a, decay_r = (-k_a * h).exp(), (-k_r * h).exp()
        return units * decay_r + c * k_a * amount * (decay_a - decay_r) / (k_r - k_a)
