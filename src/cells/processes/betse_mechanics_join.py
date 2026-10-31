"""Ordinary FULL pressure/steady/display seam on explicit seeded owners.

Flow and dynamic deformation remain disabled by the ordinary native loader.
Fields are supplied after handlers and before deferred material/voltage commit.
Sampled display needs a separate post-commit receipt and never rebuilds physics.
"""

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from cells.processes import betse_deformation as deformation
from cells.processes import betse_fluid_flow as flow

LAW_ID = "betse_ordinary_full_steady_mechanics_join_v1_5_0@1"
FIELD_STAGE = "normal_full_after_handlers_before_deferred_material_voltage"
SAMPLE_STAGE = "normal_full_after_deferred_material_voltage_check_v"
MAX_STEPS = 3
CACHE_KEYS = (
    "osmo_P_cell",
    "osmo_P_env",
    "osmo_P_delta",
    "u_osmo",
    "div_u_osmo",
    "PP",
    "gPxc",
    "gPyc",
    "d_cells_x",
    "d_cells_y",
    "u_cells_x",
    "u_cells_y",
    "u_env_x",
    "u_env_y",
    "display_centres_m",
    "display_vertices_m",
)


def freeze(value):
    if isinstance(value, np.ndarray):
        if value.dtype.kind not in "bifu":
            raise ValueError("Only typed numeric arrays belong to the mechanics cache")
        return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    return value


def plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if hasattr(value, "_asdict"):
        return {key: plain(item) for key, item in value._asdict().items()}
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


