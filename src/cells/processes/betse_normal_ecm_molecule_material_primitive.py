"""Opt-in standalone material chronology beyond the legacy three-call domain.

The only arithmetic is betse_ecm_transport._step_source. This domain does not
extend network, field, calcium, catalog, mechanics, INIT/SIM or checkpoint
admission. Initial data are explicitly declared inputs, not native derivation
or a transported completed owner. The existing external process guard remains
required: the local resource checks sample at Python/source boundaries.
"""

import os
import sys
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from cells.processes import betse_ecm_transport as material
from cells.processes import betse_normal_ecm_molecule_checkpoint_codec as codec
from cells.processes import betse_normal_ecm_molecule_material_domain as contract

KIND = "cells.standalone_extended_ECM_material@1"
RELEASE = "CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED"
require = codec.require
_SOURCE_CODE = material._step_source.__wrapped__.__code__


@dataclass(frozen=True, slots=True)
class Policy:
    cpu: int = 0
    threads: int = 1
    max_rss_bytes: int = 2**30
    min_available_bytes: int = 8 * 2**30
    outer_guard_required: bool = True


@dataclass(frozen=True, slots=True)
class Domain:
    budget: contract.Budget
    policy: Policy
    run_id: str
    provenance: str
    identity: str


DEFAULT_POLICY = Policy()


def domain_record(value):
    return (
        KIND,
        contract.budget_record(value.budget),
        tuple(getattr(value.policy, name) for name in Policy.__dataclass_fields__),
        value.run_id,
        value.provenance,
    )


def declare(budget, *, run_id, provenance, policy=DEFAULT_POLICY):
    """Metadata declaration only; no material binding/state or numerical credit."""
    contract.verify_budget(budget)
    require(type(policy) is Policy, "Typed standalone resource policy required")
    require(
        type(policy.cpu) is int
        and policy.cpu == 0
        and type(policy.threads) is int
        and policy.threads == 1
        and type(policy.max_rss_bytes) is int
        and 0 < policy.max_rss_bytes <= 2**30
        and type(policy.min_available_bytes) is int
        and policy.min_available_bytes >= 8 * 2**30
        and policy.outer_guard_required is True
        and budget.wall_seconds <= 480.0,
        "Require the bounded CPU0/one-thread standalone process-guard policy",
    )
    require(
        all(type(v) is str and bool(v.strip()) for v in (run_id, provenance)),
        "Explicit run identity and declared input provenance required",
    )
    value = Domain(budget, policy, run_id, provenance, "")
    return replace(value, identity=codec.fingerprint(domain_record(value)))


def verify_domain(value):
    require(
        type(value) is Domain,
        "Separate typed numerical domain required; metadata borrowing refused",
    )
    checked = declare(
        value.budget, run_id=value.run_id, provenance=value.provenance, policy=value.policy
    )
    require(value.identity == checked.identity, "Changed standalone domain")


@dataclass(frozen=True, slots=True)
class Binding:
    domain: Domain
    source: material.Binding
    input_fingerprint: str
    identity: str


@dataclass(frozen=True, slots=True)
class State:
    binding_identity: str
    source: material.State
    initial_identity: str
    previous_identity: str | None
    forcing_fingerprint: str | None
    attempt_ordinal: int
    status: str
    identity: str

    @property
    def absolute_index(self):
        return self.source.step_index


def binding_record(value):
    return (KIND, domain_record(value.domain), value.source, value.input_fingerprint)


def state_record(value):
    return (
        KIND,
        value.binding_identity,
        value.source,
        value.initial_identity,
        value.previous_identity,
        value.forcing_fingerprint,
        value.attempt_ordinal,
        value.status,
    )


class PrimitiveRejected(RuntimeError):
    def __init__(self, error, *, execution, stage, parent, forcing):
        super().__init__(str(error))
        self.primary, self.execution, self.stage = error, execution, stage
        self.parent, self.forcing = parent, forcing
        self.trial = getattr(error, "trial", None)
        self.accepted = execution.current
        self.automatic_retry = False


class WorkLimit(ValueError):
    pass


def resources(policy):
    """Samples supplement, and do not replace, the external group guard."""
    require(os.sched_getaffinity(0) == {policy.cpu}, "Changed actual CPU affinity")
    require(
        all(
            os.environ.get(n) == "1"
            for n in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        ),
        "Actual one-thread environment required before source construction",
    )
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    memory = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
    rss = int(status["VmRSS"].split()[0]) * 1024
    available = int(memory["MemAvailable"].split()[0]) * 1024
    require(
        rss <= policy.max_rss_bytes and available >= policy.min_available_bytes,
        "Standalone sampled memory/reserve policy exhausted",
    )
    return dict(rss_bytes=rss, available_bytes=available)


