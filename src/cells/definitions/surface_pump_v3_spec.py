"""resolved_pump_tissue@3: resolved_pump_tissue@2 plus voltage-gated channel populations.

Every field of resolved_pump_tissue@2 keeps its meaning and is parsed by that
identity's parser. The model adds ``channels``: populations on named membrane
patches, each with one law of CHANNEL_LAWS, a maximal permeability (m/s), an
abundance, its law's gate state and its law's permeant ion (the shared-gate
population format of resolved_tissue@5 and later). The experiment adds
``channel_controls`` (one availability schedule per population) and the
execution ``channel_capacity``. With no channels the identity reproduces
resolved_pump_tissue@2.

A channel population's entry may declare ``factors``, a list of factor-source IDs
in declared order (docs/CORE_SEAMS_DESIGN.md §4.3, B1's routing door into @3): at
each stage its availability is the held value times its sources' factors, a left
fold, as a passive route's multiplier is (docs/INNER_MODEL_V4_DESIGN.md §7.4 (n)).
The sources are declared kinds'. Such a population parses as a
FactoredChannelPopulation, the shared ChannelPopulation with its factors; every
other population, the definition and its fingerprint are today's, and the model
gains no field (other families build their models from its fields by name).

An optional model key ``junction_heat_booking`` selects how IMEX steps book
junction heat. The default, ``explicit_tableau`` (omitted from definitions, so
default fingerprints are unchanged), books it with the tableau's explicit
weights like every other route. ``trapezoid_nonnegative@1`` books
dt (q_start + q_end) / 2 from the junction powers at the step's start and end
states, which cannot be negative; trajectories and every other booking are the
default's (models/surface_pump_v3.imex_step).

The gate laws are the existing Cells kinetics under neutral IDs (the stage-B
proposals in stage-b-plan-20261108-01): Kv1.5 m*h (laws/channels/voltage_gates.py),
Kir2.1 m*h^2 (laws/channels/potassium_channels.py) and NaV1.2 m^3*h
(laws/channels/sodium_channels.py), whose rate laws and coefficients come from the
BETSE v1.5.0 channel library, plus always-open K and Na leaks, which carry no
gate state here. Like their source laws, the gates have no temperature term:
the declared temperature (the pump law's 200-400 K domain, as in @1 and @2)
enters the constant-field flux, the affinities and the pumps only.
"""

import copy
from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields, replace

import numpy as np

from cells.definitions import surface_kinetic_spec as kinetic
from cells.definitions import surface_pump_spec as first
from cells.definitions import surface_pump_v2_spec as second
from cells.definitions.spec_values import fraction, identifier
from cells.definitions.specs import ConfigError, _fields, _integer, _number
from cells.registry import kind_registry
from cells.registry import species_registry as registry

MODEL_ID = "resolved_pump_tissue@3"
KV1P5_LAW_ID = "kv1p5_mh@1"
KIR2P1_LAW_ID = "kir2p1_mh2@1"
NAV1P2_LAW_ID = "nav1p2_m3h_regularized@1"
KLEAK_LAW_ID = "kleak_always_open@1"
NALEAK_LAW_ID = "naleak_always_open@1"
DEFAULT_JUNCTION_HEAT = "explicit_tableau"
TRAPEZOID_JUNCTION_HEAT = "trapezoid_nonnegative@1"
JUNCTION_HEAT_BOOKINGS = (DEFAULT_JUNCTION_HEAT, TRAPEZOID_JUNCTION_HEAT)
# Today's five channel laws, the full catalogue's (structure None), by name: codes 0-2 are those of
# laws/channels/sodium_channels.LAW_CODES, whose dispatch that path reuses; 3 and 4 are gate-free
# leaks. Padding slots are inactive, not a code. The full-catalogue dispatch, its domain and the
# replacement operator's tables are sized and checked by these five, so a law the registry adds
# (a code from 5) never reaches them. What a definition may name is the law registry's: law_codes,
# law_permeabilities and gate_counts below. LAW_CODES, LAW_PERMEABILITIES and GATE_COUNTS are
# these five's rows of those tables, read from the registry on use (the Kv1 trigger, the lead's
# ruling of 19 November 2026), so the law modules' declarations are their one source.
TODAYS_CHANNEL_LAWS = (KV1P5_LAW_ID, KIR2P1_LAW_ID, NAV1P2_LAW_ID, KLEAK_LAW_ID, NALEAK_LAW_ID)
GATED_CODES = 3  # Codes below this have two relaxation gates (m, h).


