"""Initial physical profiles and a single native selection-to-component handoff.

The component owns the NumPy tape after the static draw. Selection tapes in
provenance are historical; Python's successor is parked, never silently joined
to a later selection. Restore validates an initial pair without any RNG draw.
"""

import hashlib
from dataclasses import dataclass, fields

import numpy as np

from cells import physiology_checkpoint as paired
from cells import tissue_profiles as static
from cells.core import physiology_perturbation_step as step
from cells.core import physiology_random_streams as streams
from cells.core import physiology_target_selection as targets
from cells.core import physiology_tissue_binding as units
from cells.core import random_tissue_profile_preparation as profiles
from cells.core.runner import validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import Checkpoint
from cells.models import physiology_permeability_view as view
from cells.processes import betse_perturbations as perturb
from cells.processes import betse_tissue_profiles as selectors

KIND = "cells.physiology_initial_preparation@1"
REQUEST_KIND = "cells.physiology_initial_preparation_request@1"
REQUEST_FIELDS = {"schema_version", "kind", "preparation", "component"}
COMPONENT_FIELDS = {
    "controls",
    "protein_mol_m3",
    "ion_ids",
    "boundary_cell_occurrences",
    "provenance",
    "stream_id",
    "next_tick",
}
SCOPE = "Initial bound tissue/component pair; no charged-protein projection or elapsed loop"
HANDOFF = "Selected NumPy successor becomes component-owned; Python successor is parked"


@dataclass(frozen=True, slots=True)
class Initialization:
    spec: object
    checkpoint: Checkpoint
    binding: units.TissueBinding
    component: step.PhysiologyPerturbationState
    provenance: dict


class InitializationRejected(ConfigError):
    def __init__(self, reason, *, stage, preparation, source_stream, component, checkpoint):
        super().__init__("Physiology initialization refused at " + stage + ": " + str(reason))
        self.stage, self.preparation, self.source_stream = stage, preparation, source_stream
        self.component_trial = getattr(reason, "trial", component)
        self.proposed_stream = getattr(
            reason, "stream", getattr(component, "stream", source_stream)
        )
        self.packet = getattr(reason, "packet", None)
        self.checkpoint, self.failure = checkpoint, reason


def _json(value):
    return profiles.direct._json(value)


def _request(request):
    static._mapping(request, REQUEST_FIELDS, "initial physiology request")
    if type(request["schema_version"]) is not int or request["schema_version"] != 1:
        raise ConfigError("Require initialization schema_version 1")
    if request["kind"] != REQUEST_KIND:
        raise ConfigError("Unsupported initialization request kind")
    raw = _json(request)
    static._mapping(raw["component"], COMPONENT_FIELDS, "initial component")
    return raw


def _inputs(raw, spec):
    options, geometry = raw["component"], raw["preparation"]["geometry"]
    layout = selectors.validate_layout(selectors.Layout(**geometry["layout"]))
    binding = units.bind_tissue(
        spec,
        cell_ids=layout.cell_ids,
        membrane_ids=layout.membrane_ids,
        environment_ids=layout.environment_ids,
        ion_ids=options["ion_ids"],
        membrane_thickness_m=geometry["thickness_m"],
        boundary_cell_occurrences=options["boundary_cell_occurrences"],
        provenance=options["provenance"],
    )
    static._mapping(options["controls"], {f.name for f in fields(perturb.Controls)}, "controls")
    controls = perturb.validate_controls(perturb.Controls(**options["controls"]))
    protein = options["protein_mol_m3"]
    static._mapping(protein, {"cell", "membrane", "environment"}, "protein owner domains")
    values = []
    for domain in ("cell", "membrane", "environment"):
        ids = getattr(binding.component, domain + "_ids")
        static._mapping(protein[domain], set(ids), domain + " protein owners")
        if any(type(v) not in (float, int) or v < 0 for v in protein[domain].values()):
            raise ConfigError("Require finite nonnegative explicit protein concentrations")
        values.append(np.asarray([protein[domain][name] for name in ids], dtype=np.float64))
    return binding, controls, perturb.ProteinState(*values), layout


