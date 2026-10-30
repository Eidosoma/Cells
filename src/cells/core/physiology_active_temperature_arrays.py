"""Trusted host preparation for homogeneous held-active array cohorts.

Point certificates preserve the existing held step/loss admission exactly;
changing a certified temperature requires a new host preparation. Runtime
control values, field solves, full rates and turnover checks are numeric.
"""

import hashlib
import json
from dataclasses import dataclass
from numbers import Real
from typing import NamedTuple

import jax
import numpy as np

from cells.core import physiology_active_temperature as contract
from cells.core.schedule import control_values
from cells.core.specs import digest, parse_spec
from cells.models import physiology_active_temperature_view as host
from cells.models import physiology_permeability_view as ordinary

KIND = "cells.physiology_active_temperature_array_cohort@1"


class Certificate(NamedTuple):
    temperature_K: object
    maximum_step_s: object


class NumericCohort(NamedTuple):
    state: object
    layout: object
    certificate: Certificate


@dataclass(frozen=True, slots=True)
class PreparedWorld:
    world_id: str
    family: str
    source_definition_sha256: str
    source_definition_json: str
    binding_record_json: str
    state: object
    layout: object
    certificate: Certificate
    original_checks: tuple
    numeric_sha256: str


@dataclass(frozen=True, slots=True)
class Cohort:
    worlds: tuple
    family: str
    numeric: NumericCohort
    identity: str


def _numeric_hash(value):
    parts = []
    for leaf in jax.tree.leaves(value):
        array = np.asarray(leaf)
        parts.append(
            dict(
                dtype=array.dtype.str,
                shape=list(array.shape),
                sha256=hashlib.sha256(array.tobytes()).hexdigest(),
            )
        )
    return digest(parts)


def prepare_world(spec, state, layout, binding, *, temperature_K, step_s, world_id):
    contract.validate_source(spec)
    contract.restore(contract.record(binding), spec)
    if type(world_id) is not str or not world_id.strip():
        raise ValueError("Declare a distinct stable world ID")
    for name, value in (("temperature_K", temperature_K), ("step_s", step_s)):
        if (
            not isinstance(value, Real)
            or isinstance(value, (bool, np.bool_))
            or not np.isfinite(value)
        ):
            raise ValueError("Require a finite host certificate scalar: " + name)
    if not 200 <= temperature_K <= 400 or not 0 < step_s <= spec.execution.dt:
        raise ValueError("Certificate leaves the held T/nominal-step contract")
    implementation = host.IMPLEMENTATIONS[type(spec.model)]
    initial, expected = implementation.initial_values(spec)
    ordinary._exact_layout(layout, expected)
    # Ordinary snapshot loading returns device buffers. Normalize EVERY leaf
    # before any NumPy validator/control construction; exact values and dtypes
    # were verified above, and the caller's original device tree is untouched.
    layout = type(layout)(*(np.asarray(value) for value in layout))
    actual = ordinary._state(state, initial)
    checks = implementation.check_values(actual, spec)
    table = control_values(spec, [0.0])
    # All-one availability cannot weaken any inherited rate/loss bound.
    # Channel padding retains its required neutral zero packet.
    maximum = type(table)(*(np.ones_like(value) for value in table))
    maximum = maximum._replace(channel=layout.channel_active[None].astype(np.float64))
    implementation.check_steps(spec, np.asarray([step_s]), maximum)
    projection = host._coefficient_projection(spec, temperature_K)
    implementation.check_steps(projection, np.asarray([step_s]), maximum)
    certificate = Certificate(
        np.asarray(temperature_K, dtype=np.float64), np.asarray(step_s, dtype=np.float64)
    )
    frozen = ordinary._immutable_tree(NumericCohort(actual, layout, certificate))
    return PreparedWorld(
        world_id,
        spec.to_dict()["model"]["id"],
        spec.fingerprint,
        json.dumps(spec.to_dict(), sort_keys=True, separators=(",", ":")),
        json.dumps(contract.record(binding), sort_keys=True, separators=(",", ":")),
        frozen.state,
        frozen.layout,
        frozen.certificate,
        tuple(sorted(checks.items())),
        _numeric_hash(frozen),
    )


