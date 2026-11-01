"""Source-only cap correspondence for the held extended-material contract."""

import ast
import hashlib
from pathlib import Path

from cells.processes import betse_normal_ecm_molecule_material_domain as domain
from validation import source_snapshot as snapshot

OWNED = (
    "src/cells/processes/betse_normal_ecm_molecule_material_domain.py",
    "validation/betse/betse_normal_ecm_molecule_material_domain.py",
    "tests/unit/test_betse_normal_ecm_molecule_material_domain.py",
)
TRACE = (
    (
        "betse_normal_ecm_molecule_dispatch",
        "verify",
        "material.state cap plus cursor/source-clock3",
        "Key",
    ),
    (
        "betse_normal_ecm_molecule_dispatch",
        "advance",
        "index>=3 before calcium._material_step",
        "Key",
    ),
    (
        "betse_normal_ecm_molecule_transport",
        "bind",
        "prior.dispatch.bind -> calcium.bind -> field.bind",
        "Key",
    ),
    (
        "betse_normal_ecm_molecule_transport",
        "verify",
        "material.state cap plus cursor/source-clock3",
        "Key",
    ),
    (
        "betse_normal_ecm_molecule_transport",
        "advance",
        "index>=3 before calcium._material_step",
        "Key",
    ),
    ("betse_ecm_transport", "state", "absolute step_index in[0,MAX_STEPS=3]", "shared"),
    ("betse_ecm_transport", "step", "step_index>=MAX_STEPS and state revalidation", "shared"),
    ("betse_ecm_grn_join", "bind", "exactly3 declared rows", "shared"),
    ("betse_ecm_grn_join", "material_step", "MAX_STEPS and material.state revalidation", "shared"),
    ("betse_normal_ecm_field_join", "bind", "exactly3 rows; material.state bootstrap", "shared"),
    (
        "betse_normal_ecm_field_join",
        "reconstruct",
        "suffix recreates material.state at absolute index",
        "shared",
    ),
    (
        "betse_normal_ecm_calcium_join",
        "_material_step",
        "MAX_STEPS=material.MAX_STEPS; exact native arithmetic",
        "Root",
    ),
    ("betse_normal_ecm_calcium_join", "advance", "three-label clock and step-row indexing", "Root"),
    (
        "betse_normal_ecm_init_phase_material",
        "step_init",
        "same cap/state plus post-network mechanics hook",
        "Root",
    ),
    ("betse_normal_ecm_catalog_join_source", "restore", "reached channel/cache validation", "Root"),
    (
        "betse_normal_ecm_catalog_join_source",
        "validate_cached_channels",
        "writer invocation counts in[0,3]",
        "Root",
    ),
    ("betse_mechanics_join", "state", "mechanics index in[0,MAX_STEPS=3]", "shared"),
    ("betse_mechanics_join", "step", "mechanics step_index>=MAX_STEPS", "shared"),
    (
        "betse_normal_ecm_molecule_lifecycle_phase",
        "bind",
        "min(3,original calendar.step_count)",
        "Key",
    ),
    (
        "betse_normal_ecm_molecule_lifecycle_phase",
        "advance",
        "INIT/SIM uses Root.step_init and mechanics.step",
        "Key",
    ),
    ("betse_normal_ecm_molecule_lifecycle", "bind", "SIM calendar.step_count exactly3", "Key"),
    (
        "betse_normal_ecm_molecule_run_lifecycle",
        "bind",
        "SIM actual calendar/call_limit exactly3",
        "Key",
    ),
    (
        "betse_normal_ecm_molecule_events",
        "verify_binding",
        "event SIM calendar/call_limit exactly3",
        "Key",
    ),
)


def source_plan(repository):
    """Bind reached functions and cap literals; never compile/call a body."""
    repository = Path(repository).resolve(strict=True)
    rows, pins, trees = [], {}, {}
    for module, member, reason, owner in TRACE:
        name = "src/cells/processes/" + module + ".py"
        path = snapshot.regular_file(repository, name)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        pins[name] = digest
        tree = trees.setdefault(name, ast.parse(data))
        nodes = [
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == member
        ]
        domain.require(
            len(nodes) == 1, "Changed reached material cap member: " + module + "." + member
        )
        node = nodes[0]
        rows.append(
            dict(
                module=module,
                function=member,
                line=node.lineno,
                reason=reason,
                owner=owner,
                whole_function_AST_sha256=hashlib.sha256(
                    ast.dump(node, include_attributes=False).encode()
                ).hexdigest(),
            )
        )
    base = trees["src/cells/processes/betse_ecm_transport.py"]
    domain.require(
        any(
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "MAX_STEPS" for target in node.targets
            )
            and isinstance(node.value, ast.Constant)
            and type(node.value.value) is int
            and node.value.value == 3
            for node in base.body
        ),
        "Legacy material MAX_STEPS changed; no silent extension adoption",
    )
    return dict(
        kind=domain.KIND,
        status="extended_numerical_entry_blocked_by_shared_domains",
        source_pins=pins,
        reached_caps=rows,
        required_seams=domain.REQUIRED_SEAMS,
        cap_trace_scope=(
            "ordinary standalone dispatch/transport, coupled INIT/SIM and events; "
            "numerical bodies unchanged"
        ),
        nontemporal_limits_unchanged=[
            "three general-owner transporter roster entries",
            "channel/catalog/species/shape limits",
        ],
        metadata_contract_only=True,
        numeric_calls=0,
        independent_biological_cases=0,
        next_source_boundary=(
            "Explicit shared material/state/field/calcium/catalog domain, preserving native "
            "body/order and legacy defaults; mechanics/INIT seam before coupled advancement"
        ),
    )
