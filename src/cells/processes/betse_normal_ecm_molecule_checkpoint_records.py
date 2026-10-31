"""Closed record vocabulary for the ordinary molecule headless checkpoint.

Record names in a file never select an import or execute a binding/setup method.
These are the existing immutable Cells records, not a native pickle vocabulary.
"""

import importlib
from dataclasses import fields, is_dataclass

RECORDS = {
    "cells.core.physiology_native_calendar": ("NativePhaseCalendar",),
    "cells.processes.betse_normal_ecm_molecule_run_lifecycle": (
        "Binding",
        "RunState",
        "CallReceipt",
        "Observation",
        "CompletedInitRun",
    ),
    "cells.processes.betse_normal_ecm_molecule_lifecycle": (
        "Binding",
        "CompleteInit",
        "FailedInitPrefix",
        "SimPhase",
    ),
    "cells.processes.betse_normal_ecm_molecule_lifecycle_phase": (
        "Declaration",
        "Binding",
        "State",
    ),
    "cells.processes.betse_normal_ecm_calcium_join": (
        "Binding",
        "RateCache",
        "Clock",
        "CalciumFieldState",
    ),
    "cells.processes.betse_ecm_transport": (
        "Binding",
        "Kernel",
        "Values",
        "State",
        "Drive",
        "Frame",
        "ECMRecord",
        "Trial",
    ),
    "cells.processes.betse_ecm_grn_join": ("Binding", "NetworkState"),
    "cells.processes.betse_environment_field": (
        "Binding",
        "Geometry",
        "Cache",
        "Readout",
        "FieldValues",
        "HodgeValues",
    ),
    "cells.processes.betse_normal_current": (
        "CurrentBinding",
        "CurrentKernel",
        "CurrentReadout",
        "CurrentInputs",
        "CurrentValues",
    ),
    "cells.processes.betse_normal_voltage": ("Binding", "Kernel", "Readout", "Values"),
    "cells.processes.betse_normal_ecm_field_join": ("Binding", "FieldStage", "State"),
    "cells.processes.betse_mechanics_join": ("Binding", "State", "Trial"),
    "cells.processes.betse_deformation": ("Operators",),
    "cells.processes.betse_fluid_flow": ("CellBinding",),
}


def registry():
    result = {}
    for module, names in RECORDS.items():
        source = importlib.import_module(module)
        for name in names:
            cls = getattr(source, name)
            if is_dataclass(cls):
                if not cls.__dataclass_params__.frozen or hasattr(cls, "__post_init__"):
                    raise ValueError("Checkpoint record constructor is not a plain frozen record")
                names = tuple(field.name for field in fields(cls))
            else:
                names = cls._fields
            result[module + "." + name] = (cls, names)
    return result
