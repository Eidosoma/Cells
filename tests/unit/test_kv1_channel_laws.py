"""The Kv1 port pilot's five laws (D211, D213; seam F's step 2, docs/CORE_SEAMS_DESIGN.md §8.2 and
§8.6 as amended, the lead's ruling (B) of 18 November 2026), each claim with a planted error it
must catch (D187). Legacy-free: an older family's reference checks, moved beside the laws (D196's
safeguard).

- Each law's kernels match both references: BETSE v1.5.0's unchanged Kv1 classes, run out of
  process in their own environment (validation/betse/kv1_native.py) against the source the Kv1
  protocol pins, and the independent 80-digit Decimal equations (validation/tissue/
  kv1_reference.py), at the protocol's tolerances (planted: a midpoint moved by a part in 10^9,
  and Kv1.1's opening with one power of h);
- each law's kernels are held to the older catalogue's dispatcher, which gathers the same floats:
  bitwise under NumPy, and under JAX within ULP_BOUND, since XLA on CPU rewrites x / constant as
  x * (1/constant) while the dispatcher divides by gathered arrays (planted: a slope moved by one
  ulp, which NumPy's equality refuses, and a midpoint moved by a part in 10^12, beyond the bound);
- the dispatcher, a recorded temporary second form, holds exactly these five laws and takes their
  numbers from their modules, so a new law only ever gets the single form (planted: a sixth law);
- each law is declared on the template, channel codes 5-9 after @3's five, with BETSE as its cited
  source and this file's test, and is registered from @3's row of the model table since @3's
  parser reads its channel table from the law registry (the Kv1 trigger): each the registry's
  own declaration from its module, under its code, while today's five keep their rows and stay
  the full catalogue's (planted: a registry without one of the five).

And the calcium channel law beside them, cav1p2_m2h@1 (docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md
§5.2; code 11, Ca²⁺ at valence 2). It declares no material term, so @3 refuses its populations: the
rows that need an admitted one use a planted twin, its kernels under tests.calcium_twin@1 (code 99),
which declares the term.
- It is declared and registered on @3, its Citation kept as its source, and a definition that names
  it is refused by name (planted, each refused: a material term that is not a name, and a second law
  at its code).
- Its kernels meet the independent 80-digit equations (validation/tissue/cav_reference.py) at 1,801
  voltages, in NumPy and compiled (planted: the 10 mV shift dropped, m³ h for m² h).
- The parser reads each ion's valence from its law, the one authority (planted, each refused by
  name: a law that says Ca is +1, a model whose Ca is +1, and a model without Ca; a law and a model
  that agree on +1 are admitted, so no table holds it).
- A law with an ion outside Na, K and Cl and no material term is refused by name.
- A calcium channel runs on no RK4 grid (planted: a twin that declares the 25 us bound, admitted).
- Its flux, the charge it carries, its transfer and its heat at a state, inward and outward, are the
  constant-field closed form's at valence 2, in 50-digit decimals from the SI constants (planted: a
  law and a model at valence 1, which miss all four).
"""

import dataclasses
import functools
import json
import math
import re
import subprocess
import types
from decimal import Decimal, localcontext
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions import surface_pump_v3_spec as spec3
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.runner import timeline
from cells.laws.channels import (
    cav1p2_m2h,
    kv1_channels,
    kv1p1_mh2,
    kv1p2_mh,
    kv1p3_mh,
    kv1p4_mh,
    kv1p6_mh,
)
from cells.registry import laws as law_registry
from cells.registry.model_table import MODELS
from cells.registry.models import get_model
from validation.tissue import cav_reference, kv1_reference
from validation.tissue import pump_water_fixtures as water_fixtures
from validation.tissue import species_reactions_fixtures as rfx

