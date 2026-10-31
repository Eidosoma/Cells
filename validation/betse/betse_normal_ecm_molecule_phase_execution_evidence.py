# ruff: noqa: C408
"""Separate lifecycle54/run59 saved-evidence contracts; metadata only."""

import functools
import json
from pathlib import Path

if __package__:
    from .betse_normal_ecm_molecule_phase_execution_contract import read, require
else:
    from betse_normal_ecm_molecule_phase_execution_contract import read, require
if __package__:
    from .betse_normal_ecm_molecule_phase_execution_semantics import (
        ROLES,
        call_native,
        complete_init,
        completed_run,
        cursor,
        json_exact,
        named_negative,
        phase_binding,
        phase_parent,
        phase_state,
        preparation_count,
        run_parent,
        sim_parent,
    )
else:
    from betse_normal_ecm_molecule_phase_execution_semantics import (
        ROLES,
        call_native,
        complete_init,
        completed_run,
        cursor,
        json_exact,
        named_negative,
        phase_binding,
        phase_parent,
        phase_state,
        preparation_count,
        run_parent,
        sim_parent,
    )


class Evidence:
    def __init__(self, inputs, family, group, target, cpu, reader):
        self.inputs, self.family, self.group, self.target, self.cpu = (
            inputs,
            family,
            group,
            Path(target),
            cpu,
        )
        self.row = inputs["rosters"][family][group]
        self.case = self.row["case"]
        self.reader = reader
        self.base = self.target / "evidence" / ("normal-ecm-molecule-" + family.replace("_", "-"))
        require(
            self.base.is_dir() and (not any((p.is_symlink() for p in self.base.rglob("*")))),
            "Complete regular family evidence tree required",
        )
        self.archives = reader.Archives(
            inputs["packets"][family]["packet"], inputs["packets"][family]["capture_profile"]
        )
        self.folders = {
            str(p.parent.relative_to(self.base)): p.parent for p in self.base.rglob("manifest.json")
        }
        require(self.folders, "Typed family evidence required")
        for folder in self.folders.values():
            self.archives.validate(folder)
        self.natives = {}
        self.references = {}
        self.need = functools.lru_cache(maxsize=2)(self.need)

    def need(self, name):
        require(name in self.folders, "Missing complete saved state/outcome: " + name)
        return self.archives.load(self.folders[name])

    def outcome(self, name, *, failure=False, stage=None):
        result = self.need(name)
        self.reader.complete_outcome(
            result,
            status="unexpected_source_failure" if failure else "source_returned",
            stage=stage or result.get("stage", result.get("failure", {}).get("stage")),
        )
        return result

    def native_at(self, prefix):
        matches = [v for name, v in self.natives.items() if name.startswith(prefix)]
        require(len(matches) == 1, "Exactly one associated native conditional required: " + prefix)
        return matches[0]

    def precision_pair(self, prefix):
        matches = [value for name, value in self.references.items() if name == prefix]
        require(len(matches) == 1, "Exact paired reference folder required: " + prefix)
        return matches[0]

    def child_inventory(self):
        starts, finishes = ([], [])
        for key, target in (
            ("subprocess-start.jsonl", starts),
            ("subprocess-finish.jsonl", finishes),
        ):
            path = self.target / key
            if path.exists():
                target.extend((json.loads(row) for row in path.read_text().splitlines()))
        require(
            len({r["child_id"] for r in starts}) == len(starts)
            and len({r["child_id"] for r in finishes}) == len(finishes),
            "Unique actual child identities required",
        )
        require(
            {r["child_id"] for r in starts} == {r["child_id"] for r in finishes},
            "Every actual child must have a durable outcome",
        )
        byid = {r["child_id"]: r for r in finishes}
        children = {}
        module = "validation.betse.betse_normal_ecm_molecule_" + self.family
        for item in starts:
            done = byid[item["child_id"]]
            require(
                item["pid"] == done["pid"]
                and done["returncode"] == 0
                and (item["cpu_affinity"] == [self.cpu])
                and (type(item["start_ticks"]) is int),
                "Actual child return/CPU/process identity differs",
            )
            command = item["command"]
            require(
                isinstance(command, list)
                and "-m" in command
                and (
                    command[command.index("-m") + 1] in {module + "_reference", module + "_native"}
                ),
                "Unexpected/unbound conditional child",
            )
            require("--output" in command, "Actual child output association required")
            output = command[command.index("--output") + 1]
            require(output not in children, "Repeated actual child output")
            children[output] = item
        failures = list(self.base.rglob("*.failure.json")) + list(
            self.base.rglob("reference-refusal-*.json")
        )
        require(
            not failures, "Independent reference refused; preserve failure without accuracy credit"
        )
        form_paths = sorted(self.base.rglob("reference-1.json")) + sorted(
            self.base.rglob("reference-2.json")
        )
        expected = self.row.get("independent_forms", self.row.get("fresh_reference_forms", 0))
        require(len(form_paths) == expected, "Exact fresh conditional form count differs")
        incoming_by_folder = {}
        for path in form_paths:
            value = read(path)
            level = int(path.stem[-1])
            require(
                value["production_imports_denied"] is True
                and (not value["loaded_production_modules"])
                and (value["carried_reference_forms"] == 0)
                and (value["decimal_precision"] == (100 if level == 1 else 160)),
                "Fresh guarded reference form required",
            )
            self.reader.runtime(
                value["runtime"], self.inputs, self.family, self.cpu, reference=True
            )
            incoming = self.reader.conditional_child(
                children.pop(str(path), None),
                self.inputs,
                self.family,
                path,
                "reference",
                refinement=level,
            )
            require(
                value.get("mode") == incoming.get("mode")
                and value["source_phase"] == incoming.get("source_phase", "INIT"),
                "Actual reference phase/mode differs",
            )
            name = str(path.parent.relative_to(self.base))
            self.references.setdefault(name, {})[level] = value
            incoming_by_folder[name] = incoming
        for name, pair in self.references.items():
            require(set(pair) == {1, 2}, "Complete Decimal100/160 pair required")
            mode = incoming_by_folder[name]["mode"]
            report = self.base / name / "comparison.json"
            if report.exists():
                self.reader.metric(read(report))
            else:
                empty = (
                    mode == "channels"
                    and (not pair[1]["events"])
                    and (not pair[2]["events"])
                    or (
                        mode == "transporters"
                        and (not pair[1]["frames"])
                        and (not pair[2]["frames"])
                    )
                )
                require(
                    mode in {"clock", "mechanics"} or empty,
                    "Independent numeric pair lost its original comparison",
                )
        reports = list(self.base.rglob("comparison.json"))
        require(
            all((str(p.parent.relative_to(self.base)) in self.references for p in reports)),
            "Comparison without its independent pair",
        )
        for output, item in list(children.items()):
            folder = Path(output)
            require(
                folder.is_relative_to(self.base), "Actual native output outside family evidence"
            )
            name = str(folder.relative_to(self.base))
            value = self.need(name)
            incoming = self.reader.conditional_child(
                item, self.inputs, self.family, folder, "native"
            )
            require(
                value["mode"] == incoming["mode"]
                and value["production_imports_denied"] is True
                and (not value["loaded_production_modules"]),
                "Actual native conditional mode/provenance differs",
            )
            self.reader.runtime(value["runtime"], self.inputs, self.family, self.cpu, native=True)
            require(not value["capture_errors"], "Native typed outcome capture incomplete")
            raw = self.need(name + "-raw-before-runtime")
            self.archives.exact(
                {
                    k: v
                    for k, v in value.items()
                    if k
                    not in {"runtime", "production_imports_denied", "loaded_production_modules"}
                },
                raw,
            )
            self.natives[name] = value
        require(
            len(self.natives) == self.row["native_captures"], "Exact native capture count differs"
        )
        return dict(
            independent_forms=len(form_paths),
            native_captures=len(self.natives),
            comparison_reports=len(reports),
        )

    def preparations(self):
        if self.family != "run_lifecycle":
            return
        requests = {
            name[:-8]: self.need(name) for name in self.folders if name.endswith("-request")
        }
        require(
            len(requests)
            == preparation_count(
                self.case, self.row["category"], self.row.get("positive_INIT_calls", 3)
            ),
            "Complete expected evolving preparation request set required",
        )
        for name, request in requests.items():
            result = self.outcome(name + "-outcome", stage=name)
            self.archives.exact(result["available"], request)
            returned = result["returned"]
            require(returned is not None, "Complete preparation return required")
            if "component" in request and "completed" in request:
                complete_init(self.archives, request["completed"])
                sim_parent(self.archives, request["component"], returned)
                self.archives.exact(returned["source_init"], request["completed"])
            if "parent" in request and "stop" in request:
                parent = returned[0]
                require(
                    type(request["stop"]) is int
                    and cursor(request["parent"]) <= request["stop"] == cursor(parent),
                    "Actual window stop/cursor differs",
                )
                require(
                    len(returned[1]) == request["stop"] - cursor(request["parent"]),
                    "Window context prefix incomplete",
                )
            if "parent" in request and "binding" in request:
                if "entry" in request["parent"]:
                    run_parent(self.archives, request["binding"], request["parent"])
                    run_parent(self.archives, request["binding"], returned[0])
                else:
                    phase_parent(self.archives, request["binding"], request["parent"])
                    phase_parent(self.archives, request["binding"], returned[0])

    def cold(self, phase_binding, entry):
        case = self.case
        name = case + "-cold-actual-return" if self.family == "lifecycle" else case + "-cold"
        cold = self.need(name)
        native = self.native_at(case + "-cold/" if self.family == "lifecycle" else case + "-entry/")
        require(native["status"] == "source_completed", "Actual native cold owner return required")
        self.archives.exact(cold["material"], native["returned"]["material"])
        require(
            set(native["returned"]["shared_absent"]) == {"rho_pump", "rho_channel"},
            "Cold late-attribute absence differs",
        )
        for role in ROLES:
            saved = cold["network_cache"]["handlers"][role]
            self.archives.exact(
                None if saved is None else saved["cache"], native["returned"]["handlers"][role]
            )
        require(
            cursor(entry) == 0 and phase_binding["calendar"]["phase"] == "INIT",
            "Actual fresh original INIT entry required",
        )

    def positive(self):
        case = self.case
        run = self.family == "run_lifecycle"
        a = self.archives
        initial = self.need(
            case + "-INIT-begin" if run else case + "-INIT-entry-before-comparisons"
        )
        binding = initial["binding"]
        entry = initial["parent"]
        phase = phase_binding(binding, entry.get("active"))
        self.cold(phase, phase_state(entry))
        init_final = self.phase_calls("INIT", binding, entry)
        if run:
            completed = self.need(case + "-complete-INIT-run")
            completed_run(a, completed)
            a.exact(completed["run"], init_final)
            leaf_completed = completed["complete_init"]
            sim_record = self.need(case + "-SIM-begin")
            sim_binding = sim_record["binding"]
            sim = sim_record["parent"]
            a.exact(sim["entry_receipt"]["previous_phase"], completed)
            outcome = self.outcome(
                case + "-headless-handoff-outcome", stage=case + "-headless-handoff"
            )
            a.exact(outcome["returned"], [sim_binding, sim])
            require(
                outcome["available"]["init_run"]["identity"] == init_final["identity"],
                "Handoff caller INIT run differs",
            )
            warm = self.need(case + "-transition-dual_owners_reinitialized")
        else:
            leaf_completed = self.need(case + "-complete-INIT")
            complete_init(a, leaf_completed)
            a.exact(leaf_completed["parent"], init_final)
            sim = self.need(case + "-SIM-entry-before-comparisons")
            raw = self.need(case + "-SIM-declaration")
            sim_binding = dict(
                identity=sim["binding_identity"],
                expected_init_identity=leaf_completed["binding"]["identity"],
                inputs=raw,
            )
            warm = self.need(case + "-warm-dual_owners_reinitialized")
        actual_sim = sim["active"] if run else sim
        a.exact(actual_sim["source_init"], leaf_completed)
        native = self.native_at(case + "-transition/")
        require(
            native["status"] == "source_completed",
            "Actual retained native warm owner return required",
        )
        a.exact(native["returned"]["material"], warm["available"]["material"])
        for role in ROLES:
            saved = warm["available"]["owners"]["handlers"][role]
            a.exact(None if saved is None else saved["cache"], native["returned"]["handlers"][role])
            if saved is None:
                continue
            identity = warm["owner_identity"][role]
            require(
                identity["owner_retained"]
                and identity["core_retained"]
                and all(identity["molecule_objects_retained"].values())
                and all(identity["channel_objects_rebuilt"].values())
                and all(identity["transporter_objects_rebuilt"].values())
                and all((v is None for v in identity["transporter_fluxes_after"].values())),
                "Actual retained/rebuilt warm object ownership differs",
            )
        final = self.phase_calls("SIM", sim_binding, sim)
        if run:
            a.exact(final["entry_receipt"]["previous_phase"], completed)
            summary = self.need(case + "-summary")
            require(
                summary["INIT_calls"] == self.row["positive_INIT_calls"]
                and summary["SIM_calls"] == 3
                and (summary["duplicate_window_baseline_new_credit"] == 0)
                and (summary["native_storage_called"] is False),
                "Separate actual phase summary differs",
            )
        return dict(
            INIT_calls=cursor(init_final),
            SIM_calls=cursor(final),
            duplicate_window_accuracy_credit=0,
            independently_carried_trajectory=False,
        )

    def phase_calls(self, kind, binding, entry):
        run = self.family == "run_lifecycle"
        a = self.archives
        case = self.case
        name = case + "-" + kind
        phase = phase_binding(binding, entry.get("active") if run else entry)
        pair = self.precision_pair(name + "/clock")
        clock = [pair[1], pair[2]]
        original = entry
        count = self.row["positive_" + kind + "_calls"]
        previous = entry
        validate = run_parent if run else phase_parent if kind == "INIT" else sim_parent
        validate(a, binding, entry, clock_forms=clock)
        for j in range(count):
            if run:
                saved = self.need(name + "-return-" + str(j))
                outcome = self.outcome(
                    name + "-advance-" + str(j) + "-outcome", stage=name + "-advance-" + str(j)
                )
                a.exact(outcome["available"]["parent"], previous)
                a.exact(outcome["returned"], [saved["parent"], saved["detail"]])
            else:
                saved = self.need(name + "-" + str(j) + "-accepted-before-comparison")
            current = saved["parent"] if run or kind == "INIT" else saved["wrapper"]
            require(current is not None, "Complete actual phase wrapper return required")
            validate(a, binding, current, clock_forms=clock)
            require(cursor(current) == j + 1, "Accepted source call prefix differs")
            active = phase_state(current)
            detail = saved["detail"]
            if not run:
                a.exact(saved["parent"], active)
            prior_leaf = phase_state(previous)
            a.exact(active["history"][:-1], prior_leaf["history"])
            require(
                active["history"][-1]["incoming_identity"] == prior_leaf["identity"],
                "Accepted phase call lost its actual caller identity",
            )
            a.exact(active["history"][-1], detail["receipt"])
            a.exact(active["field"], detail["field"])
            a.exact(active["mechanics"], detail["mechanics_trial"]["candidate"])
            a.exact(
                active["observations"][: len(prior_leaf["observations"])],
                prior_leaf["observations"],
            )
            if active["history"][-1]["sample_eligible"]:
                observation = active["observations"][-1]
                for key in ("network", "field", "mechanics"):
                    a.exact(observation[key], active[key])
            if run:
                a.exact(current["entry"], original["entry"])
                a.exact(current["entry_receipt"], original["entry_receipt"])
                a.exact(current["history"][:-1], previous["history"])
                a.exact(
                    current["observations"][: len(previous["observations"])],
                    previous["observations"],
                )
                if current["history"][-1]["sample_eligible"]:
                    a.exact(current["observations"][-1]["state"], current["active"])
            native = self.native_at(name + "/call-" + str(j) + "/")
            call_native(a, phase, active, detail, native)
            mechanics = self.precision_pair(name + "/call-" + str(j) + "/mechanics")
            for form in mechanics.values():
                json_exact(
                    a,
                    detail["mechanics_trial"]["candidate"]["cache"],
                    form["history"][0]["candidate"],
                )
            previous = current
        require(
            (previous["status"] if run or kind == "INIT" else previous["active"]["status"])
            == "exhausted",
            "Positive original phase did not complete",
        )
        require(
            cursor(previous) == count == phase["calendar"]["step_count"] == phase["call_limit"],
            "Positive call count differs from original full calendar",
        )
        if run:
            requests = sorted(
                (
                    name
                    for name in self.folders
                    if name.startswith(case + "-" + kind + "-duplicate-window-")
                    and name.endswith("-request")
                )
            )
            duplicate = original
            for request in requests:
                value = self.need(request)
                a.exact(value["parent"], duplicate)
                returned = self.outcome(request[:-8] + "-outcome")["returned"]
                duplicate = returned[0]
            a.exact(duplicate, previous)
        return previous

    def raw(self):
        case = self.case
        run = self.family == "run_lifecycle"
        a = self.archives
        require(len(self.natives) == 1, "Raw source refusal needs one exact native conditional")
        native = next(iter(self.natives.values()))
        if case.startswith("warm_"):
            outcome = self.outcome(
                case + "-warm-outcome"
                if run
                else case + "-warm-call-outcome-before-classification",
                failure=True,
            )
            partial = outcome["available"]["partial"]
            chain = outcome["available"]["exception_chain"]
            require(
                native["status"] == "source_refused"
                and native["failure"]["type"] == chain[-1]["type"] == "KeyError"
                and (native["failure"]["message"] == chain[-1]["message"] == "'max rate'"),
                "Exact native/owned missing-max-rate cause required",
            )
            component = partial["component_partial"] if run else partial
            a.exact(
                component["inner_partial"]["available"]["partial_wires"],
                native["partial_buffers"]["partial_wires"],
            )
            require(component["automatic_retry"] is False, "Warm refusal cannot retry")
            if run:
                require(partial["automatic_retry"] is False, "Outer warm refusal cannot retry")
                run_parent(a, outcome["available"]["binding"], partial["accepted_INIT_run"])
                a.exact(partial["accepted_INIT_run"], outcome["available"]["parent"])
        elif case.startswith("cold_"):
            outcome = self.outcome(case + "-initialize-outcome-before-classification", failure=True)
            partial = outcome["available"]["partial"]
            chain = outcome["available"]["exception_chain"]
            require(
                native["status"] == "source_refused"
                and native["failure"]["type"] == chain[-1]["type"] == "KeyError"
                and (native["failure"]["message"] == chain[-1]["message"] == "'max rate'"),
                "Cold original missing-max-rate cause required",
            )
            for key in ("material", "partial_wires"):
                a.exact(partial["owner_buffers"][key], native["partial_buffers"][key])
        else:
            outcome = self.outcome(
                case + "-advance-outcome"
                if run
                else case + "-call-0-outcome-before-classification",
                failure=True,
            )
            partial = outcome["available"]["partial"]
            component = partial["component_partial"] if run else partial
            initial = self.need(case + "-INIT-begin") if run else None
            raw = (
                initial["binding"]["composition"]["inputs_raw"]
                if run
                else self.need(case + "-raw-input")
            )
            named_negative(a, case, outcome, native, component, raw, run=run)
            if run:
                failed = partial["accepted"]
                run_parent(a, initial["binding"], failed)
                require(
                    failed["status"] == "failed" and cursor(failed) == 0,
                    "Raw outer accepted prefix differs",
                )
                a.exact(failed["active"], outcome["available"]["parent"]["active"])
        return dict(expected_original_source_refusal=True, accuracy_credit=0)

    def controls(self):
        case = self.case
        kind = self.row["category"]
        run = self.family == "run_lifecycle"
        a = self.archives
        if run and kind == "dependency":
            challenged = self.need(case + "-challenged-run-input")
            outcome = self.outcome(case + "-dependency-outcome", failure=True)
            for key in ("binding", "parent", "raw", "challenge"):
                a.exact(challenged[key], outcome["available"][key])
            if case in ("boolean_stop", "stop_before_cursor", "stop_past_cap"):
                stop = challenged["challenge"]["stop"]
                require(
                    type(stop) is bool and stop is True
                    if case == "boolean_stop"
                    else type(stop) is int and stop == (0 if case == "stop_before_cursor" else 4),
                    "Exact challenged stop keyword missing",
                )
        elif run and kind == "observer":
            outcome = self.outcome(case + "-observer-outcome", failure=True)
            partial = outcome["available"]["partial"]
            failed = partial["accepted"]
            prior = outcome["available"]["parent"]
            initial = self.need(case + "-INIT-begin")
            run_parent(a, initial["binding"], prior)
            run_parent(a, initial["binding"], failed)
            require(
                partial["automatic_retry"] is False and partial["native_pickle_called"] is False,
                "Observer refusal cannot retry or acquire persistence credit",
            )
            a.exact(partial["caller_parent"], prior)
            a.exact(self.need(case + "-observer-prefix")["partial"], partial)
            expected = 2 if case == "headless_observation" else 1 if case == "accepted_call" else 0
            require(
                failed["status"] == "failed" and cursor(failed) == expected,
                "Outer observer acceptance boundary differs",
            )
            require(
                outcome["available"]["exception_chain"][-1]["type"] == "RuntimeError",
                "Named observer cause differs",
            )
            if case == "phase_after_call":
                leaf = partial["component_partial"]["available"]["accepted"]
                require(
                    cursor(leaf) == cursor(prior) + 1 and cursor(failed) == cursor(prior),
                    "Leaf acceptance must remain nested in outer refusal",
                )
        elif run and kind == "prefix":
            outcome = self.outcome(case + "-completion-outcome", failure=True)
            parent = outcome["available"]["parent"]
            initial = self.need(case + "-INIT-begin")
            run_parent(a, initial["binding"], parent)
            require(
                parent["status"]
                == {"paused_INIT": "paused", "capped_INIT": "capped", "failed_INIT": "failed"}[
                    case
                ],
                "Incomplete INIT prefix status differs",
            )
            a.exact(outcome["available"]["partial"]["accepted"], parent)
            a.exact(self.need(case + "-handoff-refused"), outcome["available"]["partial"])
        elif not run and kind == "dependency":
            cached = case in (
                "changed_transporter_cache",
                "changed_gate_epoch",
                "changed_phase_receipt",
            )
            outcome = self.outcome(
                case
                + (
                    "-verify-outcome-before-classification"
                    if cached
                    else "-transition-outcome-before-classification"
                ),
                failure=True,
            )
            if cached:
                a.exact(
                    self.need(case + "-cache-refusal")["parent"], outcome["available"]["parent"]
                )
            else:
                a.exact(
                    self.need(case + "-dependency-refusal")["inputs"], outcome["available"]["raw"]
                )
        elif not run and kind == "observer":
            ending = (
                "warm"
                if case == "warm_before_reinitialize"
                else "sample"
                if case == "headless_sample"
                else "advance"
            )
            outcome = self.outcome(
                case + "-" + ending + "-outcome-before-classification", failure=True
            )
            saved = self.need(case + "-observer-partial")
            a.exact(saved["partial"], outcome["available"]["partial"])
            if case == "after_call":
                require(
                    cursor(saved["reached"][case]) == 1, "Actual accepted leaf candidate missing"
                )
            if case == "headless_sample":
                require(
                    saved["partial"]["display_completed"]
                    is saved["partial"]["native_storage_called"]
                    is False,
                    "Native sample refusal lost scope",
                )
        else:
            ending = "admit" if case == "failed_INIT" else "prepare"
            outcome = self.outcome(
                case + "-" + ending + "-outcome-before-classification", failure=True
            )
            if case == "failed_INIT":
                require(
                    "failure" in outcome["available"]["failed"],
                    "Failed prefix cannot be relabeled complete",
                )
            else:
                parent = outcome["available"]["parent"]
                require(
                    parent["status"] == ("paused" if case == "paused_INIT" else "capped"),
                    "Incomplete INIT state differs",
                )
        return dict(expected_control_refusal=True, accuracy_credit=0)


def evidence(inputs, family, group, target, cpu, reader):
    state = Evidence(inputs, family, group, target, cpu, reader)
    counts = state.child_inventory()
    state.preparations()
    kind = state.row["category"]
    if kind == "positive":
        result = state.positive()
    elif kind.startswith("raw"):
        result = state.raw()
    else:
        result = state.controls()
    return dict(
        family=family,
        group=group,
        category=kind,
        typed_archives=len(state.folders),
        **counts,
        semantics=result,
        no_inherited_accuracy_credit=True,
        physical_global_conservation_credit=False,
        biological_credit=False,
    )
