"""cells.model.resolved_pump_tissue@3: cells.model.resolved_pump_tissue@2 plus voltage-gated channel populations.

Every field of cells.model.resolved_pump_tissue@2 keeps its meaning and is parsed by that
identity's parser. The model adds ``channels``: populations on named membrane
patches, each with one law of CHANNEL_LAWS, a maximal permeability (m/s), an
abundance, its law's gate state and its law's permeant ion (the shared-gate
population format of cells.model.resolved_tissue@8). The experiment adds
``channel_controls`` (one availability schedule per population) and the
execution ``channel_capacity``. With no channels the identity reproduces
cells.model.resolved_pump_tissue@2.

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
weights like every other route. ``cells.heat.trapezoid_nonnegative@1`` books
dt (q_start + q_end) / 2 from the junction powers at the step's start and end
states, which cannot be negative; trajectories and every other booking are the
default's (models/surface_pump_v3.imex_step).

Seam D (docs/CORE_SEAMS_DESIGN.md §6.1-6.2): an optional model key ``heat_bookings``, {mover class:
booking ID}, picks the heat booking of @3's other mover classes (``channels``, ``membranes``,
``pumps``, ``calcium_pumps``) and of each declared kind's routes (by the kind's namespaced ID),
beyond the tableau, which books every class by default and is never listed. Each class admits what
models/inner_laws.OWN_HEAT_BOOKINGS (or the kind's heat_bookings) lists:
``cells.heat.trapezoid_nonnegative@1``, booked once in the core for every class
(models/surface_pump_v3.trapezoid_fields), and, for ``faces`` alone, ``cells.heat.exact_free_energy_heat@1``
(D280): each face books the exact free-energy release of the neutral rows it moves, and a face that
carries a charged row, touches a held bath, or carries a row another mover moves in the step, is
refused under it (models/surface_pump_v3.exact_face_heat). Junctions keep ``junction_heat_booking``
and are refused here. The key is omitted at its default, so every definition of today's keeps its
fingerprint and its structure. The water and replacement families run @3 through compositions whose
inner carries the structure, so they book what is picked as well (the lead, 19 November 2026); a
caller that checks @3 without its structure refuses a booking rather than ignore it.

FR-50 phase 2 (D327; the registered protocol fr50-one-way-records-v1 §3): an optional model key
``one_way_records``, a list of ``{"entity", "id", "species"}`` entries, asks for one-way cumulative
records of @3's own routes: each entry names one entity that books a net record (``membrane``, a
patch's own permeability, membrane_transferred; ``junction``, junction_transferred; ``face``, a face
of today's law, face_transferred, uncharged rows only; ``channel``, a population,
channel_transferred) and the species it records. Each (entity, species) pair keeps a forward and a
backward record in its net record's orientation and the step rule's relative gap
(models/surface_pump_v3.own_one_way_records). Refused, each by name: a pump, a forms face, a charged
face row, a kind's route (its own one_way key), an unknown entity or species, a pair declared twice;
RK4, projective execution and the families with fixed internals at their own checks. The key is
omitted where none is declared, so every definition of today's keeps its form and fingerprint.

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
import math
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
from cells.laws.channels import open_channel_block as block_law
from cells.laws.junctions import junction_gate
from cells.laws.junctions import junction_series_gates as series_gates
from cells.laws.routes import logmean_electrodiffusion_forms as forms_law
from cells.numerics import surface_imex as imex
from cells.numerics.surface_field import SPARSE_SOLVER_ID
from cells.registry import kind_registry
from cells.registry import species_registry as registry

MODEL_ID = "cells.model.resolved_pump_tissue@3"
KV1P5_LAW_ID = "cells.channel.kv1p5_mh@1"
KIR2P1_LAW_ID = "cells.channel.kir2p1_mh2@1"
NAV1P2_LAW_ID = "cells.channel.nav1p2_m3h_regularized@1"
KLEAK_LAW_ID = "cells.channel.kleak_always_open@1"
NALEAK_LAW_ID = "cells.channel.naleak_always_open@1"
DEFAULT_JUNCTION_HEAT = "explicit_tableau"
TRAPEZOID_JUNCTION_HEAT = "cells.heat.trapezoid_nonnegative@1"
JUNCTION_HEAT_BOOKINGS = (DEFAULT_JUNCTION_HEAT, TRAPEZOID_JUNCTION_HEAT)
# Seam D's exact booking for @3's faces (D280; INNER_MODEL_V4_DESIGN §7.5's name and version 1).
EXACT_FREE_ENERGY_HEAT = "cells.heat.exact_free_energy_heat@1"
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


# The ions a channel law may carry on the charge rule alone; a law that carries any other, a scarce
# one, declares its material term (docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md §5.2).
MAJOR_IONS = ("Na", "K", "Cl")
CHANNEL_FIELDS = set(kinetic.ChannelPopulation.__dataclass_fields__)
# B1's door (docs/CORE_SEAMS_DESIGN.md §4.3): a population's optional factor sources, parsed beside
# the shared ChannelPopulation dataclass (whose fields and fingerprints other families share).
CHANNEL_FACTORS = "factors"
_NONE = object()  # A channel entry without factors, or without a block.
# FR-51 (D327): a population's optional open-channel block, popped before the strict parse as
# factors is. A population that declares neither stays a ChannelPopulation.
CHANNEL_BLOCK = "block"
BLOCK_KEYS = {"law", "blocker", "reference", "modes"}
BLOCKER_KEYS = {"id", "valence", "side", "concentration_mM"}
STEEPNESS_KEYS = ("electrical_distance", "effective_valence")  # Exactly one per mode (ruling 7).
REVERSAL_OF = "reversal_of"
BLOCK_N2_REFUSAL = (
    "An implicit-conductance solver (N2) beside a blocked channel population is refused: a "
    "negative slope in its operator could make it indefinite (FR-51, ruling 5)"
)
# FR-50 phase 2 (D327; fr50-one-way-records-v1 §3): @3's own one-way records (module docstring), an
# optional model key popped before the base's strict parse, as heat_bookings is. The entity kinds
# are sorted, the structure's order of its pairs (InnerStructure.one_way_records).
ONE_WAY_RECORDS_KEY = "one_way_records"
ONE_WAY_ENTITIES = ("channel", "face", "junction", "membrane")
ONE_WAY_ENTRY_KEYS = {"entity", "id", "species"}
# The model fields @3's parse sets itself; the others are the @2 base's.
OWN_FIELDS = (
    "channels",
    "junction_heat_booking",
    "species_registry",
    "kinds",
    "heat_bookings",
    "forms_faces",
    ONE_WAY_RECORDS_KEY,
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
    # The faces of cells.route.logmean_electrodiffusion_forms@1 (FormsFace), in declared order: their own
    # entity set, never in `faces` or its arrays; () for every definition of today's, and then
    # to_dict writes nothing, so fingerprints are unchanged.
    forms_faces: tuple = ()
    # FR-50 phase 2: the one_way_records entries (OneWayRecords), in declared order; () for every
    # definition of today's, and then to_dict writes nothing, so fingerprints are unchanged.
    one_way_records: tuple = ()


@dataclass(frozen=True)
class FormsFace(ExtracellularFaceSpec):
    """A face of cells.route.logmean_electrodiffusion_forms@1 (laws/routes/logmean_electrodiffusion_forms):
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
    """The cells.model.resolved_pump_tissue@2 part of a definition (no channel populations)."""
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
    """One channel population, strictly; `ids` and `z` are the model's species and their valences.
    Its law, from the law registry, is the one authority for its ions: their species, valences and
    permeability ratios. A law that carries an ion outside MAJOR_IONS and declares no material term
    is refused by name."""
    _fields(raw, CHANNEL_FIELDS, "channel")
    law_id, laws = raw["kinetic_law"], channel_laws()  # The registry's (§8.3).
    if type(law_id) is not str or law_id not in laws or type(raw["permeant_ions"]) is not list:
        raise ConfigError(
            "Channel requires a cells.model.resolved_pump_tissue@3 law and permeant ions"
        )
    law = laws[law_id]
    valence = {species: own for species, own, _ in law.permeant}
    ions = []
    for ion in raw["permeant_ions"]:
        _fields(ion, set(kinetic.PermeantIon.__dataclass_fields__), "permeant ion")
        species = identifier(ion["species_id"])
        weight = _number(ion["relative_permeability"], "relative permeability")
        own = valence.get(species)
        given = z[ids.index(species)] if species in ids else None
        if own is None or given != own:
            carries = f"no {species}" if own is None else f"{species} at valence {own}"
            declares = "no such species" if given is None else f"it at valence {given}"
            raise ConfigError(
                f"Channel ion requires its law's species and valence: {law_id} carries {carries}, "
                f"and the model declares {declares}"
            )
        ions.append(kinetic.PermeantIon(species, weight))
    ratios = tuple((species, weight) for species, _, weight in law.permeant)
    if tuple((i.species_id, i.relative_permeability) for i in ions) != ratios:
        raise ConfigError("Channel ions must exactly match the named law's permeability ratios")
    scarce = [species for species in valence if species not in MAJOR_IONS]
    if scarce and law.material_term is None:
        raise ConfigError(
            f"Channel {identifier(raw['id'])}: {law_id} carries {scarce[0]}, which is not Na, K or "
            "Cl, and declares no material_term; the charge rule alone does not hold a scarce ion's "
            "amounts"
        )
    patch = identifier(raw["membrane_id"])
    if (
        patch not in membranes
        or type(raw["initial_gate"]) is not list
        or len(raw["initial_gate"]) != len(law.gates)
    ):
        raise ConfigError("Channel requires its patch and exactly its law's gate state")
    return kinetic.ChannelPopulation(
        identifier(raw["id"]),
        patch,
        law_id,
        _number(raw["max_permeability_m_per_s"], "channel permeability"),
        _number(raw["abundance"], "channel abundance"),
        tuple(fraction(v, "initial channel gate") for v in raw["initial_gate"]),
        tuple(ions),
    )