ROOT = Path(__file__).resolve().parents[2]
BETSE_PYTHON = "/mnt/workspaces/Cells/venv-betse/bin/python"
PROTOCOL = ROOT / "validation/tissue/surface_calcium_kv1_protocol.json"
LAWS = {1: kv1p1_mh2, 2: kv1p2_mh, 3: kv1p3_mh, 4: kv1p4_mh, 6: kv1p6_mh}  # BETSE family -> law
CODES = {kv1p1_mh2: 5, kv1p2_mh: 6, kv1p3_mh: 7, kv1p4_mh: 8, kv1p6_mh: 9}  # @3's channel codes
HOST3 = "cells.resolved_pump_tissue@3"
TODAYS_CODES = {  # Today's five rows, codes 0-4, which the Kv1 laws leave as they were.
    spec3.KV1P5_LAW_ID: 0,
    spec3.KIR2P1_LAW_ID: 1,
    spec3.NAV1P2_LAW_ID: 2,
    spec3.KLEAK_LAW_ID: 3,
    spec3.NALEAK_LAW_ID: 4,
}
RTOL, ATOL = 5e-14, 5e-15  # The Kv1 protocol's source and Decimal tolerances.
ULP_BOUND = 32  # Per-law kernel against the dispatcher under JAX: the largest measured, 32 ulps.
VOLTAGE = np.linspace(-0.12, 0.06, 20001)


def ulps(a, b):
    """The largest distance in units in the last place between two float64 arrays."""
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    return int(np.max(np.abs(a.view(np.int64) - b.view(np.int64))))


@functools.cache
def reference_kinetics(reference, family, voltage):
    """A Decimal reference's (targets, time constants) at one voltage, as floats."""
    return tuple(tuple(map(float, part)) for part in reference.kinetics(voltage, family))


def reference_errors(law, family, voltage, opening=None, reference=kv1_reference):
    """Where a law's kernels leave the Decimal reference (empty: they keep it)."""
    target, tau = law.kinetics(voltage, xp=np)
    rows = [reference_kinetics(reference, family, v) for v in voltage]
    expected = [np.asarray([row[i] for row in rows]).T for i in (0, 1)]
    out = []
    for name, actual, wanted in (("target", target, expected[0]), ("tau", tau, expected[1])):
        if not np.allclose(actual, wanted, rtol=RTOL, atol=ATOL):
            out.append(name)
    gates = np.stack((np.linspace(0.0, 1.0, 101), np.linspace(1.0, 0.0, 101)))
    opened = (opening or law.opening)(gates, xp=np)
    wanted = [float(reference.opening(pair, family)) for pair in gates.T]
    if not np.allclose(opened, wanted, rtol=3e-15, atol=3e-16):
        out.append("opening")
    return out


def _kinetics_with(law, coefficients):
    """A law's kernel reading `coefficients` in place of its module's: a planted kernel, the
    module untouched."""
    kernel = law.kinetics
    planted = types.FunctionType(
        kernel.__code__, {**kernel.__globals__, **coefficients}, "kinetics"
    )
    planted.__kwdefaults__ = kernel.__kwdefaults__
    return planted


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    """BETSE's capture of its unchanged Kv1 classes, out of process in its own environment."""
    output = tmp_path_factory.mktemp("betse") / "native.json"
    script = ROOT / "validation/betse/kv1_native.py"
    child = subprocess.run(
        [BETSE_PYTHON, "-B", str(script), str(output)], capture_output=True, text=True, timeout=120
    )
    assert child.returncode == 0, child.stderr[-2000:]
    return json.loads(output.read_text())


