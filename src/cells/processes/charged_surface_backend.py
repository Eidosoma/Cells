"""HELD CPU/JAX execution adapter for the same bounded charged-surface owner.

No science imports occur until exact scalar acceptance and external backend
release dependencies pass. A call attempts one original interval per world.
Every member is retained, and any failed world refuses cohort publication.
"""

import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import version
from time import perf_counter

from cells.processes import charged_surface_backend_arrays as arrays
from cells.processes import charged_surface_backend_gate as gate
from cells.processes import charged_surface_backend_kernel as kernel
from cells.processes import charged_surface_backend_plan as planning
from cells.processes import charged_surface_work as scalar

HELD_SOURCE_PROTOTYPE = True
SCALAR_QUALIFICATION_REQUIRED = True
PREPARATION_AUTHORIZES_EXECUTION = False


@dataclass(frozen=True)
class WorldAttempt:
    world_id: int
    case_id: str
    source_checkpoint_json: str
    candidate_checkpoint_json: object
    accepted: bool
    terminal: bool
    evidence_json: str


@dataclass(frozen=True)
class BatchProposal:
    plan_identity: str
    cohort_identity: str
    worlds: tuple
    runtime_json: str
    authorization_json: str
    journal_json: str
    identity: str


@dataclass(frozen=True)
class BatchSnapshot:
    record_json: str
    identity: str


class BatchRejected(ValueError):
    def __init__(self, reason, *, worlds, evidence):
        super().__init__(reason)
        self.worlds = tuple(worlds)
        self.evidence = evidence


def cohort_identity(plan):
    return scalar.digest(
        dict(
            law=scalar.LAW_ID,
            scalar_source_manifest=planning.SCALAR_MANIFEST_SHA256,
            worlds=[
                dict(
                    world_id=world.world_id,
                    case_id=world.case_id,
                    declaration=scalar.parse(world.declaration_json),
                )
                for world in sorted(plan.worlds, key=lambda item: item.world_id)
            ],
        )
    )


def proposal_record(value):
    return dict(
        plan_identity=value.plan_identity,
        cohort_identity=value.cohort_identity,
        worlds=[
            dict(
                world_id=world.world_id,
                case_id=world.case_id,
                source_checkpoint_json=world.source_checkpoint_json,
                candidate_checkpoint_json=world.candidate_checkpoint_json,
                accepted=world.accepted,
                terminal=world.terminal,
                evidence_json=world.evidence_json,
            )
            for world in value.worlds
        ],
        runtime_json=value.runtime_json,
        authorization_json=value.authorization_json,
        journal_json=value.journal_json,
    )


