# ruff: noqa: C408
import functools
import json
from pathlib import Path

if __package__:
    from .betse_normal_ecm_molecule_events_execution_contract import read, require
else:
    from betse_normal_ecm_molecule_events_execution_contract import read, require


class Inventory:
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
                    mode in {"clock", "mechanics", "entry_controls"} or empty,
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