class Execution:
    """Single live lineage: an old parent or a failed call cannot be replayed.

    No public constructor accepts an owner, saved state, receipt or metadata
    Retained record. Work counters survive rejection; admission of new numerical
    state occurs only after the shared source returns an accepted complete trial.
    """

    def __init__(self, declared, definition, initial):
        self.domain = declared
        self._declared_domain = declared
        self._declared_identity = declared.identity
        self.definition, self.initial = definition, initial
        self.binding = self.current = None
        self._advance_active = False
        self._active_context = None
        self._accepted_calls = 0
        self._initial_identity = self._last_identity = None
        self._binding_fingerprint = self._state_fingerprint = None
        self.journal, self.attempts, self.recovery_errors = [], [], []
        self.failed = False
        self.requests = self.material_attempts = self.owner_verifications = 0
        self.source_requests = self.source_entries = self.nested_source_calls = 0
        self.retained_bytes = 0
        self.started = time.monotonic()
        self.thread = threading.get_ident()
        self.input_fingerprint = codec.fingerprint((definition, initial))

    def _check(self):
        require(
            self.domain is self._declared_domain
            and self.domain.identity == self._declared_identity,
            "Changed declared execution domain; limits cannot be rebound after issue",
        )
        require(threading.get_ident() == self.thread, "Execution belongs to its original thread")
        limit = self.domain.budget
        if (
            time.monotonic() - self.started > limit.wall_seconds
            or self.nested_source_calls > limit.max_nested_source_invocations
            or self.owner_verifications > limit.max_owner_verifications
        ):
            raise WorkLimit("Declared cumulative material work/wall policy exhausted")
        resources(self.domain.policy)

    def _call(self, stage, operation):
        self._check()
        previous = sys.getprofile()
        row = dict(stage=stage, status="attempted", nested_before=self.nested_source_calls)
        self.journal.append(row)

        def observe(frame, event, arg):
            if previous is not None:
                previous(frame, event, arg)
            if event == "call" and frame.f_globals.get("__name__", "").startswith("cells."):
                self.nested_source_calls += 1
                if frame.f_code is _SOURCE_CODE:
                    self.source_entries += 1
                if self.nested_source_calls > self.domain.budget.max_nested_source_invocations:
                    raise WorkLimit("Cumulative Cells Python source invocation budget exhausted")

        error = None
        sys.setprofile(observe)
        try:
            value = operation()
            row["returned"] = value
            require(sys.getprofile() is observe, "Source observer was replaced")
            self._check()
        except BaseException as primary:
            error = primary
            row.update(status="failed", error_type=type(primary).__name__, message=str(primary))
            raise
        finally:
            try:
                sys.setprofile(previous)
                require(sys.getprofile() is previous, "Source observer restoration failed")
                row.update(
                    nested_after=self.nested_source_calls,
                    elapsed_seconds=time.monotonic() - self.started,
                )
            except BaseException as secondary:
                self.recovery_errors.append(dict(stage="observer-restoration", error=secondary))
                if error is None:
                    raise
                error.add_note("Secondary observer-restoration failure: " + repr(secondary))
        row["status"] = "returned"
        return value

    def _retain(self, *extra, current=None):
        encoder = codec.Encoder()
        roots = (
            binding_record(self.binding),
            state_record(self.current if current is None else current),
            self.definition,
            self.initial,
            self.journal,
            self.attempts,
            extra,
        )
        tree = encoder.capture(roots)
        size = encoder.bytes + len(codec.json_bytes(tree))
        require(
            size <= self.domain.budget.max_retained_bytes,
            "Complete primitive evidence byte budget exhausted",
        )
        self.retained_bytes = size

    @np.errstate(all="ignore")
    def _verify(self, parent, forcing):
        verify_domain(self.domain)
        require(
            type(parent) is State and parent is self.current,
            "Only the actual current live parent may advance",
        )
        require(
            type(parent.source) is material.State and type(parent.source.values) is material.Values,
            "Complete typed source material state required",
        )
        require(self.binding.domain is self.domain, "Foreign numerical binding/domain association")
        require(
            parent.absolute_index == self._accepted_calls
            and parent.initial_identity == self._initial_identity
            and parent.identity == self._last_identity,
            "Accepted absolute epoch/initial lineage may not be replaced, rebased or cycled",
        )
        require(
            parent.binding_identity == self.binding.identity
            and self.binding.identity == codec.fingerprint(binding_record(self.binding))
            and parent.identity == codec.fingerprint(state_record(parent)),
            "Changed standalone source/domain/state association",
        )
        require(
            codec.fingerprint(self.binding.source) == self._binding_fingerprint
            and codec.fingerprint(parent.source) == self._state_fingerprint,
            "Typed source buffers/layout/alias association changed",
        )
        require(
            codec.fingerprint((self.definition, self.initial)) == self.input_fingerprint,
            "Original declared initial/source inputs changed",
        )
        index = parent.absolute_index
        require(
            type(index) is int and 0 <= index < self.domain.budget.source_calls,
            "Original absolute material domain exhausted; no rebase/cycle",
        )
        require(parent.status == "ready", "Failed or exhausted material state cannot advance")
        self.owner_verifications += 1
        self._check()
        material.validate_binding(self.binding.source)
        self.owner_verifications += 1
        self._check()
        checked = material._state_values(
            self.binding.source, parent.source.values._asdict(), step_index=index
        )
        require(
            checked.identity == parent.source.identity
            and material.current.record(checked.values)
            == material.current.record(parent.source.values)
            and not any(v.flags.writeable for v in parent.source.values),
            "Changed source state or mutable/non-float64 buffers",
        )
        self.owner_verifications += 1
        self._check()
        require(
            type(forcing) is material.Drive
            and material.current.record(material.drive(self.binding.source, forcing._asdict()))
            == material.current.record(forcing)
            and not any(isinstance(v, np.ndarray) and v.flags.writeable for v in forcing),
            "Require complete immutable typed ECM source drive",
        )

    def advance(self, parent, forcing):
        """Call the shared source once at the retained absolute epoch, including 3+."""
        if self._advance_active:
            self.requests += 1
            self.failed = True
            error = ValueError("Reentrant material advance refused before source dispatch")
            entry = dict(
                ordinal=self.requests,
                status="refused_reentrant",
                source_requested=False,
                parent=state_record(parent) if type(parent) is State else None,
                forcing=forcing,
                outer_ordinal=self._active_context["ordinal"],
                outer_parent=(
                    state_record(self._active_context["accepted"])
                    if type(self._active_context["accepted"]) is State
                    else None
                ),
                error_type=type(error).__name__,
                message=str(error),
            )
            if len(self.attempts) <= self.domain.budget.max_material_attempts:
                self.attempts.append(entry)
            refusal = PrimitiveRejected(
                error, execution=self, stage="reentrant-admission", parent=parent, forcing=forcing
            )
            refusal.attempt = entry
            refusal.outer_context = self._active_context
            refusal.accepted = self._active_context["accepted"]
            raise refusal from error
        # Plain attribute/counter operations precede the first observable
        # helper call. Nested refusal must never clear this outer call's guard.
        self._advance_active = True
        self.requests += 1
        self._active_context = {
            "ordinal": self.requests,
            "accepted": self.current,
            "epoch": self._accepted_calls,
            "last_identity": self._last_identity,
            "state_fingerprint": self._state_fingerprint,
        }
        try:
            return self._advance_once(parent, forcing, self._active_context)
        finally:
            self._active_context = None
            self._advance_active = False

    def _advance_once(self, parent, forcing, context):
        ordinal = context["ordinal"]
        stage = "admission"
        source_trial = None
        entry = dict(
            ordinal=ordinal,
            parent=state_record(parent) if type(parent) is State else None,
            forcing=forcing,
            requested_absolute_index=(
                parent.source.step_index
                if type(parent) is State and type(parent.source) is material.State
                else None
            ),
            source_requested=False,
            status="attempted",
        )
        # The terminal refusal itself is retained on the raised exception if
        # the finite journal capacity has already been exhausted.
        if len(self.attempts) <= self.domain.budget.max_material_attempts:
            self.attempts.append(entry)
        try:
            require(
                os.environ.get(RELEASE) == "1", "Standalone material scientific entry remains held"
            )
            require(
                not self.failed, "Failed lineage cannot retry or restore a prior accepted prefix"
            )
            require(
                self.requests <= self.domain.budget.max_material_attempts,
                "Cumulative material attempt budget exhausted",
            )
            self.material_attempts += 1
            self._call("owner-and-drive-verification", lambda: self._verify(parent, forcing))
            forcing_fingerprint = codec.fingerprint(forcing)
            self.source_requests += 1
            entry["source_requested"] = True
            stage = "shared-material-source"
            source_trial = self._call(
                stage, lambda: material._step_source(self.binding.source, parent.source, forcing)
            )
            stage = "trial-association"
            require(
                type(source_trial) is material.Trial
                and source_trial.binding_identity == self.binding.source.identity
                and source_trial.parent_identity == parent.source.identity
                and source_trial.drive is forcing
                and type(source_trial.candidate) is material.State
                and source_trial.candidate.binding_identity == self.binding.source.identity
                and type(source_trial.candidate.step_index) is int
                and source_trial.candidate.step_index == parent.absolute_index + 1
                and type(source_trial.candidate.values) is material.Values
                and all(
                    type(v) is np.ndarray and v.dtype == np.float64 and not v.flags.writeable
                    for v in source_trial.candidate.values
                )
                and source_trial.diagnostics["finite"] is True
                and source_trial.identity
                == material.current._digest(material.trial_record(source_trial))
                and source_trial.candidate.identity
                == material.current._digest(material.state_record(source_trial.candidate)),
                "Foreign, duplicate or omitted material source epoch/trial",
            )
            candidate = State(
                self.binding.identity,
                source_trial.candidate,
                parent.initial_identity,
                parent.identity,
                forcing_fingerprint,
                ordinal,
                "exhausted"
                if source_trial.candidate.step_index == self.domain.budget.source_calls
                else "ready",
                "",
            )
            candidate = replace(candidate, identity=codec.fingerprint(state_record(candidate)))
            entry.update(status="returned", trial=source_trial, candidate=state_record(candidate))
            candidate_fingerprint = codec.fingerprint(candidate.source)
            self.journal[-1]["proposed_state_identity"] = candidate.identity
            self._retain(source_trial, current=candidate)
            self._check()
            stage = "commit-admission"
            # No callable/property access between this final check and the
            # plain assignments below: an inherited profiler cannot interleave
            # another callback after a require() condition has been computed.
            if (
                self.failed
                or self.current is not parent
                or self._accepted_calls != context["epoch"]
                or parent.source.step_index != context["epoch"]
                or self._last_identity != context["last_identity"]
                or self._state_fingerprint != context["state_fingerprint"]
            ):
                raise ValueError(
                    "Original parent/absolute epoch changed or failed during active advance"
                )
            self.current = candidate
            self._accepted_calls += 1
            self._last_identity = candidate.identity
            self._state_fingerprint = candidate_fingerprint
            entry["status"] = "accepted"
            return candidate, source_trial
        except BaseException as error:
            self.failed = True
            entry.update(
                status="failed",
                error_type=type(error).__name__,
                message=str(error),
                trial=getattr(error, "trial", source_trial),
            )
            try:
                if self.binding is not None and self.current is not None:
                    self._retain()
            except BaseException as secondary:
                self.recovery_errors.append(dict(stage="failed-evidence-capture", error=secondary))
            refusal = PrimitiveRejected(
                error, execution=self, stage=stage, parent=parent, forcing=forcing
            )
            refusal.attempt = entry
            refusal.accepted = context["accepted"]
            if refusal.trial is None:
                refusal.trial = source_trial
            raise refusal from error


