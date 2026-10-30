"""Independent Decimal/Fraction temperature/cache/clock replay, no array imports."""

import hashlib
import json
import math
from decimal import Decimal, localcontext
from fractions import Fraction

from validation.betse.betse_fast_solver_reference import coefficients as cache_coefficients
from validation.betse.betse_fast_solver_reference import serial
from validation.perturbations.physiology_calendar_reference import evaluate as phase_calendar

LAW = "betse_temperature_calendar_source_v1_5_0@1"


def _finite(value):
    if isinstance(value, dict):
        return all(_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite(item) for item in value)
    return value is None or math.isfinite(float(value))


def d(value):
    return Decimal.from_float(float(value))


def _authenticate(record):
    raw = dict(record)
    identity = raw.pop("identity")
    actual = hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    if actual != identity:
        raise ValueError("Independent source declaration identity mismatch")


def _temperature(program, old, time_s, base):
    if not program["events"]:
        return old
    row = program["events"][0]
    gain = Decimal(10) / d(row["change_s"])
    first = 1 / (1 + (-gain * (d(time_s) - d(row["on_s"]))).exp())
    last = 1 / (1 + (-gain * (d(time_s) - d(row["off_s"]))).exp())
    return float(d(base) * (1 + d(row["amplitude"]) * (first - last)))


def _gates(g, old, duration):
    dt, phi = d(duration) * d(g["time_unit"]), d(g["Phi"])
    mn, hn, md, hd, mln, mld = [], [], [], [], [], []
    for i in range(len(g["owner_ids"])):
        mt, ht, mlt = (
            d(g[key][i]) for key in ("hh_m_tau_native", "hh_h_tau_native", "ml_tau_native")
        )
        mn.append(mt * d(old["hh_m"][i]) + dt * d(g["hh_m_inf"][i]))
        hn.append(ht * d(old["hh_h"][i]) + dt * d(g["hh_h_inf"][i]))
        md.append(mt + dt)
        hd.append(ht + dt)
        mln.append(d(old["ml_m"][i]) + dt * phi * d(g["ml_m_inf"][i]) / mlt)
        mld.append(1 + dt * phi / mlt)
    arithmetic = dict(
        duration_native_units=dt,
        hh_m_numerator=mn,
        hh_h_numerator=hn,
        hh_m_denominator=md,
        hh_h_denominator=hd,
        ml_numerator=mln,
        ml_denominator=mld,
    )
    values = dict(
        hh_m=[float(a / b) for a, b in zip(mn, md, strict=True)],
        hh_h=[float(a / b) for a, b in zip(hn, hd, strict=True)],
        ml_m=[float(a / b) for a, b in zip(mln, mld, strict=True)],
    )
    return values, serial(arithmetic)


def _probes(raw, cache, temperature):
    material = raw["material"]
    p, ions = material["parameters"], material["ions"]
    m = len(material["geometry"]["membrane_ids"])
    r, f, q, kb, configured = (
        d(p[key]) for key in ("R_J_mol_K", "F_C_mol", "q_C", "kb_J_K", "configured_temperature_K")
    )
    t = d(temperature)
    # Preserve native binary64 in-place nonce addition before independent algebra.
    vm = [float(v + 1e-25) for v in raw["membrane_voltage_V"]]
    vj = [float(v + 1e-25) for v in raw["junction_voltage_V"]]
    used_z = [float(v + 1e-25) for v in ions["valence"]]
    ma, ja, np_alpha, cond = [], [], [], []
    for i, name in enumerate(ions["ids"]):
        z = d(ions["valence"][i])
        ma.append([d(used_z[i]) * d(v) * f / (r * t) for v in vm])
        ja.append([d(used_z[i]) * d(v) * f / (r * configured) for v in vj])
        np_alpha.append([d(ions["free_diffusion_m2_s"][i]) * z * q / (kb * t)] * m)
        cond.append(
            [
                d(ions["membrane_diffusion_m2_s"][i][j])
                * q
                * z**2
                * f
                * cache["ion_mean_mol_m3"][name][j]
                / (d(p["membrane_thickness_m"]) * kb * configured)
                for j in range(m)
            ]
        )
    return serial(
        dict(
            membrane_electroflux_alpha=ma,
            configured_junction_electroflux_alpha=ja,
            live_nernst_planck_alpha=np_alpha,
            configured_conductivity_S_m2=cond,
            configured_normal_sigma_S_m=cache["sigma_cell_S_m"],
            membrane_voltage_after_nonce_V=vm,
            junction_voltage_after_nonce_V=vj,
            valence_after_nonce=[[value] * m for value in used_z],
        )
    )