class _TodaysLaws(Mapping):
    """{one of today's five channel laws: its row of a law-registry table}, in TODAYS_CHANNEL_LAWS'
    order (code order), read from the active law registry on each use and never at import:
    models/inner_laws, which registers the five, imports this module. Membership and size are
    the five names' alone, so a law the registry adds is never one of them."""

    def __init__(self, name, table):
        self._name, self._table = name, table

    def _rows(self):
        rows = self._table()
        missing = [law for law in TODAYS_CHANNEL_LAWS if law not in rows]
        if missing:
            raise KeyError(f"{self._name}: the active law registry lacks {', '.join(missing)}")
        return {law: rows[law] for law in TODAYS_CHANNEL_LAWS}

    def __getitem__(self, law):
        if law not in TODAYS_CHANNEL_LAWS:
            raise KeyError(law)
        return self._rows()[law]

    def __iter__(self):
        return iter(TODAYS_CHANNEL_LAWS)

    def __len__(self):
        return len(TODAYS_CHANNEL_LAWS)

    def __contains__(self, law):
        return law in TODAYS_CHANNEL_LAWS

    def __repr__(self):
        return f"{self._name}({self._rows()!r})"


LAW_CODES = _TodaysLaws("LAW_CODES", lambda: law_codes())
LAW_PERMEABILITIES = _TodaysLaws("LAW_PERMEABILITIES", lambda: law_permeabilities())
GATE_COUNTS = _TodaysLaws("GATE_COUNTS", lambda: gate_counts())


def channel_laws():
    """{law ID: declaration} of the channel laws @3 runs, in code order: the active law
    registry's laws of cells.channel_law@1 hosted by @3 (docs/CORE_SEAMS_DESIGN.md §8.3). Read at
    parse time, never at import (models/inner_laws, which registers today's five, imports this
    module)."""
    from cells.registry import laws as law_registry

    hosted = law_registry.active().laws(law_registry.CHANNEL_LAW, kind_registry.qualified(MODEL_ID))
    return {law.law_id: law for law in sorted(hosted, key=lambda law: law.code)}


def law_codes():
    """{law ID: registry code} of the channel laws @3 runs (channel_laws)."""
    return {law_id: law.code for law_id, law in channel_laws().items()}


def law_permeabilities():
    """{law ID: ((species, relative permeability), ...)} from each law's permeant ions."""
    return {
        law_id: tuple((species, weight) for species, _, weight in law.permeant)
        for law_id, law in channel_laws().items()
    }


def gate_counts():
    """{law ID: its gate count} (0 for a gate-free law)."""
    return {law_id: len(law.gates) for law_id, law in channel_laws().items()}


SPECIES_VALENCE = {"Na": 1, "K": 1}
CHANNEL_FIELDS = set(kinetic.ChannelPopulation.__dataclass_fields__)
# B1's door (docs/CORE_SEAMS_DESIGN.md §4.3): a population's optional factor sources, parsed beside
# the shared ChannelPopulation dataclass (whose fields and fingerprints other families share).
CHANNEL_FACTORS = "factors"
_NONE = object()  # A channel entry without factors.
# The model fields @3's parse sets itself; the others are the @2 base's.
OWN_FIELDS = ("channels", "junction_heat_booking", "species_registry", "kinds")
Control = second.Control  # The channel field is filled; absent slots stay zero.


