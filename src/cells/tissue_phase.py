"""Prepare an explicit INIT-to-SIM transition with continuous physical history."""

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

from cells.core import active_membrane_profile_phase_handoff as active_bridge
from cells.core import active_profile_barrier_phase_handoff as combined_bridge
from cells.core import joint_water_barrier_phase_handoff as joint_water_barrier_bridge
from cells.core import joint_water_profile_barrier_phase_handoff as joint_water_combined_bridge
from cells.core import joint_water_profile_phase_handoff as joint_water_bridge
from cells.core import membrane_profile_phase_handoff as bridge
from cells.core import open_calcium_bath_phase_handoff as open_calcium_bath_bridge
from cells.core import owned_barrier_phase_handoff as owned_barrier_bridge
from cells.core import owned_calcium_profile_barrier_phase_handoff as owned_combined_bridge
from cells.core import owned_calcium_profile_phase_handoff as owned_bridge
from cells.core import surface_active_profile_barrier_epoch_spec as combined_epoch
from cells.core import surface_active_profile_barrier_interventions_spec as combined_scheduled
from cells.core import surface_active_profile_epoch_spec as active_epoch
from cells.core import surface_active_profile_interventions_spec as active_scheduled
from cells.core import surface_bath_phase_handoff as bath_bridge
from cells.core import surface_profile_epoch_spec as epoch
from cells.core import surface_profile_interventions_spec as scheduled
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError, digest, read_json
from cells.io import load_snapshot


def _read_json(path):
    value = read_json(path)
    # The shared reader rejects duplicate keys and nonstandard constants;
    # serialization also rejects overflowing literals such as 1e999.
    json.dumps(value, allow_nan=False)
    return value


def prepare_request(request):
    """Preserve the component's explicit state, clock and reset policies."""
    try:
        json.dumps(request, allow_nan=False)
        if type(request) is not dict:
            raise ConfigError("Require an explicit INIT-to-SIM request object")
        adapter = _adapter(request.get("kind"), request=True)
        return adapter.prepare(request)
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError, IndexError) as error:
        raise ConfigError("Invalid INIT-to-SIM request: " + str(error)) from error


def replay(provenance):
    try:
        if type(provenance) is not dict:
            raise ConfigError("Require complete INIT-to-SIM preparation provenance")
        adapter = _adapter(provenance.get("kind"))
        json.dumps(provenance, allow_nan=False)
        return adapter.replay(provenance)
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError, IndexError) as error:
        raise ConfigError("Invalid INIT-to-SIM provenance: " + str(error)) from error


def _adapter(kind, *, request=False):
    for candidate in (
        bridge,
        active_bridge,
        combined_bridge,
        owned_combined_bridge,
        owned_bridge,
        joint_water_bridge,
        joint_water_barrier_bridge,
        joint_water_combined_bridge,
        owned_barrier_bridge,
        bath_bridge,
        open_calcium_bath_bridge,
    ):
        expected = candidate.REQUEST_KIND if request else candidate.KIND
        if kind == expected:
            return candidate
    raise ConfigError("Require complete supported INIT-to-SIM preparation provenance or request")


def _source_adapter(spec):
    """Exact owner types prevent an epoch or coupled state reaching a parent adapter."""
    if any(type(spec.model) is contract.model_type for contract in open_calcium_bath_bridge.OWNERS):
        contract = open_calcium_bath_bridge.owner(spec)
        return open_calcium_bath_bridge, contract.epoch.POLICIES
    if any(type(spec.model) is contract.model_type for contract in bath_bridge.OWNERS):
        contract = bath_bridge.owner(spec)
        return bath_bridge, contract.epoch.POLICIES
    if any(type(spec.model) is c.model_type for c in joint_water_combined_bridge.OWNERS):
        contract = joint_water_combined_bridge.owner(spec)
        return joint_water_combined_bridge, contract.epoch.POLICIES
    if any(type(spec.model) is c.model_type for c in owned_combined_bridge.OWNERS):
        contract = owned_combined_bridge.owner(spec)
        return owned_combined_bridge, contract.epoch.POLICIES
    if type(spec.model) is combined_scheduled.SurfaceActiveProfileBarrierInterventionModel:
        return combined_bridge, combined_epoch.POLICIES
    if any(type(spec.model) is c.model_type for c in joint_water_barrier_bridge.OWNERS):
        contract = joint_water_barrier_bridge.owner(spec)
        return joint_water_barrier_bridge, contract.epoch.POLICIES
    if any(type(spec.model) is c.model_type for c in owned_barrier_bridge.OWNERS):
        contract = owned_barrier_bridge.owner(spec)
        return owned_barrier_bridge, contract.epoch.POLICIES
    if type(spec.model) is scheduled.SurfaceProfileInterventionModel:
        return bridge, epoch.POLICIES
    if type(spec.model) is active_scheduled.SurfaceActiveProfileInterventionModel:
        return active_bridge, active_epoch.POLICIES
    if any(type(spec.model) is candidate.model_type for candidate in joint_water_bridge.OWNERS):
        contract = joint_water_bridge.owner(spec)
        return joint_water_bridge, contract.epoch.POLICIES
    contract = owned_bridge.owner(spec)
    return owned_bridge, contract.epoch.POLICIES


