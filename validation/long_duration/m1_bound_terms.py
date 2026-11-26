"""M1: @3's explicit bound per world, term by term (REGISTRATION_20261118.md §3).

Host-side, at the definitions alone. For each world:

* today's definition-time terms (models/surface_pump_v3.StepChecks, on @3's channel-free
  projection): F, J and M recomputed from surface_pump.explicit_rate_bound's formulas on the
  bound's own layout; N and Z the engine's own functions; Ca, K and G the step checks' own;
* today's run-time terms at the declared initial state under the t = 0 controls: Mc
  (surface_pump_v3.membrane_rate) and Kc (material_rate; None without a kind);
* Cm, reported for N2 and not in today's bound: N's formula over every species (this
  registration's reading, S), with its charged part Cm_z and, as a labelled extra, the same with
  the channel populations' open permeabilities at the initial state;
* for a composite, its operators' declared conditions (the coupling's k_on + k_off per state).

The criteria C1.1 (bitwise reproduction), C1.2 (the step checks admit 0.999 dt_def and refuse
1.001 dt_def with the binding check's message) and C1.3 (Mc from the engine's function) are
evaluated and recorded; the readings follow §3. Stage 0 makes no qualification claim.

Usage: python -m validation.long_duration.m1_bound_terms OUTPUT.json
"""

import json
import math
import sys
import time

import numpy as np

EXPLICIT_MESSAGE = "IMEX step exceeds the explicit-rate stability bound"
CALCIUM_MESSAGE = "IMEX step exceeds the explicit calcium pump rate bound"
KIND_MESSAGE = "IMEX step exceeds a declared kind's explicit-rate bound"
GATE_MESSAGE = "Resolved junction step exceeds conservative kinetic bound"
DEFINITION_TERMS = ("F", "J", "M", "N", "Z", "Ca", "K", "G")
EXPLICIT_TERMS = ("F", "J", "M", "N", "Z")  # explicit_rate_bound's five.
MESSAGES = dict(
    F=EXPLICIT_MESSAGE,
    J=EXPLICIT_MESSAGE,
    M=EXPLICIT_MESSAGE,
    N=EXPLICIT_MESSAGE,
    Z=EXPLICIT_MESSAGE,
    Ca=CALCIUM_MESSAGE,
    K=KIND_MESSAGE,
    G=GATE_MESSAGE,
)


def inner_spec(spec):
    """The cells.model.resolved_pump_tissue@3 definition of a composite (its projection), or the spec."""
    from cells.definitions import pump_composite_spec as cs

    if spec.model.__class__.__name__ == "CompositeModel":
        return cs.projection(spec)
    return spec


def explicit_terms(base):
    """F, J, M, N and Z (1/s) on the channel-free definition `base`, as explicit_rate_bound
    computes them: the same layout, the same operations in the same order."""
    from cells.laws.electrochemistry import F, R
    from cells.models import surface_kinetic as kinetic
    from cells.models import surface_pump as first
    from cells.numerics.extracellular_field import scatter

    _, p = kinetic.initial_values(base)
    z2 = p.valence**2
    volume = np.where(p.outside_active & ~p.reservoir, p.extracellular_volume * 1e-15, np.inf)
    zero = np.zeros((len(z2), p.outside_active.size))
    rows = scatter(p.face_factor, zero, (p.face_sender,), xp=np)
    rows += scatter(p.face_factor, zero, (p.face_receiver,), xp=np)
    face = 2 * np.max(rows / volume, initial=0.0)
    ci = np.where(p.active, p.amount_reference / p.volume, 0.0)
    co = np.where(p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 0.0)
    slope = F * F / (R * p.temperature)
    capacitance = scatter(
        p.membrane_capacitance, np.zeros(p.active.size), (p.membrane_cell,), xp=np
    )
    capacitance = np.where(p.active, capacitance, np.inf)
    gj = (
        slope
        * np.sum(
            z2
            * p.junction_permeability
            * np.maximum(ci[:, p.junction_sender], ci[:, p.junction_receiver]),
            axis=0,
        )
        * np.where(p.junction_active, p.junction_area, 0.0)
    )
    cells = scatter(gj, np.zeros(p.active.size), (p.junction_sender,), xp=np)
    cells += scatter(gj, np.zeros(p.active.size), (p.junction_receiver,), xp=np)
    gm = (
        slope
        * np.sum(
            z2
            * p.membrane_permeability
            * np.maximum(ci[:, p.membrane_cell], co[:, p.membrane_outside]),
            axis=0,
        )
        * np.where(p.membrane_active, p.membrane_area, 0.0)
    )
    membranes = scatter(gm, np.zeros(p.active.size), (p.membrane_cell,), xp=np)
    return dict(
        F=face,
        J=2 * np.max(cells / capacitance),
        M=np.max(membranes / capacitance),
        N=first.neutral_material_rate(p, volume),
        Z=first.face_free_node_rate(base, p, gm),
    )