def digest(value):
    def record(item):
        if isinstance(item, np.ndarray):
            return dict(
                shape=item.shape,
                dtype=item.dtype.str,
                bytes_sha256=hashlib.sha256(item.tobytes()).hexdigest(),
            )
        if isinstance(item, Mapping):
            return {key: record(child) for key, child in item.items()}
        if isinstance(item, (tuple, list)):
            return [record(child) for child in item]
        if type(item) is float:
            return dict(binary64_hex=item.hex())
        return item

    return hashlib.sha256(
        json.dumps(record(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Binding:
    definition_json: str
    operators: deformation.Operators
    flow_binding: flow.CellBinding
    environment_average: object
    display_weights: object
    identity: str

    @property
    def definition(self):
        return json.loads(self.definition_json)


@dataclass(frozen=True)
class State:
    binding_identity: str
    step_index: int
    sampled_steps: tuple
    cache: object
    identity: str


@dataclass(frozen=True)
class Trial:
    parent_identity: str
    binding_identity: str
    inputs: object
    frames: tuple
    auxiliaries: object
    candidate: State
    identity: str


class MechanicsRejected(ValueError):
    def __init__(self, reason, *, stage, trial=None):
        super().__init__("Native mechanics refused at " + stage + ": " + str(reason))
        self.stage, self.trial = stage, trial


def _binding_record(binding):
    return dict(
        definition=binding.definition,
        operators=tuple(binding.operators),
        environment_average=binding.environment_average,
        display_weights=binding.display_weights,
        flow_owner_ids=binding.flow_binding.owner_ids,
        flow_identity=binding.flow_binding.identity,
        flow_operators=tuple(binding.flow_binding.operators),
    )


def bind(raw):
    if (
        set(raw) != {"kind", "geometry", "parameters", "policy", "provenance"}
        or raw["kind"] != LAW_ID
    ):
        raise MechanicsRejected("Require complete mechanics ownership declaration", stage="binding")
    policy = raw["policy"]
    if set(policy) != {
        "solver",
        "fluid_flow",
        "td_deform",
        "deformation",
        "deform_osmo",
        "is_ecm",
        "molecules_enabled",
        "grn_enabled",
        "display_regime",
    }:
        raise MechanicsRejected("Incomplete source controls", stage="binding")
    if policy["solver"] != "FULL" or any(
        type(policy[key]) is not bool for key in policy if key not in ("solver", "display_regime")
    ):
        raise MechanicsRejected("Require explicit FULL booleans", stage="binding")
    if policy["fluid_flow"] or policy["td_deform"]:
        raise MechanicsRejected(
            "Ordinary loader disables flow and dynamic deformation; "
            "recalc_fluid belongs to isolated sim-grn",
            stage="ordinary_policy",
        )
    if policy["display_regime"] not in ("none", "global_quartic_conditional"):
        raise MechanicsRejected(
            "Adaptive FITPACK needs a separate display implementation", stage="binding"
        )
    geometry, parameters, provenance = (
        raw[key] for key in ("geometry", "parameters", "provenance")
    )
    if set(provenance) != {"geometry_epoch", "graph_origin", "prerequisites"} or (
        provenance["graph_origin"] not in ("seed_graphLaplacian", "post_cut_graphLaplacian")
        or not isinstance(provenance["geometry_epoch"], str)
        or not provenance["geometry_epoch"]
        or provenance["prerequisites"] != "caller_supplied_layout_DEC_fields_no_seed_execution"
    ):
        raise MechanicsRejected(
            "Require explicit seeded/post-cut operator provenance", stage="binding"
        )
    ids, mesh = geometry["cell_ids"], geometry["layout"]
    if (
        not 1 <= len(ids) <= 64
        or len(set(ids)) != len(ids)
        or any(type(v) is not str or not v for v in ids)
    ):
        raise MechanicsRejected("Require bounded distinct cell IDs", stage="binding")
    if len(mesh["centers_m"]) != len(ids):
        raise MechanicsRejected("Cell owner axis mismatch", stage="binding")
    op = deformation.bind_operators(
        *(
            mesh[key]
            for key in (
                "neighbors",
                "lengths_m",
                "force_directions",
                "curl_directions",
                "sum_membranes",
                "incidence",
                "incidence_inverse",
                "dual_edge_m",
                "primal_edge_m",
                "dual_area_m2",
            )
        )
    )
    cb = flow.bind_cells(ids, op, provenance)
    op = deformation.Operators(*(freeze(np.asarray(value)) for value in cb.operators))
    cb = flow.CellBinding(cb.owner_ids, op, cb.provenance_json, cb.identity)
    environment_ids = geometry["environment_ids"]
    if (
        not environment_ids
        or len(environment_ids) > 128
        or len(set(environment_ids)) != len(environment_ids)
        or any(type(value) is not str or not value for value in environment_ids)
    ):
        raise MechanicsRejected("Require complete bounded environment owner IDs", stage="binding")
    average = np.asarray(geometry["environment_average"], dtype=np.float64)
    if (
        average.shape != (len(ids), len(environment_ids))
        or not np.isfinite(average).all()
        or (np.any(average < 0) or not np.all(average.sum(axis=1) == 1))
    ):
        raise MechanicsRejected(
            "Require native map/average on original environment axis", stage="binding"
        )
    if policy["is_ecm"]:
        mapping = geometry["cell_to_environment"]
        if len(mapping) != len(ids) or not np.array_equal(
            average, np.eye(len(environment_ids))[mapping]
        ):
            raise MechanicsRejected(
                "ECM pressure samples declared cell-to-grid map", stage="binding"
            )
    else:
        sm = np.asarray(mesh["sum_membranes"], dtype=np.float64)
        membrane_map = geometry["membrane_to_environment"]
        if (
            len(environment_ids) != sm.shape[1]
            or membrane_map != list(range(sm.shape[1]))
            or any(type(index) is not int for index in membrane_map)
        ):
            raise MechanicsRejected(
                "NoECM requires the original membrane environment axis and identity map",
                stage="binding",
            )
        expected = sm / sm.sum(axis=1)[:, None]
        if not np.array_equal(average, expected):
            raise MechanicsRejected(
                "NoECM pressure uses original membrane average", stage="binding"
            )
    weights = np.asarray(geometry["display_vertex_weights"], dtype=np.float64)
    for key in ("cell_area_m2", "cell_volume_m3"):
        values = np.asarray(mesh[key], dtype=np.float64)
        if values.shape != (len(ids),) or not np.isfinite(values).all() or np.any(values <= 0):
            raise MechanicsRejected("Invalid declared physical measures: " + key, stage="binding")
    sm, area, total = (
        np.asarray(mesh[key], dtype=np.float64)
        for key in (
            "sum_membranes",
            "membrane_area_m2",
            "cell_area_m2",
        )
    )
    if weights.shape != (len(ids), len(mesh["vertices_m"])) or not np.array_equal(
        weights, sm * area[None, :] / total[:, None]
    ):
        raise MechanicsRejected(
            "Require original source area-weighted display owners", stage="binding"
        )
    required = {
        "young_modulus_Pa",
        "galvanotropism_m2_V",
        "fixed_boundary",
        "dt_s",
        "viscous_damping_native",
        "cell_radius_m",
        "gas_constant_J_mol_K",
        "aquaporin_fraction",
        "water_viscosity_Pa_s",
        "membrane_thickness_m",
        "density_kg_m3",
    }
    if set(parameters) != required or type(parameters["fixed_boundary"]) is not bool:
        raise MechanicsRejected("Require complete phase mechanics parameters", stage="binding")
    if any(
        type(v) not in (int, float) or not math.isfinite(v)
        for k, v in parameters.items()
        if k != "fixed_boundary"
    ):
        raise MechanicsRejected("Require finite scalar parameters", stage="binding")
    if parameters["water_viscosity_Pa_s"] != 0.01:
        raise MechanicsRejected(
            "Ordinary loader fixes water viscosity at0.01 Pa*s", stage="ordinary_policy"
        )
    if any(
        parameters[k] <= 0
        for k in required
        - {"fixed_boundary", "galvanotropism_m2_V", "viscous_damping_native", "aquaporin_fraction"}
    ) or (parameters["aquaporin_fraction"] < 0 or parameters["viscous_damping_native"] < 0):
        raise MechanicsRejected("Invalid declared mechanics domain", stage="binding")
    binding = Binding(
        json.dumps(raw, sort_keys=True, allow_nan=False),
        op,
        cb,
        freeze(average),
        freeze(weights),
        "",
    )
    return Binding(
        binding.definition_json,
        op,
        cb,
        binding.environment_average,
        binding.display_weights,
        digest(_binding_record(binding)),
    )


def state(binding, raw, *, step_index=0, sampled_steps=()):
    if (
        set(raw) != set(CACHE_KEYS)
        or type(step_index) is not int
        or not 0 <= step_index <= MAX_STEPS
    ):
        raise MechanicsRejected(
            "Require complete mechanics cache and bounded source count", stage="state"
        )
    if len(set(sampled_steps)) != len(sampled_steps) or any(
        type(index) is not int or not 1 <= index <= step_index for index in sampled_steps
    ):
        raise MechanicsRejected("Invalid imported display sample ownership", stage="state")
    cache = {key: np.asarray(value, dtype=np.float64) for key, value in raw.items()}
    if any(not np.isfinite(value).all() for value in cache.values()):
        raise MechanicsRejected("Nonfinite imported mechanics cache", stage="state")
    geometry = binding.definition["geometry"]
    n, e = len(geometry["cell_ids"]), len(geometry["environment_ids"])
    for key in CACHE_KEYS:
        shape = (
            (n, 2)
            if key == "display_centres_m"
            else (
                (len(geometry["layout"]["vertices_m"]), 2)
                if key == "display_vertices_m"
                else ((e,) if key == "osmo_P_env" else (n,))
            )
        )
        if (
            not key.startswith("u_cells_")
            and not key.startswith("u_env_")
            and cache[key].shape != shape
        ):
            raise MechanicsRejected("Incorrect imported cache owner axis: " + key, stage="state")
    return _state(binding, cache, step_index, tuple(sampled_steps))


def _state(binding, cache, index, samples):
    cache = freeze(cache)
    identity = digest(dict(binding=binding.identity, step=index, samples=samples, cache=cache))
    return State(binding.identity, index, samples, cache, identity)


def _verify(binding, parent):
    if (
        digest(_binding_record(binding)) != binding.identity
        or bind(binding.definition).identity != binding.identity
        or parent.binding_identity != binding.identity
    ):
        raise MechanicsRejected("Changed geometry/operators or foreign state", stage="association")
    if digest(
        dict(
            binding=binding.identity,
            step=parent.step_index,
            samples=parent.sampled_steps,
            cache=parent.cache,
        )
    ) != parent.identity or any(value.flags.writeable for value in parent.cache.values()):
        raise MechanicsRejected("Changed or writable mechanics state", stage="association")


def step(binding, parent, supplied):
    _verify(binding, parent)
    if parent.step_index >= MAX_STEPS:
        raise MechanicsRejected("Three-call source cap", stage="source")
    definition = binding.definition
    geometry, p, policy = (definition[key] for key in ("geometry", "parameters", "policy"))
    receipt = supplied["receipt"]
    if receipt != dict(
        stage=FIELD_STAGE,
        geometry_epoch=definition["provenance"]["geometry_epoch"],
        cell_ids=geometry["cell_ids"],
        environment_ids=geometry["environment_ids"],
        source_step=parent.step_index,
        deferred_material_voltage_commit_done=False,
    ):
        raise MechanicsRejected(
            "Incorrect shared-field owner/stage receipt", stage="field_prerequisite"
        )
    clock = supplied["clock_s"]
    if (
        type(clock) not in (int, float)
        or not math.isfinite(clock)
        or clock < 0
        or supplied["dt_s"] != p["dt_s"]
    ):
        raise MechanicsRejected(
            "Require original phase dt and explicit finite source clock", stage="clock"
        )
    cache = {key: np.array(value, copy=True) for key, value in parent.cache.items()}
    frames, auxiliary, stage = [], {}, "initial"

    def observe(name):
        frames.append(
            freeze(
                dict(
                    stage=name,
                    cache={key: np.array(value, copy=True) for key, value in cache.items()},
                )
            )
        )

    def trial():
        candidate = _state(binding, cache, parent.step_index + 1, parent.sampled_steps)
        record = dict(
            parent=parent.identity,
            binding=binding.identity,
            supplied=freeze(supplied),
            frames=frames,
            auxiliaries=auxiliary,
            candidate=candidate.identity,
        )
        return Trial(
            parent.identity,
            binding.identity,
            freeze(supplied),
            tuple(frames),
            freeze(auxiliary),
            candidate,
            digest(record),
        )

    observe("initial")
    try:
        mesh = geometry["layout"]
        pressure = np.asarray(supplied["pressure_Pa"], dtype=np.float64)
        if policy["deform_osmo"]:
            stage = "osmotic_pressure"
            for group, enabled in (
                ("primary", True),
                ("molecule", policy["molecules_enabled"]),
                ("grn", policy["grn_enabled"]),
            ):
                if enabled:
                    ids = supplied[group + "_ids"]
                    a, b = supplied[group + "_cell_mM"], supplied[group + "_env_mM"]
                    if (
                        not 1 <= len(ids) <= 16
                        or len(ids) != len(a)
                        or len(a) != len(b)
                        or len(set(ids)) != len(ids)
                        or any(type(value) is not str or not value for value in ids)
                        or np.shape(a) != (len(ids), len(geometry["cell_ids"]))
                        or np.shape(b) != (len(ids), len(geometry["environment_ids"]))
                    ):
                        raise ValueError(
                            "Incomplete paired concentration inventory owners: " + group
                        )
            cell = np.sum(np.asarray(supplied["primary_cell_mM"], dtype=np.float64), axis=0)
            env = np.sum(np.asarray(supplied["primary_env_mM"], dtype=np.float64), axis=0)
            for group, enabled in (
                ("molecule", policy["molecules_enabled"]),
                ("grn", policy["grn_enabled"]),
            ):
                if enabled:
                    for row in supplied[group + "_cell_mM"]:
                        cell = cell + np.asarray(row, dtype=np.float64)
                    for row in supplied[group + "_env_mM"]:
                        env = env + np.asarray(row, dtype=np.float64)
            osmotic = deformation.osmotic_auxiliary(
                cell,
                env,
                pressure,
                deformation.OsmoticGeometry(
                    binding.environment_average,
                    np.asarray(mesh["cell_area_m2"]),
                    np.asarray(mesh["cell_volume_m3"]),
                ),
                binding.operators,
                deformation.OsmoticParameters(
                    p["gas_constant_J_mol_K"],
                    supplied["temperature_K"],
                    p["aquaporin_fraction"],
                    p["water_viscosity_Pa_s"],
                    p["membrane_thickness_m"],
                    p["density_kg_m3"],
                    p["dt_s"],
                ),
                xp=np,
            )
            auxiliary["osmotic"] = osmotic._asdict()
            for key, value in zip(
                ("osmo_P_cell", "osmo_P_env", "osmo_P_delta", "u_osmo", "div_u_osmo", "PP"),
                osmotic,
                strict=True,
            ):
                cache[key] = np.asarray(value)
            observe("osmotic_pressure")
        stage = "disabled_flow_gate"
        auxiliary["flow"] = flow.flow(None, binding.flow_binding, None, fluid_flow=False)
        observe("disabled_flow_gate")
        if policy["deformation"]:
            stage = "steady_deformation"
            # Native writes these two stores before reading E_cell at the final
            # displacement assignment. Retain them if the later supplied field is missing.
            cache["gPxc"] = np.einsum("ij,j->i", binding.operators.pressure_gradient_x, pressure)
            cache["gPyc"] = np.einsum("ij,j->i", binding.operators.pressure_gradient_y, pressure)
            forcing = deformation.Forcing(
                pressure,
                cache["PP"],
                np.asarray(supplied["electric_field_V_m"]),
                np.asarray(supplied["current_density_A_m2"]),
                np.asarray(supplied["charge_density_C_m3"]),
                np.asarray(supplied["conductivity_S_m"]),
            )
            parameters = deformation.Parameters(
                p["young_modulus_Pa"] / (2 * (1 + 0.49)),
                p["galvanotropism_m2_V"],
                policy["deform_osmo"],
                p["fixed_boundary"],
                p["dt_s"],
                p["viscous_damping_native"],
                p["cell_radius_m"],
            )
            result = deformation.steady(forcing, binding.operators, parameters, xp=np)
            auxiliary["steady"] = result._asdict()
            cache["gPxc"], cache["gPyc"] = result.pressure_gradient_Pa_m
            cache["d_cells_x"], cache["d_cells_y"] = result.displacement_m
            observe("steady_deformation")
        returned = trial()
        if any(not np.isfinite(value).all() for value in returned.candidate.cache.values()):
            raise MechanicsRejected(
                "Nonfinite complete mechanics output", stage=stage, trial=returned
            )
        return returned
    except MechanicsRejected:
        raise
    except Exception as error:
        raise MechanicsRejected(error, stage=stage, trial=trial()) from error


def sample(binding, parent, *, clock_s, postcommit_receipt):
    """Conditional sampled display after the caller's declared material/voltage barrier."""
    _verify(binding, parent)
    policy = binding.definition["policy"]
    expected = dict(
        stage=SAMPLE_STAGE,
        state_identity=parent.identity,
        geometry_epoch=binding.definition["provenance"]["geometry_epoch"],
        clock_s=clock_s,
    )
    if (
        postcommit_receipt != expected
        or type(clock_s) not in (int, float)
        or not math.isfinite(clock_s)
        or clock_s < 0
    ):
        raise MechanicsRejected(
            "Missing post-commit display barrier receipt", stage="sample_prerequisite"
        )
    if not policy["deformation"] or policy["display_regime"] != "global_quartic_conditional":
        raise MechanicsRejected(
            "No supported declared display interpolation regime", stage="sample_domain"
        )
    if parent.step_index == 0 or parent.step_index in parent.sampled_steps:
        raise MechanicsRejected(
            "Source step already sampled or no displacement yet", stage="sample_clock"
        )
    mesh = binding.definition["geometry"]["layout"]
    interpolation = result = None
    try:
        interpolation = deformation.quartic_display_interpolator(
            parent.cache["display_centres_m"], mesh["vertices_m"]
        )
        result = deformation.display(
            np.stack((parent.cache["d_cells_x"], parent.cache["d_cells_y"])),
            interpolation,
            np.asarray(mesh["vertices_m"]),
            binding.display_weights,
            xp=np,
        )
        if any(not np.isfinite(value).all() for value in result):
            raise ValueError("Nonfinite sampled display output")
    except Exception as error:
        raise MechanicsRejected(
            error,
            stage="sample_interpolation",
            trial=freeze(
                dict(
                    parent_identity=parent.identity,
                    parent_cache=parent.cache,
                    interpolation=interpolation,
                    result=result,
                    original_vertices_m=np.asarray(mesh["vertices_m"]),
                )
            ),
        ) from error
    cache = dict(parent.cache) | dict(
        display_centres_m=result.cell_centres_m, display_vertices_m=result.vertices_m
    )
    candidate = _state(
        binding, cache, parent.step_index, (*parent.sampled_steps, parent.step_index)
    )
    return freeze(
        dict(
            parent_identity=parent.identity,
            candidate_identity=candidate.identity,
            interpolation=interpolation,
            source_original_vertices_unchanged=True,
            physical_geometry_rebuilt=False,
            source_clock_s=clock_s,
        )
    ), candidate
