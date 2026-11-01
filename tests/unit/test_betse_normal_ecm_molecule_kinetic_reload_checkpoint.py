"""Native/model/RNG-blocked scalar kinetic route and capture controls.

All positive owners here are unowned synthetic records. Profiled functions are
synthetic, never the actual reinitializers. No successful INIT/SIM is claimed.
"""

import copy
import json
import sys
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_normal_ecm_molecule_checkpoint_codec as codec
from cells.processes import betse_normal_ecm_molecule_kinetic_reload as kinetics
from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from tests.unit.test_betse_normal_ecm_molecule_checkpoint_codec import packed
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import (
    no_actual_execution as no_actual_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import plain_record
from validation.betse import betse_normal_ecm_molecule_kinetic_reload_checkpoint as route


@pytest.fixture(autouse=True)
def no_warm_source_calls(tmp_path):
    attempted, previous = [], sys.getprofile()
    codes = (*kinetics.CODES, *kinetics.COLD_CODES)

    def guard(frame, event, arg):
        if event == "call" and frame.f_code in codes:
            attempted.append(frame.f_code.co_name)
            raise AssertionError("Actual native/adopted warm chemistry forbidden")
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(guard)
    yield attempted
    sys.setprofile(previous)
    (tmp_path / "warm-control.json").write_text(
        json.dumps(
            dict(actual_source_entries=attempted, synthetic_only=True, scientific_acceptance=False)
        )
    )
    assert attempted == []


def change(role="molecules", species="X", field="production rate"):
    return dict(
        role=role,
        species=species,
        field=field,
        before=0.1 if field == "production rate" else 0.2,
        after=0.3 if field == "production rate" else 0.4,
    )


def raw_owners():
    handlers = {}
    for role in kinetics.ROLES:
        cfg = dict(
            biomolecules=[
                dict(
                    name=name,
                    Dm=0.0,
                    **{
                        "growth and decay": {
                            "production rate": 0.1,
                            "decay rate": 0.2,
                            "apply to": "all",
                        }
                    },
                )
                for name in ("X", "Y")
            ],
            transporters=[],
            reactions=[],
            modulators=[],
            channels=[],
        )
        handlers[role] = dict(
            network=dict(configuration=cfg, cold_publish=True), catalog=dict(populations=[])
        )
    raw = dict(
        handlers=handlers,
        transport=dict(raw_setup_fault=None),
        configuration={
            "general network": dict(
                copy.deepcopy(handlers["molecules"]["network"]["configuration"]),
                **{"implement network": True},
            ),
            "gene regulatory network settings": {"gene regulatory network simulated": True},
        },
        field=dict(network=copy.deepcopy(handlers["grn"]["network"])),
    )
    return raw


def synchronize(raw):
    raw["configuration"]["general network"].update(
        copy.deepcopy(raw["handlers"]["molecules"]["network"]["configuration"])
    )
    raw["field"]["network"] = copy.deepcopy(raw["handlers"]["grn"]["network"])


def graph(changes=None):
    changes = changes if changes is not None else [change()]
    old = raw_owners()
    new = copy.deepcopy(old)
    for row in changes:
        mol = next(
            m
            for m in new["handlers"][row["role"]]["network"]["configuration"]["biomolecules"]
            if m["name"] == row["species"]
        )
        mol["growth and decay"][row["field"]] = row["after"]
    synchronize(new)
    selected = dict(
        kind=kinetics.KIND,
        provenance="synthetic declaration, no actual INIT admission",
        source_INIT_binding_identity="INIT-binding",
        source_INIT_parent_identity="INIT-parent",
        source_complete_INIT_identity="complete-INIT",
        changes=changes,
    )
    cache = dict(handlers={})
    live = {}
    for role in kinetics.ROLES:
        molecules = {}
        for index, name in enumerate(("X", "Y")):
            values = dict(r_production=0.1, r_decay=0.2)
            values.update({key: np.array([index + 1.0, index + 2.0]) for key in kinetics.BUFFERS})
            molecules[name] = SimpleNamespace(**values)
        live[role] = SimpleNamespace(core=SimpleNamespace(molecules=molecules))
        cache["handlers"][role] = dict(
            cache=dict(
                wire=dict(molecule_fields={n: copy.deepcopy(vars(m)) for n, m in molecules.items()})
            )
        )
    geometry = dict(parameters=dict(configured_temperature_K=310.0))
    base = plain_record(
        lifecycle.init.Binding,
        identity="INIT-binding",
        inputs_raw=dict(owners=old),
        material_binding=SimpleNamespace(geometry_binding=SimpleNamespace(definition=geometry)),
    )
    parent = plain_record(
        lifecycle.init.State,
        identity="INIT-parent",
        network=plain_record(network.NetworkState, network_cache=cache),
    )
    completed = lifecycle.CompleteInit(base, parent, "unowned-synthetic-only", "complete-INIT")
    inputs = dict(
        sim_phase=dict(
            owners=new, field=dict(definition=dict(environment_geometry_definition=geometry))
        ),
        kinetic_reload=selected,
    )
    binding = lifecycle.Binding(
        inputs,
        base.identity,
        plain_record(lifecycle.init.Declaration, identity="declaration"),
        "synthetic-SIM-binding",
    )
    p = SimpleNamespace(
        network_config=new["configuration"]["general network"],
        grn=SimpleNamespace(conf=new["handlers"]["grn"]["network"]["configuration"]),
        _run_sim=True,
    )
    sim = SimpleNamespace(**live)
    ctx = SimpleNamespace(p=p, sim=sim, raw=new, enabled={r: True for r in kinetics.ROLES})
    ctx.phase = SimpleNamespace(p=p, sim=sim, kind="SIM")
    return binding, completed, ctx


def synthetic_growth(self, phase):
    return None


def synthetic_tissue(self, phase, config_substances):
    for row in config_substances:
        mol = self.molecules[row["name"]]
        mol.r_production = row["growth and decay"]["production rate"]
        mol.r_decay = row["growth and decay"]["decay rate"]
        synthetic_growth(mol, phase)


def synthetic_molecules(self, phase):
    synthetic_tissue(self.core, phase, phase.p.network_config["biomolecules"])


def synthetic_grn(self, phase):
    synthetic_tissue(self.core, phase, phase.p.grn.conf["biomolecules"])


def synthetic_dispatch(self, phase, p):
    synthetic_molecules(self.molecules, phase)
    synthetic_grn(self.grn, phase)
    return p is phase.p


@pytest.fixture
def synthetic_source(monkeypatch):
    pin = kinetics.source_identity()
    monkeypatch.setattr(kinetics, "source_identity", lambda: pin)
    monkeypatch.setattr(
        kinetics,
        "CODES",
        tuple(
            f.__code__
            for f in (
                synthetic_dispatch,
                synthetic_molecules,
                synthetic_grn,
                synthetic_tissue,
                synthetic_growth,
            )
        ),
    )
    return pin


def observe(monkeypatch):
    binding, completed, ctx = graph([change(), change("grn", "Y", "decay rate")])
    observation = kinetics.Observation(ctx, binding, completed)
    with observation:
        synthetic_dispatch(ctx.sim, ctx.phase, ctx.p)
    return binding, completed, ctx, observation, observation.finish()


def test_source_plan_matches_four_complete_pinned_original_method_bodies():
    plan = route.source_plan()
    assert len(plan["methods"]) == 4
    assert all(row["complete_body_match"] for row in plan["methods"])
    assert plan["actual_native_entries"] == 0 and plan["numerical_parity"] is False


@pytest.mark.parametrize(
    "changes",
    [
        [change()],
        [change("grn", "Y", "decay rate")],
        [change(), change("molecules", "X", "decay rate"), change("grn", "Y")],
    ],
)
def test_explicit_supported_rate_edits_retain_default_owner_guards(changes):
    binding, completed, _ = graph(changes)
    assert kinetics.check(binding, completed) is binding.inputs[kinetics.KEY]
    lifecycle.check_stable_owner_scope(binding, completed)


def test_legacy_path_remains_strict_for_any_configuration_change():
    binding, completed, _ = graph()
    binding.inputs.pop(kinetics.KEY)
    assert kinetics.selection(binding.inputs) is None
    with pytest.raises(ValueError, match="complete source correspondence"):
        lifecycle.check_stable_owner_scope(binding, completed)


@pytest.mark.parametrize(
    "fault",
    [
        "missing-kind",
        "missing-parent",
        "empty",
        "duplicate",
        "field",
        "role",
        "bool",
        "nan",
        "infinite",
        "negative",
        "array",
        "numpy-scalar",
        "category",
        "no-edit",
    ],
)
def test_request_schema_refuses_unowned_or_ambiguous_rate_edits(fault):
    binding, _, _ = graph()
    selected = binding.inputs[kinetics.KEY]
    row = selected["changes"][0]
    if fault == "missing-kind":
        selected.pop("kind")
    elif fault == "missing-parent":
        selected.pop("source_INIT_parent_identity")
    elif fault == "empty":
        selected["changes"] = []
    elif fault == "duplicate":
        selected["changes"].append(copy.deepcopy(row))
    elif fault == "field":
        row["field"] = "Dm"
    elif fault == "role":
        row["role"] = "foreign"
    else:
        row["after"] = {
            "bool": True,
            "nan": float("nan"),
            "infinite": float("inf"),
            "negative": -0.1,
            "array": np.array(0.3),
            "numpy-scalar": np.float64(0.3),
            "category": 1,
            "no-edit": 0.1,
        }[fault]
    with pytest.raises(ValueError):
        kinetics.selection(binding.inputs)


@pytest.mark.parametrize(
    "fault",
    [
        "INIT",
        "parent",
        "complete",
        "before",
        "after",
        "enabled",
        "fault",
        "new-species",
        "reorder",
        "growth-null",
        "growth-disabled",
        "Dm",
        "target",
        "latent",
        "carrier",
        "rate-order",
        "role-order",
    ],
)
def test_configuration_delta_is_exact_and_source_parent_bound(fault):
    binding, completed, _ = graph([change(), change("grn", "Y", "decay rate")])
    selected = binding.inputs[kinetics.KEY]
    raw = binding.inputs["sim_phase"]["owners"]
    cfg = raw["handlers"]["molecules"]["network"]["configuration"]
    if fault in ("INIT", "parent", "complete"):
        selected[
            {
                "INIT": "source_INIT_binding_identity",
                "parent": "source_INIT_parent_identity",
                "complete": "source_complete_INIT_identity",
            }[fault]
        ] = "foreign"
    elif fault in ("before", "after"):
        selected["changes"][0][fault] += 0.01
    elif fault == "enabled":
        raw["configuration"]["general network"]["implement network"] = False
    elif fault == "fault":
        raw["transport"]["raw_setup_fault"] = "missing_max_rate_0"
    elif fault == "new-species":
        cfg["biomolecules"].append(copy.deepcopy(cfg["biomolecules"][0]))
    elif fault == "reorder":
        cfg["biomolecules"].reverse()
    elif fault.startswith("growth-"):
        cfg["biomolecules"][0]["growth and decay"] = None if fault == "growth-null" else "None"
    elif fault == "Dm":
        cfg["biomolecules"][0]["Dm"] = 1e-10
    elif fault == "target":
        cfg["biomolecules"][0]["growth and decay"]["apply to"] = ["foreign"]
    elif fault == "latent":
        cfg["transporters"] = None
    elif fault == "carrier":
        raw["configuration"]["general network"]["biomolecules"][0]["growth and decay"][
            "production rate"
        ] += 1
    elif fault == "rate-order":
        selected["changes"] = [change("molecules", "X", "decay rate"), change()]
    else:
        selected["changes"].reverse()
    with pytest.raises(ValueError):
        kinetics.check(binding, completed)


@pytest.mark.parametrize("fault", ["flag", "catalog", "publication", "temperature"])
def test_explicit_route_preserves_other_original_boundary_refusals(fault):
    binding, completed, _ = graph()
    raw = binding.inputs["sim_phase"]["owners"]
    if fault == "flag":
        raw["configuration"]["gene regulatory network settings"][
            "gene regulatory network simulated"
        ] = False
    elif fault == "catalog":
        raw["handlers"]["grn"]["catalog"]["extra"] = True
    elif fault == "publication":
        raw["handlers"]["grn"]["network"]["cold_publish"] = False
        synchronize(raw)
    else:
        binding.inputs["sim_phase"]["field"]["definition"]["environment_geometry_definition"] = (
            dict(parameters=dict(configured_temperature_K=300.0))
        )
    with pytest.raises(ValueError):
        lifecycle.check_stable_owner_scope(binding, completed)


def test_profiled_synthetic_warm_calls_capture_all_rates_objects_buffers_and_work(
    monkeypatch, synthetic_source, tmp_path
):
    _, _, _, obs, receipt = observe(monkeypatch)
    assert receipt["capture_complete"] is True and receipt["pending_calls"] == 0
    assert len(receipt["calls"]) == 9 and receipt["independent_cases"] == 0
    assert receipt["normal_exit"] is True and sys.getprofile() is obs.original
    assert receipt["before"]["molecules"]["X"]["rates"]["production rate"] == 0.1
    assert receipt["after"]["molecules"]["X"]["rates"]["production rate"] == 0.3
    route.preparation.archives.write_archive(
        tmp_path / "synthetic-capture",
        lifecycle.ions.data(
            dict(
                receipt=receipt,
                synthetic_only=True,
                actual_source_entries=0,
                scientific_acceptance=False,
            )
        ),
    )


@pytest.mark.parametrize(
    "fault",
    [
        "owner",
        "core",
        "molecule",
        "buffer-copy",
        "buffer-value",
        "rate",
        "omitted-call",
        "duplicate-call",
    ],
)
def test_capture_refuses_reinitialization_or_unaccounted_work(monkeypatch, synthetic_source, fault):
    binding, completed, ctx = graph()
    obs = kinetics.Observation(ctx, binding, completed)
    with obs:
        if fault != "omitted-call":
            synthetic_dispatch(ctx.sim, ctx.phase, ctx.p)
        if fault == "duplicate-call":
            synthetic_dispatch(ctx.sim, ctx.phase, ctx.p)
        mol = ctx.sim.molecules.core.molecules["X"]
        if fault == "owner":
            ctx.sim.molecules = copy.deepcopy(ctx.sim.molecules)
        elif fault == "core":
            ctx.sim.molecules.core = copy.deepcopy(ctx.sim.molecules.core)
        elif fault == "molecule":
            ctx.sim.molecules.core.molecules["X"] = copy.deepcopy(mol)
        elif fault == "buffer-copy":
            mol.c_cells = mol.c_cells.copy()
        elif fault == "buffer-value":
            mol.c_cells[0] += 1
        elif fault == "rate":
            mol.r_production += 1
    with pytest.raises(ValueError):
        obs.finish()


def test_profiled_exception_unwind_preserves_exact_primary_and_cause(monkeypatch, synthetic_source):
    binding, completed, ctx = graph()
    cause, primary = LookupError("synthetic cause"), OSError("synthetic warm failure")

    def broken_tissue(self, phase, config_substances):
        raise primary from cause

    def broken_molecules(self, phase):
        broken_tissue(self.core, phase, phase.p.network_config["biomolecules"])

    def broken_dispatch(self, phase, p):
        broken_molecules(self.molecules, phase)
        return p

    monkeypatch.setattr(
        kinetics,
        "CODES",
        (
            broken_dispatch.__code__,
            broken_molecules.__code__,
            synthetic_grn.__code__,
            broken_tissue.__code__,
            synthetic_growth.__code__,
        ),
    )
    obs = kinetics.Observation(ctx, binding, completed)
    with pytest.raises(OSError) as caught, obs:
        broken_dispatch(ctx.sim, ctx.phase, ctx.p)
    assert caught.value is primary and caught.value.__cause__ is cause
    assert obs.normal_exit is False and obs.restored is True
    assert all(c["exit_event"] == "return_or_unwind" for c in obs.calls)
    with pytest.raises(ValueError, match="Incomplete"):
        obs.finish()


def test_observer_copy_failure_is_separate_from_success_or_primary(monkeypatch, synthetic_source):
    binding, completed, ctx = graph()
    obs = kinetics.Observation(ctx, binding, completed)
    monkeypatch.setattr(
        obs, "observe", lambda *a: (_ for _ in ()).throw(TypeError("synthetic capture"))
    )
    with obs:
        synthetic_dispatch(ctx.sim, ctx.phase, ctx.p)
    assert obs.errors and obs.normal_exit is True
    with pytest.raises(ValueError, match="Incomplete"):
        obs.finish()
    primary = KeyError("source primary")
    with pytest.raises(KeyError) as caught, obs:
        raise primary
    assert caught.value is primary and obs.restored is True


@pytest.mark.parametrize(
    "fault", ["phase", "run-sim", "p", "configuration", "INIT-cache", "INIT-rate"]
)
def test_warm_entry_requires_actual_phase_configuration_and_retained_cache(synthetic_source, fault):
    binding, completed, ctx = graph()
    if fault == "phase":
        ctx.phase.kind = "INIT"
    elif fault == "run-sim":
        ctx.p._run_sim = False
    elif fault == "p":
        ctx.phase.p = copy.deepcopy(ctx.p)
    elif fault == "configuration":
        ctx.p.network_config = copy.deepcopy(ctx.p.network_config)
        ctx.p.network_config["biomolecules"][0]["Dm"] = 1.0
    elif fault == "INIT-cache":
        ctx.sim.molecules.core.molecules["X"].c_cells[0] = 2
    else:
        ctx.sim.molecules.core.molecules["X"].r_decay = 1.0
    with pytest.raises(ValueError):
        kinetics.Observation(ctx, binding, completed)


def parent_graph(binding, completed, ctx, receipt):
    setup = dict(kinetic_reload_complete=receipt)
    cache = dict(
        handlers={
            role: dict(
                cache=dict(
                    wire=dict(
                        molecule_fields={
                            n: copy.deepcopy(vars(m))
                            for n, m in getattr(ctx.sim, role).core.molecules.items()
                        }
                    )
                )
            )
            for role in kinetics.ROLES
        }
    )
    phase = plain_record(lifecycle.init.Binding, setup_receipt=dict(source_setup=setup))
    active = plain_record(
        lifecycle.init.State,
        clock=plain_record(lifecycle.init.Clock, call_index=0),
        network=plain_record(network.NetworkState, network_cache=cache),
    )
    return lifecycle.SimPhase(
        binding.identity, completed, phase, active, dict(source_setup=setup), "unowned-parent"
    )


def test_closed_codec_transports_kinetic_binding_receipt_arrays_and_alias_without_replay(
    monkeypatch, synthetic_source, tmp_path
):
    binding, completed, ctx, _, receipt = observe(monkeypatch)
    completed = replace(completed, binding=replace(completed.binding, material_binding=None))
    parent = parent_graph(binding, completed, ctx, receipt)
    tree, data = packed((binding, parent))
    decoded_binding, decoded = codec.decode(tree, data)
    assert codec.fingerprint((binding, parent)) == codec.fingerprint((decoded_binding, decoded))
    assert (
        decoded.receipt["source_setup"]["kinetic_reload_complete"]
        is decoded.phase_binding.setup_receipt["source_setup"]["kinetic_reload_complete"]
    )
    assert kinetics.resolve(decoded_binding, decoded)["capture_complete"] is True
    route.preparation.archives.write_archive(
        tmp_path / "synthetic-codec",
        dict(
            tree=tree,
            graph_sha256=codec.fingerprint((decoded_binding, decoded)),
            synthetic_only=True,
            actual_source_entries=0,
            scientific_acceptance=False,
        ),
    )
    (tmp_path / "closed-arrays.npz").write_bytes(data)


@pytest.mark.parametrize(
    "fault", ["identity", "source", "capture", "before", "after", "runtime", "secondary"]
)
def test_resolver_rejects_changed_or_resealed_rate_and_parent_evidence(
    monkeypatch, synthetic_source, fault
):
    binding, completed, ctx, _, receipt = observe(monkeypatch)
    parent = parent_graph(binding, completed, ctx, receipt)
    altered = lifecycle.ions.data(receipt)
    if fault == "identity":
        altered["identity"] = "foreign"
    elif fault == "source":
        altered["source_complete_INIT_identity"] = "foreign"
    elif fault == "capture":
        altered["capture_errors"] = [dict(stage="capture", message="missing")]
    elif fault in ("before", "after"):
        altered[fault]["molecules"]["X"]["rates"]["production rate"] += 1
    elif fault == "runtime":
        parent.active.network.network_cache["handlers"]["molecules"]["cache"]["wire"][
            "molecule_fields"
        ]["X"]["r_decay"] += 1
    else:
        other = lifecycle.ions.data(receipt)
        other["after"]["molecules"]["X"]["rates"]["production rate"] += 1
        parent.phase_binding.setup_receipt["source_setup"] = dict(kinetic_reload_complete=other)
    if fault != "identity":
        altered["identity"] = lifecycle.ions.digest(
            {k: v for k, v in altered.items() if k != "identity"}
        )
    # Replace the outer copy only; legitimate secondary alias stays intact.
    parent = replace(
        parent,
        receipt=dict(source_setup=dict(kinetic_reload_complete=lifecycle.ions.freeze(altered))),
    )
    with pytest.raises(ValueError):
        kinetics.resolve(binding, parent)


@pytest.mark.parametrize("gates", [("0", "0"), ("1", "0"), ("0", "1")])
def test_release_gates_precede_any_output_or_parent_work(monkeypatch, tmp_path, gates):
    for name, value in zip(route.RELEASES, gates, strict=True):
        monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match="releases"):
        route.actual_continuity(tmp_path / "held", changes=[change()], provenance="held", cut=1)
    assert not (tmp_path / "held").exists()


