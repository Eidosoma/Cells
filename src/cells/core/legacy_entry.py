"""The core's one entry point into the older model families (D188 R1).

The dispatch points (models/registry.get_model, core/specs.parse_spec and
SimulationSpec._fine_dict, core/schedule.control_values, the command line and the ensemble
adapters) check the active families first. On a miss they call legacy(), which imports the older
families' registration module by its one name, LEGACY, on first use: the pattern of
kind_registry.BUILTIN_PACKAGE. No other module outside the legacy package names that package
(tests/unit/test_legacy_entry.py).
"""

import importlib

LEGACY = "cells.legacy.registration"
_registration = None


def legacy():
    """The older families' registration module, imported once."""
    global _registration
    if _registration is None:
        _registration = importlib.import_module(LEGACY)
    return _registration