def evaluate(inputs, *, precision=125):
    if precision not in (125, 170):
        raise ValueError("Require the two declared independent reference precisions")
    raw, calendar, program = (inputs[key] for key in ("raw", "calendar", "program"))
    _authenticate(calendar)
    _authenticate(program)
    if (
        calendar["phase"] not in ("INIT", "SIM")
        or not 0 <= calendar["step_count"] <= 64
        or program["membrane_ids"] != raw["material"]["geometry"]["membrane_ids"]
        or raw["clock_probes"]["owner_ids"] != program["membrane_ids"]
        or len(program["events"]) > 1
        or any(row["kind"] != "temperature" for row in program["events"])
    ):
        raise ValueError("Independent original clock/owner/source scope mismatch")
    with localcontext() as context:
        context.prec = precision
        cache, _ = cache_coefficients(raw["material"])
        phase = phase_calendar(calendar)
        gate = raw["clock_probes"]
        state = dict(
            temperature_K=raw["material"]["parameters"]["temperature_K"],
            hh_m=list(gate["initial_hh_m"]),
            hh_h=list(gate["initial_hh_h"]),
            ml_m=list(gate["initial_ml_m"]),
        )
        if raw["entry_mode"] == "fresh_configured_copy":
            state["temperature_K"] = raw["material"]["parameters"]["configured_temperature_K"]
        frames = []
        for i, label in enumerate(phase["event_label_s"]):
            next_state, arithmetic = dict(state), None
            enabled = calendar["phase"] == "SIM"
            if enabled:
                next_state["temperature_K"] = _temperature(
                    program,
                    state["temperature_K"],
                    label,
                    raw["material"]["parameters"]["configured_temperature_K"],
                )
                evolved, arithmetic = _gates(gate, state, calendar["dt_s"])
                next_state.update(evolved)
            temperature = next_state["temperature_K"]
            positive = math.isfinite(temperature) and temperature > 0
            probes = _probes(raw, cache, temperature) if positive else None
            finite_gate = _finite(arithmetic) and _finite(
                {key: next_state[key] for key in ("hh_m", "hh_h", "ml_m")}
            )
            admissible = positive and finite_gate and _finite(probes)
            frames.append(
                dict(
                    call_index=i,
                    event_label_s=label,
                    elapsed_start_s=float(Fraction(i) * Fraction(calendar["dt_s"])),
                    elapsed_end_s=float(Fraction(i + 1) * Fraction(calendar["dt_s"])),
                    duration_s=calendar["dt_s"],
                    sampled=phase["sampled"][i],
                    events_enabled=enabled,
                    values=next_state,
                    probes=probes,
                    gate_arithmetic=arithmetic,
                    temperature_positive=positive,
                    gate_arithmetic_finite=finite_gate,
                    admissible=admissible,
                )
            )
            if not admissible:
                break
            state = next_state
        return dict(
            law=LAW,
            precision=precision,
            cache=serial(cache),
            frames=frames,
            calendar=phase,
            endpoint=state,
            first_refused_call_index=(
                frames[-1]["call_index"] if frames and not frames[-1]["admissible"] else None
            ),
            source_discrete_only=True,
            no_new_heat_law=True,
        )
