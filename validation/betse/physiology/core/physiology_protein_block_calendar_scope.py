"""Private control scopes for unchanged frozen charged-loop function code.

Every scope owns its globals dictionary. Original modules, functions, model
definitions and control baselines are never patched. Only control resolution
and endpoint role selection differ; the physical and accounting bodies retain
their qualified code objects and original thresholds.
"""

from functools import lru_cache
from types import FunctionType, SimpleNamespace

import numpy as np

from validation.betse.physiology import physiology_protein_loop_io as loop_io
from validation.betse.physiology.core import physiology_native_calendar as clocks
from validation.betse.physiology.core import physiology_protein_loop as loop
from validation.betse.physiology.core import physiology_protein_packet_provider as provider
from validation.betse.physiology.models import physiology_block_control_view as blocks

POLICY = "private_frozen_code_globals_with_explicit_block_control_roles@1"
INNER_KIND = "cells.block_scoped_complete_protein_loop_restart@1"
INNER_SCHEDULED_KIND = "cells.block_scoped_complete_protein_loop_restart_scheduled@1"


def _function(original, namespace):
    result = FunctionType(
        original.__code__, namespace, original.__name__, original.__defaults__, original.__closure__
    )
    result.__kwdefaults__ = (
        None if original.__kwdefaults__ is None else dict(original.__kwdefaults__)
    )
    result.__annotations__ = dict(original.__annotations__)
    result.__qualname__, result.__doc__ = original.__qualname__, original.__doc__
    return result


def _namespace(module, **overrides):
    namespace = dict(vars(module)) | overrides
    for name, value in vars(module).items():
        if isinstance(value, FunctionType) and value.__globals__ is vars(module):
            namespace[name] = _function(value, namespace)
    return namespace


class _View:
    def __init__(self, original, **overrides):
        self._original, self._overrides = original, overrides

    def __getattr__(self, name):
        return self._overrides[name] if name in self._overrides else getattr(self._original, name)


class ControlScope:
    """Immutable physical context with a bounded pure-memory replay cache."""

    def __init__(
        self, spec, tissue_binding, binding, initial_block_state, calendar, origin_call_index
    ):
        self.spec, self.tissue_binding, self.binding = spec, tissue_binding, binding
        self.calendar, self.origin_call_index = clocks.validate(calendar), origin_call_index
        blocks.restore(blocks.record(binding), spec, tissue_binding)
        self.initial = provider._frozen_tree(blocks._state(initial_block_state, binding))
        self.memory_at = lru_cache(maxsize=64)(self._memory_at)
        if type(origin_call_index) is not int or not 0 <= origin_call_index <= calendar.step_count:
            raise ValueError("Require the original integer blocker memory origin")
        namespace = _namespace(loop)
        namespace["_actual"] = self._accepted_actual
        self.validation = SimpleNamespace(**namespace)
        self.codec = SimpleNamespace(
            **_namespace(
                loop_io,
                loop=self.validation,
                KIND=INNER_KIND,
                SCHEDULED_KIND=INNER_SCHEDULED_KIND,
            )
        )

    def _spec(self, spec):
        if spec.fingerprint != self.spec.fingerprint:
            raise ValueError("Scoped controls belong to another exact physical definition")

    def _memory_at(self, call_index):
        if (
            type(call_index) is not int
            or not self.origin_call_index <= call_index <= self.calendar.step_count
        ):
            raise ValueError("Blocker memory cursor differs from the original calendar")
        state = self.initial
        for index in range(self.origin_call_index, call_index):
            state = self.stage(index, state=state).block_state
        return state

    def stage(self, call_index, *, state=None):
        label = clocks.event_label_s(self.calendar, call_index)
        return blocks.prepare(
            self.spec,
            self.tissue_binding,
            self.binding,
            self.memory_at(call_index) if state is None else state,
            loop.held._control(self.spec, call_index * self.calendar.dt_s),
            time_s=label,
            events_enabled=self.calendar.phase == "SIM",
        )

    def effective(self, state, spec, time):
        self._spec(spec)
        return blocks.prepare(
            spec,
            self.tissue_binding,
            self.binding,
            state,
            loop.held._control(spec, time),
            time_s=time,
            events_enabled=False,
        ).effective_control

    def _held(self, state):
        return _View(loop.held, _control=lambda spec, time: self.effective(state, spec, time))

    def _fixed_actual(self, block_state, spec, point, state, component, time):
        namespace = dict(vars(loop)) | dict(held=self._held(block_state))
        return _function(loop._actual, namespace)(spec, point, state, component, time)

    def _accepted_actual(self, spec, point, state, component, time):
        block_state = (
            self.initial if time == point.origin.time else self.memory_at(point.loop_index)
        )
        return self._fixed_actual(block_state, spec, point, state, component, time)

    def proposal_loop(self, call_index):
        preparation = self.stage(call_index)
        held = self._held(preparation.block_state)
        transition = _View(
            loop.transition,
            _endpoints=_function(
                loop.transition._endpoints, dict(vars(loop.transition)) | dict(held=held)
            ),
        )
        namespace = _namespace(loop, held=held, transition=transition)
        namespace["validate"] = self.validation.validate
        return SimpleNamespace(**namespace), preparation

    def controls(self, proposal, state):
        result = []
        for interval in proposal.intervals:
            result.append(
                provider._frozen_tree(
                    dict(
                        start_s=np.asarray(interval.start_s, np.float64),
                        end_s=np.asarray(interval.end_s, np.float64),
                        base_left=loop.held._control(self.spec, interval.start_s),
                        actual_left=self.effective(state, self.spec, interval.start_s),
                        base_right=loop.held._control(self.spec, interval.end_s),
                        actual_right=self.effective(state, self.spec, interval.end_s),
                    )
                )
            )
        return tuple(result)