class Runner:
    def __init__(self, plan, *, release_path=None, observer=None):
        self.plan = planning.validate_plan(plan)
        self.execution = json.loads(plan.execution_json)
        self.release_path, self.observer = release_path, observer
        self.authorization = gate.authorize(release_path, self.execution)
        # All numerical imports and host admission are below the release gate.
        import numpy as np

        self.np = np
        self.jax = self.xp = self.device = None
        if self.execution["engine"] == "jax":
            import jax
            import jax.numpy as jnp

            from cells.core.devices import execution_device

            self.device = execution_device(self.execution["backend"])
            if not jax.config.x64_enabled:
                raise ValueError("Binary64 execution is required; no precision fallback")
            self.jax, self.xp = jax, jnp
        else:
            self.xp = np
        self.contexts = {}
        failures = []
        for world in plan.worlds:
            try:
                binding = scalar.bind(scalar.parse(world.declaration_json))
                parameters = scalar._parameters(binding)
                for array in (*parameters[6], *parameters[7:]):
                    array.setflags(write=False)
                self.contexts[world.world_id] = (binding, parameters)
            except Exception as error:
                failures.append(
                    dict(
                        world_id=world.world_id,
                        case_id=world.case_id,
                        status="scalar_admission_failed",
                        reason=str(error),
                        code=getattr(error, "code", None),
                        partial=getattr(error, "partial", None),
                    )
                )
        if failures:
            raise BatchRejected(
                "Complete scalar world admission refused; no cohort published",
                worlds=tuple(world.world_id for world in plan.worlds),
                evidence=dict(
                    failed_admissions=failures,
                    all_world_declarations=json.loads(plan.declaration_json),
                ),
            )
        self.cache = {}
        self.compiler_code_bytes = 0
        self.compiler_peak_buffer_bytes = 0

    def runtime_identity(self):
        value = dict(
            engine=self.execution["engine"],
            backend=self.execution["backend"],
            jit=self.execution["jit"],
            mapping="lax_map",
            precision="binary64",
            python=sys.version,
            numpy=self.np.__version__,
            jax=version("jax"),
            jaxlib=version("jaxlib"),
        )
        if self.device is None:
            value.update(platform="cpu", device_kind="host_numpy", device_id=None, x64=True)
        else:
            value.update(
                platform=self.device.platform,
                device_kind=self.device.device_kind,
                device_id=self.device.id,
                x64=bool(self.jax.config.x64_enabled),
            )
        return value

    def _emit(self, name, value):
        if self.observer is not None:
            self.observer(name, value)

    def _sources(self):
        actual = gate.authorize(self.release_path, self.execution)
        if actual != self.authorization:
            raise ValueError("Release/source identity changed during cohort execution")

    def _checkpoint_map(self, checkpoints):
        if not isinstance(checkpoints, Mapping) or any(type(key) is not int for key in checkpoints):
            raise ValueError("Complete checkpoints must be keyed by exact integer world IDs")
        if set(checkpoints) != {world.world_id for world in self.plan.worlds}:
            raise ValueError("No missing, duplicated, extra or implicitly dropped world")
        failures = []
        for world in self.plan.worlds:
            binding, parameters = self.contexts[world.world_id]
            try:
                vector = scalar._checkpoint(binding, checkpoints[world.world_id], parameters)
                scalar._check_balances(vector, parameters)
            except Exception as error:
                checkpoint = checkpoints[world.world_id]
                failures.append(
                    dict(
                        world_id=world.world_id,
                        case_id=world.case_id,
                        input=scalar.checkpoint_record(checkpoint)
                        if type(checkpoint) is scalar.Checkpoint
                        else repr(checkpoint),
                        code=getattr(error, "code", None),
                        reason=str(error),
                        partial=getattr(error, "partial", None),
                    )
                )
        if failures:
            raise BatchRejected(
                "Source checkpoint admission refused before any group execution",
                worlds=tuple(world.world_id for world in self.plan.worlds),
                evidence=dict(
                    failed_admissions=failures,
                    member_world_ids=[world.world_id for world in self.plan.worlds],
                    complete_available_parents=self._source_inventory(checkpoints),
                ),
            )

    def _source_inventory(self, checkpoints):
        result = {}
        for world in self.plan.worlds:
            value = checkpoints.get(world.world_id) if isinstance(checkpoints, Mapping) else None
            try:
                record = scalar.checkpoint_record(value)
            except Exception as error:
                record = dict(
                    type=type(value).__name__, available_repr=repr(value), reason=str(error)
                )
            result[str(world.world_id)] = dict(case_id=world.case_id, checkpoint=record)
        return result

    def initial_checkpoints(self):
        self._sources()
        result = {}
        for world in self.plan.worlds:
            try:
                result[world.world_id] = scalar.initial(self.contexts[world.world_id][0])
            except Exception as error:
                raise BatchRejected(
                    "Initial setup failed before any interval execution",
                    worlds=tuple(row.world_id for row in self.plan.worlds),
                    evidence=dict(
                        failed_world_id=world.world_id,
                        complete_declarations=json.loads(self.plan.declaration_json),
                        available_parents={
                            str(key): scalar.checkpoint_record(value)
                            for key, value in result.items()
                        },
                        original_reason=str(error),
                        original_partial=getattr(error, "partial", None),
                    ),
                ) from error
        return result

    def _inputs(self, group, checkpoints):
        np = self.np
        inputs = []
        for world_id in group.world_ids:
            binding, parameters = self.contexts[world_id]
            raw, _, _, _, _, _, p, anchor, reference, potential = parameters
            checkpoint = checkpoints[world_id]
            vector = arrays.State(*scalar._checkpoint(binding, checkpoint, parameters))
            index = checkpoint.step_index
            ready = index + 1 < len(raw["time_labels_s"])
            dt = raw["time_labels_s"][index + 1] - raw["time_labels_s"][index] if ready else 0.0
            numeric = arrays.Parameters(arrays.Layout(*p), anchor, reference, potential)
            inputs.append(
                arrays.Inputs(vector, numeric, np.asarray(dt, dtype=np.float64), np.asarray(ready))
            )
        packed = kernel._stack(inputs, np)
        arrays.check_axes(
            packed, arrays.schemas(*group.dimensions)["inputs"], np, worlds=len(group.world_ids)
        )
        if arrays.actual_bytes(packed) != group.input_array_bytes:
            raise ValueError("Actual input array bytes differ from preallocation schema")
        return packed

    def _execute(self, group, inputs):
        _, parameters = self.contexts[group.world_ids[0]]
        _, _, movement, fixed, F, R, _, _, _, _ = parameters
        from cells.numerics.extracellular_field import ordered_scatter

        key = (group.signature, len(group.world_ids))
        if key not in self.cache:
            _, mapped = kernel.build_kernel(
                xp=self.xp,
                jax=self.jax,
                movement=movement,
                fixed=fixed,
                F=F,
                R=R,
                ordered_scatter=ordered_scatter,
                scalar=scalar,
                dimensions=group.dimensions,
            )
            self.cache[key] = dict(mapped=mapped, compiled=None, compiler_memory=None)
        entry = self.cache[key]
        device_inputs = inputs
        failures = []
        if self.jax is not None:
            device_inputs = self.jax.device_put(inputs, self.device)
            self.jax.block_until_ready(device_inputs)
        started = perf_counter()
        if self.jax is not None and self.execution["jit"]:
            if entry["compiled"] is None:
                compiled = self.jax.jit(entry["mapped"]).lower(device_inputs).compile()
                stats = compiled.memory_analysis()
                if stats is None:
                    raise ValueError(
                        "Compiled allocation report unavailable; no unaccounted compiled execution"
                    )
                report = {
                    name: int(getattr(stats, name))
                    for name in (
                        "argument_size_in_bytes",
                        "output_size_in_bytes",
                        "temp_size_in_bytes",
                        "alias_size_in_bytes",
                        "generated_code_size_in_bytes",
                    )
                }
                code_bytes = self.compiler_code_bytes + report["generated_code_size_in_bytes"]
                buffers = max(
                    self.compiler_peak_buffer_bytes,
                    report["argument_size_in_bytes"]
                    + report["output_size_in_bytes"]
                    + report["temp_size_in_bytes"]
                    - report["alias_size_in_bytes"],
                )
                if code_bytes + buffers > self.execution["max_compiler_bytes"]:
                    raise ValueError(
                        "Compiler-reported code/buffer bytes exceed the declared allowance"
                    )
                self.compiler_code_bytes, self.compiler_peak_buffer_bytes = code_bytes, buffers
                entry.update(compiled=compiled, compiler_memory=report)
            outputs = entry["compiled"](device_inputs)
        elif self.jax is not None:
            with self.jax.disable_jit():
                outputs = entry["mapped"](device_inputs)
        else:
            outputs = entry["mapped"](device_inputs)
        if self.jax is not None:
            self.jax.block_until_ready(outputs)
            leaves = self.jax.tree.leaves((device_inputs, outputs))
            if any(value.dtype.kind == "f" and value.dtype.itemsize != 8 for value in leaves):
                failures.append("Actual device computation lost binary64 precision")
            if any(set(value.devices()) != {self.device} for value in leaves):
                failures.append("Actual array placement differs; no backend fallback")
        host = arrays.map_tree(self.np.asarray, outputs)
        try:
            arrays.check_axes(
                host,
                arrays.schemas(*group.dimensions)["attempt"],
                self.np,
                worlds=len(group.world_ids),
            )
        except ValueError as error:
            failures.append(str(error))
        if arrays.actual_bytes(host) != group.output_array_bytes:
            failures.append("Actual complete output bytes differ from predeclared schema")
        return host, dict(
            input_array_bytes=arrays.actual_bytes(inputs),
            output_array_bytes=arrays.actual_bytes(host),
            compiler_memory=entry["compiler_memory"],
            elapsed_seconds=perf_counter() - started,
            output_admission_failures=failures,
            timing_scope="One actual attempt; no warmup, repeats or performance qualification",
        )

    def advance(self, checkpoints):
        """Try every member; publish no cohort checkpoint if any member fails."""
        context = dict(
            phase="setup",
            complete_declaration=json.loads(self.plan.declaration_json),
            plan_identity=self.plan.identity,
            complete_available_parents=self._source_inventory(checkpoints),
            groups=[],
            completed_worlds={},
        )
        try:
            return self._advance(checkpoints, context)
        except BatchRejected as error:
            error.evidence = dict(available_context=context, original_failure=error.evidence)
            raise
        except Exception as error:
            raise BatchRejected(
                "Cohort setup/execution/final-readout failed",
                worlds=tuple(world.world_id for world in self.plan.worlds),
                evidence=dict(
                    available_context=context,
                    original_type=type(error).__name__,
                    original_reason=str(error),
                    original_partial=getattr(error, "partial", None),
                ),
            ) from error

    def _advance(self, checkpoints, context):
        context["phase"] = "source_and_checkpoint_admission"
        self._sources()
        self._checkpoint_map(checkpoints)
        attempts = {}
        group_evidence = context["groups"]
        backend_failed = False
        for group_index, group in enumerate(self.plan.groups):
            context.update(
                phase="group_pack", group_index=group_index, current_world_ids=group.world_ids
            )
            if backend_failed:
                for world_id in group.world_ids:
                    attempts[world_id] = self._failed_world(
                        world_id, checkpoints, "not_attempted_after_backend_failure"
                    )
                continue
            inputs = self._inputs(group, checkpoints)
            raw_input = scalar._record(inputs, self.np)
            context["current_complete_input"] = raw_input
            self._emit(
                "group_input",
                dict(group_index=group_index, world_ids=group.world_ids, raw=raw_input),
            )
            try:
                context["phase"] = "array_execution"
                host, resources = self._execute(group, inputs)
            except Exception as error:
                backend_failed = True
                failure = dict(
                    type=type(error).__name__,
                    reason=str(error),
                    actual_outputs_available=False,
                    group_index=group_index,
                    world_ids=group.world_ids,
                    complete_inputs=raw_input,
                )
                group_evidence.append(failure)
                self._emit("backend_failure", failure)
                for world_id in group.world_ids:
                    attempts[world_id] = self._failed_world(
                        world_id, checkpoints, "backend_failure", failure
                    )
                continue
            raw_output = scalar._record(host, self.np)
            context["phase"] = "raw_output_before_admission"
            evidence = dict(
                group_index=group_index,
                signature=group.signature,
                original_positions=group.positions,
                world_ids=group.world_ids,
                complete_inputs=raw_input,
                complete_raw_outputs=raw_output,
                resources=resources,
            )
            group_evidence.append(evidence)
            self._emit("group_output_before_acceptance", evidence)
            if resources["output_admission_failures"]:
                for world_id in group.world_ids:
                    attempts[world_id] = self._failed_world(
                        world_id, checkpoints, "complete_output_admission_failed", evidence
                    )
                continue
            for slot, world_id in enumerate(group.world_ids):
                context.update(phase="world_final_readout", current_world_id=world_id)
                observed = arrays.map_tree(lambda leaf, slot=slot: leaf[slot], host)
                attempts[world_id] = self._world_attempt(world_id, checkpoints, observed)
                context["completed_worlds"][str(world_id)] = dict(
                    world_id=world_id,
                    case_id=attempts[world_id].case_id,
                    accepted=attempts[world_id].accepted,
                    evidence_json=attempts[world_id].evidence_json,
                )
        ordered = tuple(attempts[world.world_id] for world in self.plan.worlds)
        journal = dict(
            plan_identity=self.plan.identity,
            cohort_identity=cohort_identity(self.plan),
            member_world_ids=[world.world_id for world in self.plan.worlds],
            groups=group_evidence,
            attempts=[
                dict(
                    world_id=row.world_id,
                    case_id=row.case_id,
                    accepted=row.accepted,
                    terminal=row.terminal,
                )
                for row in ordered
            ],
        )
        self._emit("complete_cohort_attempt", journal)
        if any(not row.accepted for row in ordered):
            raise BatchRejected(
                "At least one world failed; no cohort checkpoint published",
                worlds=ordered,
                evidence=journal,
            )
        try:
            context["phase"] = "final_source_and_publication_checks"
            self._sources()
        except Exception as error:
            raise BatchRejected(
                "Source/release changed before publication",
                worlds=ordered,
                evidence=dict(journal=journal, reason=str(error)),
            ) from error
        payload = BatchProposal(
            self.plan.identity,
            cohort_identity(self.plan),
            ordered,
            json.dumps(self.runtime_identity(), sort_keys=True),
            json.dumps(self.authorization, sort_keys=True),
            json.dumps(journal, sort_keys=True, separators=(",", ":"), allow_nan=False),
            "",
        )
        record = proposal_record(payload)
        encoded = json.dumps(record, allow_nan=False, separators=(",", ":"))
        if len(encoded.encode()) > self.execution["max_evidence_bytes"]:
            raise BatchRejected(
                "Complete evidence exceeds declared cap; no cohort published",
                worlds=ordered,
                evidence=journal,
            )
        return BatchProposal(
            payload.plan_identity,
            payload.cohort_identity,
            payload.worlds,
            payload.runtime_json,
            payload.authorization_json,
            payload.journal_json,
            scalar.digest(record),
        )

    def _world(self, world_id):
        return next(world for world in self.plan.worlds if world.world_id == world_id)

    def _failed_world(self, world_id, checkpoints, reason, failure=None):
        world = self._world(world_id)
        return WorldAttempt(
            world_id,
            world.case_id,
            scalar.dump_checkpoint(checkpoints[world_id]),
            None,
            False,
            False,
            json.dumps(dict(status=reason, failure=failure), sort_keys=True),
        )

    def _world_attempt(self, world_id, checkpoints, observed):
        world = self._world(world_id)
        parent = checkpoints[world_id]
        binding, parameters = self.contexts[world_id]
        record = dict(
            world_id=world_id,
            case_id=world.case_id,
            source_checkpoint=scalar.checkpoint_record(parent),
            raw_array_attempt=scalar._record(observed, self.np),
            masks=(
                "attempted/called/endpoint_formed distinguish actual outputs "
                "from absent arithmetic slots"
            ),
        )
        candidate = None
        accepted = bool(observed.ok)
        terminal = not bool(observed.ready)
        try:
            if accepted and terminal:
                if int(observed.code) != 0:
                    raise ValueError("Terminal world has a nonterminal status")
                source = scalar._checkpoint(binding, parent, parameters)
                if any(
                    not self.np.array_equal(a.view("uint8"), b.view("uint8"))
                    for a, b in zip(source, observed.candidate, strict=True)
                ):
                    raise ValueError("Terminal world state changed")
                candidate = parent
            elif accepted:
                if (
                    int(observed.code) != 1
                    or not bool(observed.endpoint_formed)
                    or not all(bool(item.ok) for item in observed.trials)
                ):
                    raise ValueError("A complete four-trial endpoint is required")
                labels = parameters[0]["time_labels_s"]
                next_index = parent.step_index + 1
                candidate = scalar._seal_checkpoint(
                    binding, observed.candidate, labels[next_index], next_index, self.np
                )
                numeric = scalar._checkpoint(binding, candidate, parameters)
                previous = scalar._checkpoint(binding, parent, parameters)
                scalar._check_balances(numeric, parameters, previous=previous)
            else:
                # Failure keeps the original source. The speculative candidate
                # and first refused actual stage remain in the raw array tree.
                source = scalar._checkpoint(binding, parent, parameters)
                if any(
                    not self.np.array_equal(a.view("uint8"), b.view("uint8"))
                    for a, b in zip(source, observed.candidate, strict=True)
                ):
                    raise ValueError("A rejected world altered its restart state")
        except Exception as error:
            accepted, candidate = False, None
            record["host_admission_failure"] = dict(
                reason=str(error),
                code=getattr(error, "code", None),
                partial=getattr(error, "partial", None),
            )
        return WorldAttempt(
            world_id,
            world.case_id,
            scalar.dump_checkpoint(parent),
            None if candidate is None else scalar.dump_checkpoint(candidate),
            accepted,
            terminal,
            json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False),
        )

    def checkpoints(self, proposal):
        self._sources()
        if (
            type(proposal) is not BatchProposal
            or proposal.plan_identity != self.plan.identity
            or proposal.cohort_identity != cohort_identity(self.plan)
            or scalar.digest(proposal_record(proposal)) != proposal.identity
        ):
            raise ValueError("Complete source-bound batch proposal required")
        if (
            json.loads(proposal.runtime_json) != self.runtime_identity()
            or json.loads(proposal.authorization_json) != self.authorization
        ):
            raise ValueError("Proposal runtime or authorization association changed")
        if [world.world_id for world in proposal.worlds] != [
            world.world_id for world in self.plan.worlds
        ] or any(not world.accepted for world in proposal.worlds):
            raise ValueError("No incomplete, reordered or rejected cohort publication")
        result = {}
        for world, row in zip(self.plan.worlds, proposal.worlds, strict=True):
            binding, parameters = self.contexts[world.world_id]
            if row.case_id != world.case_id:
                raise ValueError("Proposal case/world association changed")
            source = scalar.load_checkpoint(binding, row.source_checkpoint_json)
            candidate = scalar.load_checkpoint(binding, row.candidate_checkpoint_json)
            record = scalar.parse(row.evidence_json, max_bytes=32 * 2**20)
            if (
                record["world_id"] != world.world_id
                or record["case_id"] != world.case_id
                or record["source_checkpoint"] != scalar.checkpoint_record(source)
            ):
                raise ValueError("Proposal raw evidence belongs to a different exact parent")
            if row.terminal:
                if (
                    candidate != source
                    or source.step_index != len(parameters[0]["time_labels_s"]) - 1
                ):
                    raise ValueError("Terminal publication changed original state or clock")
            elif candidate.step_index != source.step_index + 1:
                raise ValueError("Only one original declared interval may be published")
            result[world.world_id] = candidate
        self._checkpoint_map(result)
        self._sources()
        return result

    def snapshot(self, checkpoints):
        self._sources()
        self._checkpoint_map(checkpoints)
        runtime_before = self.runtime_identity()
        record = dict(
            kind="cells.charged_surface_backend_checkpoint@1",
            cohort_identity=cohort_identity(self.plan),
            origin_plan_identity=self.plan.identity,
            source_manifest_sha256=self.authorization["source_manifest_sha256"],
            scalar_source_manifest_sha256=planning.SCALAR_MANIFEST_SHA256,
            runtime=runtime_before,
            worlds=[
                dict(
                    world_id=world.world_id,
                    case_id=world.case_id,
                    binding_identity=self.contexts[world.world_id][0].identity,
                    checkpoint_json=scalar.dump_checkpoint(checkpoints[world.world_id]),
                )
                for world in self.plan.worlds
            ],
        )
        self._sources()
        if self.runtime_identity() != runtime_before:
            raise ValueError("Runtime changed during cohort checkpoint publication")
        text = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return BatchSnapshot(text, scalar.digest(record))

    def load_snapshot(self, snapshot):
        if type(snapshot) is not BatchSnapshot:
            raise ValueError("Require a complete immutable batch snapshot")
        self._sources()
        record = scalar.parse(snapshot.record_json, max_bytes=64 * 2**20)
        expected = {
            "kind",
            "cohort_identity",
            "origin_plan_identity",
            "source_manifest_sha256",
            "scalar_source_manifest_sha256",
            "runtime",
            "worlds",
        }
        if (
            set(record) != expected
            or scalar.digest(record) != snapshot.identity
            or record["kind"] != "cells.charged_surface_backend_checkpoint@1"
            or record["cohort_identity"] != cohort_identity(self.plan)
        ):
            raise ValueError("Complete unchanged scientific cohort snapshot required")
        if (
            record["source_manifest_sha256"] != self.authorization["source_manifest_sha256"]
            or record["scalar_source_manifest_sha256"] != planning.SCALAR_MANIFEST_SHA256
            or record["runtime"] != self.runtime_identity()
        ):
            raise ValueError("Source/runtime differs; no implicit checkpoint migration")
        rows = record["worlds"]
        if len(rows) != len(self.plan.worlds) or len({row["world_id"] for row in rows}) != len(
            rows
        ):
            raise ValueError("Every original named world must occur exactly once")
        lookup = {world.world_id: world for world in self.plan.worlds}
        result = {}
        for row in rows:
            if (
                set(row) != {"world_id", "case_id", "binding_identity", "checkpoint_json"}
                or type(row["world_id"]) is not int
                or row["world_id"] not in lookup
            ):
                raise ValueError("Snapshot has an invalid or unknown world")
            world = lookup[row["world_id"]]
            binding = self.contexts[world.world_id][0]
            if row["case_id"] != world.case_id or row["binding_identity"] != binding.identity:
                raise ValueError("Case or exact scalar owner binding changed")
            result[world.world_id] = scalar.load_checkpoint(binding, row["checkpoint_json"])
        self._checkpoint_map(result)
        return result


def dump_snapshot(snapshot):
    if type(snapshot) is not BatchSnapshot:
        raise ValueError("Complete batch snapshot required")
    return json.dumps(
        dict(
            record=scalar.parse(snapshot.record_json, max_bytes=64 * 2**20),
            identity=snapshot.identity,
        ),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def parse_snapshot(text):
    raw = scalar.parse(text, max_bytes=64 * 2**20)
    if set(raw) != {"record", "identity"} or scalar.digest(raw["record"]) != raw["identity"]:
        raise ValueError("Complete batch snapshot seal differs")
    return BatchSnapshot(
        json.dumps(raw["record"], sort_keys=True, separators=(",", ":"), allow_nan=False),
        raw["identity"],
    )
