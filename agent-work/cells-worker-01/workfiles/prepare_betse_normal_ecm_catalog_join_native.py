# ruff: noqa: E501
"""Copy capture plumbing and independently selected original AST; no execution."""

from pathlib import Path

ROOT = Path("/home/robert/Cells")
folder = ROOT / "validation/betse"
text = (folder / "betse_normal_ecm_calcium_join_native.py").read_text()
text = text.replace(
    "betse_ecm_grn_native_network as network",
    "betse_normal_ecm_catalog_join_native_network as network",
)
text = text.replace(
    "Authenticated normal ECM CaATP/GRN/full fields",
    "Authenticated normal ECM modern catalog/CaATP/GRN/full fields",
)
# Correct only the local observation map that otherwise shadows outer ion role names.
text = text.replace(
    "names = dict(\n                        Qnumo=",
    "arithmetic_names = dict(\n                        Qnumo=",
)
text = text.replace(
    "for native, key in names.items()", "for native, key in arithmetic_names.items()"
)
text = text.replace(
    "def run_dispatch(ctx, material_declaration, publication, source_time_s, observer=None):",
    "def run_dispatch(ctx, material_declaration, publication, source_time_s, observer=None, channel_observer=None):",
)
text = text.replace(
    "network.attach(ctx, material_declaration, observer)",
    "network.attach(ctx, material_declaration, observer, channel_observer)",
)
text = text.replace(
    "    ctx = network.augment(sim, cells, parameters, definition, names)",
    '    ctx = network.augment(sim, cells, parameters, definition, names)\n    network.configure(ctx, declared["catalog"])',
)
text = text.replace(
    "            cold_failure=network.cache(ctx),",
    "            cold_failure=network.cache(ctx),\n            cold_trace=network.clone(ctx.trace),\n            cold_material=values(),",
)
text = text.replace(
    '            for index, call in enumerate(inputs["steps"]):',
    '            for index, call in enumerate(inputs["steps"][:declared["stop_after_calls"]]):',
)
text = text.replace(
    "                ctx.trace = network.new_trace()",
    "                ctx.trace = network.new_trace()\n                ctx.trace.update(channel_events=[],channel_initializations=[])",
)
text = text.replace(
    "                    clock=clock(index),\n                )",
    '                    clock=clock(index),\n                    catalog=network.clone(declared["catalog"]),\n                    network_cache=network.cache(ctx),\n                )',
)
text = text.replace(
    "    cold_material = values()",
    "    cold_material = values()\n    cold_trace=network.clone(ctx.trace)",
)
text = text.replace(
    "        cold_cache=cold_cache,",
    "        cold_cache=cold_cache,\n        cold_trace=cold_trace,",
)
text = text.replace("normal_ecm_calcium_join", "normal_ecm_catalog_join")
(folder / "betse_normal_ecm_catalog_join_native.py").write_text(text)
# Unchanged base geometry/context validation is intentionally separate from new channel validation.
p = folder / "betse_normal_ecm_catalog_join_native_network.py"
body = p.read_text().replace(
    "new_trace = base.new_trace",
    "new_trace = base.new_trace\naugment,validate_definition=base.augment,base.validate_definition",
)
p.write_text(body)
print(
    "Emitted native capture with nonshadowing observation map and complete cold/channel snapshots"
)