@dataclass(frozen=True)
class SurfacePumpChannelModel:
    species_ids: tuple[str, ...]
    valence: tuple[int, ...]
    temperature_K: float
    cells: tuple
    extracellular: tuple
    membranes: tuple[second.Membrane, ...]
    junctions: tuple[kinetic.Junction, ...]
    faces: tuple
    gauge_reference: str | None
    channels: tuple[kinetic.ChannelPopulation, ...]
    junction_heat_booking: str = DEFAULT_JUNCTION_HEAT
    # The species registry the model declares (core/species_registry.Declared), or None: then
    # to_dict writes nothing, so every definition without one keeps its fingerprint
    # (docs/INNER_MODEL_V4_DESIGN.md §7.4 (f) 7).
    species_registry: object = None
    # Declared kinds (docs/INNER_MODEL_V4_DESIGN.md §7.4 (j), (k)): ((namespaced kind ID, its
    # parsed declaration), ...) in canonical order; () for every definition of today's, and then
    # to_dict writes nothing, so fingerprints are unchanged.
    kinds: tuple = ()


@dataclass(frozen=True)
class KindChange(second.Change):
    """@2's change record plus each scheduled kind's values at its time (§7.4 (l))."""

    kinds: tuple  # One Schedule.at(time) per entry of Experiment.kinds, in canonical order.


@dataclass(frozen=True)
class Experiment(second.Experiment):
    """@2's experiment with populated channel schedules (one per population).

    kinds: the declared kinds' parsed schedules (docs/INNER_MODEL_V4_DESIGN.md §7.4 (l)), ((kind
    ID, kind_registry.Schedule), ...) in canonical order, for the declared kinds that declare
    experiment keys; () for every other definition, whose change records stay today's, by value
    and type. With a schedule, the change times also hold its breakpoints (so each is a step
    boundary: core/grid.EventGrid) and each record is a KindChange carrying its values (so
    branch_checkpoint refuses a branch that rewrites them before its checkpoint).
    """

    kinds: tuple = field(default=(), kw_only=True)

    def _held_availabilities(self):
        held = super()._held_availabilities()
        if not self.kinds:
            return held  # Today's records.
        clock = [c.time for c in held]
        times = sorted({*clock, *(t for _, schedule in self.kinds for t in schedule.times)})
        names = [f.name for f in fields(second.Change) if f.name != "time"]
        return tuple(
            KindChange(
                time,
                **{name: getattr(held[bisect_right(clock, time) - 1], name) for name in names},
                kinds=tuple(schedule.at(time) for _, schedule in self.kinds),
            )
            for time in times
        )


def projection(spec):
    """The resolved_pump_tissue@2 part of a definition (no channel populations)."""
    m, e = spec.model, spec.experiment
    model = second.SurfacePumpModel(
        **{
            k: getattr(m, k)
            for k in second.SurfacePumpModel.__dataclass_fields__
            if k != "channels"
        }
    )
    experiment = second.Experiment(
        **{k: getattr(e, k) for k in second.Experiment.__dataclass_fields__ if k != "channels"},
        channels=(),
    )
    return replace(
        spec,
        model=model,
        experiment=experiment,
        execution=replace(spec.execution, channel_capacity=0),
    )


def parse_channel(raw, ids, z, membranes):
    _fields(raw, CHANNEL_FIELDS, "channel")
    law = raw["kinetic_law"]
    permeabilities, gates = law_permeabilities(), gate_counts()  # The registry's (§8.3).
    if type(law) is not str or law not in gates or type(raw["permeant_ions"]) is not list:
        raise ConfigError("Channel requires a resolved_pump_tissue@3 law and permeant ions")
    ions = []
    for ion in raw["permeant_ions"]:
        _fields(ion, set(kinetic.PermeantIon.__dataclass_fields__), "permeant ion")
        species = identifier(ion["species_id"])
        weight = _number(ion["relative_permeability"], "relative permeability")
        if species not in ids or z[ids.index(species)] != SPECIES_VALENCE.get(species):
            raise ConfigError("Channel ion requires its law's species and valence")
        ions.append(kinetic.PermeantIon(species, weight))
    if tuple((i.species_id, i.relative_permeability) for i in ions) != permeabilities[law]:
        raise ConfigError("Channel ions must exactly match the named law's permeability ratios")
    patch = identifier(raw["membrane_id"])
    if (
        patch not in membranes
        or type(raw["initial_gate"]) is not list
        or len(raw["initial_gate"]) != gates[law]
    ):
        raise ConfigError("Channel requires its patch and exactly its law's gate state")
    return kinetic.ChannelPopulation(
        identifier(raw["id"]),
        patch,
        law,
        _number(raw["max_permeability_m_per_s"], "channel permeability"),
        _number(raw["abundance"], "channel abundance"),
        tuple(fraction(v, "initial channel gate") for v in raw["initial_gate"]),
        tuple(ions),
    )