def material_terms(base, channel_permeability=None):
    """Cm (1/s, S): N's formula, 2 max over species and nodes of sum P A / V over junction and
    membrane routes, applied to every species; Cm_z the same over charged species only. With
    channel_permeability [species, membrane] (m/s), that is added to the patches' (the
    labelled extra)."""
    from cells.models import surface_kinetic as kinetic
    from cells.numerics.extracellular_field import scatter

    _, p = kinetic.initial_values(base)
    outside_volume = np.where(
        p.outside_active & ~p.reservoir, p.extracellular_volume * 1e-15, np.inf
    )
    species = np.asarray(p.valence).reshape(-1).size
    cell_volume = np.where(p.active, p.volume * 1e-15, np.inf)
    membrane_permeability = np.asarray(p.membrane_permeability, dtype=float)
    if channel_permeability is not None:
        membrane_permeability = membrane_permeability + channel_permeability
    pj = p.junction_permeability * np.where(p.junction_active, p.junction_area, 0.0)
    pm = membrane_permeability * np.where(p.membrane_active, p.membrane_area, 0.0)
    cells = scatter(pj, np.zeros((species, p.active.size)), (p.junction_sender,), xp=np)
    cells += scatter(pj, np.zeros((species, p.active.size)), (p.junction_receiver,), xp=np)
    cells += scatter(pm, np.zeros((species, p.active.size)), (p.membrane_cell,), xp=np)
    outside = scatter(pm, np.zeros((species, p.outside_active.size)), (p.membrane_outside,), xp=np)
    rates = np.concatenate((cells / cell_volume, outside / outside_volume), axis=1)
    charged = np.asarray(p.valence).reshape(-1) != 0
    return (
        2 * float(np.max(rates, initial=0.0)),
        2 * float(np.max(rates[charged], initial=0.0)) if charged.any() else 0.0,
    )


def channel_open_permeability(state, control, p):
    """[species, membrane] (m/s): each population's P r a o v at the initial state under the
    t = 0 control, summed per patch (the channels' share of membrane_rate's slope, without its
    concentration factor)."""
    from cells.models import surface_pump_v3 as v3
    from cells.numerics.extracellular_field import scatter

    open_fraction = np.where(
        p.channel_active,
        p.channel_abundance * v3.channel_opening(state.channel_gate, p.channel_laws, xp=np),
        0.0,
    )
    per_population = (
        p.channel_permeability * p.channel_relative_permeability * open_fraction * control.channel
    )
    zero = np.zeros((per_population.shape[0], p.membrane_active.size))
    return scatter(per_population, zero, (p.channel_membranes,), xp=np)


def initial_control(spec):
    from cells.execution.schedule import control_values

    controls = control_values(spec, [0.0])
    return type(controls)(*(np.asarray(v[0], dtype=float) for v in controls))


def step_refusal(checks, step):
    """None if the step checks admit a step of `step` s, else the refusal's message."""
    from cells.definitions.specs import ConfigError

    try:
        checks(np.array([step]))
    except ConfigError as error:
        return str(error)
    return None


def operator_conditions(raw):
    """A composite's declared operator conditions: the coupling's k_on + k_off per state
    (dt (k_on + k_off) <= 1, ruling 5). Turnover is exact at any step and has none."""
    out = {}
    for block in raw["model"].get("operators", []):
        if block.get("law") == "cells.operator.species_regulated_availability@1":
            for s in block["states"]:
                out[f"coupling:{s['id']}"] = float(s["on_rate_per_s"] + s["off_rate_per_s"])
    return out


def gate_formula(inner):
    """The junction-gate term by its formula, 1.3 exp(77 threshold) + 20 (1/s), over the gated
    junctions (minimum open fraction below 1), with the registered E07 value for comparison."""
    from validation.long_duration import worlds

    gated = [j for j in inner.model.junctions if j.minimum_open_fraction < 1]
    if not gated:
        return None
    thresholds = sorted({float(j.threshold_voltage_V) for j in gated})
    rate = max(1.3 * math.exp(77 * t) + 20 for t in thresholds)
    registered = worlds.registration()["m1"]["e07_gate_rate_per_s_by_formula"]
    return dict(
        gated_junctions=len(gated),
        thresholds_V=thresholds,
        rate_by_formula_per_s=rate,
        registered_e07_rate_per_s=registered,
        step_admitted_s=worlds.registration()["m1"]["gate_step_bound"] / rate,
    )


