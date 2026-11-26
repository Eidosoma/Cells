"""cells.model.resolved_pump_composite@1: an inner pump-tissue model plus an ordered list of operators.

Definition (D143; docs/CELL_DIVISION_DESIGN.md §3.2). The model holds the inner
model's own fields, parsed by that identity's own parser (here only
cells.model.resolved_pump_tissue@3), plus

* ``inner_model``: the inner identity;
* ``operators``: an ordered list of operator declarations, each naming its law
  (``law``, one of models/operators.OPERATORS) with its parameters, parsed by that
  operator.

The experiment adds each operator's schedule under the operator's own keys (for
example ``water_controls``, ``symport_controls``, ``replacement_events``), parsed
by the operator; two operators may not declare one key. The schedule union
(experiment.changes) holds light records: the time, the inner record active then
(shared, not copied) and each operator's record at that time.

A run's identity is the composite ID, the inner ID and the ordered operator IDs
(identity()); all of them enter the batch signature and the run manifest. New
combinations are definitions, not model families. A combination is not qualified
by its parts: an unqualified combination runs as a labelled development run, and
judged status comes only from a registered protocol (D143).

frozen_definition(raw) rewrites a cells.model.resolved_pump_tissue@3, cells.model.resolved_pump_water@1,
cells.model.resolved_pump_water@2 or cells.model.resolved_pump_replacement@1 definition as the equivalent
composition (their frozen experiment keys are the operators' keys).
"""

import copy
from bisect import bisect_right
from dataclasses import MISSING, dataclass, field, fields, make_dataclass, replace
from functools import cache, cached_property
from typing import NamedTuple

import numpy as np

from cells.definitions import surface_pump_v3_spec as ionic
from cells.definitions.specs import ConfigError
from cells.registry import kind_registry

MODEL_ID = "cells.model.resolved_pump_composite@1"
INNER_MODEL_IDS = (ionic.MODEL_ID,)
DEVELOPMENT_STATUS = (
    "development composition: integration grants no acceptance; judged status only "
    "from a registered protocol for this composition"
)


def _model_fields():
    inner = fields(ionic.SurfacePumpChannelModel)
    required = [
        (f.name, f.type) for f in inner if f.default is MISSING and f.default_factory is MISSING
    ]
    optional = [
        (f.name, f.type, field(default=f.default)) for f in inner if f.default is not MISSING
    ]
    return [*required, ("inner_model", str), ("operators", tuple), *optional]


# The inner model's fields (whatever @3 declares), its identity and the operators.
CompositeModel = make_dataclass("CompositeModel", _model_fields(), frozen=True, module=__name__)


@dataclass(frozen=True)
class OperatorSchedule:
    """One operator's parsed schedule (its law and operator-defined data)."""

    law: str
    data: object


@dataclass(frozen=True)
class CompositeChange:
    """One schedule time: the inner record active then and each operator's record."""

    time: float
    inner: object
    operators: tuple


@dataclass(frozen=True)
class Experiment(ionic.Experiment):
    """The inner experiment plus one OperatorSchedule per declared operator."""

    operators: tuple

    @cached_property
    def changes(self):
        from cells.operators import OPERATORS

        inner = ionic.Experiment.changes.fget(self)
        inner_times = [c.time for c in inner]
        laws = [OPERATORS[s.law] for s in self.operators]
        times = sorted(
            {
                *inner_times,
                *(
                    t
                    for op, s in zip(laws, self.operators, strict=True)
                    for t in op.schedule_times(s.data)
                ),
            }
        )
        return tuple(
            CompositeChange(
                t,
                inner[bisect_right(inner_times, t) - 1],
                tuple(op.value_at(s.data, t) for op, s in zip(laws, self.operators, strict=True)),
            )
            for t in times
        )


def projection(spec):
    """The inner (cells.model.resolved_pump_tissue@3) definition: no composite declarations."""
    m, e = spec.model, spec.experiment
    model = ionic.SurfacePumpChannelModel(
        **{k: getattr(m, k) for k in ionic.SurfacePumpChannelModel.__dataclass_fields__}
    )
    experiment = ionic.Experiment(
        **{k: getattr(e, k) for k in ionic.Experiment.__dataclass_fields__}
    )
    return replace(spec, model=model, experiment=experiment)


def operator_laws(model):
    return tuple(d.law for d in model.operators)


def identity(model):
    """The run identity: composite ID, inner ID and the ordered operator IDs."""
    return dict(model=MODEL_ID, inner_model=model.inner_model, operators=list(operator_laws(model)))


def entries(spec):
    """(operator, declaration, schedule data) for each declared operator, in order."""
    from cells.operators import OPERATORS

    return tuple(
        (OPERATORS[d.law], d, s.data)
        for d, s in zip(spec.model.operators, spec.experiment.operators, strict=True)
    )


def to_dict(spec):
    m, e = spec.model, spec.experiment
    if type(m) is not CompositeModel or type(e) is not Experiment:
        raise ConfigError("The composite requires its own model and experiment")
    if len(m.operators) != len(e.operators) or any(
        type(s) is not OperatorSchedule or s.law != d.law
        for d, s in zip(m.operators, e.operators, strict=True)
    ):
        raise ConfigError("Require one operator schedule per declared operator, in order")
    base = projection(spec)
    raw = ionic.to_dict(base)
    raw["model"]["id"] = MODEL_ID
    raw["model"]["inner_model"] = m.inner_model
    raw["model"]["operators"] = [op.to_dict(d, base) for op, d, _ in entries(spec)]
    for op, d, s in entries(spec):
        raw["experiment"].update(op.schedule_to_dict(s, base, d))
    return raw


