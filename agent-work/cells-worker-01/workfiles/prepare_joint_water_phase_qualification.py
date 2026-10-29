"""Prepare isolated calcium/fuel INIT/SIM epoch qualification routes and source pins."""

import ast
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
STEM = "joint_water_profile_phase_handoff"
BASE = Path("/mnt/workspaces/Cells/joint-water-profiles-development-20261029-02")
RUNTIME = (
    "src/cells/core/joint_water_profile_phase_handoff.py",
    "src/cells/core/surface_calcium_energy_water_profile_epoch_spec.py",
    "src/cells/core/surface_calcium_energy_water_repair_profile_epoch_spec.py",
    "src/cells/models/surface_calcium_energy_water_profile_epoch.py",
    "src/cells/models/surface_calcium_energy_water_repair_profile_epoch.py",
)
OWNERS = (
    (
        "surface_calcium_energy_water_profile_epoch",
        "SurfaceCalciumEnergyWaterProfileEpochModel",
        "resolved_calcium_energy_water_membrane_profile_epoch@1",
    ),
    (
        "surface_calcium_energy_water_repair_profile_epoch",
        "SurfaceCalciumEnergyWaterRepairProfileEpochModel",
        "resolved_calcium_energy_water_repair_membrane_profile_epoch@1",
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
        "src/cells/core/tissue_profile_composition_preparation.py",
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
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    package = Path(relative).parent.parts
                    if package[0] == "src":
                        package = package[1:]
                    base = ".".join(package[: len(package) - node.level + 1])
                    module = base + ("." + node.module if node.module else "")
                else:
                    module = node.module
                if module:
                    names.append(module)
                    names.extend(module + "." + n.name for n in node.names)
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


def state_flow(node):
    parents = {child: owner for owner in ast.walk(node) for child in ast.iter_child_nodes(owner)}
    attributes, calls, other = set(), set(), set()
    for value in ast.walk(node):
        if isinstance(value, ast.Name) and value.id == "state" and isinstance(value.ctx, ast.Load):
            owner = parents[value]
            if isinstance(owner, ast.Attribute):
                attributes.add(owner.attr)
            elif isinstance(owner, ast.Call):
                calls.add(ast.unparse(owner.func))
            else:
                other.add(type(owner).__name__)
    return dict(attributes=sorted(attributes), calls=sorted(calls), other=sorted(other))


def main():
    routes(BASE / "workspace", "_test_dispatch")
    patch = WORK / (STEM + "_test_dispatch.patch")
    metadata_path = patch.with_suffix(".json")
    metadata = json.loads(metadata_path.read_text())
    relative = "src/cells/core/schedule.py"
    before = (BASE / "workspace" / relative).read_text()
    insertion = ""
    for module, cls, _ in OWNERS:
        insertion += (
            f"    from cells.core import {module}_spec as {module}\n"
            f"    if isinstance(spec.model, {module}.{cls}):\n"
            f"        return control_values({module}.scheduled_spec(spec), times)\n"
        )
    after = before.replace(
        "def control_values(spec, times):\n", "def control_values(spec, times):\n" + insertion
    )
    with patch.open("a") as stream:
        stream.write(
            "".join(
                difflib.unified_diff(
                    before.splitlines(True),
                    after.splitlines(True),
                    fromfile="a/" + relative,
                    tofile="b/" + relative,
                )
            )
        )
    metadata["files"][relative] = dict(
        base_sha256=sha(before.encode()), patched_sha256=sha(after.encode())
    )
    metadata["patch_sha256"] = sha(patch.read_bytes())
    write(metadata_path, metadata)
    owned = [
        *RUNTIME,
        "tests/unit/test_joint_water_profile_phase_handoff.py",
        "validation/topology/" + STEM + "_fixtures.py",
        "validation/topology/" + STEM + "_reference.py",
    ]
    readonly = dependency_closure(
        [
            *owned,
            "validation/betse/contact.py",
            "validation/assembly/component_process.py",
            "validation/ensemble/profile_cluster.py",
        ]
    )
    readonly = {k: v for k, v in readonly.items() if k not in owned}
    parent_contracts = [
        Path(
            "/mnt/workspaces/Cells/joint-water-profiles-development-20261029-"
            + number
            + "/result.json"
        )
        for number in ("01", "02")
    ]
    protocol = dict(
        purpose="Explicit full56 joint water INIT-to-SIM epoch with original accounting anchors",
        supported_owners={
            OWNERS[0][2]: "resolved_calcium_energy_water_membrane_profiles@1",
            OWNERS[1][2]: "resolved_calcium_energy_water_repair_membrane_profiles@1",
        },
        scope=(
            "Bounded evolved-checkpoint contracts and independent complete stages; "
            "no branch/cut/remap, no long trajectory admission"
        ),
        readonly_source_sha256=readonly,
        frozen_workspace=dict(
            path=str(BASE / "workspace"),
            manifest=str(BASE / "workspace-manifest.json"),
            manifest_sha256=sha((BASE / "workspace-manifest.json").read_bytes()),
            source_hash_key="source_sha256",
        ),
        parent_contract_receipts={str(p): sha(p.read_bytes()) for p in parent_contracts},
        parent_long_qualification=(
            "Pending; separate CPU4 run is not queried. Epoch trajectories held until closure."
        ),
        resources=dict(
            cpu_affinity=[7],
            max_child_tree_rss_bytes=2**30,
            min_available_host_bytes=8 * 2**30,
            max_phase_seconds=480,
            gpu=False,
            jit=False,
        ),
        budgets=dict(
            rhs_rtol=3e-10,
            rhs_atol=3e-12,
            charge_rhs_atol_C_s=3e-23,
            potential_rtol=3e-10,
            potential_atol_V=3e-13,
            stage_energy_atol_pJ_s=1e-10,
            trajectory_rtol=3e-9,
            trajectory_atol=2e-11,
            trajectory_charge_atol_C=3e-25,
            initial_gross_fuel_fraction_limit=0.05,
        ),
        test_dispatch_patch=str(patch.relative_to(ROOT)),
        test_dispatch_metadata=str(metadata_path.relative_to(ROOT)),
        expected_contract_checks=71,
        expected_defined_checks=77,
        long_trajectory_launch_admitted=False,
        automatic_followup=False,
        preservation=(
            "All43/48 parent fields, actual water/fuel/repair histories and original physical "
            "layout; reset only explicit phase clock"
        ),
    )
    write(ROOT / ("validation/topology/" + STEM + "_protocol.json"), protocol)


if __name__ == "__main__":
    main()
