"""Capture unchanged pinned BETSE HCNLeak/HCN2_cAMP/HCN4_cAMP classes.

Run with the separate BETSE environment. This module does not import Cells or
the independent oracle. Capture files include source provenance and complete
native clamp states; the consumer separately validates them against the oracle.
"""

import argparse
import hashlib
import inspect
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import betse
import numpy as np
from betse.science.channels import channelsabc, vg_funny


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _pair(first, second, count):
    return np.stack([np.broadcast_to(value, (count,)) for value in (first, second)])


def _source(protocol):
    checkout = Path(protocol["source_checkout"])
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != protocol["source_revision"] or betse.__version__ != protocol["source_version"]:
        raise ValueError("Pinned BETSE revision/version mismatch")
    package = Path(betse.__file__).resolve().parent.parent
    hashes = {}
    for relative, expected in protocol["source_files"].items():
        installed, upstream = package / relative, checkout / relative
        got_installed, got_upstream = _sha(installed), _sha(upstream)
        if got_installed != expected or got_upstream != expected:
            raise ValueError("Pinned source mismatch: " + relative)
        hashes[relative] = dict(
            installed_path=str(installed),
            checkout_path=str(upstream),
            installed_sha256=got_installed,
            checkout_sha256=got_upstream,
        )
    return dict(
        revision=revision,
        version=betse.__version__,
        files=hashes,
        class_module_path=inspect.getfile(vg_funny),
        clock_module_path=inspect.getfile(channelsabc),
        unchanged_classes=True,
    )


def _case(name, voltage, targets, protocol, label):
    channel = getattr(vg_funny, name)()
    total = 1 if np.ndim(voltage) == 0 else len(voltage)
    cells = SimpleNamespace(mem_i=np.arange(total))
    channel.init(voltage, cells, SimpleNamespace(), targets=targets)
    count = channel.data_length
    selected = np.atleast_1d(voltage if targets is None else voltage[targets])
    initial = _pair(channel.m, channel.h, count).copy()
    channel._calculate_state(selected * 1000)
    target = _pair(channel._mInf, channel._hInf, count)
    tau = _pair(channel._mTau, channel._hTau, count) / channel.time_unit
    row = dict(
        label=label,
        voltage_V=np.atleast_1d(voltage).tolist(),
        scalar_input=np.ndim(voltage) == 0,
        targets=None if targets is None else targets.tolist(),
        selected_voltage_V=selected.tolist(),
        initial=initial.tolist(),
        target=target.tolist(),
        tau_s=tau.tolist(),
        time_unit=channel.time_unit,
        powers=[channel._mpower, channel._hpower],
        ions=channel.ions,
        relative_permeability=channel.rel_perm,
        native_steps=[],
    )
    for dt in protocol["native_capture"]["step_dt_s"]:
        channel.m, channel.h = (
            np.full(count, value) for value in protocol["native_capture"]["initial_update_gates"]
        )
        before = _pair(channel.m, channel.h, count).copy()
        channel.run(voltage, SimpleNamespace(dt=dt))
        row["native_steps"].append(
            dict(
                dt_s=dt,
                initial=before.tolist(),
                gates=_pair(channel.m, channel.h, count).tolist(),
                opening=np.atleast_1d(channel.P).tolist(),
            )
        )
    return row


def _clock(tau, refinement, duration):
    stop, step = duration * max(tau), min(tau) / 4
    current, base = 0.0, [0.0]
    while current < stop:
        current = min(stop, current + step)
        base.append(current)
        step *= 1.2
    times = [0.0]
    for left, right in zip(base[:-1], base[1:], strict=True):
        times.extend(
            left + (right - left) * index / refinement for index in range(1, refinement + 1)
        )
    return times


def _clamp(name, refinement, protocol):
    settings = protocol["native_capture"]
    channel = getattr(vg_funny, name)()
    channel.init(float(settings["clamp_voltages_V"][0]), None, SimpleNamespace())
    channel.m, channel.h = (np.array([value]) for value in settings["initial_update_gates"])
    phases = []
    for voltage in settings["clamp_voltages_V"]:
        channel._calculate_state(voltage * 1000)
        tau = (np.array([channel._mTau, channel._hTau]) / channel.time_unit).tolist()
        times = _clock(tau, refinement, settings["clamp_duration_max_tau"])
        states = [_pair(channel.m, channel.h, 1)[:, 0].tolist()]
        probabilities = []
        for left, right in zip(times[:-1], times[1:], strict=True):
            channel.run(float(voltage), SimpleNamespace(dt=right - left))
            states.append(_pair(channel.m, channel.h, 1)[:, 0].tolist())
            probabilities.append(float(np.atleast_1d(channel.P)[0]))
        phases.append(
            dict(
                voltage_V=voltage,
                tau_s=tau,
                times_s=times,
                gates=states,
                opening_after_step=probabilities,
            )
        )
    return dict(refinement=refinement, clock="native_backward_euler", phases=phases)


def capture(protocol):
    result = dict(
        kind="cells.pinned_hcn_extra_native_capture@1",
        source=_source(protocol),
        native_clock="backward_euler",
        classes={},
    )
    settings = protocol["native_capture"]
    vector = np.linspace(*protocol["voltage_domain_V"], settings["vector_count"])
    target_vector = np.array(settings["ordinary_voltage_V"], dtype=float)
    for name in protocol["classes"]:
        cases = [
            _case(name, float(voltage), None, protocol, f"scalar-{index}")
            for index, voltage in enumerate(settings["ordinary_voltage_V"])
        ]
        cases.append(_case(name, vector, None, protocol, "vector"))
        cases.extend(
            _case(name, target_vector, np.array(indices, dtype=int), protocol, f"targets-{index}")
            for index, indices in enumerate(settings["target_indices"])
        )
        result["classes"][name] = dict(
            cases=cases,
            clamps=[
                _clamp(name, refinement, protocol) for refinement in settings["clamp_refinements"]
            ],
        )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--protocol", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise FileExistsError("Preserve existing native evidence: " + str(arguments.output))
    protocol = json.loads(arguments.protocol.read_text())
    result = capture(protocol)
    result["protocol_sha256"] = _sha(arguments.protocol)
    result["capture_source_sha256"] = _sha(__file__)
    arguments.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(
                status="captured",
                classes=list(result["classes"]),
                output=str(arguments.output),
                sha256=_sha(arguments.output),
            )
        )
    )


if __name__ == "__main__":
    main()
