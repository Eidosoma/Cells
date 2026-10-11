"""Device-wide DCGM counters; separate from GPU busy time and kernel traces.

The isolated sampler alone needs profiling privileges. It exits when its parent
closes stdin, with an independent timeout as a backstop. Simulation workers keep
their ordinary user identity. Raw status codes and counter timestamps are retained.
"""

import argparse
import hashlib
import json
import math
import os
import select
import subprocess
import sys
import threading
import time
from pathlib import Path

FIELDS = {
    1001: "graphics_engine_active",
    1002: "sm_active",
    1003: "sm_occupancy",
    1005: "dram_active",
}
PERIOD = 1.0
MAX_GAP = 1.5
MIN_COVERAGE = 0.98


def need(condition, message):
    if not condition:
        raise ValueError(message)


def tool_identity(root):
    """Bind the extracted runtime and vendor package receipt, without installing a service."""
    paths = [root / "installation.json"]
    paths += sorted((root / "extracted").rglob("*.py"))
    paths += sorted((root / "extracted").rglob("*.so.4.7.0"))
    need(len(paths) > 3 and all(p.is_file() for p in paths), "DCGM runtime is incomplete")
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def valid_field(row):
    value = row.get("value")
    return (
        row.get("status") == 0
        and row.get("field_type") == ord("d")
        and isinstance(row.get("timestamp_usec"), int)
        and row["timestamp_usec"] > 0
        and isinstance(value, (float, int))
        and math.isfinite(value)
        and 0 <= value <= 1
    )


def summarize(rows, began, ended):
    """Weight interval-ending counters; omit gaps, blanks and invalid samples.

    DCGM ratios average the preceding counter interval. Intervals crossing the
    requested boundaries are clipped, assuming a constant rate within that one
    second. Coverage is reported independently; missing values are never zeroes.
    """
    need(math.isfinite(began) and math.isfinite(ended) and ended > began, "Invalid interval")
    output = {}
    for field, name in FIELDS.items():
        previous, total, covered, count, invalid, duplicates = None, 0.0, 0.0, 0, 0, 0
        maximum = None
        for sample in rows:
            if sample.get("type") != "sample":
                continue
            row = sample.get("fields", {}).get(str(field))
            if row is None:
                continue
            timestamp = row.get("timestamp_usec", 0) / 1e6
            if timestamp <= 0:
                invalid += 1
                previous = None
                continue
            if previous is not None and timestamp == previous:
                duplicates += 1
                continue
            need(previous is None or timestamp > previous, "Counter timestamp moved backwards")
            valid = valid_field(row)
            invalid += not valid
            if previous is not None and valid and 0 < timestamp - previous <= MAX_GAP:
                duration = max(0.0, min(ended, timestamp) - max(began, previous))
                if duration:
                    total += row["value"] * duration
                    covered += duration
                    count += 1
                    maximum = max(maximum or 0, row["value"])
            previous = timestamp if timestamp > 0 else None
        coverage = covered / (ended - began)
        output[name] = {
            "field_id": field,
            "mean_pct_over_covered_time": 100 * total / covered if covered else None,
            "max_interval_pct": 100 * maximum if maximum is not None else None,
            "coverage_fraction": coverage,
            "covered_seconds": covered,
            "valid_intervals": count,
            "invalid_samples": invalid,
            "duplicate_samples": duplicates,
            "coverage_pass": coverage >= MIN_COVERAGE,
        }
    return {
        "seconds": ended - began,
        "fields": output,
        "coverage_pass": all(value["coverage_pass"] for value in output.values()),
        "scope": "Device-wide counter averages including idle time; not per-kernel metrics",
        "weighting": "Interval-ending timestamps, boundary clipping, gaps over 1.5 s excluded",
        "missing_values_are_zero": False,
        "minimum_coverage_fraction": MIN_COVERAGE,
    }


class CounterMonitor:
    def __init__(self, root, settings):
        self.root, self.settings = root, settings
        self.ready = threading.Event()
        self.rows = []
        self.valid_samples = 0
        self.error = None
        self.process = None
        self.thread = None
        self.finished = False

    def start(self):
        settings = self.settings
        need(
            tool_identity(Path(settings["tool_root"])) == settings["tool_sha256"],
            "DCGM runtime changed",
        )
        driver = self.root / "source/gpu_counters.py"
        need(
            hashlib.sha256(driver.read_bytes()).hexdigest() == settings["driver_sha256"],
            "Counter driver changed",
        )
        command = [
            "sudo",
            "-n",
            "/usr/bin/timeout",
            "--signal=TERM",
            "--kill-after=5s",
            str(settings["timeout_seconds"]),
            "/usr/bin/python3",
            "-I",
            "-B",
            str(driver),
            "--dcgm-root",
            settings["tool_root"],
            "--uuid",
            settings["uuid"],
            "--log-file",
            str(self.root / "dcgm.log"),
        ]
        with (self.root / "gpu-counters.stderr.log").open("x") as stderr:
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr,
                text=True,
                bufsize=1,
                cwd=self.root,
            )
        self.thread = threading.Thread(target=self.record, daemon=True)
        self.thread.start()
        need(self.ready.wait(20), "No valid GPU counter sample within 20 seconds")
        need(self.error is None, "Counter startup failed: " + str(self.error))
        need(
            self.valid_samples > 0 and self.process.poll() is None,
            "Counter sampler must be live with valid measurements before starting work",
        )

    def record(self):
        try:
            with (self.root / "gpu-counters.jsonl").open("x") as stream:
                for line in self.process.stdout:
                    stream.write(line)
                    stream.flush()
                    row = json.loads(line)
                    self.rows.append(row)
                    if row.get("type") == "sample" and all(
                        valid_field(row.get("fields", {}).get(str(field), {})) for field in FIELDS
                    ):
                        self.valid_samples += 1
                        self.ready.set()
            need(
                self.rows and self.rows[-1].get("type") == "finished",
                "GPU counter sampler exited without a completion record",
            )
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.ready.set()

    def finish(self):
        if self.finished or self.process is None:
            return
        self.finished = True
        # EOF also closes the sampler automatically if the controller disappears.
        self.process.stdin.close()
        code = self.process.wait(timeout=20)
        self.thread.join(timeout=5)
        need(
            code == 0 and not self.thread.is_alive() and self.error is None,
            f"GPU counter sampler failed (exit {code}): {self.error}",
        )