def begin(declared, definition, initial):
    """Create a fresh, separately bound zero epoch via existing source validators.

    Supplied data do not attest native initialization. Accepting a previous
    State/Retained record, assigning a new index or restoring a saved owner is
    deliberately absent. No metadata borrowing issues numerical state.
    """
    require(os.environ.get(RELEASE) == "1", "Standalone material scientific entry remains held")
    verify_domain(declared)
    require(
        type(definition) is dict and type(initial) is dict,
        "Explicit source definition and complete fresh buffer declaration required; "
        "no owner import",
    )
    require(
        set(initial) == set(material.Values._fields),
        "Fresh buffer declaration may not import a saved owner/cursor/cache or omit buffers",
    )
    execution = Execution(declared, definition, initial)
    try:
        execution.owner_verifications += 1
        source = execution._call("source-binding", lambda: material.bind(definition))
        require(
            type(source) is material.Binding, "Actual source binding constructor return required"
        )
        binding = Binding(declared, source, execution.input_fingerprint, "")
        execution.binding = replace(binding, identity=codec.fingerprint(binding_record(binding)))
        execution.owner_verifications += 1
        first = execution._call(
            "initial-source-state", lambda: material._state_values(source, initial, step_index=0)
        )
        require(
            type(first) is material.State
            and type(first.step_index) is int
            and first.step_index == 0
            and first.binding_identity == source.identity
            and first.identity == material.current._digest(material.state_record(first)),
            "Actual fresh zero-index source state required",
        )
        current = State(
            execution.binding.identity, first, first.identity, None, None, 0, "ready", ""
        )
        execution.current = replace(current, identity=codec.fingerprint(state_record(current)))
        execution._initial_identity = first.identity
        execution._last_identity = execution.current.identity
        execution._binding_fingerprint = codec.fingerprint(source)
        execution._state_fingerprint = codec.fingerprint(first)
        execution._retain()
        execution._check()
        return execution
    except BaseException as error:
        execution.failed = True
        raise PrimitiveRejected(
            error, execution=execution, stage="initial-source", parent=None, forcing=None
        ) from error