@dataclass(frozen=True)
class BlockMode:
    """One weighted mode of a block (FR-51): its weight w (dimensionless), K(0) in mM, and exactly
    one steepness (ruling 7). That is the electrical distance delta in [0, 1] or the effective
    valence z_eff > 0; the other is None."""

    weight: float
    k0_mM: float
    electrical_distance: float | None = None
    effective_valence: float | None = None


@dataclass(frozen=True)
class ChannelBlock:
    """A population's open-channel blocker (FR-51, D327; cells.channel_block.open_channel_block_weighted_modes@1).

    The blocker has valence z_B and is held at concentration_mM (mM, constant in version 1) on its
    side. It is referenced to the patch voltage (reversal_of None) or to V - E of the named
    permeant ion, and binds in weighted modes. The block declares no count, and the bound blocker
    is taken from no row (trace binding)."""

    law: str
    blocker_id: str
    valence: int
    side: str
    concentration_mM: float
    reversal_of: str | None
    modes: tuple[BlockMode, ...]

    def steepness(self):
        """Each mode's signed steepness s sgn(z_B) m_k (dimensionless), with m_k = |z_B| delta_k or
        z_eff,k. a_k is this times F/(R T) (fr51-channel-block-v1 §1.1)."""
        sign = block_law.SIDES[self.side] * (1 if self.valence > 0 else -1)
        return tuple(
            sign
            * (
                abs(self.valence) * m.electrical_distance
                if m.effective_valence is None
                else m.effective_valence
            )
            for m in self.modes
        )