def _initial(spec):
    implementation = view.IMPLEMENTATIONS[type(spec.model)]
    state, layout = implementation.initial_values(spec)
    point = Checkpoint(
        view._immutable_tree(state), view._immutable_tree(layout), 0.0, 0, event_index(spec, 0.0)
    )
    validate_checkpoint(spec, point)
    return point


def _arrays(point):
    return {
        kind: {
            key: dict(
                dtype=np.asarray(value).dtype.str,
                shape=list(np.shape(value)),
                sha256=hashlib.sha256(np.asarray(value).tobytes()).hexdigest(),
            )
            for key, value in getattr(point, kind)._asdict().items()
        }
        for kind in ("state", "layout")
    }


def _physical(spec, point, binding, component):
    table = control_values(spec, [0.0])
    control = type(table)(*(value[0] for value in table))
    result = view.evaluate(
        spec, point.state, point.layout, control, binding, component, step_s=spec.execution.dt
    )
    return _json(
        dict(
            step_s=spec.execution.dt,
            potential_V=result.field.potential_V,
            derivative=result.derivative._asdict(),
            energy_rate_residual_pJ_s=result.field.energy_balance_pJ_s,
            passive_fraction=result.admission["passive_fraction"],
            fuel_fraction=result.admission["fuel_fraction"],
        )
    )


def initialize(request):
    stage, preparation, source, component, point = "request", None, None, None, None
    try:
        raw = _request(request)
        stage = "target_preparation"
        preparation = profiles.prepare(raw["preparation"])
        spec = parse_spec(preparation.definition)
        stage = "physical_binding"
        binding, controls, protein, _ = _inputs(raw, spec)
        source = streams.new_stream(
            binding.component,
            preparation.stream.numpy,
            stream_id=raw["component"]["stream_id"],
            world_id=preparation.stream.world_id,
            next_tick=raw["component"]["next_tick"],
        )
        stage = "static_initialization"
        component = step.initialise(
            binding.component, controls, protein, units.initial_diffusion(binding), source
        )
        stage = "initial_physical_admission"
        point = _initial(spec)
        physical = _physical(spec, point, binding, component)
        payload = dict(
            kind=KIND,
            request=raw,
            preparation=preparation.provenance,
            definition=spec.to_dict(),
            binding=units.binding_record(binding),
            component=paired._component_record(component, binding.component, component.stream),
            active_stream=streams.stream_record(component.stream),
            source_component_stream=streams.stream_record(source),
            parked_python=targets.python_record(preparation.stream.python),
            initial_arrays=_arrays(point),
            physical_admission=physical,
            handoff=HANDOFF,
            scope=SCOPE,
        )
        provenance = _json(payload | dict(identity=digest(payload)))
        return Initialization(spec, point, binding, component, provenance)
    except Exception as error:
        raise InitializationRejected(
            error,
            stage=stage,
            preparation=preparation,
            source_stream=source,
            component=component,
            checkpoint=point,
        ) from error