def read_preparation(directory):
    path = Path(directory)
    definition = _read_json(path / "definition.json")
    prepared = replay(_read_json(path / "provenance.json"))
    if digest(definition) != digest(prepared.definition):
        raise ConfigError("Prepared definition changed relative to its INIT-to-SIM recipe")
    return prepared


def _parser():
    parser = argparse.ArgumentParser(prog="cells tissue-phase", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("prepare", "prepare SIM from a complete embedded INIT checkpoint and explicit recipe"),
        ("replay", "rebuild a SIM preparation from its complete provenance"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("input", type=Path)
        command.add_argument("--output", type=Path, required=True, help="new directory")
    command = commands.add_parser(
        "from-snapshot",
        help="carry an accepted INIT snapshot into an explicit new SIM phase starting at zero",
    )
    command.add_argument("snapshot", type=Path)
    command.add_argument("simulation", type=Path, help="ordinary scheduled SIM definition")
    command.add_argument("--output", type=Path, required=True, help="new directory")
    command = commands.add_parser("validate", help="verify both files and their complete recipe")
    command.add_argument("input", type=Path)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        parent = None
        if args.command == "validate":
            prepared = read_preparation(args.input)
        else:
            if args.output.exists() or args.output.is_symlink():
                raise ConfigError(f"Output already exists; choose a new directory: {args.output}")
            if args.command == "from-snapshot":
                saved = load_snapshot(args.snapshot)
                adapter, policies = _source_adapter(saved.spec)
                prepared = prepare_request(
                    dict(
                        kind=adapter.REQUEST_KIND,
                        policies=deepcopy(policies),
                        source=adapter.capture_source(saved.spec, saved.checkpoint),
                        simulation=_read_json(args.simulation),
                    )
                )
                parent = saved.fingerprint
            else:
                value = _read_json(args.input)
                prepared = prepare_request(value) if args.command == "prepare" else replay(value)
            _adapter(prepared.provenance["kind"]).write_preparation(args.output, prepared)
        summary = dict(
            status={
                "prepare": "prepared",
                "from-snapshot": "prepared",
                "replay": "replayed",
                "validate": "valid",
            }[args.command],
            kind=prepared.provenance["kind"],
            model_id=prepared.definition["model"]["id"],
            clocks=prepared.provenance["clocks"],
            source_identity=prepared.provenance["source_identity"],
            definition_sha256=digest(prepared.definition),
            preparation_identity=prepared.provenance["identity"],
        )
        if _adapter(prepared.provenance["kind"]) in (bath_bridge, open_calcium_bath_bridge):
            summary["carried_fields"] = prepared.provenance["preservation"]["carried_fields"]
            summary["controller_operation"] = prepared.provenance["controller_operation"]
            if prepared.provenance["kind"] == open_calcium_bath_bridge.KIND:
                # Replay has already recomputed this complete witness from the
                # carried state. Reporting it must not substitute fresh pools
                # or turn this one admission bound into a recommended timestep.
                summary["carried_admission"] = prepared.definition["model"]["handoff"][
                    "carried_admission"
                ]
        else:
            summary["carried_parent_fields"] = prepared.provenance["preservation"][
                "carried_parent_fields"
            ]
        if args.command != "validate":
            summary["output"] = str(args.output)
        if parent is not None:
            summary["source_snapshot_sha256"] = parent
        print(json.dumps(summary, indent=2, allow_nan=False))
        return 0
    except (ConfigError, NumericalError, OSError, ValueError, TypeError, RecursionError) as error:
        print(f"cells tissue-phase: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
