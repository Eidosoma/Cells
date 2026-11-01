"""Opt-in extended-material budget/state contract; numerical entry stays closed.

Legacy dispatch/transport, material, CaATP, field, catalog and mechanics owners
still have their original three-call laws. This contract retains a fresh owner
graph by reference and records refused work. It cannot produce a fourth state,
admit a saved cache, cycle a prefix or act as a numerical ownership verifier.
"""

import math
from dataclasses import dataclass, replace

from cells.core import physiology_native_calendar as calendars
from cells.processes import betse_normal_ecm_molecule_checkpoint_codec as codec
from cells.processes import betse_normal_ecm_molecule_dispatch as dispatch
from cells.processes import betse_normal_ecm_molecule_transport as transport
from cells.processes import betse_normal_ion_join as ions

KIND = "cells.normal_ecm_molecule_extended_material_contract@1"
BUDGET_KIND = "cells.normal_ecm_molecule_extended_material_budget@1"
REQUIRED_SEAMS = (
    "material.state_and_step_explicit_domain_preserving_absolute_index",
    "calcium.material_step_and_source_clock_domain",
    "field_and_network_complete_N_row_binding_and_field_suffix",
    "catalog_absolute_writer_epochs_beyond_three",
    "INIT_post_network_material_and_mechanics_domain_if_INIT_selected",
    "actual_nested_source_invocation_meter_and_numerical_release",
)
require = codec.require


@dataclass(frozen=True, slots=True)
class Budget:
    source_calls: int
    max_material_attempts: int
    max_owner_verifications: int
    max_nested_source_invocations: int
    max_retained_bytes: int
    wall_seconds: float
    provenance: str
    identity: str


def budget_record(value):
    return (
        BUDGET_KIND,
        value.source_calls,
        value.max_material_attempts,
        value.max_owner_verifications,
        value.max_nested_source_invocations,
        value.max_retained_bytes,
        value.wall_seconds,
        value.provenance,
    )


def budget(
    *,
    source_calls,
    max_material_attempts,
    max_owner_verifications,
    max_nested_source_invocations,
    max_retained_bytes,
    wall_seconds,
    provenance,
):
    """Declare finite limits. No limit authorizes any numerical source call."""
    for name, value, minimum, maximum in (
        ("source_calls", source_calls, 4, calendars.MAX_PHASE_CALLS),
        ("max_material_attempts", max_material_attempts, source_calls, 10_000_000),
        ("max_owner_verifications", max_owner_verifications, 1, 100_000_000),
        ("max_nested_source_invocations", max_nested_source_invocations, 1, 1_000_000_000),
        ("max_retained_bytes", max_retained_bytes, 1, codec.DEFAULT_LIMITS.expanded_bytes),
    ):
        require(
            type(value) is int and minimum <= value <= maximum,
            "Finite exact integer budget required: " + name,
        )
    require(
        max_nested_source_invocations >= source_calls + 1,
        "Nested work budget cannot omit declared source entries and owner verification",
    )
    require(
        type(wall_seconds) is float and math.isfinite(wall_seconds) and 0 < wall_seconds <= 1e9,
        "Finite positive binary64 wall budget required",
    )
    require(
        type(provenance) is str and bool(provenance.strip()),
        "Explicit extended-domain provenance required",
    )
    value = Budget(
        source_calls,
        max_material_attempts,
        max_owner_verifications,
        max_nested_source_invocations,
        max_retained_bytes,
        wall_seconds,
        provenance,
        "",
    )
    return replace(value, identity=ions.digest(budget_record(value)))


def verify_budget(value):
    require(type(value) is Budget, "Typed separately versioned material budget required")
    expected = budget(
        **{name: getattr(value, name) for name in Budget.__dataclass_fields__ if name != "identity"}
    )
    require(value.identity == expected.identity, "Changed material work budget")


@dataclass(frozen=True, slots=True)
class Attempt:
    ordinal: int
    requested_source_call: int
    input_binding_identity: str
    input_parent_identity: str
    forcing_fingerprint: str | None
    reason: str
    numerical_entries: int = 0