@dataclass(frozen=True)
class FactoredChannelPopulation(kinetic.ChannelPopulation):
    """A channel population whose entry declares factors (B1's door, docs/CORE_SEAMS_DESIGN.md
    §4.3): the shared ChannelPopulation with its factor-source IDs, in declared order. A population
    without factors stays a ChannelPopulation, so its form and fingerprint are today's."""

    factors: tuple[str, ...] = ()


def factored(channel, factors):
    """The population as a FactoredChannelPopulation with these factors."""
    values = {f.name: getattr(channel, f.name) for f in fields(kinetic.ChannelPopulation)}
    return FactoredChannelPopulation(**values, factors=tuple(factors))


def channel_factors(model):
    """((slot, channel ID, (factor-source ID, ...)), ...) of the model's factored populations, in
    channel order; () for every definition of today's (B1's door)."""
    return tuple(
        (slot, c.id, c.factors)
        for slot, c in enumerate(getattr(model, "channels", ()))
        if getattr(c, "factors", ())
    )


def _factor_sources(given, channel_id):
    """A population's factors (B1's door): a non-empty list of distinct factor-source IDs."""
    if (
        not isinstance(given, list)
        or not given
        or any(not isinstance(f, str) or not f for f in given)
        or len(set(given)) != len(given)
    ):
        raise ConfigError(
            f"Channel {channel_id}: factors is a non-empty list of distinct factor-source IDs "
            "(omit it for none)"
        )
    return tuple(given)


def channel_to_dict(p):
    if type(p) not in (kinetic.ChannelPopulation, FactoredChannelPopulation) or any(
        type(i) is not kinetic.PermeantIon for i in p.permeant_ions
    ):
        raise ConfigError("Require explicit immutable channel population types")
    out = asdict(p) | {
        "initial_gate": list(p.initial_gate),
        "permeant_ions": [asdict(i) for i in p.permeant_ions],
    }
    if type(p) is FactoredChannelPopulation:  # B1's door: its factors, in declared order.
        out[CHANNEL_FACTORS] = list(p.factors)
    return out


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    if (
        type(m) is not SurfacePumpChannelModel
        or type(e) is not Experiment
        or type(x) is not kinetic.Execution
    ):
        raise ConfigError("Resolved pump tissue @3 requires its own model and experiment")
    raw = second.to_dict(projection(spec))
    raw["model"]["id"] = MODEL_ID
    raw["model"]["channels"] = [channel_to_dict(p) for p in m.channels]
    if m.junction_heat_booking != DEFAULT_JUNCTION_HEAT:
        raw["model"]["junction_heat_booking"] = m.junction_heat_booking
    if m.species_registry is not None:  # The registry's keys, back on their entries.
        species, keys = registry.to_entries(m.species_registry)
        for entry in raw["model"]["species"]:
            entry.update(species.get(entry["id"], {}))
        raw["model"].update(keys)
    for kind_id, declaration in m.kinds:  # Each declared kind's model key (§7.4 (k)).
        kind = kind_registry.active().lookup(kind_id)
        raw["model"][kind.model_key] = kind.to_dict(declaration)
    raw["experiment"]["channel_controls"] = [
        dict(channel_id=p.id, schedule=[asdict(c) for c in g])
        for p, g in zip(m.channels, e.channels, strict=True)
    ]
    declarations = dict(m.kinds)
    for kind_id, schedule in e.kinds:  # §7.4 (l): each scheduled kind's experiment keys.
        kind = kind_registry.active().lookup(kind_id)
        written = kind.schedule_to_dict(schedule, declarations[kind_id])
        if not set(written) <= set(kind.experiment_keys):
            raise ConfigError(f"Kind {kind_id}'s schedule_to_dict writes keys it does not declare")
        raw["experiment"].update(written)
    raw["execution"]["channel_capacity"] = x.channel_capacity
    return raw