def test_missing_real_parent_retains_failure_without_any_model_entry(monkeypatch, tmp_path):
    for name in route.RELEASES:
        monkeypatch.setenv(name, "1")
    path = tmp_path / "missing-parent"
    with pytest.raises(ValueError, match="actual retained INIT"):
        route.actual_continuity(path, changes=[change()], provenance="held", cut=1)
    failure = json.loads((path / "failure/data.json").read_text())
    assert "Missing actual retained INIT" in json.dumps(failure)
    attempts = json.loads((path / "attempts.json").read_text())
    assert len(attempts["attempts"]) == 1 and attempts["invocations"] == {}


def test_setup_and_transition_hooks_keep_explicit_and_legacy_routes_separate():
    # Structural integration control; actual producers remain forbidden.
    from pathlib import Path

    transition = Path(lifecycle.__file__).read_text()
    setup = Path(lifecycle.setup.__file__).read_text()
    assert "kinetic_reload.selection(binding.inputs)" in transition
    assert "source_binding.event_owner_inputs is not None" in setup
    assert "kinetic_reload.selection(raw)" in setup


def parent_pair(count=1):
    _, completed, _ = graph()
    calendar = plain_record(route.run.calendars.NativePhaseCalendar, phase="INIT", step_count=count)
    owner = replace(completed.binding, calendar=calendar, call_limit=count)
    active = replace(
        completed.parent,
        binding_identity=owner.identity,
        status="exhausted",
        clock=plain_record(lifecycle.init.Clock, call_index=count),
    )
    binding = route.run.Binding(owner, None, "outer-INIT")
    parent = plain_record(
        route.run.RunState,
        active=active,
        binding_identity=binding.identity,
        identity="outer-parent",
        status="exhausted",
    )
    return binding, parent