@dataclass(frozen=True)
class FactoredChannelPopulation(kinetic.ChannelPopulation):
    """A channel population whose entry declares factors (B1's door, docs/CORE_SEAMS_DESIGN.md
    §4.3), a block (FR-51), or both: the shared ChannelPopulation with its factor-source IDs, in
    declared order, and its block. A population with neither stays a ChannelPopulation, so its
    form and fingerprint are today's."""

    factors: tuple[str, ...] = ()
    block: ChannelBlock | None = None


def factored(channel, factors, block=None):
    """The population as a FactoredChannelPopulation with these factors and this block."""
    values = {f.name: getattr(channel, f.name) for f in fields(kinetic.ChannelPopulation)}
    return FactoredChannelPopulation(**values, factors=tuple(factors), block=block)


def channel_factors(model):
    """((slot, channel ID, (factor-source ID, ...)), ...) of the model's factored populations, in
    channel order; () for every definition of today's (B1's door)."""
    return tuple(
        (slot, c.id, c.factors)
        for slot, c in enumerate(getattr(model, "channels", ()))
        if getattr(c, "factors", ())
    )


def channel_blocks(model):
    """((slot, channel ID, its ChannelBlock), ...) of the model's blocked populations, in channel
    order; () for every definition of today's (FR-51)."""
    return tuple(
        (slot, c.id, c.block)
        for slot, c in enumerate(getattr(model, "channels", ()))
        if getattr(c, "block", None) is not None
    )