def _kind_schedules(registry, declared, given, base):
    """((kind ID, Schedule), ...): each declared kind with experiment keys parses its schedule from
    the keys the definition gives (its default where none), in canonical order (§7.4 (l)); every
    breakpoint lies within the horizon."""
    out = []
    for kind_id, declaration in declared:
        kind = registry.lookup(kind_id)
        if not kind.experiment_keys:
            continue
        schedule = kind.parse_schedule(given.get(kind_id, {}), base, declaration)
        if type(schedule) is not kind_registry.Schedule:
            raise ConfigError(f"Kind {kind_id}'s parse_schedule must return a Schedule")
        end = base.experiment.end_time
        if schedule.times[-1] > end:
            raise ConfigError(
                f"Kind {kind_id}'s schedule has a breakpoint past the horizon "
                f"({schedule.times[-1]} > {end})"
            )
        out.append((kind_id, schedule))
    return tuple(out)


def parse(data):
    raw = copy.deepcopy(data)
    m, e, x = raw.get("model"), raw.get("experiment"), raw.get("execution")
    if (
        not isinstance(m, dict)
        or not isinstance(e, dict)
        or not isinstance(x, dict)
        or m.get("id") != MODEL_ID
    ):
        raise ConfigError("Require resolved_pump_tissue@3")
    if "channels" not in m or "channel_controls" not in e or "channel_capacity" not in x:
        raise ConfigError("Declare channels, channel_controls and channel_capacity")
    channels, controls = m.pop("channels"), e.pop("channel_controls")
    capacity = x.pop("channel_capacity")
    booking = m.pop("junction_heat_booking", DEFAULT_JUNCTION_HEAT)
    if type(booking) is not str or booking not in JUNCTION_HEAT_BOOKINGS:
        raise ConfigError("junction_heat_booking must be " + " or ".join(JUNCTION_HEAT_BOOKINGS))
    if booking != DEFAULT_JUNCTION_HEAT and x.get("solver") == "rk4":
        raise ConfigError("A junction-heat booking option requires an IMEX solver")
    if type(channels) is not list:
        raise ConfigError("channels requires an explicit list")
    # B1's door: each entry's factors leave this copy before the strict channel parse.
    popped = [c.pop(CHANNEL_FACTORS, _NONE) if isinstance(c, dict) else _NONE for c in channels]
    # The registry hook (§7.4 (f) 7): the registry's keys leave this copy's species entries and
    # model block before @2's strict species parse; None when the model declares none.
    declared = registry.parse_entries(m)
    # Declared kinds (§7.4 (k)): each registered kind's model key leaves this copy before @2's
    # strict parse; its entries are parsed with the base definition below.
    kinds = kind_registry.active()
    pending = {key: (kind, m.pop(key)) for key, kind in kinds.model_keys().items() if key in m}
    # §7.4 (l): a declared kind's experiment keys (its schedule) leave the experiment too; a
    # registered kind's experiment key without its model key is refused.
    given = {}
    for key, kind in kinds.experiment_keys().items():
        if key not in e:
            continue
        if kind.model_key not in pending:
            raise ConfigError(
                f"Experiment key {key!r} belongs to kind {kind_registry.qualified(kind.kind_id)}, "
                f"which the model does not declare (model key {kind.model_key!r})"
            )
        given.setdefault(kind_registry.qualified(kind.kind_id), {})[key] = e.pop(key)
    m["id"] = second.MODEL_ID
    base = second.parse(raw)
    ids, z = base.model.species_ids, base.model.valence
    parsed = tuple(parse_channel(c, ids, z, {p.id for p in base.model.membranes}) for c in channels)
    parsed = tuple(
        c if given is _NONE else factored(c, _factor_sources(given, c.id))
        for c, given in zip(parsed, popped, strict=True)
    )
    model = base.model
    names = [
        p.id
        for p in (
            *model.cells,
            *model.extracellular,
            *model.membranes,
            *model.junctions,
            *model.faces,
            *(p.pump for p in model.membranes if p.pump is not None),
            *(p.calcium_pump for p in model.membranes if p.calcium_pump is not None),
            *parsed,
        )
    ]
    if len(names) != len(set(names)):
        raise ConfigError("Owner, route, pump and channel IDs must be globally unique")
    schedules = first._schedules(
        controls, "channel", [c.id for c in parsed], base.experiment.end_time
    )
    model = SurfacePumpChannelModel(
        **{
            k: getattr(model, k)
            for k in SurfacePumpChannelModel.__dataclass_fields__
            if k not in OWN_FIELDS
        },
        channels=parsed,
        junction_heat_booking=booking,
        species_registry=declared,
        kinds=tuple(
            sorted(
                (
                    (kind_registry.qualified(kind.kind_id), kind.parse(entries, base))
                    for kind, entries in pending.values()
                ),
                key=lambda item: item[0],
            )
        ),
    )
    experiment = Experiment(
        **{
            k: getattr(base.experiment, k)
            for k in second.Experiment.__dataclass_fields__
            if k != "channels"
        },
        channels=tuple(schedules[c.id] for c in parsed),
        kinds=_kind_schedules(kinds, model.kinds, given, base),
    )
    execution = replace(
        base.execution,
        channel_capacity=_integer(capacity, "channel_capacity", minimum=len(parsed)),
    )
    spec = replace(base, model=model, experiment=experiment, execution=execution)
    from cells.models.surface_pump_v3 import check_definition, structure

    registry.check_definition(spec)  # Ahead of @3's own checks, so its refusals come first.
    try:
        # A definition that declares kinds is checked by its structure's own functions (§7.4 (k)),
        # and so is one whose channels declare factors (binding resolves their sources, B1) or
        # name a law beyond today's five (the full catalogue's domain refuses its code).
        declared = (
            spec.model.kinds
            or channel_factors(spec.model)
            or any(c.kinetic_law not in LAW_CODES for c in spec.model.channels)
        )
        check_definition(spec, structure=structure(spec.model) if declared else None)
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Invalid resolved pump @3 definition: " + str(error)) from error
    return spec


