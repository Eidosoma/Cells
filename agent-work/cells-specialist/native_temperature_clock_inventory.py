"""Freeze a static native temperature/clock inventory without executing BETSE.

This is source evidence and explicitly labelled algebraic inference. It does
not run, inspect or poll any active qualification, nor define a thermal law.
All generated files are confined to the caller's /mnt/workspaces/Cells output.
"""

import argparse
import ast
import hashlib
import json
import os
import resource
import shutil
import sys
import time
import traceback
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/robert/Cells")
OUTPUT_ROOT = Path("/mnt/workspaces/Cells")
MANIFEST = ROOT / "validation/temperature/source_manifest.json"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, record):
    with path.open("x") as stream:
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted(node.value)
        return prefix + "." + node.attr if prefix else None
    return None


class Scan(ast.NodeVisitor):
    def __init__(self, path, text, digest):
        self.path, self.lines, self.digest = path, text.splitlines(), digest
        self.scope, self.rows = [], []

    def site(self, node, kind, **extra):
        self.rows.append(
            dict(
                file=self.path,
                sha256=self.digest,
                line=node.lineno,
                end_line=node.end_lineno,
                column=node.col_offset,
                context=".".join(self.scope),
                kind=kind,
                source_line=self.lines[node.lineno - 1].strip(),
                **extra,
            )
        )

    def visit_ClassDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        self.scope.append(node.name)
        if any(arg.arg == "T" for arg in (*node.args.posonlyargs, *node.args.args)):
            self.site(node, "explicit_T_parameter", signature=ast.unparse(node.args))
        self.generic_visit(node)
        self.scope.pop()

    def visit_Attribute(self, node):
        name = dotted(node)
        temperatures = {
            "p.T": "configured_temperature",
            "phase.p.T": "configured_temperature",
            "self.p.T": "configured_temperature",
            "sim.T": "runtime_temperature",
            "phase.sim.T": "runtime_temperature",
            "p.sim.T": "runtime_temperature",
            "self.T": "self_temperature_owner_requires_context",
        }
        if name in temperatures:
            self.site(node, temperatures[name], expression=name, access=type(node.ctx).__name__)
        if name in ("p.dt", "phase.p.dt", "self.p.dt", "sim.dt", "self.dt", "p.grn_dt"):
            self.site(node, "step_parameter", expression=name, access=type(node.ctx).__name__)
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str) and any(s in node.value for s in ("sim.T", "p.T")):
            self.site(node, "literal_T_reference_not_proof_of_execution", literal=node.value)

    def visit_Call(self, node):
        name = dotted(node.func)
        if name and (name.endswith(".fire_events") or name == "self.time.append"):
            self.site(node, "event_or_storage_clock_call", expression=ast.unparse(node))
        if name in ("np.linspace", "np.arange"):
            self.site(node, "candidate_grid_not_necessarily_time", expression=ast.unparse(node))
        self.generic_visit(node)


