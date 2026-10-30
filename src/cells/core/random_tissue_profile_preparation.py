"""Native random targets composed with the qualified static physical bridge.

This creates a new initial definition, never modifies an evolved checkpoint.
The source and successor of both selection tapes are retained. Deterministic
recipe replay starts from the saved source, not from the saved successor.
"""

from copy import deepcopy
from dataclasses import dataclass, fields, replace

from cells import tissue_profiles as static
from cells.core import physiology_target_selection as selection
from cells.core import tissue_profile_composition_preparation as composed
from cells.core import tissue_profile_preparation as direct
from cells.core.specs import ConfigError, digest, parse_spec
from cells.processes import betse_tissue_profiles as profiles

KIND = "cells.random_tissue_profile_preparation@1"
REQUEST_KIND = "cells.random_tissue_profile_preparation_request@1"
SUPPORTED_MODELS = (
    "resolved_tissue@1",
    "resolved_tissue@12",
    "resolved_calcium@11",
    "resolved_calcium_energy@5",
)
REQUEST_FIELDS = static.REQUEST_FIELDS | {
    "selection_stream",
    "stream_id",
    "world_id",
    "global_gj_percent",
}


@dataclass(frozen=True, slots=True)
class Preparation:
    definition: dict
    provenance: dict
    stream: selection.SelectionStream


class PreparationRejected(ConfigError):
    def __init__(self, reason, *, stage, source_stream, selected=None, failure=None):
        super().__init__("Random tissue preparation refused at " + stage + ": " + str(reason))
        self.stage, self.source_stream = stage, source_stream
        self.selection, self.failure = selected, failure
        self.trial_stream = (
            selected.stream
            if selected is not None
            else getattr(failure, "trial_stream", source_stream)
        )


def prepare(request):
    stage, source_stream, selected = "request_admission", None, None
    try:
        static._mapping(request, REQUEST_FIELDS, "random preparation request")
        if (
            type(request["schema_version"]) is not int
            or request["schema_version"] != 1
            or request["kind"] != REQUEST_KIND
        ):
            raise ConfigError("Require random tissue preparation schema_version 1")
        raw = direct._json(deepcopy(request))
        if (
            type(raw["definition"]) is not dict
            or type(raw["definition"].get("model")) is not dict
            or raw["definition"]["model"].get("id") not in SUPPORTED_MODELS
        ):
            raise ConfigError(
                "Random preparation requires one of the four qualified ordinary families"
            )
        if type(raw["profiles"]) is not list:
            raise ConfigError("Require an ordered profile list")
        geometry_record = deepcopy(raw["geometry"])
        static._mapping(geometry_record, {f.name for f in fields(direct.Geometry)}, "geometry")
        layout_record = geometry_record.pop("layout")
        static._mapping(layout_record, {f.name for f in fields(profiles.Layout)}, "layout")
        geometry = direct.Geometry(profiles.Layout(**layout_record), **geometry_record)
        spec = parse_spec(raw["definition"])
        bridge = static._definition_bridge(raw["definition"])
        physical = spec if bridge is direct else parse_spec(composed.parameter_view(spec))
        layout, _, _, _, _ = direct._geometry(geometry, physical.model)
        source_stream = selection.restore_stream(
            raw["selection_stream"], layout, stream_id=raw["stream_id"], world_id=raw["world_id"]
        )
        default = static._profile(raw["default"])
        declarations = tuple(static._profile(row) for row in raw["profiles"])
        kwargs = {key: raw[key] for key in ("ion_enabled", "enabled", "is_ecm")}
        stage = "owned_selection"
        selected = selection.resolve(
            layout,
            source_stream,
            default,
            declarations,
            global_gj_percent=raw["global_gj_percent"],
            **kwargs,
        )
        permutations = {
            op.name: op.permutation for op in selected.operations if op.kind == "percent"
        }
        resolved = tuple(
            replace(
                row, selector=replace(row.selector, permutation_cell_ids=permutations[row.name])
            )
            if row.name in permutations
            else row
            for row in declarations
        )
        stage = "physical_preparation"
        prepared = bridge.prepare(raw["definition"], geometry, default, resolved, **kwargs)
        parameter_recipe = (
            prepared.provenance
            if bridge is direct
            else prepared.provenance["direct_parameter_preparation"]
        )
        # Static preparation depends on membership, never mutable native ALL
        # occurrence order. Keep both truthful bindings and check their complete
        # numerical coefficient/insularity inputs rather than rewriting either.
        actual_kernel = profiles.binding_manifest(selected.binding)["kernel"]
        if selection._json(parameter_recipe["binding"]["kernel"]) != selection._json(actual_kernel):
            raise ConfigError("Physical preparation differs from the actual selected membership")
        payload = dict(
            kind=KIND,
            request=raw,
            selection=selection.result_record(selected),
            static_preparation=prepared.provenance,
            prepared_definition_sha256=digest(prepared.definition),
            scope=(
                "Initial physical coefficients and native selection tapes; no evolved-state remap"
            ),
            global_gj_scope="Targets and consumed Python tape only; no blocker event fired",
        )
        provenance = direct._json(payload | dict(identity=digest(payload)))
        return Preparation(prepared.definition, provenance, selected.stream)
    except Exception as error:
        raise PreparationRejected(
            error, stage=stage, source_stream=source_stream, selected=selected, failure=error
        ) from error


def replay(provenance):
    """Reconstruct the same private draws and definition from the original source."""
    try:
        static._mapping(
            provenance,
            {
                "kind",
                "request",
                "selection",
                "static_preparation",
                "prepared_definition_sha256",
                "scope",
                "global_gj_scope",
                "identity",
            },
            "complete random preparation",
        )
        payload = {key: value for key, value in provenance.items() if key != "identity"}
        if provenance["kind"] != KIND or provenance["identity"] != digest(payload):
            raise ConfigError("Stale random preparation identity")
        result = prepare(provenance["request"])
        if selection._json(result.provenance) != selection._json(provenance):
            raise ConfigError("Random preparation targets, tapes or physical recipe changed")
        return result
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid complete random preparation: " + str(error)) from error