@dataclass(frozen=True)
class OneWayRecords:
    """One entry of one_way_records (FR-50 phase 2): an entity of @3's, its kind (one of
    ONE_WAY_ENTITIES) and its ID, and the species, in declared order, whose one-way records it
    keeps."""

    entity: str
    entity_id: str
    species: tuple[str, ...]


def one_way_pairs(model):
    """((entity kind, entity ID, species ID), ...), sorted: the model's declared one-way record
    pairs (FR-50 phase 2), () for every definition of today's (InnerStructure.one_way_records)."""
    return tuple(
        sorted(
            (entry.entity, entry.entity_id, species)
            for entry in getattr(model, ONE_WAY_RECORDS_KEY, ())
            for species in entry.species
        )
    )


def parse_one_way_records(given, model, channels, forms_faces):
    """The model's one_way_records key (FR-50 phase 2) as OneWayRecords entries, in declared
    order, from the base model's entities, its parsed channel populations and its forms faces. Each
    refusal names the key and its reason (fr50-one-way-records-v1 §3, E5): a pump's cycles, a forms
    face's movers and a charged face row have no one-way form in version 1."""
    if type(given) is not list or not given:
        raise ConfigError(
            f"{ONE_WAY_RECORDS_KEY} is a non-empty list of {{entity, id, species}} entries (omit "
            "it for none)"
        )
    pumps = {p.pump.id for p in model.membranes if p.pump is not None}
    pumps |= {p.calcium_pump.id for p in model.membranes if p.calcium_pump is not None}
    forms = {f.id for f in forms_faces}
    entities = dict(
        channel={c.id for c in channels},
        face={f.id for f in model.faces},
        junction={j.id for j in model.junctions},
        membrane={p.id for p in model.membranes},
    )
    valence = dict(zip(model.species_ids, model.valence, strict=True))
    parsed, seen = [], set()
    for k, raw in enumerate(given):
        name = f"{ONE_WAY_RECORDS_KEY}[{k}]"
        _fields(raw, ONE_WAY_ENTRY_KEYS, name)
        entity, entity_id, species = raw["entity"], raw["id"], raw["species"]
        if not isinstance(entity, str) or not isinstance(entity_id, str) or not entity_id:
            raise ConfigError(f"{name}: entity and id are names")
        if entity in ("pump", "calcium_pump") or entity_id in pumps:
            raise ConfigError(
                f"{name}: {entity_id!r} is a pump, whose cycles have no one-way form, so "
                "one_way records are refused on a pump (FR-50, version 1)"
            )
        if entity_id in forms:
            raise ConfigError(
                f"{name}: {entity_id!r} is a forms face ({forms_law.LAW_ID}), whose movers have no "
                "one-way term, so one_way records are refused on it (FR-50, version 1)"
            )
        if entity not in ONE_WAY_ENTITIES:
            raise ConfigError(
                f"{name}: entity is one of {', '.join(ONE_WAY_ENTITIES)}; a declared kind's routes "
                "keep their own one_way records, by their own key"
            )
        if entity_id not in entities[entity]:
            raise ConfigError(f"{name}: {entity_id!r} names no {entity} of the model")
        if (
            type(species) is not list
            or not species
            or len(set(species)) != len(species)
            or any(not isinstance(s, str) or s not in valence for s in species)
        ):
            raise ConfigError(f"{name}: species is a non-empty list of distinct species rows")
        charged = [s for s in species if valence[s] != 0]
        if entity == "face" and charged:
            raise ConfigError(
                f"{name}: face {entity_id} would record the charged species "
                f"{', '.join(charged)}, whose face flux is implicit electromigration with no "
                "one-way form, so one_way records are refused for a charged face row (FR-50, "
                "version 1)"
            )
        for s in species:
            if (entity, entity_id, s) in seen:
                raise ConfigError(f"{name}: ({entity}, {entity_id}, {s}) is declared twice")
            seen.add((entity, entity_id, s))
        parsed.append(OneWayRecords(entity, entity_id, tuple(species)))
    return tuple(parsed)


