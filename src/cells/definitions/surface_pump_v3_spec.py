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

Seam D (docs/CORE_SEAMS_DESIGN.md §6.1-6.2): an optional model key ``heat_bookings``, {mover class:
booking ID}, picks the heat booking of @3's other mover classes (``channels``, ``membranes``,
``pumps``, ``calcium_pumps``) and of each declared kind's routes (by the kind's namespaced ID),
beyond the tableau, which books every class by default and is never listed. Each class admits what
models/inner_laws.OWN_HEAT_BOOKINGS (or the kind's heat_bookings) lists:
``trapezoid_nonnegative@1``, booked once in the core for every class
(models/surface_pump_v3.trapezoid_fields), and, for ``faces`` alone, ``exact_free_energy_heat@1``
(D280): each face books the exact free-energy release of the neutral rows it moves, and a face that
carries a charged row, touches a held bath, or carries a row another mover moves in the step, is
refused under it (models/surface_pump_v3.exact_face_heat). Junctions keep ``junction_heat_booking``
and are refused here. The key is omitted at its default, so every definition of today's keeps its
fingerprint and its structure. The water and replacement families run @3 through compositions whose
inner carries the structure, so they book what is picked as well (the lead, 19 November 2026); a
caller that checks @3 without its structure refuses a booking rather than ignore it.

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
from typing import ClassVar

import numpy as np

from cells.definitions import surface_kinetic_spec as kinetic
from cells.definitions import surface_pump_spec as first
from cells.definitions import surface_pump_v2_spec as second
from cells.definitions import surface_tissue_spec as tissue
from cells.definitions.spec_values import fraction, identifier
from cells.definitions.specs import ConfigError, ExtracellularFaceSpec, _fields, _integer, _number
from cells.laws.junctions import junction_gate
from cells.laws.junctions import junction_series_gates as series_gates
from cells.laws.routes import logmean_electrodiffusion_forms as forms_law
from cells.numerics import surface_imex as imex
from cells.numerics.surface_field import SPARSE_SOLVER_ID
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
# Seam D's exact booking for @3's faces (D280; INNER_MODEL_V4_DESIGN §7.5's name and version 1).
EXACT_FREE_ENERGY_HEAT = "exact_free_energy_heat@1"
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


SPECIES_VALENCE = {"Na": 1, "K": 1, "Cl": -1}  # Cl⁻ for clleak_always_open@1 (D228 item 3).
CHANNEL_FIELDS = set(kinetic.ChannelPopulation.__dataclass_fields__)
# B1's door (docs/CORE_SEAMS_DESIGN.md §4.3): a population's optional factor sources, parsed beside
# the shared ChannelPopulation dataclass (whose fields and fingerprints other families share).
CHANNEL_FACTORS = "factors"
_NONE = object()  # A channel entry without factors.
# The model fields @3's parse sets itself; the others are the @2 base's.
OWN_FIELDS = (
    "channels",
    "junction_heat_booking",
    "species_registry",
    "kinds",
    "heat_bookings",
    "forms_faces",
)
HEAT_BOOKINGS_KEY = "heat_bookings"  # Seam D's model key (module docstring).
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
    # Seam D's picks (docs/CORE_SEAMS_DESIGN.md §6.1): ((mover class, booking ID), ...), sorted by
    # class, the tableau never listed; () for every definition of today's, and then to_dict
    # writes nothing. Held by the structure (InnerStructure.heat_bookings), never by the layout.
    heat_bookings: tuple = ()
    # The faces of logmean_electrodiffusion_forms@1 (FormsFace), in declared order: their own
    # entity set, never in `faces` or its arrays; () for every definition of today's, and then
    # to_dict writes nothing, so fingerprints are unchanged.
    forms_faces: tuple = ()


@dataclass(frozen=True)
class FormsFace(ExtracellularFaceSpec):
    """A face of logmean_electrodiffusion_forms@1 (laws/routes/logmean_electrodiffusion_forms):
    today's face fields, one diffusivity per species. The base families parse and check it as its
    degenerate plain face (surface_tissue_spec.admitting_faces); @3 holds it in forms_faces."""

    LAW: ClassVar[str] = forms_law.LAW_ID


FORMS_FACE_SOLVERS = (imex.EULER_ID, imex.ARS222_ID)
FORMS_FACE_SOLVER_REFUSAL = (
    f"{forms_law.LAW_ID} runs on the plain IMEX tableaux in version 1 "
    f"({', '.join(FORMS_FACE_SOLVERS)}): RK4 and N2 refuse it"
)
# FR-17 stage 1 (D317): @3 admits the sparse field solver (surface_field.SPARSE_SOLVER_ID), and
# the models that parse through it do; @1's and @2's parses refuse it. In its first stage it runs
# the plain IMEX tableaux alone, with plain faces: RK4, N2's implicit conductances (a dense
# conductance Laplacian) and the forms faces (a dense forms Laplacian) are refused under it, as is
# any field-input provider (pump_composite_adapter.check_field_inputs).
SPARSE_FIELD_SOLVERS = (imex.EULER_ID, imex.ARS222_ID)
SPARSE_FIELD_REFUSAL = (
    f"{SPARSE_SOLVER_ID} runs the plain IMEX tableaux ({', '.join(SPARSE_FIELD_SOLVERS)}) "
    "with plain faces in its first stage (FR-17): RK4, N2's implicit conductances and "
    f"{forms_law.LAW_ID} are refused under it"
)


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
    if m.forms_faces:  # Their own entity set, written after today's faces with their law.
        for face in m.forms_faces:
            row = asdict(face)
            row["diffusivity_m2_per_s"] = dict(
                zip(m.species_ids, face.diffusivity_m2_per_s, strict=True)
            )
            row["law"] = forms_law.LAW_ID
            raw["model"]["faces"].append(row)
    raw["model"]["channels"] = [channel_to_dict(p) for p in m.channels]
    if m.junction_heat_booking != DEFAULT_JUNCTION_HEAT:
        raw["model"]["junction_heat_booking"] = m.junction_heat_booking
    if m.heat_bookings:  # Seam D: omitted at its default, so fingerprints are unchanged.
        raw["model"][HEAT_BOOKINGS_KEY] = dict(m.heat_bookings)
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


def _heat_bookings(given, solver):
    """The model's heat_bookings key (module docstring) as ((mover class, booking ID), ...),
    sorted: a mapping of class names to booking IDs. Junctions book through junction_heat_booking;
    the tableau is the default and is never listed; any other booking needs an IMEX solver. Which
    class admits which booking is the structure's check (models/inner_laws.heat_booking_errors),
    run with the declared kinds at check_definition."""
    if not isinstance(given, dict) or not all(
        isinstance(k, str) and k and isinstance(v, str) and v for k, v in given.items()
    ):
        raise ConfigError("heat_bookings maps mover classes to booking IDs (names)")
    if "junctions" in given:
        raise ConfigError(
            "Junctions book their heat through junction_heat_booking, not heat_bookings"
        )
    listed = sorted(k for k, v in given.items() if v == DEFAULT_JUNCTION_HEAT)
    if listed:
        raise ConfigError(
            f"heat_bookings: the tableau ({DEFAULT_JUNCTION_HEAT}) is the default; leave "
            + ", ".join(listed)
            + " out"
        )
    if given and solver == "rk4":
        raise ConfigError("A heat booking option requires an IMEX solver")
    return tuple(sorted(given.items()))


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
        if schedule is None:  # None of its keys given and no schedule: today's records.
            continue
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


# --- FR-30 (D262): junctions whose gate is junction_series_gates@1, development only ----------

SERIES_GATE_LAW_ID = series_gates.LAW_ID
SERIES_DEVELOPMENT = (
    f"{SERIES_GATE_LAW_ID} is development only until a voltage series qualifies it: its "
    "junction's gate declares development: true, and a registered or judged result whose "
    "definition carries it is not admissible (D262)"
)


def series_gate_parameters(gate):
    """A parsed SeriesGate's parameters as its kind's NamedTuple (the law's own types)."""
    kind_type = {
        "threshold_relaxation": junction_gate.Parameters,
        "boltzmann_eyring": series_gates.BoltzmannEyring,
    }[gate.kind]
    return kind_type(*gate.parameters)


def parse_series_gate(block):
    """A junction_series_gates@1 gate block: {law, development: true, gates: [fast, slow]}, each
    gate {kind, its kind's parameters by name, initial}. Returns @1's admission tuple: the
    junction's minimum and initial conductance (the products of the gates' residuals and initial
    factors), its class and its extra fields. Every gate lies on the law's own domain at 0 V."""
    _fields(block, {"law", "development", "gates"}, "series junction gate")
    if block["development"] is not True:
        raise ConfigError(SERIES_DEVELOPMENT)
    raw = block["gates"]
    if type(raw) is not list or len(raw) != series_gates.GATE_COUNT:
        raise ConfigError(
            f"A series junction declares its {series_gates.GATE_COUNT} gates "
            f"({', '.join(series_gates.GATES)}) as a list"
        )
    gates = []
    for name, g in zip(series_gates.GATES, raw, strict=True):
        if not isinstance(g, dict) or g.get("kind") not in series_gates.KINDS:
            raise ConfigError(
                f"Series junction gate {name}'s kind is one of {', '.join(series_gates.KINDS)}"
            )
        names = kinetic.series_parameter_names(g["kind"])
        _fields(g, {"kind", "initial", *names}, f"series junction gate {name}")
        values = tuple(_number(g[k], f"series junction gate {name}'s {k}") for k in names)
        gates.append(kinetic.SeriesGate(g["kind"], values, _number(g["initial"], "initial")))
    kinds = tuple(g.kind for g in gates)
    parameters = tuple(series_gate_parameters(g) for g in gates)
    initial = tuple(np.asarray(g.initial, dtype=float) for g in gates)
    if not bool(
        series_gates.domain_valid(
            initial, np.asarray(0.0), parameters, np.asarray(1.0), kinds=kinds, xp=np
        )
    ):
        raise ConfigError(
            "A series junction's gates lie on the law's domain: each parameter finite and in "
            "range, and each initial factor in [its residual, 1] (the law's domain_valid)"
        )
    pairs = zip(kinds, parameters, strict=True)
    residuals = [series_gates.residual_of(kind, values) for kind, values in pairs]
    return (
        float(np.prod(residuals)),
        float(np.prod([g.initial for g in gates])),
        kinetic.SeriesJunction,
        dict(gates=tuple(gates), development=True),
    )


def series_junction_errors(model):
    """v1's refusals for series junctions (D262), at parse: a world's junctions all take one gate
    law; and a series junction carries no neutral species, since its factor is the ionic
    conductance, while a neutral species needs its own route factor (its residuals per gate,
    FR-30 design §7), which is not built."""
    series = [j for j in model.junctions if isinstance(j, kinetic.SeriesJunction)]
    if not series:
        return
    if len(series) != len(model.junctions):
        raise ConfigError(
            f"A world's junctions take one gate law: {SERIES_GATE_LAW_ID} on every junction or "
            "on none (v1, D262)"
        )
    kinds = {tuple(g.kind for g in j.gates) for j in series}
    if len(kinds) != 1:
        raise ConfigError(
            f"A world's {SERIES_GATE_LAW_ID} junctions declare the same kind for each gate (v1)"
        )
    neutral = [z == 0 for z in model.valence]
    for j in series:
        carried = sorted(
            s
            for s, z0, value in zip(model.species_ids, neutral, j.permeability_m_per_s, strict=True)
            if z0 and value
        )
        if carried:
            raise ConfigError(
                f"Junction {j.id} ({SERIES_GATE_LAW_ID}) carries neutral species {carried}: its "
                "factor is the ionic conductance, and a neutral species needs its own route "
                "factor (its residuals per gate), which is not built (v1, D262)"
            )


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
    heat_bookings = _heat_bookings(m.pop(HEAT_BOOKINGS_KEY, {}), x.get("solver"))
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
    # N2 (D235): the implicit-conductance IDs are admitted wherever the ionic step is @3's, so by
    # this parse: @3 itself and the models that parse through it (water@1, the composite), the
    # intended scope. @2's parse validates ARS(2,2,2), their tableau, and the ID returns to the
    # execution below; @1 and @2 refuse it themselves.
    solver = x.get("solver")
    if solver in imex.IMPLICIT_CONDUCTANCE_IDS:
        x["solver"] = imex.ARS222_ID
    # The forms law (logmean_electrodiffusion_forms@1): @3 alone admits it on faces. The base
    # families parse and check each forms face as its degenerate plain face, so the declared
    # face_capacity, which counts today's faces, is widened for their parse alone; the forms faces
    # then leave `faces` for their own entity set (forms_faces).
    declared_faces = x.get("face_capacity")
    faces = m.get("faces")  # A malformed list is the base parse's to refuse.
    forms_count = sum(
        1
        for f in (faces if isinstance(faces, list) else ())
        if isinstance(f, dict) and f.get("law") == forms_law.LAW_ID
    )
    if forms_count and type(declared_faces) is int:
        x["face_capacity"] = declared_faces + forms_count
    if x.get("field_solver") == SPARSE_SOLVER_ID and (
        solver not in SPARSE_FIELD_SOLVERS or forms_count
    ):
        raise ConfigError(SPARSE_FIELD_REFUSAL)
    # FR-30 (D262): @3 alone admits junction_series_gates@1; @1's and @2's parses refuse it.
    with first.admitting({SERIES_GATE_LAW_ID: parse_series_gate}):
        with tissue.admitting_faces({forms_law.LAW_ID: FormsFace}):
            with first.admitting_field_solvers((SPARSE_SOLVER_ID,)):
                base = second.parse(raw)
    series_junction_errors(base.model)
    forms_faces = tuple(f for f in base.model.faces if type(f) is FormsFace)
    if forms_faces:
        plain = tuple(f for f in base.model.faces if type(f) is not FormsFace)
        if declared_faces < len(plain):
            raise ConfigError("face_capacity must hold every face of logmean_electrodiffusion@1")
        if solver not in FORMS_FACE_SOLVERS:
            raise ConfigError(FORMS_FACE_SOLVER_REFUSAL)
        base = replace(
            base,
            model=replace(base.model, faces=plain),
            execution=replace(base.execution, face_capacity=declared_faces),
        )
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
            *forms_faces,
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
        heat_bookings=heat_bookings,
        forms_faces=forms_faces,
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
    if solver in imex.IMPLICIT_CONDUCTANCE_IDS:
        execution = replace(execution, solver=solver)
    spec = replace(base, model=model, experiment=experiment, execution=execution)
    from cells.models.surface_pump_v3 import check_definition, structure

    if forms_faces and any(
        kind_registry.active().lookup(kind_id).stage_read is not None
        and getattr(declaration, "read_id", None) != forms_law.CLOSURE_READ_ID
        for kind_id, declaration in model.kinds
    ):  # Ahead of the registry's closure checks: the forms read is the general closure's.
        raise ConfigError(
            f"{forms_law.LAW_ID} faces read the general closure ({forms_law.CLOSURE_READ_ID}) "
            "alone: beside another stage read they are refused (version 1)"
        )
    registry.check_definition(spec)  # Ahead of @3's own checks, so its refusals come first.
    try:
        # A definition that declares kinds is checked by its structure's own functions (§7.4 (k)),
        # and so is one whose channels declare factors (binding resolves their sources, B1) or
        # name a law beyond today's five (the full catalogue's domain refuses its code).
        declared = (
            spec.model.kinds
            or channel_factors(spec.model)
            or any(c.kinetic_law not in LAW_CODES for c in spec.model.channels)
            or spec.model.heat_bookings  # Seam D: the structure holds the picks.
            or any(isinstance(j, kinetic.SeriesJunction) for j in spec.model.junctions)  # FR-30.
            or spec.model.forms_faces  # The forms law: their own entity set (the structure's).
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
