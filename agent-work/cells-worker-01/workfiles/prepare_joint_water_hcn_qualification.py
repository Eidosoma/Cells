"""Build isolated @2 water/repair routes on a qualified immutable engine."""

import ast
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
STEM = "joint_water_hcn"
BASE = Path("/mnt/workspaces/Cells/owned-calcium-profiles-development-20261029-07")
RUNTIME = (
    "src/cells/core/surface_calcium_energy_water_hcn_extra_spec.py",
    "src/cells/core/surface_calcium_energy_water_repair_hcn_extra_spec.py",
    "src/cells/models/surface_calcium_energy_water_hcn_extra.py",
    "src/cells/models/surface_calcium_energy_water_repair_hcn_extra.py",
)
OWNERS = (
    (
        "surface_calcium_energy_water_repair_hcn_extra",
        "SurfaceCalciumEnergyWaterRepairHCNExtraModel",
        "resolved_calcium_energy_water_repair@2",
    ),
    (
        "surface_calcium_energy_water_hcn_extra",
        "SurfaceCalciumEnergyWaterHCNExtraModel",
        "resolved_calcium_energy_water@2",
    ),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def routes(base, suffix):
    result = []
    files = {}
    for relative in (
        "src/cells/core/specs.py",
        "src/cells/models/registry.py",
        "src/cells/ensemble/ionic.py",
    ):
        before = (base / relative).read_text()
        after = before
        if relative.endswith("specs.py"):
            statements = ""
            for module, cls, _ in OWNERS:
                statements += (
                    f"        from cells.core.{module}_spec import {cls}\n"
                    f"        from cells.core.{module}_spec import to_dict as {module}_dict\n"
                    f"        if isinstance(m, {cls}):\n"
                    f"            return {module}_dict(self)\n"
                )
            needle = "        m, e, x = self.model, self.experiment, self.execution\n"
            assert after.count(needle) == 1
            after = after.replace(needle, needle + statements)
            statements = ""
            for module, _, mid in OWNERS:
                statements += (
                    '    if isinstance(data["model"], dict) '
                    f'and data["model"].get("id") == "{mid}":\n'
                    f"        from cells.core.{module}_spec import parse\n"
                    "        return parse(data)\n"
                )
            needle = '        raise ConfigError("Only schema_version 1 is supported")\n'
            assert after.count(needle) == 1
            after = after.replace(needle, needle + statements)
        elif relative.endswith("registry.py"):
            statements = ""
            for module, cls, _ in OWNERS:
                statements += (
                    f"    from cells.core.{module}_spec import {cls}\n"
                    f"    if isinstance(spec, {cls}):\n"
                    f"        from cells.models import {module}\n"
                    f"        return {module}\n"
                )
            needle = "def get_model(spec):\n"
            assert after.count(needle) == 1
            after = after.replace(needle, needle + statements)
        else:
            needle = '        "resolved_calcium@1",\n'
            assert after.count(needle) == 1
            after = after.replace(needle, "".join(f'        "{v[2]}",\n' for v in OWNERS) + needle)
        files[relative] = dict(base_sha256=sha(before.encode()), patched_sha256=sha(after.encode()))
        result.extend(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile="a/" + relative,
                tofile="b/" + relative,
            )
        )
    path = WORK / (STEM + suffix + ".patch")
    path.write_text("".join(result))
    write(
        path.with_suffix(".json"),
        dict(
            patch_sha256=sha(path.read_bytes()),
            files=files,
            shared_files_written=False,
            base=str(base),
        ),
    )


def source_path(module):
    path = Path(*module.split("."))
    root = ROOT / "src" if module.startswith("cells") else ROOT
    for candidate in (root / path.with_suffix(".py"), root / path / "__init__.py"):
        if candidate.is_file():
            return candidate.relative_to(ROOT).as_posix()