@pytest.mark.parametrize("count", [0, 1, 3])
def test_structural_parent_check_does_not_admit_or_construct_an_INIT(count):
    binding, parent = parent_pair(count)
    value = route.preflight(
        binding,
        parent,
        expected_binding_identity="outer-INIT",
        expected_parent_identity="outer-parent",
    )
    assert value["numeric_admission"] is False and value["cursor"] == count


@pytest.mark.parametrize(
    "fault",
    [
        "binding-none",
        "dictionary",
        "SIM",
        "paused",
        "failed",
        "capped",
        "cursor",
        "limit",
        "boolean",
        "binding-id",
        "parent-id",
        "active-owner",
    ],
)
def test_real_parent_preflight_refuses_before_native_or_numeric_work(fault):
    binding, parent = parent_pair()
    if fault == "binding-none":
        binding = None
    elif fault == "dictionary":
        parent = {"status": "exhausted"}
    elif fault == "SIM":
        binding = replace(
            binding,
            composition=replace(
                binding.composition, calendar=replace(binding.composition.calendar, phase="SIM")
            ),
        )
    elif fault in ("paused", "failed", "capped"):
        parent = replace(parent, status=fault)
    elif fault in ("cursor", "boolean"):
        parent = replace(
            parent,
            active=replace(
                parent.active,
                clock=replace(parent.active.clock, call_index=0 if fault == "cursor" else True),
            ),
        )
    elif fault == "limit":
        binding = replace(binding, composition=replace(binding.composition, call_limit=0))
    elif fault == "binding-id":
        binding = replace(binding, identity="foreign")
    elif fault == "parent-id":
        parent = replace(parent, identity="foreign")
    else:
        parent = replace(parent, active=replace(parent.active, binding_identity="foreign"))
    with pytest.raises(ValueError):
        route.preflight(
            binding,
            parent,
            expected_binding_identity="outer-INIT",
            expected_parent_identity="outer-parent",
        )