def control_values(spec, times):
    """resolved_pump_tissue@2 controls with the channel availabilities filled in."""
    base = second.control_values(projection(spec), times)
    changes = spec.experiment.changes
    clock = [c.time for c in changes]
    indices = np.searchsorted(clock, times, side="right") - 1
    values = np.asarray([c.channel for c in changes], dtype=np.float64)
    padded = np.zeros((len(times), spec.execution.channel_capacity))
    padded[:, : values.shape[-1]] = values[indices]
    result = base._replace(channel=padded)
    if not spec.model.kinds:
        return result
    # §7.4 (k): the declared kinds' controls follow today's, in the structure's Control type
    # (availabilities, rule (d)). §7.4 (l): each kind's controls are evaluated once per change
    # record, at the change times, and each row is held over the steps that record governs (the
    # families' own indices), so they are constant between change times on every path; a kind's
    # schedule breakpoints are change times (Experiment.kinds).
    from cells.models import surface_pump_v3 as inner

    structure = inner.structure(spec.model)
    control = inner.kind_types(structure).Control
    registry, entries, extra = kind_registry.active(), dict(structure.kinds), {}
    for kind_id, declaration in spec.model.kinds:  # Each bound to its entry's fields ((n) 5).
        kind = kind_registry.bound(registry.lookup(kind_id), entries[kind_id])
        if kind.control_fields:
            held = kind.control_values(spec, declaration, clock)
            kind_registry.refuse_foreign_writes(
                kind, "control_values", held, kind.control_fields, "control"
            )
            extra |= {name: np.asarray(value)[indices] for name, value in held.items()}
    return control(*result, *(extra[name] for name in control._fields[len(result) :]))
