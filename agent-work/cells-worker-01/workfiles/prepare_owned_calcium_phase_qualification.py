"""Prepare isolated calcium/fuel INIT/SIM epoch qualification routes and source pins."""

import ast
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
STEM = "owned_calcium_profile_phase_handoff"
BASE = Path("/mnt/workspaces/Cells/owned-calcium-profiles-development-20261029-07")
RUNTIME = (
    "src/cells/core/owned_calcium_profile_phase_handoff.py",
    "src/cells/core/surface_calcium_profile_epoch_spec.py",
    "src/cells/core/surface_calcium_energy_profile_epoch_spec.py",
    "src/cells/models/surface_calcium_profile_epoch.py",
    "src/cells/models/surface_calcium_energy_profile_epoch.py",
)
OWNERS = (
    (
        "surface_calcium_profile_epoch",
        "SurfaceCalciumProfileEpochModel",
        "resolved_calcium_membrane_profile_epoch@1",
    ),
    (
        "surface_calcium_energy_profile_epoch",
        "SurfaceCalciumEnergyProfileEpochModel",
        "resolved_calcium_energy_membrane_profile_epoch@1",
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
    graphs = {
        "surface_kinetic": ["readouts", "domain_valid"],
        "surface_tissue": ["field_values", "physical_amounts", "charge_increment"],
        "spatial_calcium": ["store_state", "cytosol_amount", "ownership_residual"],
        "surface_calcium": [
            "ionic_state",
            "ionic_layout",
            "readouts",
            "domain_valid",
            "physical_amounts",
            "balances",
            "check_values",
            "observe_history",
        ],
        "surface_calcium_energy": [
            "prior_state",
            "energy_amounts",
            "stage_layout",
            "readouts",
            "domain_valid",
            "balances",
            "check_values",
            "observe_history",
        ],
        "ip3_calcium": ["ip3_readouts"],
    }
    call_graph = []
    for module, functions in graphs.items():
        relative = "src/cells/models/" + module + ".py"
        content = (ROOT / relative).read_bytes()
        tree = ast.parse(content)
        nodes = {
            name: next(
                n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name
            )
            for name in functions
        }
        call_graph.append(
            dict(
                path=relative,
                sha256=sha(content),
                body_ast_sha256={
                    name: sha(ast.dump(n, include_attributes=False).encode())
                    for name, n in nodes.items()
                },
                state_flow={name: state_flow(n) for name, n in nodes.items()},
            )
        )
    old = json.loads(
        (
            ROOT / "validation/topology/surface_active_profile_interventions_protocol.json"
        ).read_text()
    )
    manifest = BASE / "workspace-manifest.json"
    receipt = Path("/mnt/workspaces/Cells/owned-calcium-profiles-handoff-20261029-01/result.json")
    protocol = dict(
        purpose=(
            "Explicit complete INIT/SIM continuity with actual stores, gates, pools "
            "and original ledgers"
        ),
        supported_owners={
            OWNERS[0][2]: "resolved_calcium_membrane_profiles@1",
            OWNERS[1][2]: "resolved_calcium_energy_membrane_profiles@1",
        },
        scope=(
            "Explicit INIT checkpoint to a new SIM epoch for complete calcium @6 "
            "and finite-fuel @5; every original accounting reference and physical array "
            "carried; no implicit branch, cut or remap"
        ),
        readonly_source_sha256=dependency_closure(
            [
                *RUNTIME,
                "validation/topology/" + STEM + "_fixtures.py",
                "validation/topology/" + STEM + "_reference.py",
                "validation/betse/contact.py",
                "tests/unit/test_owned_calcium_profile_interventions.py",
            ]
        ),
        frozen_workspace=dict(
            path=str(BASE / "workspace"),
            manifest=str(manifest),
            manifest_sha256=sha(manifest.read_bytes()),
            source_hash_key="source_sha256",
            handoff_receipt=str(receipt),
            handoff_receipt_sha256=sha(receipt.read_bytes()),
        ),
        owner_call_graph=call_graph,
        native_phase_scope=old["native_phase_scope"],
        resources=old["resources"],
        budgets=old["budgets"],
        history_projection=(
            "Only closed background membrane_transferred is masked in a temporary "
            "readout view. Every physical store, gate and live fuel pool stays "
            "actual. All material and energy diagnostics use untouched full "
            "history under union support."
        ),
        timestep_admission=(
            "Maximum scheduled background P adds a conservative "
            "per-owner GHK outflow bound to the unchanged parent chemical "
            "loss bound; step times their sum must be <=0.25."
        ),
        trajectory_claim=(
            "Independent full-state agreement at both allowed steps; "
            "compare all observations and control boundaries, retain full state/reference "
            "NPZ arrays "
            "and require measurable transient membrane-transfer refinement."
        ),
        carried_initial_fuel_admission=(
            "Retain the unchanged 0.05 gross turnover limit "
            "using actual carried ATP/ADP/Pi and actual SIM-stage controls, plus the "
            "qualified scheduled background/chemical and native ramp bounds."
        ),
        test_dispatch_patch="agent-work/cells-worker-01/workfiles/" + STEM + "_test_dispatch.patch",
        test_dispatch_metadata="agent-work/cells-worker-01/workfiles/"
        + STEM
        + "_test_dispatch.json",
        automatic_followup=False,
        expected_unique_checks=62,
        retained_trajectory_arrays=(
            "Two complete INIT and four carried SIM datasets, "
            "all observations/control boundaries at both timesteps, full padded production "
            "arrays plus active reference/production flats and shape metadata."
        ),
        expected_coarse_failure=(
            "Reproduce the original 31.25 ns failed transient "
            "comparison from unchanged equations; save full failed arrays separately and "
            "do not count it as a passing scientific case."
        ),
    )
    write(ROOT / ("validation/topology/" + STEM + "_protocol.json"), protocol)


if __name__ == "__main__":
    main()