@pytest.mark.parametrize(
    "fault", ["growth-duplicate", "growth-order", "owner-omitted", "association"]
)
def test_resealed_both_receipts_still_require_complete_source_order(
    monkeypatch, synthetic_source, fault
):
    binding, completed, ctx, _, receipt = observe(monkeypatch)
    parent = parent_graph(binding, completed, ctx, receipt)
    altered = lifecycle.ions.data(receipt)
    if fault == "growth-duplicate":
        altered["calls"][4]["species"] = "X"
    elif fault == "growth-order":
        altered["calls"][3], altered["calls"][4] = altered["calls"][4], altered["calls"][3]
    elif fault == "owner-omitted":
        altered["before"].pop("grn")
        altered["after"].pop("grn")
    else:
        altered["calls"][1]["association"] = False
    altered["identity"] = lifecycle.ions.digest(
        {k: v for k, v in altered.items() if k != "identity"}
    )
    altered = lifecycle.ions.freeze(altered)
    parent = replace(
        parent,
        receipt=dict(source_setup=dict(kinetic_reload_complete=altered)),
        phase_binding=replace(
            parent.phase_binding,
            setup_receipt=dict(source_setup=dict(kinetic_reload_complete=altered)),
        ),
    )
    with pytest.raises(ValueError):
        kinetics.resolve(binding, parent)