def test_each_kv1_law_matches_its_references(native):
    baseline = json.loads(PROTOCOL.read_text())["source_baseline"]
    assert native["version"] == baseline["version"] == "1.5.0"
    pinned = {name: baseline["sha256"][name] for name in native["source_sha256"]}
    assert native["source_sha256"] == pinned  # The protocol's pinned source, read as data.
    voltage = np.asarray(native["voltage_V"])
    for family, law in LAWS.items():
        row = native["families"][str(family)]
        assert row["powers"] == [1, 2 if family == 1 else 1] and row["ions"] == ["K"]
        for xp, run in ((np, law.kinetics), (jnp, jax.jit(law.kinetics))):
            target, tau = run(voltage) if xp is jnp else run(voltage, xp=np)
            np.testing.assert_allclose(target, row["target"], rtol=RTOL, atol=ATOL)
            np.testing.assert_allclose(tau, row["tau_s"], rtol=RTOL, atol=ATOL)
        assert reference_errors(law, family, voltage) == [], law.LAW_ID
    # Planted: a midpoint moved by a part in 10^9, and Kv1.1's opening with one power of h.
    moved = _kinetics_with(
        kv1p2_mh, {"ACTIVATION": (kv1p2_mh.ACTIVATION[0] * (1 + 1e-9), kv1p2_mh.ACTIVATION[1])}
    )
    planted = types.SimpleNamespace(kinetics=moved, opening=kv1p2_mh.opening)
    assert reference_errors(planted, 2, voltage) == ["target"]
    one_power = lambda gates, *, xp: gates[..., 0, :] * gates[..., 1, :]  # noqa: E731
    assert reference_errors(kv1p1_mh2, 1, voltage, opening=one_power) == ["opening"]


def test_each_kernel_is_held_to_the_catalogue_s_dispatcher():
    gates = np.stack((np.linspace(0.0, 1.0, VOLTAGE.size), np.linspace(1.0, 0.0, VOLTAGE.size)))
    for code, law in enumerate(kv1_channels.LAWS, 6):
        codes = np.full(VOLTAGE.shape, code, np.int64)
        old = kv1_channels.kinetics(VOLTAGE, codes, xp=np)
        new = law.kinetics(VOLTAGE, xp=np)
        assert all(np.array_equal(a, b) for a, b in zip(old, new, strict=True)), law.LAW_ID
        assert np.array_equal(kv1_channels.opening(gates, codes, xp=np), law.opening(gates, xp=np))
        for run_old, run_new in (
            (kv1_channels.kinetics, law.kinetics),
            (jax.jit(kv1_channels.kinetics), jax.jit(law.kinetics)),
        ):
            old = run_old(jnp.asarray(VOLTAGE), jnp.asarray(codes))
            new = run_new(jnp.asarray(VOLTAGE))
            assert max(ulps(a, b) for a, b in zip(old, new, strict=True)) <= ULP_BOUND, law.LAW_ID
        opened = jax.jit(kv1_channels.opening)(jnp.asarray(gates), jnp.asarray(codes))
        assert np.array_equal(opened, jax.jit(law.opening, static_argnames="xp")(gates, xp=jnp))
    # Planted: a slope one ulp away, which NumPy's equality refuses, and a midpoint moved by a part
    # in 10^12, beyond the bound under JAX.
    codes = np.full(VOLTAGE.shape, 6, np.int64)
    slope = kv1p1_mh2.ACTIVATION[1]
    nudged = _kinetics_with(
        kv1p1_mh2, {"ACTIVATION": (kv1p1_mh2.ACTIVATION[0], math.nextafter(slope, 0.0))}
    )
    old = kv1_channels.kinetics(VOLTAGE, codes, xp=np)
    assert not all(np.array_equal(a, b) for a, b in zip(old, nudged(VOLTAGE, xp=np), strict=True))
    shifted = _kinetics_with(
        kv1p1_mh2, {"ACTIVATION": (kv1p1_mh2.ACTIVATION[0] * (1 + 1e-12), slope)}
    )
    old = jax.jit(kv1_channels.kinetics)(jnp.asarray(VOLTAGE), jnp.asarray(codes))
    new = jax.jit(shifted)(jnp.asarray(VOLTAGE))
    assert max(ulps(a, b) for a, b in zip(old, new, strict=True)) > ULP_BOUND


def dispatcher_errors(module, laws):
    """Where the catalogue's Kv1 dispatcher is not the recorded second form of exactly `laws`."""
    out = []
    if tuple(module.LAWS) != tuple(laws):
        out.append(f"its laws are {[m.__name__ for m in module.LAWS]}")
    if sorted(module.KV1_LAWS) != sorted(law.LAW_ID for law in laws):
        out.append(f"its law IDs are {sorted(module.KV1_LAWS)}")
    if max(module.LAW_CODES.values()) != 5 + len(laws):
        out.append("its codes run past the five laws'")
    return out