def measure(raw):
    """Every §3 quantity of one world, with C1.1-C1.3 evaluated."""
    from cells.definitions import surface_pump_v3_spec as v3spec
    from cells.definitions.specs import parse_spec
    from cells.models import surface_pump as first
    from cells.models import surface_pump_v2 as second
    from cells.models import surface_pump_v3 as v3
    from validation.long_duration import worlds

    started = time.perf_counter()
    spec = parse_spec(raw)
    inner = inner_spec(spec)
    base = v3spec.projection(inner)
    checks = v3.bind_step_checks(inner)
    terms = explicit_terms(base)
    terms["Ca"] = second.calcium_rate_bound(base)
    terms["K"] = checks.kind_rate
    terms["G"] = first.junction_gate_rate_bound(inner)
    engine = dict(
        explicit_rate_bound=first.explicit_rate_bound(base),
        calcium_rate_bound=checks.calcium_rate,
        kind_rate=checks.kind_rate,
        junction_gate_rate_bound=checks.junction_rate,
    )
    c11 = dict(
        explicit=bool(max(terms[k] for k in EXPLICIT_TERMS) == engine["explicit_rate_bound"]),
        calcium=bool(terms["Ca"] == engine["calcium_rate_bound"]),
        kind=bool(terms["K"] == engine["kind_rate"]),
        gate=bool(terms["G"] == engine["junction_gate_rate_bound"]),
    )
    state, p = v3.initial_values(inner)
    control = initial_control(inner)
    with np.errstate(all="ignore"):
        mc = float(v3.membrane_rate(state, control, p, xp=np))
        kc = v3.material_rate(state, control, p, xp=np)
    cm, cm_z = material_terms(base)
    cm_ch, cm_ch_z = material_terms(base, channel_open_permeability(state, control, p))
    reported = dict(Cm=cm, Cm_z=cm_z, Cm_with_channels=cm_ch, Cm_with_channels_z=cm_ch_z)
    operators = operator_conditions(raw)
    bound = dict(explicit=first.EXPLICIT_STEP_BOUND, gate=first.GATE_STEP_BOUND)

    def limit(name, rate):
        b = bound["gate"] if name == "G" else bound["explicit"]
        return math.inf if not rate else b / rate

    rates = {k: float(v) for k, v in terms.items()} | {"Mc": mc}
    if kc is not None:
        rates["Kc"] = float(kc)
    rates |= {k: float(v) for k, v in reported.items()}
    rates |= operators
    limits = {k: limit(k, v) for k, v in rates.items()}
    dt_world = float(spec.execution.dt)
    definition = {k: limits[k] for k in DEFINITION_TERMS}
    dt_def = min(definition.values())
    binding_def = min(definition, key=definition.get)
    today_terms = [*DEFINITION_TERMS, "Mc", *(["Kc"] if kc is not None else [])]
    today = {k: limits[k] for k in today_terms}
    admitted = step_refusal(checks, 0.999 * dt_def)
    refused = step_refusal(checks, 1.001 * dt_def)
    c12 = dict(
        dt_def_s=dt_def,
        binding=binding_def,
        admits_0p999=admitted is None,
        refusal_at_1p001=refused,
        refusal_message_expected=MESSAGES[binding_def],
        passed=bool(admitted is None and refused == MESSAGES[binding_def]),
    )
    registered = worlds.registration()["m1"]
    stays = [k for k in registered["n2_stays"] if k != "operators"] + list(operators)
    readings = {}
    for name in ("primary", "alternative"):
        reading = registered[f"n2_{name}"]
        kept = [k for k in stays if k in limits] + [k for k, v in reading.items() if v == "stays"]
        n2 = {k: limits[k] for k in kept}
        dt_n2 = min(n2.values())
        readings[name] = dict(
            kept=sorted(kept),
            dt_N2_s=dt_n2,
            binding=min(n2, key=n2.get),
            gain_over_world=dt_n2 / dt_world,
            gain_over_today=dt_n2 / min(today.values()),
            reaches_illustrative_cuts={
                str(c): bool(dt_n2 / dt_world >= c) for c in registered["illustrative_cuts"]
            },
        )
    return dict(
        model=raw["model"]["id"],
        inner_model=getattr(spec.model, "inner_model", raw["model"]["id"]),
        dt_world_s=dt_world,
        rates_per_s=rates,
        dt_times_rate={k: dt_world * v for k, v in rates.items()},
        step_admitted_by_term_s=limits,
        dt_today_s=min(today.values()),
        binding_today=min(today, key=today.get),
        dt_definition_s=dt_def,
        binding_definition=binding_def,
        n2=readings,
        criteria=dict(
            C1_1=dict(c11, engine=engine, passed=all(c11.values())),
            C1_2=c12,
            C1_3=dict(source="surface_pump_v3.membrane_rate", Mc_per_s=mc, passed=True),
        ),
        junction_gate_formula=gate_formula(inner),
        host_seconds=time.perf_counter() - started,
    )


def run(output):
    import jax

    jax.config.update("jax_enable_x64", True)
    from validation.long_duration import worlds

    started = time.perf_counter()
    out = dict(
        measurement="M1",
        registration=worlds.registration()["registration"],
        qualification_claim="none (stage 0; amendment 1, Q1)",
        worlds={},
    )
    for name, raw in worlds.m1_worlds().items():
        out["worlds"][name] = measure(raw)
        print(name, json.dumps(out["worlds"][name]["criteria"]), flush=True)
    passed = all(
        w["criteria"]["C1_1"]["passed"] and w["criteria"]["C1_2"]["passed"]
        for w in out["worlds"].values()
    )
    out["criteria_passed"] = passed
    out["host_seconds"] = time.perf_counter() - started
    with open(output, "x") as stream:
        json.dump(out, stream, indent=1)
        stream.write("\n")
    print("criteria passed" if passed else "criteria FAILED", flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(run(sys.argv[1]))