def test_declaration_preserves_template_and_synchronizes_only_actual_rate_carriers(monkeypatch):
    binding, completed, _ = graph()
    template = copy.deepcopy(binding.inputs)
    template.pop(kinetics.KEY)
    template["sim_phase"]["owners"] = lifecycle.ions.data(completed.binding.inputs_raw["owners"])
    original = copy.deepcopy(template)
    seen = []

    def supplied_template(case, actual):
        seen.append((case, actual))
        return copy.deepcopy(template)

    monkeypatch.setattr(route.preparation.fixtures, "sim_inputs", supplied_template)
    raw = route.declaration(
        completed,
        [change("grn", "Y", "decay rate")],
        provenance="synthetic SIM declaration, no admission",
    )
    assert seen == [("zero_INIT_calls", completed)] and kinetics.same(template, original)
    new = lifecycle.Binding(raw, completed.binding.identity, binding.declaration, "synthetic")
    kinetics.check(new, completed)
    assert (
        raw["sim_phase"]["field"]["network"]["configuration"]["biomolecules"][1][
            "growth and decay"
        ]["decay rate"]
        == 0.4
    )


def test_foreign_adopted_dispatcher_is_refused_without_entering_it(monkeypatch):
    monkeypatch.setattr(kinetics.source, "initialize_both", lambda *a, **k: None)
    with pytest.raises(ValueError, match="Foreign"):
        kinetics.source_identity()