def test_the_dispatcher_holds_these_five_and_takes_their_numbers():
    five = (kv1p1_mh2, kv1p2_mh, kv1p3_mh, kv1p4_mh, kv1p6_mh)
    assert dispatcher_errors(kv1_channels, five) == []
    for name in ("ACTIVATION", "INACTIVATION"):
        columns = [[vars(law)[name][k] for law in five] for k in (0, 1)]
        assert kv1_channels._columns(name) == columns
    # Planted: a sixth law joined to the dispatcher.
    sixth = types.SimpleNamespace(LAW_ID="kv1p7_mh@1", __name__="kv1p7_mh")
    planted = types.SimpleNamespace(
        LAWS=(*five, sixth),
        KV1_LAWS={**kv1_channels.KV1_LAWS, "kv1p7_mh@1": 7},
        LAW_CODES={**kv1_channels.LAW_CODES, "kv1p7_mh@1": 11},
    )
    assert len(dispatcher_errors(planted, five)) == 3


def kv1_registration_errors(registry):
    """Why `registry` does not hold the Kv1 laws as declared on @3: each its own module's LAW,
    declared by that module, under its code after today's five, which keep their rows."""
    hosted = {law.law_id: law for law in registry.laws(law_registry.CHANNEL_LAW, HOST3)}
    out = [
        f"{law.LAW_ID}: not its module's declaration, from its module"
        for law in CODES
        if hosted.get(law.LAW_ID) is not law.LAW or registry.module(law.LAW_ID) != law.__name__
    ]
    with law_registry.scope(registry):
        codes, rows = spec3.law_codes(), dict(spec3.LAW_CODES)
    if rows != TODAYS_CODES:
        out.append(f"today's five rows are {rows}")
    expected = {**TODAYS_CODES, **{law.LAW_ID: code for law, code in CODES.items()}}
    wrong = {
        law_id: codes.get(law_id) for law_id, code in expected.items() if codes.get(law_id) != code
    }
    if wrong:  # Today's five and the Kv1 laws: later laws take codes of their own.
        out.append(f"@3's codes for {sorted(wrong)} are {wrong}")
    return out


def test_each_law_is_declared_on_the_template_and_held_until_at3_reads_the_registry():
    """Its name is kept from the hold, which ended when @3's parser came to read the registry (the
    Kv1 trigger), so the collected test IDs stay the base's: each law is now registered on @3."""
    hosted = law_registry.active().laws(law_registry.CHANNEL_LAW, HOST3)
    today = {law.code for law in hosted if law.law_id in TODAYS_CODES}
    at3_homes = MODELS["resolved_pump_tissue@3"].law_homes
    for law, code in CODES.items():
        declared = law.LAW
        assert declared.errors() == [] and declared.law_id == law.LAW_ID and declared.code == code
        assert code not in today  # After @3's five, none reused.
        assert declared.gates == ("m", "h") and declared.permeant == (("K", 1, 1.0),)
        assert declared.rk4_step_s == 2.5e-6 and declared.voltage_domain_V == (-0.120, 0.060)
        assert declared.kinetics is law.kinetics and declared.opening is law.opening
        assert declared.provenance == "cited" and "vg_k.py:" in declared.source.place
        (work,) = declared.source.works
        assert work.url == "https://github.com/betsee/betse" and "1.5.0" in work.title
        test_file, test_name = declared.test.split("::")
        assert (ROOT / test_file).resolve() == Path(__file__).resolve()
        assert callable(globals()[test_name])
        # Registered from @3's row of the model table since the Kv1 trigger: a definition may
        # name it, while today's five stay the full catalogue's (LAW_CODES, GATE_COUNTS and
        # LAW_PERMEABILITIES hold their five rows alone).
        assert law.__name__ in at3_homes and law.LAW_ID not in spec3.LAW_CODES
        assert spec3.gate_counts()[law.LAW_ID] == 2
        assert spec3.law_permeabilities()[law.LAW_ID] == (("K", 1.0),)
    assert kv1_registration_errors(law_registry.active()) == []
    assert dict(spec3.GATE_COUNTS) == dict.fromkeys(TODAYS_CODES, 2) | {
        spec3.KLEAK_LAW_ID: 0,
        spec3.NALEAK_LAW_ID: 0,
    }
    # Planted, refused: a registry without one of the five, each other law from its own declarer
    # as the loader registers it.
    active, kept = law_registry.active(), law_registry.LawRegistry()
    for key, law in sorted(active._laws.items()):
        if law is not kv1p3_mh.LAW:
            kept._register(law, active.module(key))
    assert kv1_registration_errors(kept) == [
        f"{kv1p3_mh.LAW_ID}: not its module's declaration, from its module",
        f"@3's codes for {[kv1p3_mh.LAW_ID]} are { ({kv1p3_mh.LAW_ID: None}) }",
    ]