def parse(data):
    from cells.operators import OPERATORS

    raw = copy.deepcopy(data)
    m, e = raw.get("model"), raw.get("experiment")
    if not isinstance(m, dict) or not isinstance(e, dict) or m.get("id") != MODEL_ID:
        raise ConfigError("Require " + MODEL_ID)
    if "inner_model" not in m or "operators" not in m:
        raise ConfigError("Declare inner_model and operators")
    inner, declared = m.pop("inner_model"), m.pop("operators")
    if inner not in INNER_MODEL_IDS:
        raise ConfigError("Composite inner model must be one of " + ", ".join(INNER_MODEL_IDS))
    if type(declared) is not list:
        raise ConfigError("Composite operators require an explicit list")
    operators = []
    for block in declared:
        if not isinstance(block, dict) or block.get("law") not in OPERATORS:
            raise ConfigError(
                "Each operator names a registered law: " + ", ".join(sorted(OPERATORS))
            )
        operators.append(OPERATORS[block["law"]])
    keys = [k for op in operators for k in op.EXPERIMENT_KEYS]
    if len(keys) != len(set(keys)):
        raise ConfigError("Two operators declare the same experiment key")
    # An inner kind's schedule keys are its own (docs/INNER_MODEL_V4_DESIGN.md §7.4 (l)): an
    # operator that declared one would take the kind's schedule before the inner parse reads it.
    claimed = kind_registry.active().experiment_keys()
    taken = sorted(k for k in keys if k in claimed)
    if taken:
        raise ConfigError(
            f"An operator declares the experiment key {taken[0]!r}, which kind "
            f"{kind_registry.qualified(claimed[taken[0]].kind_id)} owns"
        )
    scheduled = {}
    for key in keys:
        if key not in e:
            raise ConfigError(f"Declare the operator schedule {key}")
        scheduled[key] = e.pop(key)
    m["id"] = inner
    base = ionic.parse(raw)
    declarations, schedules = [], []
    for op, block in zip(operators, declared, strict=True):
        declaration = op.parse(block, base, inner)
        schedule = op.parse_schedule(
            {k: scheduled[k] for k in op.EXPERIMENT_KEYS}, base, declaration
        )
        declarations.append(declaration)
        schedules.append(OperatorSchedule(op.LAW_ID, schedule))
    model = CompositeModel(
        **{k: getattr(base.model, k) for k in ionic.SurfacePumpChannelModel.__dataclass_fields__},
        inner_model=inner,
        operators=tuple(declarations),
    )
    experiment = Experiment(
        **{k: getattr(base.experiment, k) for k in ionic.Experiment.__dataclass_fields__},
        operators=tuple(schedules),
    )
    spec = replace(base, model=model, experiment=experiment)
    from cells.models.pump_composite import check_definition

    try:
        check_definition(spec)
    except (ArithmeticError, ValueError) as error:  # ConfigError included, as the family does.
        raise ConfigError("Invalid composite definition: " + str(error)) from error
    return spec


@cache
def control_type(names):
    """The composite control type for these field names (one class per composition)."""
    return NamedTuple("CompositeControl", [(k, object) for k in names])


def control_fields(model):
    from cells.operators import OPERATORS

    return (
        *inner_control_type(model)._fields,
        *(k for law in operator_laws(model) for k in OPERATORS[law].CONTROL_FIELDS),
    )


def inner_control_type(model):
    """The inner model's control type for this model block: @3's Control, or, where the block
    declares kinds, its structure's, the implementation object's own (schema A,
    docs/INNER_MODEL_V4_DESIGN.md §7.4 (j): today's fields, then the kinds' controls in canonical
    order)."""
    if not getattr(model, "kinds", ()):
        return ionic.Control
    from cells.models import surface_pump_v3 as inner

    return inner.implementation(inner.structure(model)).Control


def control_values(spec, times):
    """Inner controls, then each operator's control arrays (CONTROL_FIELDS order)."""
    base = ionic.control_values(projection(spec), times)
    changes = spec.experiment.changes
    indices = np.searchsorted([c.time for c in changes], times, side="right") - 1
    arrays = []
    for k, (op, declaration, schedule) in enumerate(entries(spec)):
        records = [c.operators[k] for c in changes]
        values = tuple(op.control_values(spec, declaration, schedule, records, indices, times))
        if len(values) != len(op.CONTROL_FIELDS):
            raise ConfigError(f"Operator {op.LAW_ID} returned the wrong control arrays")
        arrays.extend(values)
    return control_type(control_fields(spec.model))(*base, *arrays)


# ------------------------------------------------------------------ frozen definitions


def frozen_definition(data):
    """A cells.model.resolved_pump_tissue@3, water@1, water@2 or replacement@1 definition as a composition.

    The operators carry the frozen blocks unchanged (each names its law), and the
    experiment keeps the frozen schedule keys, which are the operators' keys.
    """
    raw = copy.deepcopy(data)
    m = raw["model"]
    kind = m["id"]
    operators, inner = [], ionic.MODEL_ID
    if kind == ionic.MODEL_ID:
        pass
    elif kind in ("cells.model.resolved_pump_water@1", "cells.model.resolved_pump_water@2"):
        operators.append(m.pop("water"))
        if kind == "cells.model.resolved_pump_water@2":
            operators.append(m.pop("symport"))
    elif kind == "cells.model.resolved_pump_replacement@1":
        block = m.pop("replacement")
        inner = block.pop("inner_model")
        operators.append(block)
    else:
        raise ConfigError("frozen_definition takes a resolved pump @3, water or replacement model")
    m["id"] = MODEL_ID
    m["inner_model"] = inner
    m["operators"] = operators
    return raw
