"""Write static contracts/ownership pins without importing scientific modules."""

# ruff: noqa: E501 -- frozen contract descriptions and mathematical strings.

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


spec = importlib.util.spec_from_file_location(
    "molecule_ast_audit", WORK / "betse_normal_molecule_join_ast_audit.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
proof = module.audit()
previous = json.loads(
    (ROOT / "validation/betse/betse_normal_network_join_protocol.json").read_text()
)
base_queue = json.loads((WORK / "betse_prepared_er_join_workqueue.json").read_text())
protected = base_queue["protected_sha256"] | base_queue["owned_sha256"]
extra_dependencies = [
    "src/cells/processes/betse_network_modulation.py",
    "src/cells/processes/betse_network_reactions.py",
    "src/cells/processes/betse_network_transport.py",
    "validation/regulation/betse_network_modulation_protocol.json",
    "validation/chemistry/betse_network_reactions_protocol.json",
    "validation/transport/betse_network_transport_protocol.json",
]
for path in extra_dependencies:
    protected.setdefault(path, sha(ROOT / path))
for path, digest in protected.items():
    assert sha(ROOT / path) == digest, path
native = dict(previous["native_source"])
native["source_sha256"] = dict(native["source_sha256"])
exception_file = Path(native["checkout"]) / "betse/exceptions.py"
assert (
    exception_file.read_bytes()
    == (Path(native["installed_package"]) / "exceptions.py").read_bytes()
)
native["source_sha256"]["betse/exceptions.py"] = sha(exception_file)
evidence = {
    "accepted_feedback_inputs": dict(
        path="/mnt/workspaces/Cells/betse-normal-network-prepared-20261030-02/inputs.json",
        sha256="eaa1a1376c228a50c46e2c8aca2c0e8c826b16e5db808b8cd32d55cf9699d97e",
    ),
    "accepted_feedback_review": dict(
        path="/mnt/workspaces/Cells/betse-normal-network-tests-20261030-01/root-review-01/REVIEW.json",
        sha256="ba8182630f163b6b6728f037d5b38d4b451f44396f48838871b4fdf04610c943",
    ),
    "accepted_prepared_ER_inputs": dict(
        path="/mnt/workspaces/Cells/betse-prepared-er-prepared-20261030-02/inputs.json",
        sha256="25070ece836bfbfda59d81323e1d0207d17126ea4b1d5b8d194de66e08fe7896",
    ),
    "accepted_prepared_ER_review": dict(
        path="/mnt/workspaces/Cells/betse-prepared-er-tests-20261030-02/root-review-01/REVIEW.json",
        sha256="a946f94703c1e860d444a5f98e591fe53c7e35379ea6233bc03914799def1334",
    ),
}
for row in evidence.values():
    assert sha(row["path"]) == row["sha256"], row["path"]
budgets = dict(previous["acceptance"]["inherited_budget_source_sha256"])
for path in (
    "validation/chemistry/betse_network_reactions_protocol.json",
    "validation/betse/betse_normal_ion_join_protocol.json",
    "tests/unit/test_betse_normal_ion_join.py",
    "validation/betse/betse_normal_current_protocol.json",
):
    budgets[path] = sha(ROOT / path)
protocol = dict(
    kind="cells.native_molecule_chemistry_transport_static_contract@1",
    law_id="betse_normal_native_molecule_chemistry_transport_v1_5_0@1",
    status="static_unqualified_no_molecule_numerics",
    purpose="First real nonempty growth/reaction/molecule_mover seam with owned state on the supplied normal prefix",
    native_source=native,
    source_map="validation/betse/betse_normal_molecule_join_source_map.json",
    binding_evidence=evidence,
    scope=dict(
        real_molecules=["X", "Y"],
        network_core="Exactly one core labelled molecules; actual low-level Molecule instances and core bodies, no high-level owner-wrapper dispatch/lifecycle credit",
        chemistry="Explicit irreversible cell X->Y with unit stoichiometry; optional genuine simple growth/decay for each real molecule; all targets are all cells",
        mover="Complete original no-ECM passive membrane/GJ mover, instant intracellular mixing, rho_channel=1; no D0 shortcut",
        initial_state="Complete caller-supplied cell/membrane/bath/flux caches and explicit source cache presence, declared parameters and context; native read_substances/tissue_init are audited mappings, not executed lifecycle",
        current="Literal charge/current publication including molecular GJ term in extra_J_mem, weighted by declared z*scale_factor",
        calcium="Existing maintained-pool CaATP with explicit Ca_dyn0",
        excluded=[
            "Mitochondria/environment chemistry",
            "Reversible or regulated molecule reaction paths",
            "Active molecule pumps, gating ligands, clamps/boundary events",
            "Intracellular shell/field and motor/convection transport",
            "ECM/TJ/environment finite-difference transport",
            "Finite ATP/buffers/full GRN/mesh/full Simulator initialization",
            "Biological or physical global conservation/trajectory accuracy qualification",
        ],
    ),
    owned_state=dict(
        dynamic_fields=[
            "c_cells",
            "cc_at_mem",
            "c_env",
            "flux_intra",
            "f_mem",
            "f_gj",
            "fenvx",
            "fenvy",
        ],
        presence="Absent initial transport caches remain explicitly absent; after actual transport the original scalar/vector cache types persist",
        static_fields="Complete transport flags/coefficients, growth parameters, boundary value, all-cell target phase, radius and rho context are immutable binding data",
        parent="Full persistent molecule state lives in the joined network_cache and identity; no silent reinitialization from initial inputs",
        native_axes="Ions first in their exact order, then molecules in declared order; growth columns in molecule order, reaction column after them",
        geometry="Same supplied ion owner/partner/boundary/areas/volumes/GJ lengths and voltage membrane radii; no independent native mesh preparation credit",
        aliases="Production live getter/setter mapping versus actual original DynamicValue/Dict in independent native capture",
        voltages="All membrane and GJ nonce stores are actual owned parent buffers and persist",
    ),
    source_order=[
        "Carried or explicitly supplied scheduled controls feed the ordinary prefix",
        "Ordinary NaK/ions/GJ/intra, then CaATP, network clear and late catalog channels",
        "Original ion-driven GJ/NaK modulators overwrite controls in order; new GJ values affect molecules in this call and ordinary transport in the next",
        "Every molecule update_intra(False) refreshes membrane cache before any RHS",
        "All genuine GAD and reaction rates, stack and matrix delta are computed before any chemical concentration mutation",
        "Sequential species commit; each molecule always runs actual transport, no_negs and optional charge/current accumulation",
        "Mover membrane flux samples pre-chemistry membrane cache, update_Co refreshes it from post-chemical bulk, then GJ uses refreshed membrane and configured T",
        "No-ECM scalar mean is rebroadcast to the full membrane bath vector; preserve all checks/partial failures",
        "Energy charge, publication, ordinary deferred commit/clipping, current and voltage; carry full state/cache/control/clock",
    ],
    input_versus_execution=dict(
        supplied="Complete initial state, static molecule parameters, actual modify_time_factor values, ordinary/scheduled/channel packets; no event/function/time-dilation initializer execution claim",
        executed="Original Molecule constructor/all-target init_growth/update_intra/transport, generated growth/reaction strings, actual core run_loop and actual molecule_mover/update_Co/electroflux/no_negs",
        observations="Read-only actual pre-network snapshot before model chemistry; copied RHS/gad/all_rates and internal mover states do not supply chemistry outputs",
        phase="Configured-state seam; native read_substances/tissue_init/charge balancing/high-level wrappers are not claimed executed",
    ),
    planned=dict(
        checks=21,
        positive_three_call_histories=15,
        new_coupled_cases=12,
        component_control_histories=3,
        raw_partial_failures=2,
        dependency_controls=4,
        native_captures=17,
        positive_native_outer_calls=45,
        actual_pre_network_points=45,
        fresh_Decimal_reference_forms=90,
        carried_reference_forms=0,
        positive_completed_mover_calls_per_implementation=90,
        biological_cases=0,
    ),
    component_controls=dict(
        new_caller_controls=["reaction_only", "growth_only", "transport_only"],
        legacy_source_laws={
            path: sha(ROOT / path) for path in extra_dependencies if path.endswith("protocol.json")
        },
        credit="Legacy component passes are not rerun or counted. New caller controls are separated from the12 coupled cases; real mover still executes at D0.",
        distinction="betse_network_transport is a configurable transporter law, not molecule_mover. Its previous qualification is not new passive-mover credit.",
    ),
    acceptance=dict(
        primary="Exact complete native arrays/dtypes, chemistry/mover frames, RHS and stack shapes, persistent buffers/cache presence, source failures, current and voltage",
        inherited_budget_source_sha256=budgets,
        feedback=previous["acceptance"],
        reaction_rates="Unchanged standalone rate_atol2e-14 mM/s + relative5e-12; delta has3*atol +relative*gross",
        molecule_material="128*eps*(ion_count+molecule_count+cell_count+membrane_count+64)*actual local Decimal gross + unchanged B24 concentration/flux floors",
        source_effective_balances="Same a priori factor times absolute old/new amount and transfer terms + B24 concentration floors times owned volume; mol units",
        charge="32*eps*(molecules+cells+16)*sum(abs(local source charge terms))+1e-30 C/m3",
        current="128*eps*(molecules+membranes+32)*local source-current gross+1e-30 A/m2",
        nonces="Explicit primitive binary64 stores in the otherwise Decimal90/140 reference, as in the accepted ion reference",
        self_resolution_fraction=0.1,
        full_errors_budgets_units_and_defect_arrays=True,
        no_outcome_tuning=True,
        conditional_pre_network_only=True,
        independently_carried_reference_forms=0,
    ),
    accounting=dict(
        single_bath_metadata="Original bath_volume_m3/vol_env is unchanged",
        source_effective="update_Co averages per-membrane environmental changes; source-effective ledger uses sum(env[j]*vol_env), equivalently M*vol_env at uniform final mean. This is an algebraic source ledger, not a physical volume reinterpretation.",
        declared_single_bath="Use original single vol_env times mean(c_env). Independently predict residual after chemistry and directed-GJ subtraction as dt*(1-1/M)*sum(f_mem*A). Report observed/predicted defect and its difference separately.",
        directed_GJ="Report -dt*modify_time_factor*sum(f_gj*A) explicitly. Do not assume zero for the supplied directed geometry/controls and do not absorb it into the bath defect.",
        growth_conversion="Separate real GAD source/sink amounts from stoichiometric X/Y conversion; preserve declared equal z*scale weighting",
        physical_global_conservation_credit=False,
        charged_environment="Source publishes no molecular extra_rho_env in no-ECM mode; retain this omission and make no closed electrochemical/field-energy claim",
        scale="Native numeric concentration/amount ledger; source scale_factor is explicitly retained in charge/current projections. No physiological calibration inferred.",
    ),
    failures=dict(
        raw=["first_molecule_negative", "second_molecule_negative"],
        partial="Preserve all pre-RHS/after-commit/internal-mover states, rate/delta caches, nonce stores and partially accumulated current/charge; failed transport tuple assignment may leave global molecule fields at the chemical commit",
        positive_credit=False,
        old_evidence="All accepted/failed/frozen predecessor trees remain unchanged; the original zero-Molecule nonempty-reaction stack refusal stays a failure, not repaired/reclassified",
        retry="No automatic retry, parameter or dt adjustment, or follow-up regression",
    ),
    artifacts=dict(
        caller_inputs_before_constructor=True,
        constructor_step_returns_and_partial_exceptions_before_assertions=True,
        actual_pre_network_before_model_math=True,
        typed_archive_codec="Existing NPZ/finite-JSON envelope; preserve raw IEEE payloads",
        native_observer_exclusion="Only _mover_observe callable is omitted from source_parameters archive; all scientific parameters remain included",
    ),
    resources=dict(
        cpu=None,
        cpu_coordination="No numerical launch in this static assignment; later explicit requested/CPU-coordinated round only",
        gpu=False,
        threads=1,
        max_command_seconds=480,
        max_process_tree_rss_bytes=2**30,
        min_available_host_memory_bytes=8 * 2**30,
    ),
    scientific_imports=0,
    pytest_collection_runs=0,
    numerical_runs=0,
    automatic_launch=False,
    automatic_polling=False,
    automatic_followup=False,
)
mapping = dict(
    kind="cells.native_molecule_chemistry_transport_source_map@1",
    source_revision=native["revision"],
    source_sha256=native["source_sha256"],
    **proof,
    ownership={
        "c_cells": "Actual Molecule.c_cells; dynamic cell_concs setter replaces the live row/object array",
        "cc_at_mem": "Actual cache refreshed for all molecules before RHS, stale across chemistry until original update_Co/GJ refresh",
        "c_env": "Actual membrane-sized vector; scalar intermediate from update_Co and final broadcast retained in frames",
        "flux_intra": "Persistent stale source cache when update_intra_conc=False, not reset or invented",
        "f_mem/f_gj": "Actual return arrays; absent before first transport and on an incomplete first tuple assignment",
        "fenvx/fenvy": "Original no-ECM scalar zeros after transport, not fabricated spatial fields",
        "geometry_controls": "Native owner/partner maps, areas/volumes/radii/GJ lengths, gjopen, gj_block/rho and runtime/configured T explicitly owned",
        "charge_current": "Literal scale-weighted accumulation, partial cache and publication-switch behavior",
    },
    inspected_unexecuted_lifecycle=dict(
        path="betse/science/chemistry/networks.py",
        read_substances=[120, 322],
        tissue_init=[326, 804],
        Molecule_constructor=[5614, 5667],
        init_growth=[6000, 6043],
        scope="Audited state-assignment correspondence only; no high-level initialization/charge-balance execution parity",
    ),
    source_effective_and_physical_ledgers_separate=True,
    source_equation_repair=False,
    supplied_chemical_results=False,
    mover_skipped_at_D0=False,
    physical_global_conservation_credit=False,
)
net_tree = ast.parse((Path(native["checkout"]) / "betse/science/chemistry/networks.py").read_text())
tool_tree = ast.parse((Path(native["checkout"]) / "betse/science/sim_toolbox.py").read_text())
source_classes = {node.name: node for node in net_tree.body if isinstance(node, ast.ClassDef)}
source_helpers = {node.name: node for node in tool_tree.body if isinstance(node, ast.FunctionDef)}
for name, row in mapping["literal_numeric_bodies"].items():
    if "." in name:
        cls, method = name.split(".")
        node = next(
            n
            for n in source_classes[cls].body
            if isinstance(n, ast.FunctionDef) and n.name == method
        )
        path = "betse/science/chemistry/networks.py"
    else:
        node = source_helpers[name]
        path = "betse/science/sim_toolbox.py"
    row.update(source_path=path, first_line=node.lineno, last_line=node.end_lineno)
write(ROOT / "validation/betse/betse_normal_molecule_join_protocol.json", protocol)
write(ROOT / "validation/betse/betse_normal_molecule_join_source_map.json", mapping)
owned = [
    "src/cells/processes/betse_normal_molecule_source.py",
    "src/cells/processes/betse_normal_molecule_join.py",
    "tests/unit/test_betse_normal_molecule_join.py",
] + [
    "validation/betse/betse_normal_molecule_join_" + name
    for name in (
        "fixtures.py",
        "native.py",
        "native_helpers.py",
        "native_network.py",
        "reference.py",
        "protocol.json",
        "source_map.json",
    )
]
unrelated = [
    "src/cells/models/surface_calcium_energy.py",
    "src/cells/models/physiology_active_temperature_arrays.py",
]
assert not set(unrelated) & set(protected)
queue = dict(
    kind="cells.native_molecule_chemistry_transport_workqueue@1",
    status="implementation_and_AST_proof_ready_final_static_checks_pending",
    owned=owned,
    owned_sha256={path: sha(ROOT / path) for path in owned},
    protected_sha256=protected,
    base_prior_protected_files=209,
    runner="agent-work/cells-worker-01/workfiles/betse_normal_molecule_join_checks.py",
    notes="agent-work/cells-worker-01/workfiles/BETSE_NORMAL_MOLECULE_JOIN_NOTES.md",
    binding_evidence=evidence,
    coordinated_shared_edit_paths=list(
        dict.fromkeys(base_queue["coordinated_shared_edit_paths"] + unrelated)
    ),
    coordinated_unrelated_physics_edits=dict(
        authority="Chief owns complete_calcium_stage/5-stage compiled refactor and tests; no edits by worker",
        paths=unrelated,
        outside_protected_and_import_closure=True,
        frozen_bytes_still_hashed=True,
    ),
    authorized_physical_helper_refactor=base_queue["authorized_physical_helper_refactor"],
    static_checks={},
    reference_closure={},
    active_numerical_job=None,
    numerical_runs=0,
    scientific_imports=0,
    pytest_collection_runs=0,
    automatic_launch=False,
    automatic_polling=False,
    automatic_followup=False,
)
write(WORK / "betse_normal_molecule_join_workqueue.json", queue)
print(
    json.dumps(
        dict(
            status=queue["status"],
            owned=len(owned),
            protected=len(protected),
            base_protected=209,
            AST_bodies=22,
            native_sources=len(native["source_sha256"]),
            planned_checks=21,
            native_captures=17,
            fresh_forms=90,
            numerical_runs=0,
        )
    )
)