@dataclass(frozen=True, slots=True)
class Retained:
    budget: Budget
    requested_calendar: calendars.NativePhaseCalendar
    owner_kind: str
    binding: object
    parent: object
    owner_fingerprint: str
    retained_bytes: int
    attempts: tuple
    status: str
    identity: str
    numerical_owner_admission: bool = False

    @property
    def cursor(self):
        # A requested long calendar is never a new numerical owner clock.
        return self.parent.cursor


class MaterialDomainRefused(RuntimeError):
    def __init__(self, reason, *, before, retained, requested_attempt, partial=None):
        super().__init__(reason)
        self.before = before
        self.retained = retained
        self.requested_attempt = requested_attempt
        self.partial = partial
        self.required_seams = REQUIRED_SEAMS
        self.automatic_retry = False
        self.numerical_entries = 0


def _owner(binding, parent):
    if type(binding) is dispatch.Binding and type(parent) is dispatch.State:
        return dispatch
    if type(binding) is transport.Binding and type(parent) is transport.State:
        return transport
    raise ValueError(
        "Require the actual typed dispatch/transport owner pair; no cache/receipt adapter"
    )


def _structure(binding, parent):
    owner = _owner(binding, parent)
    require(
        type(binding.component) is owner.calcium.Binding
        and type(parent.material) is owner.material.State
        and type(parent.material.values) is owner.material.Values
        and type(parent.field) is owner.full.FieldStage
        and type(parent.rate_cache) is owner.calcium.RateCache
        and type(parent.clock) is owner.calcium.Clock,
        "Missing complete typed material/field/rate/clock records",
    )
    require(
        parent.owners is not None and parent.controls is not None,
        "Missing complete dual-owner/control stores",
    )
    return owner


def _roots(binding, parent):
    owner = _structure(binding, parent)
    # Explicit complete record roots avoid pretending this new control record
    # belongs to the frozen ordinary checkpoint vocabulary. No field is dropped.
    return (
        owner.LAW_ID,
        owner.binding_record(binding),
        binding.component,
        owner.state_record(parent),
    )


def _fingerprint(binding, parent, maximum):
    encoder = codec.Encoder()
    tree = encoder.capture(_roots(binding, parent))
    retained_bytes = encoder.bytes + len(codec.json_bytes(tree))
    require(retained_bytes <= maximum, "Complete retained owner graph exceeds declared byte budget")
    return encoder.seal(tree), retained_bytes


def record(value):
    return (
        KIND,
        value.budget.identity,
        value.requested_calendar.identity,
        value.owner_kind,
        value.binding.identity,
        value.parent.identity,
        value.owner_fingerprint,
        value.retained_bytes,
        value.attempts,
        value.status,
        value.numerical_owner_admission,
    )


def retain(value, calendar, binding, parent):
    """Borrow a fresh complete graph; this is not extended numerical admission.

    No initializer, verifier or arithmetic body runs. Original IDs, arrays,
    aliases, clocks, owners, rates and field stores remain in the same objects.
    Only a zero-cursor owner can be retained: a three-call prefix cannot be
    rebased into a longer domain. A future shared seam must admit real owners.
    """
    verify_budget(value)
    calendars.validate(calendar)
    require(
        calendar.phase == "SIM" and calendar.step_count == value.source_calls,
        "Require the explicit original extended SIM calendar, never remaining calls",
    )
    owner = _structure(binding, parent)
    require(
        type(parent.cursor) is int
        and parent.cursor == 0
        and type(parent.clock.call_index) is int
        and parent.clock.call_index == 0
        and parent.clock.material_dt_sum_s == 0.0,
        "Evolved, cycled or rebased three-call owners cannot seed this control contract",
    )
    require(
        parent.binding_identity == binding.identity
        and binding.identity == ions.digest(owner.binding_record(binding))
        and parent.identity == ions.digest(owner.state_record(parent)),
        "Changed complete retained binding/state record",
    )
    fingerprint, size = _fingerprint(binding, parent, value.max_retained_bytes)
    result = Retained(
        value,
        calendar,
        owner.LAW_ID,
        binding,
        parent,
        fingerprint,
        size,
        (),
        "awaiting_shared_material_domain",
        "",
    )
    return replace(result, identity=ions.digest(record(result)))