# ------------------------------------------------------------------ the calcium law

TWIN = "tests.calcium_twin@1"
CALCIUM_GATES = (0.2, 0.7)
NO_TERM = (
    "Channel ca_0: {law} carries Ca, which is not Na, K or Cl, and declares no material_term; the "
    "charge rule alone does not hold a scarce ion's amounts"
)


def twin(**changes):
    """A planted law with cav1p2_m2h@1's record and kernels that declares its material term, so @3
    admits its populations (code 99, reserved for plants); `changes` plant the rest."""
    given = dict(law_id=TWIN, code=99, material_term="material_slope_per_s")
    return dataclasses.replace(cav1p2_m2h.LAW, **(given | changes))


def with_laws(*laws):
    return law_registry.scope(law_registry.BUILTIN.extended(*laws))


def calcium_world(law_id=TWIN, *, valence=2, cell_mM=1e-4, bath_mM=1.8, **cell):
    """The heredity cell with calcium (at `valence`) and one population of `law_id` on its patch;
    `cell` goes to the fixture. NaV1.2 is left out, so under RK4 only Kir2.1 and the calcium law
    bound the step."""
    raw = water_fixtures.heredity_cell("D", **(dict(end_time=0.004) | cell))
    raw = rfx.with_charged_trace(
        raw, "Ca", valence, concentrations_mM=dict(cell_0=cell_mM, bath_0=bath_mM)
    )
    m, e = raw["model"], raw["experiment"]
    m["channels"] = [c for c in m["channels"] if c["kinetic_law"] != spec3.NAV1P2_LAW_ID]
    m["channels"].append(
        dict(
            id="ca_0",
            membrane_id=m["membranes"][0]["id"],
            kinetic_law=law_id,
            max_permeability_m_per_s=2e-6,
            abundance=0.5,
            initial_gate=list(CALCIUM_GATES),
            permeant_ions=[dict(species_id="Ca", relative_permeability=1.0)],
        )
    )
    e["channel_controls"] = [
        dict(channel_id=c["id"], schedule=[dict(time=0.0, availability=0.8)]) for c in m["channels"]
    ]
    raw["execution"]["channel_capacity"] = len(m["channels"])
    return raw


def test_the_calcium_law_is_declared_and_registered_on_at3():
    law = cav1p2_m2h.LAW
    assert law.errors() == [] and law.law_id == cav1p2_m2h.LAW_ID
    assert (law.code, law.gates, law.permeant) == (11, ("m", "h"), (("Ca", 2, 1.0),))
    assert law.rk4_step_s is None and law.voltage_domain_V == (-0.120, 0.060)
    assert law.kinetics is cav1p2_m2h.kinetics and law.opening is cav1p2_m2h.opening
    assert law.provenance == "parity" and isinstance(law.source, law_registry.Citation)
    assert "vg_ca.py:292" in law.source.place and "(not read)" in law.source.place
    test_file, test_name = law.test.split("::")
    assert (ROOT / test_file).resolve() == Path(__file__).resolve()
    assert callable(globals()[test_name])
    registry = law_registry.active()
    assert registry.lookup(law.law_id) is law and registry.module(law.law_id) == cav1p2_m2h.__name__
    assert cav1p2_m2h.__name__ in MODELS["resolved_pump_tissue@3"].law_homes
    assert spec3.law_codes()[law.law_id] == 11 and spec3.gate_counts()[law.law_id] == 2
    assert spec3.law_permeabilities()[law.law_id] == (("Ca", 1.0),)
    assert law.law_id not in spec3.LAW_CODES
    # It declares no material term, so a definition that names it is refused (fails closed).
    assert law.material_term is None
    with pytest.raises(ConfigError, match=f"^{re.escape(NO_TERM.format(law=law.law_id))}$"):
        parse_spec(calcium_world(law.law_id))
    for value in ("", 1):  # Planted: a material term that is no name.
        with pytest.raises(ValueError, match="its material_term is named, or None"):
            law_registry.LawRegistry().register(twin(material_term=value))
    with pytest.raises(ValueError, match="channel codes are distinct"):  # Planted: its code taken.
        law_registry.BUILTIN.extended(twin(code=11))


