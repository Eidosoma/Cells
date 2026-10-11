"""Resolve a recorded native-only refinement without changing frozen tolerances."""

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "configs/reference/source_emt_pair_panel_v1.json"
PROTOCOL = ROOT / "configs/reference/source_emt_pair_numerics_v1.json"


def native_plan(extension=None):
    panel, protocol = json.loads(PANEL.read_text()), json.loads(PROTOCOL.read_text())
    cases, levels = panel["cases"], protocol["native_levels"]
    if extension is None:
        return cases, levels
    data = json.loads(extension.read_text())
    for path, key in ((PANEL, "panel_sha256"), (PROTOCOL, "base_protocol_sha256")):
        if hashlib.sha256(path.read_bytes()).hexdigest() != data[key]:
            raise ValueError("Native extension base identity changed")
    selected = data["case_ids"]
    if (
        not selected
        or len(set(selected)) != len(selected)
        or set(selected) - {c["id"] for c in cases}
    ):
        raise ValueError("Invalid extension case selection")
    cases = [c for c in cases if c["id"] in selected]
    base = levels[-1]
    levels = [base.copy()]
    previous = 1.0
    for entry in data["native_refinements"]:
        scale = entry["scale_from_fine"]
        if not math.isfinite(scale) or not 0 < scale < previous:
            raise ValueError("Refinement scales must strictly decrease below one")
        if not entry["name"].isidentifier() or entry["name"] in {level["name"] for level in levels}:
            raise ValueError("Invalid or duplicate refinement name")
        levels.append(
            {k: value * scale for k, value in base.items() if k != "name"} | {"name": entry["name"]}
        )
        previous = scale
    if len(levels) != 3:
        raise ValueError("Two additional refinement levels required")
    return cases, levels