@pytest.mark.parametrize("mode", ["selected", "legacy", "primary-failure", "retention-failure"])
def test_real_setup_hook_carries_exact_owners_and_preserves_primary_with_stubbed_warm_source(
    monkeypatch, synthetic_source, mode, tmp_path
):
    binding, completed, ctx = graph()
    ctx.views = {
        role: SimpleNamespace(
            definition=copy.deepcopy(ctx.raw["handlers"][role]["network"]),
            catalog=copy.deepcopy(ctx.raw["handlers"][role]["catalog"]),
        )
        for role in kinetics.ROLES
    }
    ctx.phase.dyna = ctx.sim.dyna = object()
    ctx.sim.vm = np.array([0.0, 0.0])
    for role in kinetics.ROLES:
        getattr(ctx.sim, role).core.channels = {}
        getattr(ctx.sim, role).core.transporters = {}
    reached, passed = {}, []
    cause, primary = KeyError("warm source cause"), OSError("warm source failure")

    def initialized(actual, hook):
        passed.append(actual)
        hook("all", "before_initialize", {})
        synthetic_dispatch(actual.sim, actual.phase, actual.p)
        if mode in ("primary-failure", "retention-failure"):
            raise primary from cause

    def capture(name, value):
        if name == "kinetic_reload_incomplete" and mode == "retention-failure":
            raise PermissionError("secondary diagnostic writer")
        reached[name] = lifecycle.ions.freeze(value)

    monkeypatch.setattr(lifecycle.owners, "initialize", initialized)
    monkeypatch.setattr(lifecycle.owners, "conditional_input", lambda *a: {})
    monkeypatch.setattr(lifecycle.owners, "available", lambda *a: {"synthetic_only": True})
    monkeypatch.setattr(
        lifecycle.catalog, "configure", lambda view, raw: setattr(view, "catalog", raw)
    )
    arguments = {} if mode == "legacy" else dict(source_binding=binding, completed=completed)

    def invoke():
        return lifecycle.setup.reinitialize_owners(
            ctx,
            completed.binding,
            completed.parent,
            binding.inputs["sim_phase"]["owners"],
            capture,
            **arguments,
        )

    if mode in ("primary-failure", "retention-failure"):
        with pytest.raises(OSError) as caught:
            invoke()
        assert caught.value is primary and primary.__cause__ is cause
        assert "kinetic_reload_complete" not in reached
        if mode == "retention-failure":
            assert "retention also failed" in " ".join(primary.__notes__)
        else:
            assert reached["kinetic_reload_incomplete"]["normal_exit"] is False
    else:
        identity = invoke()
        assert all(
            value["owner_retained"] and value["core_retained"] for value in identity.values()
        )
        assert ("kinetic_reload_complete" in reached) is (mode == "selected")
    assert passed == [ctx]
    route.preparation.archives.write_archive(
        tmp_path / "setup-hook",
        lifecycle.ions.data(
            dict(
                mode=mode,
                reached=reached,
                synthetic_only=True,
                actual_native_source_entries=0,
                primary_failure=None
                if mode in ("legacy", "selected")
                else dict(
                    type=type(primary).__name__,
                    message=str(primary),
                    cause_type=type(cause).__name__,
                ),
                scientific_acceptance=False,
            )
        ),
    )