def compatible_groups(groups, fields):
    """Each hardware counter domain may select only one minor group (no multiplexing)."""
    choices = {()}
    for field in fields:
        options = [(g["major"], g["minor"]) for g in groups if field in g["fields"]]
        updated = set()
        for choice in choices:
            for major, minor in options:
                mapping = dict(choice)
                if major not in mapping or mapping[major] == minor:
                    mapping[major] = minor
                    updated.add(tuple(sorted(mapping.items())))
        choices = updated
    need(choices, "Requested GPU counters would be unsupported or multiplexed")
    return list(min(choices))


def sample(tool_root, uuid, log_file):
    root = tool_root / "extracted"
    sys.path.insert(0, str(root / "usr/share/datacenter-gpu-manager-4/bindings/python3"))
    os.environ["__DCGM_DBG_FILE"] = str(log_file)
    os.environ["__DCGM_DBG_LVL"] = "INFO"
    import dcgm_agent as agent
    import dcgm_fields as fields
    import dcgm_structs as structs

    def emit(row):
        print(json.dumps(row, allow_nan=False), flush=True)

    structs._dcgmInit(str(root / "usr/lib/x86_64-linux-gnu"))
    agent.dcgmInit()
    handle = None
    try:
        handle = agent.dcgmStartEmbedded(structs.DCGM_OPERATION_MODE_AUTO)
        devices = {
            agent.dcgmGetDeviceAttributes(handle, gpu).identifiers.uuid: gpu
            for gpu in agent.dcgmGetAllSupportedDevices(handle)
        }
        need(uuid in devices, "Requested GPU UUID is unavailable to DCGM")
        gpu = devices[uuid]
        catalog = agent.dcgmProfGetSupportedMetricGroups(handle, gpu)
        groups = [
            {"major": g.majorId, "minor": g.minorId, "fields": list(g.fieldIds[: g.numFieldIds])}
            for g in catalog.metricGroups[: catalog.numMetricGroups]
        ]
        selection = compatible_groups(groups, FIELDS)
        emit(
            {
                "type": "started",
                "time": time.time(),
                "uuid": uuid,
                "gpu_id": gpu,
                "pid": os.getpid(),
                "fields": FIELDS,
                "period_seconds": PERIOD,
                "groups": groups,
                "compatible_selection": selection,
                "multiplexing": False,
            }
        )
        group = agent.dcgmGroupCreate(handle, structs.DCGM_GROUP_EMPTY, "cells-sm-observer")
        agent.dcgmGroupAddDevice(handle, group, gpu)
        fieldgroup = agent.dcgmFieldGroupCreate(handle, list(FIELDS), "cells-sm-observer")
        agent.dcgmWatchFields(handle, group, fieldgroup, int(PERIOD * 1e6), 30.0, 30)
        previous = None

        def record():
            nonlocal previous
            values = agent.dcgmEntityGetLatestValues(handle, fields.DCGM_FE_GPU, gpu, list(FIELDS))
            stamp = tuple((v.fieldId, v.ts, v.status) for v in values)
            if stamp == previous:
                return
            previous = stamp
            emit(
                {
                    "type": "sample",
                    "time": time.time(),
                    "uuid": uuid,
                    "fields": {
                        str(v.fieldId): {
                            "timestamp_usec": v.ts,
                            "status": v.status,
                            "field_type": v.fieldType,
                            "value": v.value.dbl if math.isfinite(v.value.dbl) else None,
                        }
                        for v in values
                    },
                }
            )

        while not select.select([sys.stdin], [], [], 0.5)[0]:
            record()
        # Capture the interval containing the campaign's end before unwatching.
        time.sleep(PERIOD + 0.1)
        record()
        agent.dcgmUnwatchFields(handle, group, fieldgroup)
        emit({"type": "finished", "time": time.time(), "reason": "parent_closed_input"})
    finally:
        if handle is not None:
            agent.dcgmStopEmbedded(handle)
        agent.dcgmShutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dcgm-root", type=Path, required=True)
    parser.add_argument("--uuid", required=True)
    parser.add_argument("--log-file", type=Path, required=True)
    args = parser.parse_args()
    sample(args.dcgm_root, args.uuid, args.log_file)