def test_the_calcium_law_meets_its_reference_and_each_plant_misses_it():
    voltage = np.linspace(-0.12, 0.06, 1801)
    check = functools.partial(reference_errors, family="Cav1p2", reference=cav_reference)
    assert check(cav1p2_m2h, voltage=voltage) == []
    compiled = jax.jit(cav1p2_m2h.kinetics)
    jitted = types.SimpleNamespace(
        kinetics=lambda v, *, xp: compiled(v), opening=cav1p2_m2h.opening
    )
    assert check(jitted, voltage=voltage) == []
    # Planted: the 10 mV shift dropped, and m³ h for m² h.
    unshifted = types.SimpleNamespace(
        kinetics=_kinetics_with(cav1p2_m2h, {"SHIFT_V": 0.0}), opening=cav1p2_m2h.opening
    )
    assert check(unshifted, voltage=voltage[::100]) == ["target", "tau"]
    cubed = lambda gates, *, xp: gates[..., 0, :] ** 3 * gates[..., 1, :]  # noqa: E731
    assert check(cav1p2_m2h, voltage=voltage[::100], opening=cubed) == ["opening"]


def test_a_law_is_the_one_authority_for_its_ions_valences():
    univalent = twin(permeant=(("Ca", 1, 1.0),))
    for law, valence in ((twin(), 2), (univalent, 1)):  # No table of valences beside the law's.
        with with_laws(law):
            spec = parse_spec(calcium_world(valence=valence))
        assert spec.model.channels[-1].kinetic_law == TWIN
    magnesium = calcium_world()
    magnesium["model"]["channels"][-1]["permeant_ions"][0]["species_id"] = "Mg"
    own = f"^Channel ion requires its law's species and valence: {TWIN} carries "
    for law, raw, words in (  # Planted, each refused by name.
        (univalent, calcium_world(), "Ca at valence 1, and the model declares it at valence 2$"),
        (
            twin(),
            calcium_world(valence=1),
            "Ca at valence 2, and the model declares it at valence 1$",
        ),
        (
            twin(permeant=(("Mg", 2, 1.0),)),
            magnesium,
            "Mg at valence 2, and the model declares no such species$",
        ),
    ):
        with with_laws(law), pytest.raises(ConfigError, match=own + words):
            parse_spec(raw)


def test_a_law_with_a_scarce_ion_and_no_material_term_is_refused_by_name():
    refusal = f"^{re.escape(NO_TERM.format(law=TWIN))}$"
    with with_laws(twin(material_term=None)), pytest.raises(ConfigError, match=refusal):
        parse_spec(calcium_world())
    with with_laws(twin()):  # The same law with its term, admitted.
        parse_spec(calcium_world())


def test_a_calcium_channel_runs_on_no_rk4_grid():
    raw = calcium_world(dt=2.5e-6, end_time=1e-4, solver="rk4")
    raw["experiment"]["observation_times"] = [0.0, 1e-4]
    refusal = rf"^Resolved gated channels \({TWIN}\) require RK4 steps <= 0 us$"
    with with_laws(twin()), pytest.raises(ConfigError, match=refusal):
        timeline(parse_spec(raw))
    with with_laws(twin(rk4_step_s=25e-6)):  # Planted: the older gated laws' bound, admitted.
        timeline(parse_spec(raw))