def dependency_closure(seeds):
    # Mutable execution routes are frozen by the complete engine manifest instead.
    excluded = {
        "src/cells/core/specs.py",
        "src/cells/core/state.py",
        "src/cells/core/schedule.py",
        "src/cells/core/runner.py",
        "src/cells/models/registry.py",
        "src/cells/ensemble/ionic.py",
    }
    pending, seen = list(seeds), set()
    while pending:
        relative = pending.pop()
        if relative in seen or relative in excluded:
            continue
        seen.add(relative)
        for node in ast.walk(ast.parse((ROOT / relative).read_bytes())):
            names = []
            if isinstance(node, ast.Import):
                names.extend(n.name for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.append(node.module)
                names.extend(node.module + "." + n.name for n in node.names)
            pending.extend(p for name in names if (p := source_path(name)))
    return {
        name: sha((ROOT / name).read_bytes())
        for name in sorted(
            seen
            - set(RUNTIME)
            - {
                "validation/topology/" + STEM + "_fixtures.py",
                "validation/topology/" + STEM + "_reference.py",
            }
        )
    }


def main():
    routes(BASE / "workspace", "_test_dispatch")
    path = WORK / (STEM + "_test_dispatch.patch")
    meta_path = path.with_suffix(".json")
    meta = json.loads(meta_path.read_text())
    relative = "src/cells/core/schedule.py"
    before = (BASE / "workspace" / relative).read_text()
    insertion = """    from cells.core import (
        surface_calcium_energy_water_repair_hcn_extra_spec as joint_hcn_repair,
    )
    from cells.core import surface_calcium_energy_water_hcn_extra_spec as joint_hcn_water
    if isinstance(spec.model, joint_hcn_repair.SurfaceCalciumEnergyWaterRepairHCNExtraModel):
        original = control_values(joint_hcn_repair.base_spec(spec), times)
        changes = spec.experiment.changes
        indexes = np.searchsorted([p.time for p in changes], times, side="right") - 1
        extra = []
        for key in ("injury", "resealing"):
            values = np.asarray([getattr(p, key) for p in changes], dtype=float)[indexes]
            padded = np.zeros((len(times), spec.execution.membrane_capacity))
            padded[:, :len(spec.model.membranes)] = values
            extra.append(padded)
        return joint_hcn_repair.Control(*original, *extra)
    if isinstance(spec.model, joint_hcn_water.SurfaceCalciumEnergyWaterHCNExtraModel):
        original = control_values(joint_hcn_water.energy_spec(spec), times)
        changes = spec.experiment.changes
        indexes = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.water for p in changes], dtype=float)[indexes]
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        padded[:, :len(spec.model.membranes)] = values
        return joint_hcn_water.Control(*original, padded)
"""
    needle = "def control_values(spec, times):\n"
    assert before.count(needle) == 1
    after = before.replace(needle, needle + insertion)
    addition = "".join(
        difflib.unified_diff(
            before.splitlines(True),
            after.splitlines(True),
            fromfile="a/" + relative,
            tofile="b/" + relative,
        )
    )
    path.write_text(path.read_text() + addition)
    meta["files"][relative] = dict(
        base_sha256=sha(before.encode()), patched_sha256=sha(after.encode())
    )
    meta["patch_sha256"] = sha(path.read_bytes())
    write(meta_path, meta)
    old = json.loads(
        (ROOT / "validation/topology/owned_calcium_profile_interventions_protocol.json").read_text()
    )
    owned = [
        *RUNTIME,
        "tests/owned_joint_water_hcn_helpers.py",
        "tests/unit/test_surface_calcium_energy_water_hcn_extra.py",
        "tests/unit/test_surface_calcium_energy_water_repair_hcn_extra.py",
        "validation/tissue/calcium_energy_water_hcn_extra_reference.py",
        "validation/tissue/calcium_energy_water_repair_hcn_extra_reference.py",
        "validation/tissue/calcium_energy_water_hcn_extra_fixtures.py",
        "validation/tissue/calcium_energy_water_repair_hcn_extra_fixtures.py",
    ]
    readonly = dependency_closure([*owned, "validation/betse/contact.py"])
    readonly = {p: v for p, v in readonly.items() if p not in owned}
    manifest = BASE / "workspace-manifest.json"
    receipt = Path("/mnt/workspaces/Cells/owned-calcium-profiles-handoff-20261029-01/result.json")
    protocol = dict(
        purpose="Full56 HCN catalog at actual chemical/fuel/water owners, with prescribed repair",
        supported_owners={
            "resolved_calcium_energy_water@2": "resolved_calcium_energy@5",
            "resolved_calcium_energy_water_repair@2": "resolved_calcium_energy_water@2",
        },
        scope=(
            "Full 43/48-state independent NumPy stages and all-observation trajectories; "
            "no compiled/GPU, stochastic histories or new repair energetics"
        ),
        readonly_source_sha256=readonly,
        frozen_workspace=dict(
            path=str(BASE / "workspace"),
            manifest=str(manifest),
            manifest_sha256=sha(manifest.read_bytes()),
            source_hash_key="source_sha256",
            handoff_receipt=str(receipt),
            handoff_receipt_sha256=sha(receipt.read_bytes()),
        ),
        resources=old["resources"],
        budgets=old["budgets"],
        test_dispatch_patch="agent-work/cells-worker-01/workfiles/" + STEM + "_test_dispatch.patch",
        test_dispatch_metadata="agent-work/cells-worker-01/workfiles/"
        + STEM
        + "_test_dispatch.json",
        expected_unique_checks=46,
        control_routes="isolated copy only; Root owns live shared routing",
        trajectories=(
            "All observations and held-control boundaries, both steps, full "
            "production/reference NPZ; precision floor explicit; "
            "no endpoint-only/order claim"
        ),
        automatic_followup=False,
    )
    write(ROOT / "validation/tissue/joint_water_hcn_protocol.json", protocol)


if __name__ == "__main__":
    main()
