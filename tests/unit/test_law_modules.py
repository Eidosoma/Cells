"""One module per law (docs/CORE_SEAMS_DESIGN.md §8.2; seam F's per-law extractions, the lead's
rulings of 18 November 2026), each claim with a planted error it must catch (D187):

- each of @3's laws and its passive kind's two is declared in a module of its own under laws/,
  inert (it registers nothing itself), which the registry records as its declarer, and whose LAW
  is the registered object (planted: a module that registers its law itself, and a declarer
  recorded from elsewhere);
- each older kernel module re-imports every name that moved, the per-law module's object itself,
  so the older families run the one copy (planted: a shim holding a copy of a kernel);
- inner_laws' tables are the registered declarations: CHANNEL_LAWS the active registry's @3
  channel laws in code order, live; the junction, pump and route tables version 1's laws, the
  pumps in today's order, the structure's (planted: a channel law registered in a scoped
  registry, which the view shows inside the scope only).
"""

import ast
import dataclasses
import importlib
import inspect
import types

from cells.models import inner_laws
from cells.registry import laws as law_registry

OWN = {  # Each law's own module: its declarer.
    "cells.channel.kv1p5_mh@1": "cells.laws.channels.kv1p5_mh",
    "cells.channel.kir2p1_mh2@1": "cells.laws.channels.kir2p1_mh2",
    "cells.channel.nav1p2_m3h_regularized@1": "cells.laws.channels.nav1p2_m3h_regularized",
    "cells.channel.kleak_always_open@1": "cells.laws.channels.kleak_always_open",
    "cells.channel.naleak_always_open@1": "cells.laws.channels.naleak_always_open",
    "cells.channel.cav1p2_m2h@1": "cells.laws.channels.cav1p2_m2h",
    "cells.junction.junction_voltage_relaxation@1": "cells.laws.junctions.junction_voltage_relaxation",
    "cells.junction.junction_series_gates@1": "cells.laws.junctions.junction_series_gates",  # FR-30 (D262).
    "cells.cycle.nak_atp_mass_action_positive@1": "cells.laws.pumps.nak_atp_mass_action_positive",
    "cells.cycle.ca_atp_mass_action_positive@1": "cells.laws.pumps.ca_atp_mass_action_positive",
    "cells.route.constant_field@1": "cells.laws.routes.constant_field",
    "cells.route.logmean_electrodiffusion@1": "cells.laws.routes.logmean_electrodiffusion",
    "cells.route.passive_neutral_permeation@1": "cells.laws.routes.passive_permeation",
    "cells.route.proton_constant_field_leak@1": "cells.laws.transport.proton_leak",
    # @1's kernel reading the general closure (MT-1b's face plan, item 3; the kinds owner's).
    "cells.route.proton_constant_field_leak@2": "cells.laws.transport.proton_leak_v2",
}
SHIMS = {  # Each older kernel module: the per-law module its names moved to, and those names.
    "cells.laws.channels.voltage_gates": (
        "cells.laws.channels.kv1p5_mh",
        ("LAW_ID", "TEMPERATURE_K", "VOLTAGE_DOMAIN_V", "kinetics"),
    ),
    "cells.laws.channels.potassium_channels": (
        "cells.laws.channels.kir2p1_mh2",
        (("KIR_LAW_ID", "LAW_ID"), "kir2p1_kinetics"),
    ),
    "cells.laws.channels.sodium_channels": (
        "cells.laws.channels.nav1p2_m3h_regularized",
        ("LAW_ID", "nav1p2_kinetics"),
    ),
    "cells.laws.channels.calcium_gates": (
        "cells.laws.channels.cav1p2_m2h",
        ("LAW_ID", "VOLTAGE_DOMAIN_V", "kinetics", ("open_probability", "opening")),
    ),
    "cells.laws.junctions.junction_gate": (
        "cells.laws.junctions.junction_voltage_relaxation",
        (
            "LAW_ID",
            "RELAXATION_LAW_ID",
            "MAX_ABS_VOLTAGE_V",
            "Parameters",
            "Rates",
            "kinetics",
            "rhs",
            "advance_clamped",
            "open_fraction",
            "domain_valid",
        ),
    ),
    "cells.laws.pumps.kinetic_pump": (
        "cells.laws.pumps.nak_atp_mass_action_positive",
        (
            "LAW_ID",
            "SODIUM_PER_CYCLE",
            "POTASSIUM_PER_CYCLE",
            "TEMPERATURE_DOMAIN_K",
            "MAX_ABS_AFFINITY_OVER_RT",
            "MAX_ABS_ION_POTENTIAL_OVER_RT",
            "STANDARD_STATE_mM",
            "Parameters",
            "Rates",
            "chemical_drive",
            "kinetics",
            "domain_valid",
        ),
    ),
    "cells.laws.pumps.calcium_atpase": (
        "cells.laws.pumps.ca_atp_mass_action_positive",
        (
            "LAW_ID",
            "CALCIUM_PER_CYCLE",
            "VALENCE",
            "MAX_ABS_AFFINITY_OVER_RT",
            "MAX_ABS_VOLTAGE_V",
            "Parameters",
            "Rates",
            "chemical_drive",
            "kernel_parameters",
            "kinetics",
            "domain_valid",
        ),
    ),
}