def one_way_records_to_dict(entries):
    """The one_way_records entries as their declaration (FR-50 phase 2)."""
    return [dict(entity=e.entity, id=e.entity_id, species=list(e.species)) for e in entries]


def _real(value, name):
    """A finite real number, an int or a float (never a bool), its sign kept."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ConfigError(f"{name} must be a finite number")
    return float(value)


def parse_block(raw, channel, species_ids):
    """A population's block (FR-51, D327). Each refusal names its reason
    (fr51-channel-block-v1 §1.2)."""
    name = f"Channel {channel.id}: block"
    _fields(raw, BLOCK_KEYS, name)
    if raw["law"] != block_law.LAW_ID:
        raise ConfigError(f"{name}: law must be {block_law.LAW_ID}")
    blocker = _fields(raw["blocker"], BLOCKER_KEYS, f"{name}'s blocker")
    blocker_id = identifier(blocker["id"])
    ions = tuple(i.species_id for i in channel.permeant_ions)
    if blocker_id in species_ids or blocker_id in ions:
        raise ConfigError(
            f"{name}: the blocker {blocker_id!r} names a species row or a permeant ion; version "
            "1's blocker is a declared constant, not a row"
        )
    valence = blocker["valence"]
    if type(valence) is not int or valence == 0:
        raise ConfigError(
            f"{name}: the blocker's valence is a nonzero integer, kept for the charge's sign"
        )
    side = blocker["side"]
    if side not in block_law.SIDES:
        raise ConfigError(f"{name}: the blocker's side is outside or inside")
    concentration = _real(blocker["concentration_mM"], f"{name}'s blocker concentration")
    low, high = block_law.BLOCKER_RANGE_MM
    if not low <= concentration <= high:
        raise ConfigError(
            f"{name}: the blocker concentration lies in [{low:g}, {high:g}] mM, the admitted domain"
        )
    reference = raw["reference"]
    if reference == block_law.MEMBRANE_VOLTAGE:
        reversal_of = None
    elif isinstance(reference, dict) and set(reference) == {REVERSAL_OF}:
        reversal_of = reference[REVERSAL_OF]
        if reversal_of not in ions:
            raise ConfigError(
                f"{name}: the reversal reference names {reversal_of!r}, an ion the population "
                "does not carry"
            )
    else:
        raise ConfigError(
            f"{name}: reference is {block_law.MEMBRANE_VOLTAGE!r} or {{{REVERSAL_OF!r}: ion}}"
        )
    carried = [i.species_id for i in channel.permeant_ions if i.relative_permeability]
    law = channel_laws()[channel.kinetic_law]
    if reversal_of is not None and len(carried) > 1 and law.material_term is not None:
        raise ConfigError(  # The stage's term through the reversal is the named ion's own flux's.
            f"{name}: {law.law_id} carries {', '.join(carried)} and declares a material term, and "
            f"the block reads the reversal of {reversal_of}: the material term bounds only "
            f"{reversal_of}'s own flux through that reversal, so its other ions' have no bound "
            "(the membrane voltage as the reference is admitted)"
        )
    modes = raw["modes"]
    if type(modes) is not list or not modes:
        raise ConfigError(f"{name}: modes is a non-empty list")
    if len(modes) > block_law.MAX_MODES:
        raise ConfigError(
            f"{name}: at most {block_law.MAX_MODES} modes, since the mode axis is static and its "
            "sums are unrolled"
        )
    parsed = tuple(_block_mode(m, valence, f"{name}'s mode {k}") for k, m in enumerate(modes))
    if abs(math.fsum(m.weight for m in parsed) - 1.0) > block_law.SUM_ULPS * np.spacing(1.0):
        raise ConfigError(
            f"{name}: the modes' weights sum to 1 within {block_law.SUM_ULPS} ulps, since they are "
            "fractions of one population"
        )
    return ChannelBlock(block_law.LAW_ID, blocker_id, valence, side, concentration, reversal_of,
                        parsed)  # fmt: skip


def _block_mode(raw, valence, name):
    """One mode (FR-51): its weight, K(0) and its one steepness (ruling 7), in the admitted
    domain."""
    if not isinstance(raw, dict):
        raise ConfigError(f"{name} must be an object")
    steep = [key for key in STEEPNESS_KEYS if key in raw]
    if len(steep) != 1:
        raise ConfigError(
            f"{name}: declare exactly one of electrical_distance and effective_valence (ruling 7: "
            "one steepness per mode)"
        )
    _fields(raw, {"weight", "k0_mM", *steep}, name)
    weight = _real(raw["weight"], f"{name}'s weight")
    if not 0.0 <= weight <= 1.0:
        raise ConfigError(f"{name}: the weight lies in [0, 1], a fraction of the population")
    k0 = _real(raw["k0_mM"], f"{name}'s k0_mM")
    low, high = block_law.K0_RANGE_MM
    if not low <= k0 <= high:
        raise ConfigError(f"{name}: k0_mM lies in [{low:g}, {high:g}] mM, the admitted domain")
    value = _real(raw[steep[0]], f"{name}'s {steep[0]}")
    if steep[0] == "electrical_distance":
        if not 0.0 <= value <= 1.0:
            raise ConfigError(
                f"{name}: the electrical distance lies in [0, 1], a fraction of the field"
            )
        steepness, mode = abs(valence) * value, BlockMode(weight, k0, electrical_distance=value)
    else:
        if value <= 0.0:
            raise ConfigError(
                f"{name}: the effective valence is positive; its sign comes from s sgn(z_B)"
            )
        steepness, mode = value, BlockMode(weight, k0, effective_valence=value)
    if steepness > block_law.MAX_STEEPNESS:
        raise ConfigError(
            f"{name}: the steepness {steepness:g} exceeds {block_law.MAX_STEEPNESS:g}, the "
            "admitted domain's limit"
        )
    return mode


def block_to_dict(block):
    """A ChannelBlock as its declaration (FR-51)."""
    return {
        "law": block.law,
        "blocker": {
            "id": block.blocker_id,
            "valence": block.valence,
            "side": block.side,
            "concentration_mM": block.concentration_mM,
        },
        "reference": (
            block_law.MEMBRANE_VOLTAGE
            if block.reversal_of is None
            else {REVERSAL_OF: block.reversal_of}
        ),
        "modes": [
            {
                "weight": m.weight,
                "k0_mM": m.k0_mM,
                **(
                    {"electrical_distance": m.electrical_distance}
                    if m.effective_valence is None
                    else {"effective_valence": m.effective_valence}
                ),
            }
            for m in block.modes
        ],
    }


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
        out.pop(CHANNEL_BLOCK)  # FR-51: written only where declared, so no fingerprint moves.
        if p.factors:
            out[CHANNEL_FACTORS] = list(p.factors)
        else:
            out.pop(CHANNEL_FACTORS)
        if p.block is not None:
            out[CHANNEL_BLOCK] = block_to_dict(p.block)
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
    if m.one_way_records:  # FR-50 phase 2: written only where declared.
        raw["model"][ONE_WAY_RECORDS_KEY] = one_way_records_to_dict(m.one_way_records)
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


# --- FR-30 (D262): junctions whose gate is cells.junction.junction_series_gates@1, development only ----------

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
    """A cells.junction.junction_series_gates@1 gate block: {law, development: true, gates: [fast, slow]}, each
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
        raise ConfigError("Require cells.model.resolved_pump_tissue@3")
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
    one_way = m.pop(ONE_WAY_RECORDS_KEY, _NONE)  # FR-50 phase 2: parsed with the channels below.
    if type(channels) is not list:
        raise ConfigError("channels requires an explicit list")
    # B1's door: each entry's factors leave this copy before the strict channel parse; so does
    # FR-51's block.
    popped = [c.pop(CHANNEL_FACTORS, _NONE) if isinstance(c, dict) else _NONE for c in channels]
    blocks = [c.pop(CHANNEL_BLOCK, _NONE) if isinstance(c, dict) else _NONE for c in channels]
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
    # The forms law (cells.route.logmean_electrodiffusion_forms@1): @3 alone admits it on faces. The base
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
    # FR-30 (D262): @3 alone admits cells.junction.junction_series_gates@1; @1's and @2's parses refuse it.
    with first.admitting({SERIES_GATE_LAW_ID: parse_series_gate}):
        with tissue.admitting_faces({forms_law.LAW_ID: FormsFace}):
            with first.admitting_field_solvers((SPARSE_SOLVER_ID,)):
                base = second.parse(raw)
    series_junction_errors(base.model)
    forms_faces = tuple(f for f in base.model.faces if type(f) is FormsFace)
    if forms_faces:
        plain = tuple(f for f in base.model.faces if type(f) is not FormsFace)
        if declared_faces < len(plain):
            raise ConfigError(
                "face_capacity must hold every face of cells.route.logmean_electrodiffusion@1"
            )
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
        c
        if given is _NONE and block is _NONE
        else factored(
            c,
            () if given is _NONE else _factor_sources(given, c.id),
            None if block is _NONE else parse_block(block, c, ids),
        )
        for c, given, block in zip(parsed, popped, blocks, strict=True)
    )
    if solver in imex.IMPLICIT_CONDUCTANCE_IDS and any(
        getattr(c, "block", None) is not None for c in parsed
    ):
        raise ConfigError(BLOCK_N2_REFUSAL)
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
    one_way = () if one_way is _NONE else parse_one_way_records(one_way, model, parsed, forms_faces)
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
        one_way_records=one_way,
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
            or channel_blocks(spec.model)  # FR-51: the structure holds the blocked populations.
            or any(c.kinetic_law not in LAW_CODES for c in spec.model.channels)
            or spec.model.heat_bookings  # Seam D: the structure holds the picks.
            or any(isinstance(j, kinetic.SeriesJunction) for j in spec.model.junctions)  # FR-30.
            or spec.model.forms_faces  # The forms law: their own entity set (the structure's).
            or spec.model.one_way_records  # FR-50 phase 2: the structure holds the pairs.
        )
        check_definition(spec, structure=structure(spec.model) if declared else None)
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Invalid resolved pump @3 definition: " + str(error)) from error
    return spec


def control_values(spec, times):
    """cells.model.resolved_pump_tissue@2 controls with the channel availabilities filled in."""
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
