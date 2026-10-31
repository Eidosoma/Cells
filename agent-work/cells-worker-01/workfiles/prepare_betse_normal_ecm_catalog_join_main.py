# ruff: noqa: E501
"""Owned composition wrapper; lower qualified math is reused without execution."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
SRC = ROOT / "src/cells/processes"
base = ast.parse((SRC / "betse_normal_ecm_calcium_join.py").read_text())


def get(name):
    return copy.deepcopy(next(n for n in base.body if getattr(n, "name", None) == name))


header = '''"""Prepared normal ECM modern catalog + source CaATP + complete field feedback.

This is a separate owned composition. CaATP and field kernels stay unchanged;
original modern gates execute inside the real configured GRN dispatcher.
"""
from dataclasses import dataclass, replace
import numpy as np

from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_normal_ecm_calcium_join as calcium_component
from cells.processes import betse_normal_ecm_catalog_join_source as source
from cells.processes import betse_normal_ecm_field_join as full
from cells.processes import betse_normal_ion_join as ions

LAW_ID="betse_normal_ecm_catalog_CaATP_field_join_v1_5_0@1"
freeze=ions.freeze
Values=material.Values
RateCache,Clock=calcium_component.RateCache,calcium_component.Clock
native_policy,calcium=calcium_component.native_policy,calcium_component.calcium
_material_step=calcium_component._material_step

@dataclass(frozen=True)
class Binding:
    material_binding: object
    voltage_binding: object
    inputs: object
    calcium: object
    catalog: object
    call_limit: int
    identity: str

@dataclass(frozen=True)
class CatalogFieldState:
    binding_identity: str
    network: object
    field: object
    rate_cache: RateCache
    clock: Clock
    identity: str

class CatalogJoinRejected(RuntimeError):
    def __init__(self,error,partial):
        super().__init__(str(error))
        self.partial=freeze(partial)

def bind(raw):
    raw=ions.data(raw)
    if (set(raw)!={"kind","case_id","case_role","field","calcium","catalog","stop_after_calls"}
        or raw["kind"]!="cells.normal_ecm_catalog_join_inputs@1"):
        raise ValueError("Require a separately owned ECM catalog composition")
    base=calcium_component.bind(dict(kind="cells.normal_ecm_calcium_join_inputs@1",
        case_id=raw["case_id"],case_role=raw["case_role"],field=raw["field"],calcium=raw["calcium"]))
    cb=base.material_binding.geometry_binding.current_binding
    source.validate_catalog(raw["catalog"],list(cb.ion_ids),len(cb.membrane_ids))
    if type(raw["stop_after_calls"]) is not int or not 1<=raw["stop_after_calls"]<=3:
        raise ValueError("Require a bounded prefix of the original three-call normal source clock")
    result=Binding(base.material_binding,base.voltage_binding,base.inputs,base.calcium,
        freeze(raw["catalog"]),raw["stop_after_calls"],"")
    return replace(result,identity=ions.digest(composition_record(result)))

def composition_record(binding):
    return (LAW_ID,binding.material_binding.identity,binding.voltage_binding.identity,
        binding.inputs,binding.calcium,binding.catalog,binding.call_limit)

def validate_composition(binding):
    if type(binding) is not Binding or binding.identity!=ions.digest(composition_record(binding)):
        raise ValueError("Require the unchanged owned ECM catalog binding")

def failure_snapshot(ctx,supplied):
    result=network._failure_snapshot(ctx,supplied)
    if ctx is not None:
        try:
            result["catalog_cache"]=source.cache(ctx)
        except Exception as error:
            result["catalog_capture_error"]=dict(type=type(error).__name__,message=str(error))
        result["catalog_trace"]=source.clone(ctx.trace)
    return result
'''
parts = []
for name in ("record", "joined_state", "initialize", "advance"):
    text = ast.unparse(get(name))
    text = text.replace("CalciumFieldState", "CatalogFieldState").replace(
        "CalciumJoinRejected", "CatalogJoinRejected"
    )
    text = text.replace("**network._failure_snapshot(", "**failure_snapshot(")
    text = text.replace(
        "ctx = network.make_context(binding, working, ions.data(binding.inputs['network']))",
        "ctx = network.make_context(binding, working, ions.data(binding.inputs['network']))\n    source.configure(ctx, ions.data(binding.catalog))",
    )
    text = text.replace(
        "ctx = network.make_context(binding, arrays, ions.data(binding.inputs['network']), forcing)",
        "ctx = network.make_context(binding, arrays, ions.data(binding.inputs['network']), forcing)\n        source.configure(ctx, ions.data(binding.catalog))",
    )
    text = text.replace(
        "dict(network=initial, policy=policy, rate_cache=rate, clock=clock)",
        "dict(network=initial, policy=policy, rate_cache=rate, clock=clock, channel_trace=ctx.trace)",
    )
    # Archive the completed cold return before the separately labelled strict finite guard.
    target = "    try:\n        prepared, fields = full.reconstruct("
    if name == "initialize":
        assert target in text
        text = text.replace(
            target,
            "    try:\n        source.validate_cached_channels(ctx,cached)\n    except Exception as error:\n        raise CatalogJoinRejected(error,dict(stage='cold_cache_guard',catalog_cache=cached,channel_trace=ctx.trace)) from error\n"
            + target,
        )
    if name == "advance":
        text = text.replace("before_network=None,", "before_network=None, before_channels=None,")
        text = text.replace(
            "    index = parent.network.material.step_index",
            "    index = parent.network.material.step_index\n    if index >= binding.call_limit:\n        raise ValueError('Declared bounded normal-call prefix is complete')",
        )
        # Channel material conditional begins at the actual parent gate cache, without a gate ctor rerun.
        text = text.replace(
            "clock=ions.data(parent.clock))",
            "clock=ions.data(parent.clock), catalog=ions.data(binding.catalog), network_cache=ions.data(parent.network.network_cache))",
        )
        text = text.replace("        run_dispatch(", "        source.run_dispatch(")
        text = text.replace("before_network)", "before_network, before_channels)")
        text = text.replace(
            "        ctx = holder['ctx']\n        candidate = network._state(",
            "        ctx = holder['ctx']\n        source.validate_cached_channels(ctx, source.cache(ctx))\n        candidate = network._state(",
        )
        # Rejects raised by the unchanged lower CaATP helper still carry its complete partials.
        text = text.replace(
            "except CatalogJoinRejected as error:",
            "except calcium_component.CalciumJoinRejected as error:",
        )
    parts.append(text)
(SRC / "betse_normal_ecm_catalog_join.py").write_text(header + "\n\n" + "\n\n".join(parts) + "\n")
print("Emitted owned wrapper; reused lower CaATP/material/field math unchanged")