def record(cohort):
    if type(cohort) is not Cohort:
        raise ValueError("Require the complete trusted array cohort")
    payload = dict(
        kind=KIND,
        policy=contract.POLICY,
        family=cohort.family,
        worlds=[
            dict(
                world_id=world.world_id,
                source_definition_sha256=world.source_definition_sha256,
                source_definition_json=world.source_definition_json,
                binding_record_json=world.binding_record_json,
                numeric_sha256=world.numeric_sha256,
                original_checks=dict(world.original_checks),
            )
            for world in cohort.worlds
        ],
        numeric_sha256=_numeric_hash(cohort.numeric),
        temperature_admission="host_certified_exact_Kelvin_point@1",
        accepted_stepping=False,
        gpu_qualified=False,
    )
    return payload | dict(identity=digest(payload))


def prepare_cohort(worlds):
    worlds = tuple(worlds)
    if not worlds or any(type(world) is not PreparedWorld for world in worlds):
        raise ValueError("Require nonempty host-prepared complete worlds")
    if len({world.world_id for world in worlds}) != len(worlds):
        raise ValueError("Array world IDs must be distinct")
    if len({world.family for world in worlds}) != 1:
        raise ValueError("An array cohort requires one exact active family")
    prototype = NumericCohort(worlds[0].state, worlds[0].layout, worlds[0].certificate)
    template, tree = jax.tree.flatten(prototype)
    for world in worlds:
        numeric = NumericCohort(world.state, world.layout, world.certificate)
        leaves, definition = jax.tree.flatten(numeric)
        if definition != tree or any(
            np.asarray(a).shape != np.asarray(b).shape or np.asarray(a).dtype != np.asarray(b).dtype
            for a, b in zip(leaves, template, strict=True)
        ):
            raise ValueError("Cohort requires homogeneous typed owner/chemical/capacity shapes")
        if _numeric_hash(numeric) != world.numeric_sha256:
            raise ValueError("Prepared source state/layout/certificate changed after admission")
        source = json.loads(world.source_definition_json)
        if digest(source) != world.source_definition_sha256:
            raise ValueError("Prepared source provenance no longer matches the actual definition")
        spec = parse_spec(source)
        binding = contract.restore(json.loads(world.binding_record_json), spec)
        checked = prepare_world(
            spec,
            world.state,
            world.layout,
            binding,
            temperature_K=float(world.certificate.temperature_K),
            step_s=float(world.certificate.maximum_step_s),
            world_id=world.world_id,
        )
        # Array equality is handled by the numeric hash; all remaining claims
        # are recomputed from actual original source admission.
        if (
            checked.family != world.family
            or checked.original_checks != world.original_checks
            or checked.numeric_sha256 != world.numeric_sha256
            or checked.source_definition_json != world.source_definition_json
            or checked.binding_record_json != world.binding_record_json
        ):
            raise ValueError("Prepared world claims differ from reconstructed source admission")
    numeric = ordinary._immutable_tree(
        jax.tree.map(
            lambda *values: np.stack(values),
            *(NumericCohort(w.state, w.layout, w.certificate) for w in worlds),
        )
    )
    pending = Cohort(worlds, worlds[0].family, numeric, "")
    return Cohort(worlds, pending.family, numeric, record(pending)["identity"])


def validate_cohort(cohort):
    if type(cohort) is not Cohort or cohort.identity != record(cohort)["identity"]:
        raise ValueError("Stale trusted cohort/source provenance")
    expected = prepare_cohort(cohort.worlds)
    if record(expected) != record(cohort):
        raise ValueError("Batched numeric arrays differ from their admitted original worlds")
    return cohort
