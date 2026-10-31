# ruff: noqa: C408
"""Complete unique saved archive paths and event-specific outcome associations."""

import json

if __package__:
    from .betse_normal_ecm_molecule_events_execution_contract import read, require, sha
else:
    from betse_normal_ecm_molecule_events_execution_contract import read, require, sha
if __package__:
    from .betse_normal_ecm_molecule_events_execution_inventory import Inventory
else:
    from betse_normal_ecm_molecule_events_execution_inventory import Inventory
if __package__:
    from .betse_normal_ecm_molecule_events_execution_lifecycle import (
        cursor,
        json_exact,
        numeric_values,
        phase_parent,
    )
else:
    from betse_normal_ecm_molecule_events_execution_lifecycle import (
        cursor,
        json_exact,
        numeric_values,
        phase_parent,
    )
if __package__:
    from .betse_normal_ecm_molecule_events_execution_semantics import (
        ROLES,
        STAGES,
        entry_receipt,
        event_trace,
        native_event,
        native_owner,
        source_partial,
        state,
        transition,
    )
else:
    from betse_normal_ecm_molecule_events_execution_semantics import (
        ROLES,
        STAGES,
        entry_receipt,
        event_trace,
        native_event,
        native_owner,
        source_partial,
        state,
        transition,
    )