def verify_retained(value):
    """Metadata integrity only; never call the legacy numerical verifier."""
    require(
        type(value) is Retained, "Extended contract record required; no legacy state substitution"
    )
    verify_budget(value.budget)
    calendars.validate(value.requested_calendar)
    require(
        value.requested_calendar.phase == "SIM"
        and value.requested_calendar.step_count == value.budget.source_calls,
        "Changed original requested calendar",
    )
    owner = _structure(value.binding, value.parent)
    require(
        value.numerical_owner_admission is False,
        "Metadata contract is not numerical owner admission",
    )
    require(
        value.owner_kind == owner.LAW_ID
        and value.cursor == 0
        and value.parent.clock.call_index == 0
        and value.parent.clock.material_dt_sum_s == 0.0
        and value.parent.binding_identity == value.binding.identity
        and value.binding.identity == ions.digest(owner.binding_record(value.binding))
        and value.parent.identity == ions.digest(owner.state_record(value.parent)),
        "Changed original retained owner epoch/record",
    )
    require(value.identity == ions.digest(record(value)), "Changed extended control record")
    require(
        value.status in {"awaiting_shared_material_domain", "refused_shared_material_domain"}
        and type(value.attempts) is tuple
        and len(value.attempts) <= value.budget.max_material_attempts,
        "Invalid material control disposition or attempt budget",
    )
    for index, entry in enumerate(value.attempts):
        require(
            type(entry) is Attempt
            and type(entry.ordinal) is int
            and entry.ordinal == index + 1
            and type(entry.requested_source_call) is int
            and entry.requested_source_call == 0
            and type(entry.numerical_entries) is int
            and entry.numerical_entries == 0
            and entry.input_binding_identity == value.binding.identity
            and entry.input_parent_identity == value.parent.identity
            and entry.reason
            in {
                "shared_material_domain_unavailable",
                "unowned_forcing_type",
                "forcing_capture_incomplete",
            }
            and (entry.forcing_fingerprint is None or type(entry.forcing_fingerprint) is str),
            "Duplicate/omitted/foreign material attempt record",
        )
    require(
        (len(value.attempts) == 0) == (value.status == "awaiting_shared_material_domain"),
        "Attempt journal and disposition differ",
    )
    fingerprint, size = _fingerprint(value.binding, value.parent, value.budget.max_retained_bytes)
    require(
        fingerprint == value.owner_fingerprint and size == value.retained_bytes,
        "Retained complete owner buffers/aliases/layout changed",
    )


def request_advance(value, forcing):
    """Count/refuse entry before any numerical body; no backend injection seam.

    Limits apply to this immutable request lineage. Actual nested-call metering,
    wall/memory enforcement and shared typed numerical admission remain release
    prerequisites; metadata packing is not reported as zero-cost source work.
    """
    verify_retained(value)
    ordinal = len(value.attempts) + 1
    if ordinal > value.budget.max_material_attempts:
        raise MaterialDomainRefused(
            "Declared material attempt budget exhausted",
            before=value,
            retained=value,
            requested_attempt=ordinal,
            partial=dict(forcing=forcing, source_calls=0),
        )
    fingerprint, capture_error = None, None
    reason = "shared_material_domain_unavailable"
    if type(forcing) is not dispatch.material.Drive:
        reason = "unowned_forcing_type"
    else:
        try:
            fingerprint = codec.fingerprint(forcing)
        except Exception as error:
            capture_error = error
            reason = "forcing_capture_incomplete"
    entry = Attempt(ordinal, 0, value.binding.identity, value.parent.identity, fingerprint, reason)
    result = replace(
        value,
        attempts=(*value.attempts, entry),
        status="refused_shared_material_domain",
        identity="",
    )
    result = replace(result, identity=ions.digest(record(result)))
    refusal = MaterialDomainRefused(
        "Extended material source seam is unavailable; no call executed",
        before=value,
        retained=result,
        requested_attempt=ordinal,
        partial=dict(
            forcing=forcing,
            original_cursor=value.cursor,
            requested_calendar=value.requested_calendar,
            numerical_owner_admission=False,
            source_calls=0,
            required_seams=REQUIRED_SEAMS,
            forcing_capture_error=capture_error,
        ),
    )
    if capture_error is not None:
        raise refusal from capture_error
    raise refusal