def validate(value):
    """Validate a restored initial association. This never executes a sampler.

    Complete saved associations are integrity checks, not authentication of
    historical execution. Explicit replay independently recomputes the recipe.
    """
    if type(value) is not Initialization:
        raise ConfigError("Require the complete typed initial association")
    p = value.provenance
    static._mapping(
        p,
        {
            "kind",
            "request",
            "preparation",
            "definition",
            "binding",
            "component",
            "active_stream",
            "source_component_stream",
            "parked_python",
            "initial_arrays",
            "physical_admission",
            "handoff",
            "scope",
            "identity",
        },
        "initialization provenance",
    )
    payload = {k: v for k, v in p.items() if k != "identity"}
    if (
        p["identity"] != digest(payload)
        or p["kind"] != KIND
        or p["scope"] != SCOPE
        or p["handoff"] != HANDOFF
    ):
        raise ConfigError("Invalid initialization provenance identity/scope")
    raw = _request(p["request"])
    if value.spec.to_dict() != p["definition"]:
        raise ConfigError("Initial physical source definition changed")
    binding, controls, protein, layout = _inputs(raw, value.spec)
    if (
        _json(units.binding_record(binding)) != p["binding"]
        or value.binding.identity != binding.identity
    ):
        raise ConfigError("Initial component physical owners changed")
    units.validate_binding(value.binding)
    parent = p["preparation"]
    if (
        parent["kind"] != profiles.KIND
        or parent["identity"] != digest({k: v for k, v in parent.items() if k != "identity"})
        or parent["request"] != raw["preparation"]
        or parent["prepared_definition_sha256"] != digest(p["definition"])
    ):
        raise ConfigError("Initial physical preparation association changed")
    selected = parent["selection"]
    if selected["identity"] != digest({k: v for k, v in selected.items() if k != "identity"}):
        raise ConfigError("Selection history identity changed")
    historical = targets.restore_stream(
        selected["source"],
        layout,
        stream_id=raw["preparation"]["stream_id"],
        world_id=raw["preparation"]["world_id"],
    )
    requested = targets.restore_stream(
        raw["preparation"]["selection_stream"],
        layout,
        stream_id=raw["preparation"]["stream_id"],
        world_id=raw["preparation"]["world_id"],
    )
    if targets._json(targets.stream_record(historical)) != targets._json(
        targets.stream_record(requested)
    ):
        raise ConfigError("Historical selection source differs from the original request")
    # This older static bridge consumes recorded explicit permutations only;
    # it contains no RNG sampling or physiological initialization.
    saved_static = parent["static_preparation"]
    static_result = static._provenance_bridge(saved_static).replay(saved_static)
    if (
        static_result.definition != p["definition"]
        or static_result.provenance["source_definition"]
        != parse_spec(raw["preparation"]["definition"]).to_dict()
    ):
        raise ConfigError("Static physical preparation source or result changed")
    successor = targets.restore_stream(
        selected["successor"],
        layout,
        stream_id=raw["preparation"]["stream_id"],
        world_id=raw["preparation"]["world_id"],
    )
    if targets.python_record(successor.python) != p["parked_python"]:
        raise ConfigError("Parked Python history changed")
    source = streams.new_stream(
        binding.component,
        successor.numpy,
        stream_id=raw["component"]["stream_id"],
        world_id=successor.world_id,
        next_tick=raw["component"]["next_tick"],
    )
    if streams.stream_record(source) != p["source_component_stream"]:
        raise ConfigError("Selected NumPy handoff changed")
    step.validate_state(value.component, binding.component)
    c = value.component
    if (
        c.time_s != 0
        or c.loop_calls != 0
        or c.controls != controls
        or c.stream.next_tick != source.next_tick + 1
        or c.stream.stream_id != source.stream_id
        or c.stream.world_id != source.world_id
        or type(c.stream.rng) is not perturb.NativeStream
    ):
        raise ConfigError("Initial component stream/clock/control association changed")
    if (
        streams.stream_record(c.stream) != p["active_stream"]
        or _json(paired._component_record(c, binding.component, c.stream)) != p["component"]
    ):
        raise ConfigError("Complete initialized component changed")
    for actual, expected in zip(c.protein, protein, strict=True):
        if actual.dtype != expected.dtype or actual.tobytes() != expected.tobytes():
            raise ConfigError("Initialization changed declared protein buffers")
    if not np.array_equal(c.diffusion.base_m2_s, units.initial_diffusion(binding)) or np.any(
        c.diffusion.scheduled_m2_s != 0
    ):
        raise ConfigError("Initial base or scheduled diffusion changed")
    initial = _initial(value.spec)
    if (
        value.checkpoint.time != 0
        or value.checkpoint.step_index != 0
        or value.checkpoint.event_index != initial.event_index
        or _arrays(value.checkpoint) != _arrays(initial)
        or _arrays(value.checkpoint) != p["initial_arrays"]
    ):
        raise ConfigError("Complete initial numeric state/layout/clocks changed")
    if _physical(value.spec, value.checkpoint, binding, c) != p["physical_admission"]:
        raise ConfigError("Initial physical admission changed")
    return value


def replay(provenance):
    """Explicit private recomputation from original tapes; not checkpoint restore."""
    value = initialize(provenance["request"])
    if targets._json(value.provenance) != targets._json(provenance):
        raise ConfigError("Initial source recipe, tapes or physical admission changed")
    return value