def closed_form(cell_mM, bath_mM, voltage_V, temperature_K, area_m2, permeability_m_s, valence):
    """(outward flux in fmol/s, its current in A, its heat in pJ/s) of one ion's constant-field
    flux, in 50-digit decimals from the SI constants and the floats' exact values."""
    with localcontext() as context:
        context.prec = 50
        avogadro = Decimal("6.02214076e23")
        faraday = avogadro * Decimal("1.602176634e-19")
        gas = avogadro * Decimal("1.380649e-23")
        inside, outside, v, t = map(Decimal, (cell_mM, bath_mM, voltage_V, temperature_K))
        x = valence * faraday * v / (gas * t)
        weight = lambda y: y / (y.exp() - 1)  # noqa: E731  B(y)
        scale = Decimal("1e15") * Decimal(area_m2) * Decimal(permeability_m_s)
        flux = scale * (inside * weight(-x) - outside * weight(x))
        drop = gas * t * (inside / outside).ln() + valence * faraday * v
        return flux, Decimal("1e-15") * faraday * valence * flux, Decimal("1e-3") * flux * drop


def calcium_errors(spec, valence=2):
    """(which of the flux, the current, the transfer and the heat at the world's start leave the
    closed form at `valence`, the flux's sign). What the cell loses the bath takes, exactly, and the
    heat is positive."""
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    controls = spec3.control_values(spec, [0.0])
    control = type(controls)(*(c[0] for c in controls))
    ca = spec.model.species_ids.index("Ca")
    slot = [c.id for c in spec.model.channels].index("ca_0")
    closed = control.channel.copy()
    closed[slot] = 0.0
    on = model.readouts(state, control, p, xp=np)
    off = model.readouts(state, control._replace(channel=closed), p, xp=np)
    rate = on.derivative
    moved = float(rate.channel_transferred[ca, slot])
    assert moved == -rate.amount_increment[ca, 0] == -rate.reservoir_supplied[ca, 0]
    heat = float(rate.channel_dissipated_energy_pJ[ca, slot])
    assert heat > 0
    (patch,) = spec.model.membranes
    m, h = CALCIUM_GATES
    flux, current, dissipated = closed_form(
        float(p.amount_reference[ca, 0] / p.volume[0]),
        float(p.extracellular_amount_reference[ca, 0] / p.extracellular_volume[0]),
        float(on.field.rates.membrane_voltage_V[0]),
        spec.model.temperature_K,
        patch.area_m2,
        2e-6 * 0.5 * 0.8 * (m * m * h),
        valence,
    )
    carried = on.field.rates.membrane_current_A[0] - off.field.rates.membrane_current_A[0]
    found = dict(
        flux=(on.channel_flux_fmol_s[ca, slot], flux, 1e-13),
        current=(carried, current, 1e-9),  # A difference of two readings of the patch's current.
        transfer=(moved, flux, 1e-13),
        heat=(heat, dissipated, 1e-13),
    )
    wrong = [
        name
        for name, (value, wanted, bound) in found.items()
        if abs(float(Decimal(float(value)) / wanted - 1)) > bound
    ]
    return wrong, np.sign(moved)


@pytest.mark.parametrize("direction, cell_mM, bath_mM", [(-1, 1e-4, 1.8), (1, 1.0, 0.05)])
def test_the_calcium_flux_charge_transfer_and_heat_are_the_closed_forms(
    direction, cell_mM, bath_mM
):
    """At the start of the planted twin's world, on the host. `direction` is the flux's sign,
    outward positive."""
    given = dict(cell_mM=cell_mM, bath_mM=bath_mM)
    with with_laws(twin()):
        assert calcium_errors(parse_spec(calcium_world(**given))) == ([], direction)
    with with_laws(twin(permeant=(("Ca", 1, 1.0),))):  # Planted: z = 1.
        wrong, _ = calcium_errors(parse_spec(calcium_world(valence=1, **given)))
    assert wrong == ["flux", "current", "transfer", "heat"]