class Evidence(Inventory):
    def __init__(self, *args, **kwargs):
        self.expected = set()
        super().__init__(*args, **kwargs)
        members = {
            folder / name
            for folder in self.folders.values()
            for name in ("manifest.json", "data.json", "arrays.npz")
        }
        actual = {
            p
            for p in self.base.rglob("*")
            if p.is_file() and p.name in {"manifest.json", "data.json", "arrays.npz"}
        }
        require(actual == members, "Orphan typed archive members refused")

    def child_inventory(self):
        path = self.target / "subprocess-start.jsonl"
        if path.exists():
            require(
                path.is_file() and (not path.is_symlink()) and (path.stat().st_size <= 64 * 2**20),
                "Bounded regular actual child stream required",
            )
            starts = [json.loads(line) for line in path.read_text().splitlines()]
            require(
                all(
                    (
                        type(r["pid"]) is int
                        and r["pid"] > 0
                        and (type(r["start_ticks"]) is int)
                        and (r["start_ticks"] > 0)
                        for r in starts
                    )
                )
                and len({(r["pid"], r["start_ticks"]) for r in starts}) == len(starts),
                "Unique actual PID/start-time child identities required",
            )
        return super().child_inventory()

    def need(self, name):
        self.expected.add(name)
        return super().need(name)

    def source(self):
        a, case = (self.archives, self.case)
        initial = self.outcome(
            case + "-source-INIT-setup-outcome", stage=case + "-source-INIT-setup"
        )
        init_binding, init_parent = initial["returned"]
        phase_parent(a, init_binding, init_parent)
        require(cursor(init_parent) == 0, "Actual unadvanced original INIT setup required")
        a.exact(
            self.need(case + "-source-INIT-input"), initial["available"]["declaration"]["inputs"]
        )
        history = self.outcome(
            case + "-source-INIT-history-outcome", stage=case + "-source-INIT-history"
        )
        a.exact(history["available"]["parent"], init_parent)
        final, contexts = history["returned"]
        phase_parent(a, init_binding, final)
        require(
            final["status"] == "exhausted"
            and cursor(final) == len(contexts) == init_binding["calendar"]["step_count"],
            "Complete actual source INIT preparation return required",
        )
        warm = self.outcome(
            case + "-source-SIM-transition-outcome", stage=case + "-source-SIM-transition"
        )
        a.exact(warm["available"]["complete"]["binding"], init_binding)
        a.exact(warm["available"]["complete"]["parent"], final)
        self.need(case + "-source-SIM-input")
        actual = self.need(case + "-actual-source-SIM-entry")
        a.exact(self.need(case + "-source-SIM-input"), actual["binding"]["inputs"])
        a.exact(warm["returned"], actual["entry"])
        a.exact(actual["entry"]["source_init"], warm["available"]["complete"])
        return actual

    def initial(self, *, positive=False):
        a, case = (self.archives, self.case)
        actual = self.source()
        declared = self.need(case + "-event-declaration-before-bind")
        begin = self.outcome(case + "-event-begin-outcome", stage=case + "-event-begin")
        entry = self.need(case + "-event-entry")
        a.exact(entry["binding"]["source_binding"], actual["binding"])
        a.exact(entry["binding"]["source_entry"], actual["entry"])
        a.exact(entry["binding"]["raw"], declared)
        a.exact(begin["available"]["source_entry"], actual["entry"])
        a.exact(begin["returned"], entry["parent"])
        state(a, entry["binding"], entry["parent"])
        require(cursor(entry["parent"]) == 0, "Actual fresh separate event entry required")
        before = self.need(case + "-entry-controls-input")
        receipt = self.need(case + "-entry-controls-return")
        a.exact(receipt, entry["parent"]["entry_receipt"])
        a.exact(before, receipt["before"])
        if positive:
            self.input_at(case + "-entry-controls/native", before)
            self.input_at(case + "-entry-controls/reference", before)
            native = self.native_at(case + "-entry-controls/native/")
            require(
                native["mode"] == "entry_controls"
                and native["status"] == "source_completed"
                and (native["native_whole_initializer"] is False),
                "Actual local native entry-control return required",
            )
            a.exact(receipt["after"]["controls"], native["returned"]["controls"])
            for form in self.precision_pair(case + "-entry-controls/reference").values():
                json_exact(a, receipt["after"]["controls"], form["controls"])
        return (entry["binding"], entry["parent"])

    def input_at(self, folder, value):
        json_exact(self.archives, value, read(self.base / folder / "inputs.json"))

    def report(self, name, folder):
        a = self.archives
        saved = self.need(name + "-comparison-metrics")
        require(
            saved["physical_global_conservation_credit"] is False,
            "Source conditional metric scope differs",
        )
        report = read(self.base / folder / "comparison.json")
        self.reader.metric(report)
        require(
            set(saved["fields"]) == set(report["fields"]) == set(report["resolutions"]),
            "Complete typed and JSON metric fields required",
        )
        for key, row in saved["fields"].items():
            json_exact(a, row["metric"], report["fields"][key])
            json_exact(a, row["resolution"], report["resolutions"][key])

    def positive(self):
        a, case = (self.archives, self.case)
        declared, prior = self.initial(positive=True)
        clock = list(self.precision_pair(case + "-calls/clock").values())
        state(a, declared, prior, clock_forms=clock)
        for j in range(3):
            name = case + "-" + str(j)
            point = case + "-calls/call-" + str(j)
            outcome = self.outcome(
                case + "-advance-" + str(j) + "-outcome", stage=case + "-advance-" + str(j)
            )
            saved = self.need(case + "-return-" + str(j))
            current, detail = (saved["parent"], saved["detail"])
            a.exact(outcome["available"]["parent"], prior)
            a.exact(outcome["returned"], [current, detail])
            state(a, declared, current, clock_forms=clock)
            transition(a, declared, prior, current, detail)
            inputs = {
                mode: self.need(name + "-" + mode + "-input")
                for mode in ("events", "nak", "material", "calcium", "mechanics", "commit", "field")
            }
            a.exact(inputs["events"], detail["before_events"])
            for mode, value in inputs.items():
                self.input_at(point + "/" + mode, value)
            self.input_at(point + "/event-native", inputs["events"])
            native_event(
                a,
                inputs["events"],
                detail["events"],
                detail["reset_return"],
                self.native_at(point + "/event-native/"),
            )
            native_owner(a, current, detail, self.native_at(point + "/owner-native/"))
            a.exact(inputs["commit"], detail["before_commit"])
            a.exact(inputs["material"], detail["material_input"])
            all_input = self.need(name + "-all-before_dispatch")
            self.input_at(point + "/owner-native", all_input)
            require(
                all_input["mode"] == "dispatch"
                and all_input["source_phase"] == "SIM"
                and (all_input["legacy_run_sim"] is True),
                "Actual all-owner conditional input required",
            )
            for mode in ("events", "nak", "material", "calcium", "commit", "field"):
                self.report(
                    name + ("-event-errors" if mode == "events" else "-" + mode), point + "/" + mode
                )
            for form in self.precision_pair(point + "/mechanics").values():
                json_exact(a, current["mechanics"]["cache"], form["history"][0]["candidate"])
            handlers = detail["network"]["handlers"]
            for role in ROLES:
                if not current["network"]["network_cache"]["enabled"][role]:
                    continue
                a.exact(self.need(name + "-" + role + "-returned"), handlers[role])
                for mode in ("network", "channels"):
                    incoming = self.need(name + "-" + role + "-" + mode)
                    self.input_at(point + "/" + role + "-" + mode, incoming)
                    require(
                        incoming["source_phase"] == "SIM" and incoming["legacy_run_sim"] is True,
                        "Actual role input selector differs",
                    )
                    pair = self.precision_pair(point + "/" + role + "-" + mode)
                    if (self.base / point / (role + "-" + mode) / "comparison.json").is_file():
                        self.report(name + "-" + role + "-" + mode, point + "/" + role + "-" + mode)
                    else:
                        require(
                            mode == "channels"
                            and (not pair[1]["events"])
                            and (not pair[2]["events"]),
                            "Only declared empty channel forms may have no metrics",
                        )
                if role == "molecules" and point + "/molecules-transporters" in self.references:
                    self.input_at(
                        point + "/molecules-transporters",
                        self.need(name + "-molecules-transporters"),
                    )
                    self.need(name + "-transporter-books")
                    if (self.base / point / "molecules-transporters/comparison.json").is_file():
                        self.report(name + "-transporters", point + "/molecules-transporters")
            prior = current
        require(
            prior["status"] == "exhausted" and cursor(prior) == self.row["positive_SIM_calls"] == 3,
            "Full original primary SIM history required",
        )
        summary = self.need(case + "-summary")
        require(
            summary["accepted_SIM_calls"] == 3
            and summary["source_INIT_preparation_accuracy_credit"]
            == summary["duplicate_window_accuracy_credit"]
            == 0
            and (summary["duplicate_window_calls"] == 3)
            and (summary["native_events_local"] is True)
            and (
                summary["native_storage_called"]
                is summary["independently_carried_trajectory"]
                is summary["physical_global_conservation_credit"]
                is False
            ),
            "Original separate entry/duplicate/primary credit accounting differs",
        )
        return dict(
            primary_SIM_calls=3,
            entry_control_boundaries=1,
            entry_additional_SIM_credit=0,
            source_INIT_preparation_credit=0,
            duplicate_window_calls=3,
            duplicate_window_accuracy_credit=0,
            independent_trajectory_credit=0,
            duplicate_window_verification=(
                "Pinned assertion-enabled source comparison; "
                "no separately serialized window return"
            ),
        )

    def raw(self):
        a, case = (self.archives, self.case)
        declared, prior = self.initial()
        end = 0 if case == "zero_global_pulse_width" else 1
        captures = []
        for j in range(end + 1):
            incoming = self.need(case + "-raw-event-input-" + str(j))
            self.input_at(case + "-raw-native-" + str(j), incoming)
            a.exact(incoming["clock"], prior["clock"])
            native = self.native_at(case + "-raw-native-" + str(j) + "/")
            captures.append(native)
            outcome = self.outcome(
                case + "-raw-step-" + str(j) + "-outcome",
                failure=j == end,
                stage=case + "-raw-step-" + str(j),
            )
            a.exact(outcome["available"]["parent"], prior)
            if j < end:
                current, detail = outcome["returned"]
                state(a, declared, current)
                transition(a, declared, prior, current, detail)
                native_event(a, incoming, detail["events"], detail["reset_return"], native)
                prior = current
                continue
            partial = outcome["available"]["partial"]
            require(
                partial["automatic_retry"] is False and partial["stage"] == "source_call",
                "Actual admitted non-retrying source failure required",
            )
            a.exact(partial["caller_parent"], prior)
            a.exact(partial["original_source_entry"], declared["source_entry"])
            failed = partial["accepted"]
            state(a, declared, failed)
            require(
                failed["status"] == "failed" and cursor(failed) == end,
                "Actual prior accepted failure prefix differs",
            )
            a.exact(
                {k: v for k, v in failed.items() if k not in ("status", "identity")},
                {k: v for k, v in prior.items() if k not in ("status", "identity")},
            )
            source = source_partial(a, partial["source_partial"], prior)
            require(
                set(source)
                >= {
                    "stage",
                    "reached_stage",
                    "call_index",
                    "parent",
                    "available",
                    "inner_partial",
                    "root_cause",
                    "owner_buffers",
                    "available_event_stores",
                    "missing_event_stores",
                },
                "Complete source failure partial required",
            )
            require(
                source["call_index"] == j and (not source["missing_event_stores"]),
                "Original failed source epoch/stores differ",
            )
            a.exact(source["parent"], prior)
            a.exact(source["available_event_stores"], native["events"]["after"])
            require(
                not native["capture_errors"] and native["native_whole_initializer"] is False,
                "Complete actual local native failed-call evidence required",
            )
            chain = outcome["available"]["exception_chain"]
            require(chain[0]["type"] == "EventsRejected", "Original owned failure wrapper required")
            if case == "zero_global_pulse_width":
                require(
                    native["status"] == "source_refused"
                    and native["failure_capture"]
                    and (chain[-1]["type"] == native["failure"]["type"] == "ZeroDivisionError")
                    and (chain[-1]["message"] == native["failure"]["message"]),
                    "Named native zero-width source cause differs",
                )
                event_trace(a, native["events"], incoming["source_time_s"], complete=False)
                a.exact(source["inner_partial"], native["events"])
            else:
                require(
                    native["status"] == "source_completed"
                    and source["available"]["events"]["source_completed"] is True,
                    "Preserve actual event completion before coefficient/temperature refusal",
                )
                a.exact(source["available"]["events"], native["events"])
                a.exact(source["available"]["reset_return"], native["reset_return"])
                key = "T" if case == "late_negative_temperature" else "Dm_cells"
                require(
                    any((v < 0 for v in numeric_values(a, source["available_event_stores"][key]))),
                    "Actual negative source endpoint witness required",
                )
                require(
                    chain[-1]["type"] in {"ValueError", "NumericalError"},
                    "Unexpected failure cannot substitute for original downstream domain refusal",
                )
        saved = self.need(case + "-source-failure-prefix")
        a.exact(saved["partial"], partial)
        a.exact(saved["captured"], captures)
        return dict(
            original_source_refusal=True, accepted_prefix=end, native_reference_accuracy_credit=0
        )

    def controls(self):
        a, case = (self.archives, self.case)
        if self.row["category"] == "dependency":
            self.source()
            challenge = self.need(case + "-challenged-input-before-classification")
            outcome = self.outcome(
                case + "-dependency-outcome", failure=True, stage=case + "-dependency"
            )
            a.exact(challenge, outcome["available"]["challenge"])
            require(
                outcome["available"]["exception_chain"][0]["type"]
                in {"ValueError", "EventsRejected"},
                "Expected original dependency wrapper/cause required",
            )
            if case == "failed_resume":
                failure = self.outcome(
                    case + "-failure-outcome", failure=True, stage=case + "-failure"
                )
                a.exact(failure["available"]["partial"]["accepted"], challenge["parent"])
                require(
                    challenge["parent"]["status"] == "failed", "Actual failed-resume input required"
                )
            return dict(
                expected_dependency_refusal=True,
                accuracy_credit=0,
                stop_keyword_serialization=(
                    "Not separately serialized by frozen tests; "
                    "exact source branch and assertion-enabled pytest required"
                ),
            )
        if case in ("entry_before", "entry_after"):
            original = self.source()
            declaration = self.need(case + "-event-declaration-before-bind")
            require(
                declaration["source_binding_identity"] == original["binding"]["identity"]
                and declaration["source_entry_identity"] == original["entry"]["identity"],
                "Entry observer lost original source association",
            )
            before = self.need(case + "-entry-controls-input")
            outcome = self.outcome(
                case + "-event-begin-outcome", failure=True, stage=case + "-event-begin"
            )
            partial = outcome["available"]["partial"]
            a.exact(outcome["available"]["source_entry"], original["entry"])
            a.exact(partial["source_entry"], original["entry"])
            a.exact(partial["before_entry_controls"], before)
            require(
                partial["stage"] == "supplied_SIM_event_entry"
                and partial["native_initializer_called"] is False,
                "Actual separate entry observer failure required",
            )
            if case == "entry_after":
                receipt = self.need(case + "-entry-controls-return")
                entry_receipt(a, dict(source_entry=original["entry"], raw=declaration), receipt)
                a.exact(receipt["before"], before)
                a.exact(receipt["after"], partial["after_entry_controls"])
            else:
                require(
                    partial["after_entry_controls"] is None,
                    "Pre-entry observer failure cannot acquire source return",
                )
        else:
            declared, prior = self.initial()
            outcome = self.outcome(
                case + "-observer-outcome", failure=True, stage=case + "-observer"
            )
            partial = outcome["available"]["partial"]
            a.exact(self.need(case + "-observer-prefix"), partial)
            a.exact(partial["caller_parent"], prior)
            a.exact(outcome["available"]["parent"], prior)
            a.exact(partial["original_source_entry"], declared["source_entry"])
            require(partial["stage"] == "source_call", "Original admitted observer call required")
            reached = source_partial(a, partial["source_partial"], prior)
            require(
                partial["automatic_retry"] is False and partial["source_partial"] is not None,
                "Complete non-retrying observer source prefix required",
            )
            failed = partial["accepted"]
            state(a, declared, failed)
            require(
                failed["status"] == "failed" and cursor(failed) == int(case == "after_call"),
                "Actual observer acceptance boundary differs",
            )
            if case == "after_call":
                candidate = partial["source_partial"]["available"]["accepted"]
                a.exact(
                    {k: v for k, v in candidate.items() if k not in ("status", "identity")},
                    {k: v for k, v in failed.items() if k not in ("status", "identity")},
                )
            else:
                a.exact(
                    {k: v for k, v in failed.items() if k not in ("status", "identity")},
                    {k: v for k, v in prior.items() if k not in ("status", "identity")},
                )
            if case == "after_global":
                trace = partial["source_partial"]["inner_partial"]
                event_trace(
                    a,
                    trace,
                    list(numeric_values(a, prior["clock"]["source_times_s"]))[0],
                    complete=False,
                )
                require(
                    [r["stage"] for r in trace["stages"]] == [STAGES[0]],
                    "Original global observer boundary differs",
                )
                a.exact(trace["after"], reached["available_event_stores"])
        require(
            outcome["available"]["exception_chain"][-1]["type"] == "RuntimeError",
            "Original named observer cause differs",
        )
        return dict(original_observer_refusal=True, accuracy_credit=0)

    def raw_reference_inventory(self):
        files = {}
        for folder, pair in self.references.items():
            for level, value in pair.items():
                root = self.base / folder / ("raw-reference-" + str(level))
                require(
                    root.is_dir() and (not root.is_symlink()),
                    "Complete original raw reference retention required",
                )
                paths = sorted(root.iterdir())
                require(
                    paths
                    and all(
                        (
                            p.is_file() and (not p.is_symlink()) and (p.suffix == ".json")
                            for p in paths
                        )
                    ),
                    "Complete regular serialized raw reference files required",
                )
                for path in paths:
                    raw = read(path)
                    if "precision" in raw:
                        require(
                            raw["precision"] == (100 if level == 1 else 160),
                            "Retained Decimal precision differs",
                        )
                    files[str(path.relative_to(self.base))] = sha(path)
                if value["mode"] in {"entry_controls", "events"}:
                    name = (
                        "actual-SIM-control-entry-conditional.json"
                        if value["mode"] == "entry_controls"
                        else "actual-SIM-event-conditional.json"
                    )
                    require(
                        [p.name for p in paths] == [name],
                        "Exact serialized event conditional required",
                    )
                    raw = read(root / name)
                    require(
                        raw
                        == {
                            k: v
                            for k, v in value.items()
                            if k
                            not in {
                                "source_phase",
                                "legacy_run_sim",
                                "independently_carried_trajectory",
                                "runtime",
                                "production_imports_denied",
                                "loaded_production_modules",
                            }
                        },
                        "Serialized event conditional/result association differs",
                    )
        return files


def evidence(inputs, family, group, target, cpu, reader):
    value = Evidence(inputs, family, group, target, cpu, reader)
    counts = value.child_inventory()
    retained = value.raw_reference_inventory()
    category = value.row["category"]
    result = (
        value.positive()
        if category == "positive"
        else value.raw()
        if category == "raw"
        else value.controls()
    )
    require(
        set(value.folders) == value.expected,
        "Exact complete unique source archive set differs: "
        + str(sorted(set(value.folders) ^ value.expected)),
    )
    return dict(
        family=family,
        group=group,
        category=category,
        typed_archives=len(value.folders),
        archive_bindings=value.archives.records,
        raw_reference_files=retained,
        **counts,
        semantics=result,
        independent_product_digest_replay_claim=False,
        assertion_enabled_pinned_verifiers_required=True,
        entry_additional_SIM_credit=0,
        duplicate_window_accuracy_credit=0,
        source_INIT_preparation_credit=0,
        independent_trajectory_credit=0,
        no_inherited_accuracy_credit=True,
        physical_global_conservation_credit=False,
        biological_credit=False,
    )