def registers_itself(module):
    """Whether a module's own code calls a registration (`....register(...)`)."""
    for node in ast.walk(ast.parse(inspect.getsource(module))):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "register"
        ):
            return True
    return False


def declarer_errors(registry, own):
    """Where a law's declaration is not its own inert module's registered LAW."""
    out = []
    for law_id, name in own.items():
        module = importlib.import_module(name)
        if registry.module(law_id) != name:
            out.append(f"{law_id}: declared by {registry.module(law_id)}, not {name}")
        if getattr(module, "LAW", None) is not registry.lookup(law_id):
            out.append(f"{law_id}: {name}.LAW is not the registered declaration")
        if registers_itself(module):
            out.append(f"{law_id}: {name} registers its law itself, so it is not inert")
    return out


def copies(shims):
    """The moved names an older module holds as copies, not as the per-law module's object."""
    out = []
    for old, (new, names) in shims.items():
        old_module = old if isinstance(old, types.ModuleType) else importlib.import_module(old)
        new_module = importlib.import_module(new)
        for name in names:
            was, now = name if isinstance(name, tuple) else (name, name)
            if getattr(old_module, was) is not getattr(new_module, now):
                out.append(f"{old_module.__name__}.{was}")
    return out


def test_each_law_is_declared_inert_in_its_own_module():
    registry = law_registry.active()
    assert declarer_errors(registry, OWN) == []
    # Planted: declarers recorded from elsewhere (this test registers each law), and a module that
    # registers its law itself (GARD's exchange law's home does, as a registering home may).
    elsewhere = law_registry.LawRegistry()
    for law_id in OWN:
        elsewhere.register(registry.lookup(law_id))
    errors = declarer_errors(elsewhere, OWN)
    assert len(errors) == len(OWN) and all(f"declared by {__name__}" in e for e in errors)
    from cells.models.assembly_lineages import exchange

    assert registers_itself(exchange)


def test_each_older_kernel_module_re_imports_the_one_copy():
    assert copies(SHIMS) == []
    # Planted: a shim holding a copy of Kv1.5's kernel, and the moved constants.
    from cells.laws.channels import kv1p5_mh

    copied = types.ModuleType("planted_voltage_gates")
    copied.LAW_ID, copied.TEMPERATURE_K = kv1p5_mh.LAW_ID, kv1p5_mh.TEMPERATURE_K
    copied.VOLTAGE_DOMAIN_V = kv1p5_mh.VOLTAGE_DOMAIN_V
    copied.kinetics = types.FunctionType(
        kv1p5_mh.kinetics.__code__, kv1p5_mh.kinetics.__globals__, "kinetics"
    )
    shim = {copied: SHIMS["cells.laws.channels.voltage_gates"]}
    assert copies(shim) == ["planted_voltage_gates.kinetics"]


def test_inner_laws_tables_are_the_registered_declarations():
    registry = law_registry.active()
    host = inner_laws.HOST
    hosted = sorted(registry.laws(law_registry.CHANNEL_LAW, host), key=lambda law: law.code)
    assert list(inner_laws.CHANNEL_LAWS) == [law.law_id for law in hosted]
    assert all(inner_laws.CHANNEL_LAWS[law.law_id] is law for law in hosted)
    for table in (inner_laws.JUNCTION_LAWS, inner_laws.PUMP_LAWS, inner_laws.ROUTE_LAWS):
        assert all(registry.lookup(law_id) is law for law_id, law in table.items())
    assert list(inner_laws.PUMP_LAWS) == [
        "cells.cycle.nak_atp_mass_action_positive@1",
        "cells.cycle.ca_atp_mass_action_positive@1",
    ]
    # Planted: a channel law registered in a scoped registry is in the live view there only.
    kv15 = inner_laws.CHANNEL_LAWS["cells.channel.kv1p5_mh@1"]
    extra = dataclasses.replace(kv15, law_id="tests.channel.planted_view_channel@1", code=99)
    with law_registry.scope(law_registry.BUILTIN.extended(extra)):
        assert list(inner_laws.CHANNEL_LAWS)[-1] == "tests.channel.planted_view_channel@1"
        assert inner_laws.CHANNEL_LAWS["tests.channel.planted_view_channel@1"] is extra
    assert "tests.channel.planted_view_channel@1" not in inner_laws.CHANNEL_LAWS