def selected_findings(trees, texts, hashes):
    sim = "betse/science/sim.py"
    phase = "betse/science/phase/phasecls.py"
    params = "betse/science/parameters.py"
    handler = "betse/science/tissue/tishandler.py"
    channels = "betse/science/channels/channelsabc.py"
    toolbox = "betse/science/sim_toolbox.py"
    network = "betse/science/chemistry/networks.py"

    def evidence(file, fragment):
        locations = [i + 1 for i, line in enumerate(texts[file].splitlines()) if fragment in line]
        assert locations, (file, fragment)
        return dict(file=file, sha256=hashes[file], lines=locations, exact_fragment=fragment)

    def item(key, statement, scope, *sites, inference=None):
        return dict(
            id=key,
            statement=statement,
            scope=scope,
            evidence=[evidence(*site) for site in sites],
            evidence_kind="static_source",
            inference=inference,
            numerical_execution=False,
        )

    plot = next(
        n for n in ast.walk(trees[sim]) if isinstance(n, ast.FunctionDef) and n.name == "_plot_loop"
    )
    assignments = {
        ast.unparse(target): node.value
        for node in ast.walk(plot)
        if isinstance(node, ast.Assign)
        for target in node.targets
    }
    assert ast.unparse(assignments["phase_time_len"]) == "phase_time_step_count * phase.p.dt"
    assert ast.unparse(assignments["time_steps"]) == (
        "np.linspace(0, phase_time_len, phase_time_step_count)"
    )
    findings = [
        item(
            "configured_and_live_T",
            "Simulator initialization copies p.T into self.T. The enabled global setter "
            "writes sim.T from p.T and the native pulse sampled at its supplied t.",
            "Direct assignments; no claim that every native consumer follows live T.",
            (sim, "self.T = p.T"),
            (handler, "sim.T = self.multT*tb.pulse(t,self.tonT,self.toffT,self.trampT)*p.T + p.T"),
        ),
        item(
            "phase_step_binding",
            "INIT and SIM bind p.dt to their configured step sizes. Their integer step "
            "counts come from int(total/time_step). Gene-network execution also has "
            "a separate p.dt = p.grn_dt assignment.",
            "Named assignments within the pinned science scan; not every dynamic caller.",
            (phase, "self.p.dt = self.p.init_time_step"),
            (phase, "self.p.dt = self.p.sim_time_step"),
            (params, "self.init_tsteps = int(self.init_time_total / self.init_time_step)"),
            (params, "self. sim_tsteps = int(self. sim_time_total / self. sim_time_step)"),
            ("betse/science/chemistry/gene.py", "p.dt = p.grn_dt"),
        ),
        item(
            "phase_label_spacing",
            "The shared full/fast phase loop creates N labels with "
            "np.linspace(0, N*p.dt, N), including both endpoints.",
            "Simulator._plot_loop for N > 1 under standard NumPy linspace semantics.",
            (sim, "phase_time_len = phase_time_step_count * phase.p.dt"),
            (sim, "time_steps = np.linspace(0, phase_time_len, phase_time_step_count)"),
            inference=dict(
                kind="algebraic_inference_not_observed_simulation",
                condition="N > 1; fixed positive p.dt during the phase",
                label_at_index_j="j * N * p.dt / (N - 1)",
                successive_label_spacing="N * p.dt / (N - 1)",
                label_spacing_divided_by_update_step="N / (N - 1)",
                distinction="The label spacing differs from the p.dt used by updates.",
                N_zero_or_one="Excluded from this spacing inference.",
            ),
        ),
        item(
            "event_sampling_and_storage_order",
            "Both full and fast loops sample events with t from time_steps during SIM. "
            "The full loop updates concentrations and voltage before write2storage(t); "
            "both storage paths retain the t label.",
            "Source ordering in these two loops; no accepted physical-clock correction.",
            (sim, "for t in time_steps:"),
            (sim, "phase.dyna.fire_events(phase=phase, t=t)"),
            (sim, "self.update_all_concs(cells, p)"),
            (sim, "self.write2storage(t, cells, p)"),
            (sim, "self.time.append(t)"),
            (sim, "self.time.append(t * 1)"),
        ),
        item(
            "gate_and_state_update_clock",
            "HH and dynamic Morris-Lecar gate updates use p.dt*self.time_unit. "
            "The fast voltage update and ordinary material updates also use p.dt.",
            "Fixed empirical gate clocks; the unused time_unit argument does not "
            "override self.time_unit in these two methods.",
            (channels, "dt = p.dt*self.time_unit"),
            (channels, "dt = p.dt * self.time_unit"),
            (channels, "self._mTau*self.m + dt*self._mInf"),
            (channels, "dt * self.Phi * self._mInf"),
            (sim, "self.vm_ave += p.dt*"),
            (toolbox, "cX_cell = cX_cell + delta_cells * p.dt"),
        ),
        item(
            "runtime_membrane_configured_junction",
            "Membrane and organelle transport callers pass live self.T/sim.T, while "
            "the actual ionic and generic-molecule junction callers pass configured p.T.",
            "Direct call arguments; whole native uniform-T equivalence is unsupported.",
            (sim, "self.Dm_cells[i], IdM*p.tm, self.zs[i]*IdM, self.vm, self.T, p,"),
            (sim, "p.T,"),
            (toolbox, "sim.vm, sim.T, p, rho = rho"),
            (toolbox, "p.T,"),
            ("betse/science/organelles/endo_retic.py", "self.Ver, sim.T, p"),
            ("betse/science/organelles/mitochondria.py", "self.Vmit, sim.T, p"),
        ),
        item(
            "configured_T_coefficients_and_fast_caches",
            "Debye/conductivity initialization reads p.T. update_V recomputes cellular "
            "conductivity with p.T. Fast initialization combines a self.T Nernst term "
            "with p.T conductivities and stores E_Leak/G_Leak/G_gj for the fast loop.",
            "Identified assignments and reads, not an exhaustive cache invalidation proof.",
            (sim, "p.er * p.eo * p.kb * p.T"),
            (sim, " / (p.R * p.T) for (z, cc, D)"),
            (sim, "revE = ((p.R * self.T)"),
            (sim, "self.E_Leak = self.vm_GHK"),
            (sim, "self.G_Leak = ("),
            (sim, "self.G_gj = sum(sigma_gj)"),
        ),
        item(
            "generated_reaction_and_influencer_T",
            "Reaction and transporter equilibrium-expression generators use sim.T. "
            "Some voltage-dependent influencer generators use p.T.",
            "Generated source expressions; previous qualified reaction probes remain "
            "separate evidence for execution of their isolated generated equations.",
            (network, "delta_Go / (p.R * sim.T)"),
            (network, "p.R*p.T"),
        ),
        item(
            "legacy_calcium_K_live_T",
            "The separate legacy calcium-K opening expression reads sim.T directly.",
            "No direct caller was found in the earlier pinned science scan; "
            "dynamic reachability remains unproved.",
            ("betse/science/tissue/channels_o.py", "np.exp(-(1.64*p.F*sim.vm)/(p.R*sim.T))"),
        ),
        item(
            "conductivity_units_erratum_retained",
            "get_conductivity divides by thickness d. For the declared SI inputs this "
            "expression is conductance per area, S/m^2, despite its S/m docstring.",
            "Dimensional inference from the equation; frozen native evidence is unchanged.",
            (toolbox, "Simple function returns conductivity (S/m)"),
            (toolbox, "return (D * p.q *(z**2) * p.F * c) / (d * p.kb * p.T)"),
            inference=dict(
                kind="SI_dimensional_inference",
                assumed_units=dict(
                    D="m^2/s", c="mol/m^3", d="m", q="C", F="C/mol", kb="J/K", T="K"
                ),
                result="C^2/(J*s*m^2) = S/m^2",
            ),
        ),
    ]
    return findings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native", type=Path, default=OUTPUT_ROOT / "betse-v1.5.0")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    assert out.is_relative_to(OUTPUT_ROOT) and out != OUTPUT_ROOT
    out.mkdir(exist_ok=False)
    os.sched_setaffinity(0, {4})
    start = time.perf_counter()
    stage = "source-freeze"
    try:
        manifest = json.loads(MANIFEST.read_text())
        hashes = manifest["temperature_scan_files"] | manifest["source_files"]
        for name in manifest["temperature_scan_files"].keys() & manifest["source_files"].keys():
            assert manifest["temperature_scan_files"][name] == manifest["source_files"][name]
        (out / "native").mkdir()
        (out / "source_manifest.json").write_bytes(MANIFEST.read_bytes())
        shutil.copyfile(Path(__file__), out / "driver.py")
        texts, trees, rows, syntax_warnings = {}, {}, [], []
        for name, digest in sorted(hashes.items()):
            payload = (args.native / name).read_bytes()
            assert hashlib.sha256(payload).hexdigest() == digest, name
            target = out / "native" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            texts[name] = payload.decode()
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", SyntaxWarning)
                trees[name] = ast.parse(payload, filename=name)
            syntax_warnings.extend(
                dict(
                    file=name,
                    line=warning.lineno,
                    category=warning.category.__name__,
                    message=str(warning.message),
                    source_changed=False,
                )
                for warning in caught
            )
            if name in manifest["temperature_scan_files"]:
                scan = Scan(name, texts[name], digest)
                scan.visit(trees[name])
                rows.extend(scan.rows)
        write(
            out / "inputs.json",
            dict(
                native_revision=manifest["source_revision"],
                native_version=manifest["source_version"],
                source_manifest_sha256=sha(out / "source_manifest.json"),
                source_hashes=hashes,
                analysis_driver_sha256=sha(out / "driver.py"),
                scope="Pinned static attribute/call inventory and selected clock/T source review.",
                static_scan_limitations=[
                    "Self.T requires its recorded class/function context.",
                    "T in a string or function parameter does not establish dynamic reachability.",
                    "Candidate linspace/arange calls can describe space rather than time.",
                    "No exhaustive alias, dynamic-eval or cache-invalidation analysis is claimed.",
                ],
                native_or_Cells_numerics_executed=False,
                active_jobs_inspected=False,
            ),
        )
        stage = "static-inventory"
        write(out / "syntax_warnings.json", dict(warnings=syntax_warnings, source_changed=False))
        findings = selected_findings(trees, texts, hashes)
        write(
            out / "clock_sites.json",
            dict(
                kind="cells.native_temperature_clock_sites@1",
                sites=rows,
                counts_by_kind=dict(sorted(Counter(row["kind"] for row in rows).items())),
            ),
        )
        write(
            out / "findings.json",
            dict(
                kind="cells.native_temperature_clock_findings@1",
                findings=findings,
                required_future_choices=[
                    "Choose explicit native phase-label or accepted physical-time event sampling.",
                    "Declare which consumers use live T, configured T or frozen coefficients.",
                    "Declare cache provenance and any approved recomputation dependencies.",
                    "Keep native fixed-step gate updates distinct from continuous held RHS.",
                    "Retain original histories and energy/charge anchors across any future "
                    "interface.",
                ],
                thermal_interface_implemented=False,
                new_heat_law_assigned=False,
                accepted_temperature_transition=False,
                existing_context="Qualified held views retain distinct source labels and original "
                "accepted checkpoint clocks; this inventory changes neither contract.",
            ),
        )
        stage = "completion"
        for name, digest in hashes.items():
            assert sha(out / "native" / name) == digest, name
        usage = resource.getrusage(resource.RUSAGE_SELF)
        write(
            out / "runtime.json",
            dict(
                python=sys.version,
                executable=str(Path(sys.executable).resolve()),
                executable_sha256=sha(Path(sys.executable).resolve()),
                affinity=sorted(os.sched_getaffinity(0)),
                elapsed_seconds=time.perf_counter() - start,
                user_CPU_seconds=usage.ru_utime,
                system_CPU_seconds=usage.ru_stime,
                process_high_water_bytes=int(usage.ru_maxrss) * 1024,
                loaded_numerical_modules=[
                    name
                    for name in sys.modules
                    if name.split(".")[0] in ("numpy", "jax", "cells", "betse")
                ],
            ),
        )
        assert not json.loads((out / "runtime.json").read_text())["loaded_numerical_modules"]
        artifacts = {
            str(path.relative_to(out)): sha(path)
            for path in sorted(out.rglob("*"))
            if path.is_file()
        }
        write(
            out / "result.json",
            dict(
                status="source_inventory_complete",
                source_version=manifest["source_version"],
                source_revision=manifest["source_revision"],
                science_scan_files=len(manifest["temperature_scan_files"]),
                captured_source_files=len(hashes),
                static_sites=len(rows),
                selected_findings=len(findings),
                artifacts=artifacts,
                generated_UTC=datetime.now(timezone.utc).isoformat(),
                native_or_Cells_numerics_executed=False,
                numerical_qualification=False,
                active_jobs_inspected=False,
                compiled_JAX_retry=False,
                model_or_guard_changes=False,
                heat_law_assigned=False,
            ),
        )
        print(
            json.dumps(
                dict(
                    status="source_inventory_complete",
                    output=str(out),
                    science_files=len(manifest["temperature_scan_files"]),
                    static_sites=len(rows),
                    findings=len(findings),
                    result_sha256=sha(out / "result.json"),
                )
            )
        )
    except BaseException as error:
        write(
            out / "failure.json",
            dict(
                status="failed",
                stage=stage,
                exception_type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                preserved=True,
                active_jobs_inspected=False,
                automatic_retry=False,
            ),
        )
        raise


if __name__ == "__main__":
    main()
