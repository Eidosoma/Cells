"""Explicit warm scalar kinetic edits on the actual retained molecule owners.

This is a declaration/capture boundary around existing reinitialize/tissue_init
methods. It supplies no numerical law, cold owner, INIT parent or native load.
Only production/decay rates in existing enabled growth records may change.
Receipts are closed data; checking them never executes setup or a callback.
"""

import hashlib
import math
import sys
from collections.abc import Mapping
from pathlib import Path

import numpy as np

from cells.processes import betse_ecm_grn_source as chemistry
from cells.processes import betse_normal_ecm_molecule_lifecycle_source as source
from cells.processes import betse_normal_ion_join as ions

KEY = "kinetic_reload"
KIND = "cells.retained_molecule_scalar_kinetic_reload@1"
ROLES = ("molecules", "grn")
FIELDS = {"production rate": "r_production", "decay rate": "r_decay"}
BUFFERS = ("c_cells", "cc_at_mem", "c_env", "c_bound", "flux_intra")
FUNCTIONS = (
    source.initialize_both,
    source.MasterOfMolecules.reinitialize,
    source.MasterOfGenes.reinitialize,
    chemistry.MasterOfNetworks.tissue_init,
    chemistry.Molecule.init_growth,
)
CODES = tuple(f.__code__ for f in FUNCTIONS)
COLD_CODES = (
    source.MasterOfMolecules.read_mol_config.__code__,
    source.MasterOfGenes.read_gene_config.__code__,
    chemistry.MasterOfNetworks.read_substances.__code__,
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same(a, b):
    """Mapping order is incidental; scalar category and array axes are exact."""
    if isinstance(a, Mapping) or isinstance(b, Mapping):
        return (
            isinstance(a, Mapping)
            and isinstance(b, Mapping)
            and set(a) == set(b)
            and all(same(a[k], b[k]) for k in a)
        )
    if isinstance(a, (np.ndarray, np.generic)) or isinstance(b, (np.ndarray, np.generic)):
        return (
            type(a) is type(b)
            and a.dtype == b.dtype
            and a.shape == b.shape
            and np.array_equal(a, b)
        )
    if isinstance(a, (tuple, list)) or isinstance(b, (tuple, list)):
        return (
            isinstance(a, (tuple, list))
            and isinstance(b, (tuple, list))
            and len(a) == len(b)
            and all(same(x, y) for x, y in zip(a, b, strict=True))
        )
    return type(a) is type(b) and a == b


def selection(raw):
    if KEY not in raw:
        return None
    value = raw[KEY]
    require(
        isinstance(value, Mapping)
        and set(value)
        == {
            "kind",
            "provenance",
            "source_INIT_binding_identity",
            "source_INIT_parent_identity",
            "source_complete_INIT_identity",
            "changes",
        }
        and value["kind"] == KIND,
        "Require the explicit complete scalar kinetic route",
    )
    for name in (
        "provenance",
        "source_INIT_binding_identity",
        "source_INIT_parent_identity",
        "source_complete_INIT_identity",
    ):
        require(
            type(value[name]) is str and bool(value[name].strip()),
            "Missing kinetic source association: " + name,
        )
    validate_changes(value["changes"])
    return value


def validate_changes(changes):
    """Check the request without inventing any INIT/owner identity."""
    require(
        isinstance(changes, (list, tuple)) and 0 < len(changes) <= 128,
        "Require bounded nonempty kinetic changes",
    )
    seen = set()
    for row in changes:
        require(
            isinstance(row, Mapping)
            and set(row) == {"role", "species", "field", "before", "after"},
            "Require every exact kinetic change field",
        )
        require(
            row["role"] in ROLES
            and type(row["species"]) is str
            and row["species"]
            and row["field"] in FIELDS,
            "Unsupported kinetic owner/species/field",
        )
        key = (row["role"], row["species"], row["field"])
        require(key not in seen, "Duplicate kinetic change")
        seen.add(key)
        for key in ("before", "after"):
            require(
                type(row[key]) in (int, float) and math.isfinite(row[key]) and row[key] >= 0,
                "Kinetic rates must be finite nonnegative Python scalars",
            )
        require(
            type(row["before"]) is type(row["after"]) and row["before"] != row["after"],
            "Require an actual rate edit without scalar-category conversion",
        )
    return changes


def configuration_after_allowed_edits(before, after, role, selected):
    """Remove only declared edits; all other configuration remains exact."""
    candidate = ions.data(after)
    for row in selected["changes"]:
        if row["role"] != role:
            continue
        left, right = before["biomolecules"], candidate["biomolecules"]
        require(
            [m["name"] for m in left] == [m["name"] for m in right]
            and len({m["name"] for m in left}) == len(left),
            "Kinetic reload may not add, omit, duplicate or reorder species",
        )
        matches = [i for i, m in enumerate(left) if m["name"] == row["species"]]
        require(len(matches) == 1, "Kinetic edit requires an existing molecule")
        i = matches[0]
        old, new = left[i].get("growth and decay"), right[i].get("growth and decay")
        require(
            isinstance(old, Mapping) and isinstance(new, Mapping),
            "Kinetic reload cannot enable or hydrate missing growth authority",
        )
        require(
            same(old.get(row["field"]), row["before"])
            and same(new.get(row["field"]), row["after"]),
            "Kinetic change differs from retained/source configuration",
        )
        new[row["field"]] = row["before"]
    require(same(before, candidate), "Undeclared configuration change outside scalar kinetics")
    return True


def check(binding, completed):
    selected = selection(binding.inputs)
    if selected is None:
        return None
    require(
        selected["source_INIT_binding_identity"]
        == completed.binding.identity
        == binding.expected_init_identity
        and selected["source_INIT_parent_identity"] == completed.parent.identity
        and selected["source_complete_INIT_identity"] == completed.identity,
        "Foreign actual complete INIT association for kinetic reload",
    )
    old = completed.binding.inputs_raw["owners"]
    new = binding.inputs["sim_phase"]["owners"]
    require(
        old["transport"]["raw_setup_fault"] is None and new["transport"]["raw_setup_fault"] is None,
        "Raw setup faults remain a separate failed source route",
    )
    positions = []
    for role in ROLES:
        key = "general network" if role == "molecules" else "gene regulatory network settings"
        flag = "implement network" if role == "molecules" else "gene regulatory network simulated"
        edits = [r for r in selected["changes"] if r["role"] == role]
        require(
            not edits
            or (
                old["configuration"][key][flag] is True and new["configuration"][key][flag] is True
            ),
            "A kinetic edit requires the retained enabled native owner",
        )
        before = old["handlers"][role]["network"]["configuration"]
        after = new["handlers"][role]["network"]["configuration"]
        configuration_after_allowed_edits(before, after, role, selected)
        for mol in before["biomolecules"]:
            for field in FIELDS:
                positions.extend(
                    (role, mol["name"], field)
                    for r in edits
                    if r["species"] == mol["name"] and r["field"] == field
                )
    require(
        positions == [(r["role"], r["species"], r["field"]) for r in selected["changes"]],
        "Kinetic declaration must retain native owner/species/rate order",
    )
    for raw in (old, new):
        general = raw["handlers"]["molecules"]
        expected = dict(
            ions.data(general["network"]["configuration"]),
            channels=ions.data(general["catalog"]["populations"]),
        )
        expected["implement network"] = raw["configuration"]["general network"]["implement network"]
        require(
            same(expected, raw["configuration"]["general network"])
            and same(raw["field"]["network"], raw["handlers"]["grn"]["network"]),
            "Foreign native kinetic configuration carrier",
        )
    return selected


def source_identity():
    current = (
        source.initialize_both,
        source.MasterOfMolecules.reinitialize,
        source.MasterOfGenes.reinitialize,
        chemistry.MasterOfNetworks.tissue_init,
        chemistry.Molecule.init_growth,
    )
    require(
        all(
            f is original and f.__code__ is code
            for f, original, code in zip(current, FUNCTIONS, CODES, strict=True)
        )
        and source.MasterOfGenes is source.qualified.MasterOfGenes
        and source.MasterOfMolecules.reinitialize.__globals__ is vars(source),
        "Foreign retained kinetic source methods or dispatcher",
    )
    return [
        dict(
            module=f.__module__,
            function=f.__qualname__,
            line=f.__code__.co_firstlineno,
            source_sha256=hashlib.sha256(
                Path(sys.modules[f.__module__].__file__).read_bytes()
            ).hexdigest(),
            bytecode_sha256=hashlib.sha256(f.__code__.co_code).hexdigest(),
        )
        for f in FUNCTIONS
    ]


def expected_calls(raw, roles):
    result = [("initialize_both", None, None)]
    for role in ROLES:
        if role in roles:
            result.extend(((role + "_reinitialize", role, None), ("tissue_init", role, None)))
            cfg = raw["handlers"][role]["network"]["configuration"]["biomolecules"]
            result.extend(
                ("init_growth", role, m["name"])
                for m in cfg
                if isinstance(m.get("growth and decay"), Mapping)
            )
    return result


def check_calls(calls, raw, roles):
    require(
        [(c["operation"], c["role"], c["species"]) for c in calls] == expected_calls(raw, roles)
        and all(c["association"] is True and c["exit_event"] == "return_or_unwind" for c in calls),
        "Omitted, duplicated, reordered or foreign warm source call",
    )


class Observation:
    """Check real warm calls and graph retention; serialize data only.

    Profile return(None) is ambiguous on CPython exception unwind. Exit events
    never decide success or raise; finish is called only after normal exit.
    """

    def __init__(self, ctx, binding, completed):
        self.ctx, self.binding, self.completed = ctx, binding, completed
        self.selected = check(binding, completed)
        require(self.selected is not None, "Explicit kinetic route required")
        self.source = source_identity()
        self.calls, self.errors, self.active = [], [], {}
        self.original, self.normal_exit, self.restored = None, False, False
        self.before, self.owners = {}, {}
        raw = binding.inputs["sim_phase"]["owners"]
        require(
            ctx.phase.kind == "SIM"
            and ctx.phase.p is ctx.p
            and ctx.phase.sim is ctx.sim
            and ctx.p._run_sim is True
            and same(ctx.p.network_config, raw["configuration"]["general network"])
            and same(ctx.p.grn.conf, raw["handlers"]["grn"]["network"]["configuration"]),
            "Foreign actual SIM phase/parameter/configuration association",
        )
        for role in ROLES:
            obj = getattr(ctx.sim, role, None)
            if not ctx.enabled[role]:
                require(obj is None, "Disabled latent owner cannot enter kinetic reload")
                continue
            require(obj is not None and hasattr(obj, "core"), "Missing retained kinetic owner")
            net = obj.core
            self.owners[role] = (obj, net, dict(net.molecules))
            fields = {}
            for name, mol in net.molecules.items():
                fields[name] = dict(
                    rates={k: getattr(mol, v, None) for k, v in FIELDS.items()},
                    buffers={k: getattr(mol, k) for k in BUFFERS},
                )
            self.before[role] = fields
        self.snapshot = ions.freeze(self.before)
        self._check_rates(self.snapshot, completed.binding.inputs_raw["owners"])
        for role, fields in self.snapshot.items():
            retained = completed.parent.network.network_cache["handlers"][role]["cache"]["wire"][
                "molecule_fields"
            ]
            require(list(retained) == list(fields), "Foreign actual INIT molecule cache")
            for name, item in fields.items():
                require(
                    all(same(item["buffers"][k], retained[name][k]) for k in BUFFERS)
                    and all(same(item["rates"][k], retained[name][v]) for k, v in FIELDS.items()),
                    "Warm entry is not the retained INIT molecule state",
                )

    def _check_rates(self, values, raw):
        for role, fields in values.items():
            cfg = raw["handlers"][role]["network"]["configuration"]["biomolecules"]
            require(list(fields) == [m["name"] for m in cfg], "Foreign retained molecule order")
            for row in cfg:
                growth = row.get("growth and decay")
                if isinstance(growth, Mapping):
                    require(
                        all(same(fields[row["name"]]["rates"][key], growth[key]) for key in FIELDS),
                        "Retained runtime rates differ from actual source configuration",
                    )

    def profile(self, frame, event, arg):
        # Capture defects remain separate from the source result/exception.
        try:
            self.observe(frame, event, arg)
        except BaseException as error:
            self.errors.append(
                dict(stage="profile_capture", type=type(error).__name__, message=str(error))
            )
        if self.original is not None:
            self.original(frame, event, arg)

    def observe(self, frame, event, arg):
        if event == "return" and id(frame) in self.active:
            self.active.pop(id(frame))["exit_event"] = "return_or_unwind"
        if event != "call":
            return
        code = frame.f_code
        if code in COLD_CODES:
            self.errors.append(dict(stage="cold_owner_call", function=code.co_name))
            return
        if code not in CODES:
            return
        position = CODES.index(code)
        row = dict(
            operation=(
                "initialize_both",
                "molecules_reinitialize",
                "grn_reinitialize",
                "tissue_init",
                "init_growth",
            )[position],
            association=False,
            exit_event=None,
            species=None,
        )
        local = frame.f_locals
        phase = local.get("phase")
        role = None
        for name, (obj, net, molecules) in self.owners.items():
            target = local.get("self")
            if target is obj or target is net or any(target is m for m in molecules.values()):
                role = name
        row["role"] = role
        row["association"] = phase is self.ctx.phase
        if position == 0:
            row["association"] &= local.get("self") is self.ctx.sim and local.get("p") is self.ctx.p
        elif position in (1, 2):
            expected = ROLES[position - 1]
            row["association"] &= (
                role == expected
                and local.get("self") is self.owners[expected][0]
                and frame.f_back.f_code is CODES[0]
            )
        elif position == 3:
            row["association"] &= (
                role is not None
                and local.get("self") is self.owners[role][1]
                and frame.f_back.f_code is CODES[ROLES.index(role) + 1]
            )
            if role is not None:
                configured = (
                    self.ctx.p.network_config if role == "molecules" else self.ctx.p.grn.conf
                )
                row["association"] &= local.get("config_substances") is configured["biomolecules"]
        else:
            row["association"] &= role is not None and frame.f_back.f_code is CODES[3]
            if role is not None:
                names = [
                    name for name, mol in self.owners[role][2].items() if local.get("self") is mol
                ]
                row["association"] &= len(names) == 1
                row["species"] = names[0] if names else None
        self.calls.append(row)
        self.active[id(frame)] = row

    def __enter__(self):
        self.original = sys.getprofile()
        sys.setprofile(self.profile)
        return self

    def __exit__(self, kind, error, traceback):
        intact = getattr(sys.getprofile(), "__self__", None) is self
        sys.setprofile(self.original)
        self.restored = sys.getprofile() is self.original
        self.normal_exit = kind is None
        if not intact or not self.restored:
            self.errors.append(
                dict(stage="profile_restoration", intact=intact, restored=self.restored)
            )
        return False

    def data(self):
        return dict(
            kind=KIND,
            selected=self.selected,
            source=self.source,
            calls=self.calls,
            capture_errors=self.errors,
            normal_exit=self.normal_exit,
            profile_restored=self.restored,
            pending_calls=len(self.active),
            source_binding_identity=self.binding.identity,
            source_complete_INIT_identity=self.completed.identity,
            before=self.snapshot,
            independent_cases=0,
            native_persistence=False,
            object_identity_scope="warm_reinitialize_only_not_across_checkpoint_codec",
        )

    def finish(self):
        require(
            self.normal_exit and self.restored and not self.errors and not self.active,
            "Incomplete or failed kinetic source observation",
        )
        check_calls(self.calls, self.ctx.raw, self.owners)
        after = {}
        for role, (obj, net, molecules) in self.owners.items():
            require(
                getattr(self.ctx.sim, role) is obj
                and obj.core is net
                and list(net.molecules) == list(molecules)
                and all(net.molecules[k] is m for k, m in molecules.items()),
                "Kinetic reload replaced a retained owner/core/molecule",
            )
            after[role] = {}
            for name, mol in molecules.items():
                buffers = {}
                for key, original in self.before[role][name]["buffers"].items():
                    value = getattr(mol, key)
                    require(
                        value is original
                        and same(value, self.snapshot[role][name]["buffers"][key]),
                        "Kinetic reload changed retained concentration/flux buffer",
                    )
                    buffers[key] = value
                after[role][name] = dict(
                    rates={k: getattr(mol, v, None) for k, v in FIELDS.items()}, buffers=buffers
                )
        self._check_rates(after, self.ctx.raw)
        value = dict(self.data(), after=ions.freeze(after), capture_complete=True)
        value["identity"] = ions.digest(value)
        return ions.freeze(value)


def resolve(binding, parent):
    selected = check(binding, parent.source_init)
    if selected is None:
        return None
    setup = parent.receipt["source_setup"]
    receipt = setup["kinetic_reload_complete"]
    require(
        receipt["identity"] == ions.digest({k: v for k, v in receipt.items() if k != "identity"})
        and receipt["capture_complete"] is True
        and receipt["capture_errors"] == ()
        and receipt["normal_exit"] is True
        and receipt["profile_restored"] is True
        and receipt["pending_calls"] == 0
        and same(receipt["selected"], selected)
        and same(receipt["source"], source_identity())
        and receipt["source_binding_identity"] == binding.identity
        and receipt["source_complete_INIT_identity"] == parent.source_init.identity,
        "Changed or incomplete kinetic source/INIT receipt",
    )
    retained = parent.phase_binding.setup_receipt["source_setup"]["kinetic_reload_complete"]
    require(same(retained, receipt), "Foreign secondary kinetic setup receipt")
    raw = binding.inputs["sim_phase"]["owners"]
    enabled = {
        role
        for role, key, flag in (
            ("molecules", "general network", "implement network"),
            ("grn", "gene regulatory network settings", "gene regulatory network simulated"),
        )
        if raw["configuration"][key][flag] is True
    }
    require(
        set(receipt["before"]) == set(receipt["after"]) == enabled,
        "Missing complete retained kinetic owner evidence",
    )
    check_calls(receipt["calls"], raw, enabled)
    for role, molecules in receipt["after"].items():
        wire = parent.active.network.network_cache["handlers"][role]["cache"]["wire"][
            "molecule_fields"
        ]
        require(list(wire) == list(molecules), "Changed kinetic runtime species order")
        for name, fields in molecules.items():
            require(
                all(
                    same(wire[name][attr], fields["rates"][field]) for field, attr in FIELDS.items()
                ),
                "Changed persisted kinetic runtime rate",
            )
            configured = next(
                m
                for m in binding.inputs["sim_phase"]["owners"]["handlers"][role]["network"][
                    "configuration"
                ]["biomolecules"]
                if m["name"] == name
            )
            if isinstance(configured.get("growth and decay"), Mapping):
                require(
                    all(
                        same(fields["rates"][k], configured["growth and decay"][k]) for k in FIELDS
                    ),
                    "Resealed kinetic receipt changed declared rates",
                )
            initial = parent.source_init.parent.network.network_cache["handlers"][role]["cache"][
                "wire"
            ]["molecule_fields"][name]
            previous = receipt["before"][role][name]
            require(
                all(
                    same(previous["buffers"][k], initial[k])
                    and same(fields["buffers"][k], initial[k])
                    for k in BUFFERS
                )
                and all(same(previous["rates"][k], initial[v]) for k, v in FIELDS.items()),
                "Changed actual retained INIT kinetic evidence",
            )
            if parent.active.cursor == 0:
                require(
                    all(same(wire[name][k], fields["buffers"][k]) for k in BUFFERS),
                    "Changed kinetic SIM entry concentration/flux",
                )
    return receipt
