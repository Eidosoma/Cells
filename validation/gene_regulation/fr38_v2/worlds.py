"""FR-38's second registered comparison: the engine's worlds (SPEC.md §1 and §2; the builder's).

Every value is the builder's transcription of `spec/SPEC.md` (tag
fr38-v2-spec-amendments-2026-11-24), built as Cells definitions with the gene regulation lane's
helpers (validation/gene_regulation/worlds.py: the inert cell, bath and patch, the inventory rows,
the registry's potentials and moieties).

The engine models (protocol §3):
- resolved_pump_composite@1 over resolved_pump_tissue@3;
- templated_polymerisation@1 with §9's release, and neutral_arrival_labels@1 in every labelled run;
- A1's scheduled_species_turnover@1 and species_regulated_availability@2 (arm B);
- local_species_reactions@1 (family C) and ideal_osmosis_linear_compliance_water@1 (family D).

**The hold worlds** (families AF, AN, C and D; `hold`):
- One 1 pL cell holding K and Y at 140 mM, a held 1 pL bath, and a patch with every permeability 0.
- The rows N, M, Pi and the fates R (durable) and R_s (short-lived), with N, M and Pi in mM and the
  fates in copies (1 copy = templated_polymerisation's COPY_FMOL, SPEC.md §0's double).
- The pool `pol` (10^4 copies) and the chain `tx` (one gene copy, L = 1200, 8 stages, 50 nt/s,
  drawing N and releasing 2 Pi per residue, K_N = 0.02 mM). Its release `tx_release`: tau =
  2400 s, H(0) = 160 copies, the machine `returned` or `held`, marked at release, p constant (0 or
  1) or scheduled (0.7, then 0.25 from 2700 s).
- `deg_R` at 1/9000 and `deg_R_s` at 1/1350 per s, each returning L M, with the standard free
  energy the potentials give (a declaration the registry checks; no rate or booking reads it).
- k_I = 3000 per mM per s. The matched blank has H(0) = 0 and k_I = 0, every other input equal.
- Outputs every 30 s to 14,400 s.
- AF's potentials are the sheet's test instance (mu°/RT of the fates 10319.123756415122, M at
  0.05 mM); AN's are SPEC.md's synthetic -12442.6668 with M at 4.0e-3 mM, and C and D take AN's.
- **C** adds the monomer store: Mx (1.0e-6 mM in the cell; mu°/RT 0 at 1 M; M's moieties) and
  local_species_reactions@1's passive M <-> Mx at its c0 of 1 mM (mu°/RT -6.907755278982137 for
  each, forward 1/3000 per s, multiplier 1), declared after the gene unit.
- **D** puts the cell in water, declared first, so the gene unit reads the current volume:
  ideal_osmosis_linear_compliance_water@1 (reference 1.0 pL, bounds 0.5 and 3.0 pL, no impermeant
  amount, no modulus or offset), the patch's L_p = 2.8029294930351318e-14 m/(Pa s) available from
  t = 0, and the held bath at 0 Pa with its K, Y and traces at 0.4 of §1.1's.

**Arm B** (`b`): the sheet's A1 at the test instance (validation/gene_regulation/worlds._a1, R2's
form), with transcription's release (tau = 1500 s, p = 0.55, H(0) = 0, fates R and R_s, marked at
release), `deg_R` at 1/8000 and `deg_R_s` at 1/1100 per s, and translation by `tl` on R and `tl_s`
on R_s. Outputs every 60 s to 21,600 s.

**The labels** (FR-42's owner): R and R_s each carry `resyn` (the base), `pool0`, `pre`, `win` and
`post`; `pool0` is the cell's whole initial share; each row's own label in force is `resyn`
throughout, so re-synthesis enters there; transcription's own schedule gives its releases `pre`
from 0, `win` from t1 and `post` from t2. A labelled run's unlabelled twin is the same world
without the owner.

**The plants' world data** (CRITERIA.md §6), at h only, each in its own process: P2 (AF p=1 at
1 - 2^-30), P3a and P3b (the window's edges half a second late), P4 (the label at completion, in
AN and in B), P5 (k_s x (1 + 1e-4)), P7 (AF's p_sched held declared returned) and P8 (the store's
forward rate x 1.01, with its own matched blank). P9 is a host-side patch (fr38_v2/plants.py).

`check()` parses every registered definition and builds its model's initial values, without
compiling or running any world (the protocol's §5: the builder runs no registered world before
the registration's tag). `python -m validation.gene_regulation.fr38_v2.worlds` prints it.
"""

import copy
import json
from dataclasses import dataclass, replace

from cells.definitions import pump_composite_spec as cs
from cells.operators.templated_polymerisation import COPY_FMOL
from validation.gene_regulation import worlds as gw

CELL, BATH, PATCH = gw.CELL, gw.BATH, gw.PATCH
RELEASE = "tx_release"
LABELS = "neutral_arrival_labels@1"
REACTIONS = "local_species_reactions@1"
WATER = "ideal_osmosis_linear_compliance_water@1"
CLASSES = ("resyn", "pool0", "pre", "win", "post")  # The base first (FR-42's owner).
FATE_ROWS = ("R", "R_s")
MACHINES = ("returned", "held")
RUNGS = (2.0, 1.0, 0.5)  # 4h, 2h and h (CRITERIA.md §1)
RETRY_RUNGS = (1.0, 0.5, 0.25)
H = 0.5  # The judged step


@dataclass(frozen=True)
class Store:
    """Family C's monomer store (SPEC.md §1.5)."""

    mx_mM: float = 1.0e-6
    c0_mM: float = 1.0
    mu_c0: float = -6.907755278982137  # M's and Mx's mu°/RT at the network's c0
    forward_per_s: float = 1 / 3000
    multiplier: float = 1.0


@dataclass(frozen=True)
class Water:
    """Family D's water (SPEC.md §1.6)."""

    lp_m_per_Pa_s: float = 2.8029294930351318e-14
    v_ref_pL: float = 1.0
    v_min_pL: float = 0.5
    v_max_pL: float = 3.0
    bath_fraction: float = 0.4
    bath_pressure_Pa: float = 0.0


@dataclass(frozen=True)
class Hold:
    """A hold family's inputs (SPEC.md §1.1, §1.2): the builder's transcription."""

    name: str
    mu_fate: float  # mu°/RT at 1 M of R and R_s: 1200 mu°_res as SPEC.md's decimal literal
    m0_mM: float
    n0_mM: float = 2.0
    pi0_mM: float = 5.0
    mu_N: float = 24.8672029410015
    r0_copies: float = 20.0
    rs0_copies: float = 15.0
    residues: int = 1200
    stages: int = 8
    speed: float = 50.0
    k_N_mM: float = 0.02
    pool_copies: float = 1.0e4
    template_copies: int = 1
    k_I: float = 3.0e3
    tau_s: float = 2400.0
    h0_copies: float = 160.0
    k_d: float = 1 / 9000
    k_s: float = 1 / 1350
    p_sched: tuple = ((0.0, 0.7), (2700.0, 0.25))
    window: tuple = (1800.0, 5400.0)
    horizon: float = 14400.0
    every: float = 30.0
    samples: tuple = (5400.0, 9000.0, 12600.0)
    background_mM: float = 140.0
    store: Store | None = None
    water: Water | None = None


AF = Hold("AF", mu_fate=10319.123756415122, m0_mM=0.05)
AN = Hold("AN", mu_fate=-12442.6668, m0_mM=4.0e-3)
HOLDS = {"AF": AF, "AN": AN, "C": replace(AN, name="C", store=Store()),
         "D": replace(AN, name="D", water=Water())}  # fmt: skip


@dataclass(frozen=True)
class B:
    """Arm B's inputs (SPEC.md §2) beside A1's own (the sheet's §5.1, sheet_check.A1)."""

    name: str = "B"
    tau_s: float = 1500.0
    p: float = 0.55
    k_d: float = 1 / 8000
    k_s: float = 1 / 1100
    window: tuple = (2400.0, 6000.0)
    horizon: float = 21600.0
    every: float = 60.0
    samples: tuple = (6000.0, 9600.0, 13200.0)


ARM_B = B()

# The registered runs (SPEC.md §1.2, §2) and the engine's support runs (CRITERIA.md §1)
LABELLED = {
    "AF": ("p=0 returned", "p=0 held", "p=1 returned", "p=1 held", "p_sched returned",
           "p_sched held"),
    "AN": ("p=0 returned", "p=1 returned", "p_sched returned", "p_sched held"),
    "B": ("p=0.55 returned", "p=0.55 held"),
    "C": ("p_sched returned",),
    "D": ("p_sched returned",),
}  # fmt: skip
BLANKS = {"AF": ("blank returned", "blank held"), "AN": ("blank returned",), "B": (),
          "C": ("blank returned",), "D": ("blank returned",)}  # fmt: skip
TWINS = {"AF": ("p_sched returned",), "AN": ("p_sched returned",),
         "B": ("p=0.55 returned", "p=0.55 held"), "C": ("p_sched returned",),
         "D": ("p_sched returned",)}  # fmt: skip
UNLABELLED = " unlabelled"  # A twin's name: its labelled run's, with this suffix
RESTART = ("AN", "p_sched returned", 7200.0)  # CRITERIA.md §1: checkpointed at 7200 s, at h


def runs(family):
    """The engine's runs of a family at one rung, by name (CRITERIA.md §1)."""
    return [*LABELLED[family], *BLANKS[family], *(t + UNLABELLED for t in TWINS[family])]


def _parse_run(name):
    """(p, machine, blank, labelled) of a run's name: "<p> <machine>[ unlabelled]" or "blank
    <machine>" (SPEC.md §1.3; a blank is published once, run here per machine option)."""
    labelled = not name.endswith(UNLABELLED)
    base = name[: -len(UNLABELLED)] if not labelled else name
    p, machine = base.split(" ")
    if machine not in MACHINES:
        raise ValueError(f"no machine option in run {name!r}")
    return p, machine, p == "blank", labelled


# ------------------------------------------------------------------ the hold worlds (SPEC.md §1)


def _hold_skeleton(f, dt):
    """The inert cell, bath and patch with N, M, Pi and the fates at their starts (mM in 1 pL)."""
    start = {"N": f.n0_mM, "M": f.m0_mM, "Pi": f.pi0_mM, "R": f.r0_copies * COPY_FMOL,
             "R_s": f.rs0_copies * COPY_FMOL}  # fmt: skip
    if f.store is not None:
        start["Mx"] = f.store.mx_mM
    raw = gw._skeleton(dt=dt, end=f.horizon, every=f.every, start=start, volume=1.0)
    for node in (*raw["model"]["cells"], *raw["model"]["extracellular"]):
        for ion in ("K", "Y"):
            node["initial_amount_fmol"][ion] = f.background_mM * node["volume_pL"]
    return raw


def _moieties(f):
    """SPEC.md §1.1's moieties over the world's rows; Mx carries M's (§1.5)."""
    phosphorus = {"N": 3, "M": 1, "Pi": 1, "R": f.residues, "R_s": f.residues}
    nucleoside = {"N": 1, "M": 1, "R": f.residues, "R_s": f.residues}
    if f.store is not None:
        phosphorus["Mx"] = nucleoside["Mx"] = 1
    return {"phosphorus": phosphorus, "nucleoside": nucleoside}


def _potentials(f):
    """mu°/RT at 1 M of the gene unit's rows (and Mx, the registry's 0)."""
    mu = {"N": f.mu_N, "M": 0.0, "Pi": 0.0, "R": f.mu_fate, "R_s": f.mu_fate}
    return mu | ({"Mx": 0.0} if f.store is not None else {})


def _chain(f, machine, p, h0):
    chain = dict(
        id="tx",
        pool="pol",
        template=dict(copies=int(f.template_copies)),
        product="R",
        residues=int(f.residues),
        stages=int(f.stages),
        speed_per_s=float(f.speed),
        draws=dict(N=1),
        releases=dict(Pi=2),
        saturation_mM=dict(N=float(f.k_N_mM)),
    )
    chain["release"] = dict(
        id=RELEASE,
        dwell_s=float(f.tau_s),
        machine=machine,
        durable_fraction=p,
        fates=[dict(durable="R", short_lived="R_s")],
        label=dict(at="release"),
        initial_copies=[float(h0)],
    )
    return chain


def _degradation(f, route, polymer, mu):
    """Each fate's loss, returning L M per molecule (SPEC.md §1.1), its standard free energy per
    net move L mu°_M - mu°_fate (in RT, at c0 = 1 M), which the registry holds to the potentials."""
    return dict(
        id=route,
        cell=CELL,
        polymer=polymer,
        residues=int(f.residues),
        monomers={"M": 1},
        standard_free_energy=dict(dG_RT=float(f.residues * mu["M"] - mu[polymer])),
    )


def _p_of(f, p):
    """(the release's durable_fraction, its schedule or None) for SPEC.md §1.3's p."""
    if p == "p=0":
        return 0.0, None
    if p == "p=1":
        return 1.0, None
    if p in ("p_sched", "blank"):
        return "scheduled", list(f.p_sched)
    raise ValueError(f"p is p=0, p=1 or p_sched in a hold family, not {p!r}")


def hold(family, run, *, dt, f=None, edits=None):
    """A hold world's definition (module docstring) by its family and run name (runs()); `f`
    replaces the family's inputs (the smoke's invented ones); `edits` are a plant's
    ({"p": value, "k_s_factor": x, "label_at": "completion", "schedule": {label: time},
    "store_factor": x})."""
    f = HOLDS[family] if f is None else f
    edits = dict(edits or {})
    p, machine, blank, labelled = _parse_run(run)
    fraction, schedule = _p_of(f, p)
    fraction = edits.pop("p", fraction)
    raw = _hold_skeleton(f, dt)
    mu = _potentials(f)
    raw = gw._with_registry(raw, mu, _moieties(f))
    raw = cs.frozen_definition(raw)
    chain = _chain(f, machine, fraction, 0.0 if blank else f.h0_copies)
    if "label_at" in edits:
        chain["release"]["label"] = dict(at=edits.pop("label_at"))
    degradations = [_degradation(f, "deg_R", "R", mu), _degradation(f, "deg_R_s", "R_s", mu)]
    rows = ("N", "M", "Pi", "R", "R_s")
    block = gw._block({r: mu[r] for r in rows}, rows, {"pol": f.pool_copies}, [chain],
                      degradations, [])  # fmt: skip
    rates = {"tx": [(0.0, 0.0 if blank else float(f.k_I))],
             "deg_R": [(0.0, float(f.k_d))],
             "deg_R_s": [(0.0, float(f.k_s) * edits.pop("k_s_factor", 1.0))]}  # fmt: skip
    extra, controls = (), {}
    if f.water is not None:
        extra, controls = _water(raw, f.water)
    out = gw._finish(raw, block, rates, extra_operators=extra, extra_controls=controls)
    if schedule is not None:
        out["experiment"]["polymerisation_controls"].append(
            dict(route_id=RELEASE, schedule=gw._schedule(schedule, "value"))
        )
    if f.store is not None:
        out = _with_store(out, f.store, edits.pop("store_factor", 1.0))
    window = dict(zip(("win", "post"), f.window, strict=True)) | edits.pop("schedule", {})
    if labelled:
        out = with_labels(out, window["win"], window["post"])
    if edits:
        raise ValueError(f"unknown edits {sorted(edits)}")
    return out


def _water(raw, w):
    """Water, declared first (SPEC.md §1.6), and the held bath at its dilution. Returns (the water
    operator, its controls); raw's bath is diluted in place."""
    for bath in raw["model"]["extracellular"]:
        if bath.get("reservoir", False):
            for name in bath["initial_amount_fmol"]:
                bath["initial_amount_fmol"][name] *= w.bath_fraction
    block = dict(
        law=WATER,
        compartments=[dict(
            compartment_id=CELL, reference_volume_pL=w.v_ref_pL, minimum_volume_pL=w.v_min_pL,
            maximum_volume_pL=w.v_max_pL, impermeant_amount_fmol=0.0, bulk_modulus_Pa=0.0,
            pressure_offset_Pa=0.0)],
        baths=[dict(compartment_id=BATH, hydrostatic_pressure_Pa=w.bath_pressure_Pa)],
        membranes=[dict(membrane_id=PATCH, hydraulic_permeability_m_per_Pa_s=w.lp_m_per_Pa_s)],
    )  # fmt: skip
    controls = dict(
        water_controls=[dict(membrane_id=PATCH, schedule=[dict(time=0.0, availability=1.0)])]
    )
    return (block,), controls


def _with_store(raw, s, factor=1.0):
    """Family C's network after the gene unit (SPEC.md §1.5; FR-43 part 2A's order): M <-> Mx,
    passive at its c0, both at mu°/RT s.mu_c0 there, M's moieties on each."""
    out = copy.deepcopy(raw)
    species = [dict(id=row, moieties={"phosphorus": 1, "nucleoside": 1}, standard_mu_RT=s.mu_c0,
                    catalogue=None, evidence=None) for row in ("M", "Mx")]  # fmt: skip
    reaction = dict(id="store_M", sites={"cells": [CELL]}, reactants={"M": 1},
                    products={"Mx": 1}, law="ideal_detailed_balance_mass_action@1",
                    forward_rate_per_s=float(s.forward_per_s) * factor, factors=[])  # fmt: skip
    out["model"]["operators"].append(
        dict(law=REACTIONS, standard_concentration_mM=s.c0_mM, species=species,
             reactions=[reaction])
    )  # fmt: skip
    out["experiment"]["reaction_controls"] = [
        dict(reaction_id="store_M", site=None,
             schedule=[dict(time=0.0, multiplier=float(s.multiplier))])
    ]  # fmt: skip
    return out


def with_labels(raw, t1, t2):
    """raw with FR-42's owner on R and R_s (module docstring): five labels, `pool0` the cell's
    initial share, each row's own label `resyn` throughout, and transcription's own schedule
    `pre` from 0, `win` from t1 and `post` from t2 (SPEC.md §1.1)."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(
        dict(law=LABELS, species=[
            dict(id=row, labels=list(CLASSES), initial=[dict(node=CELL, shares={"pool0": 1.0})])
            for row in FATE_ROWS])
    )  # fmt: skip
    own = [dict(species=row, schedule=[dict(time=0.0, label="resyn")]) for row in FATE_ROWS]
    source = dict(species="R", source="tx", schedule=[
        dict(time=0.0, label="pre"), dict(time=float(t1), label="win"),
        dict(time=float(t2), label="post")])  # fmt: skip
    out["experiment"]["label_arrivals"] = [*own, source]
    return out


# ------------------------------------------------------------------ arm B (SPEC.md §2)


def b(run, *, dt, edits=None):
    """B's world by its run name: A1 with transcription's release (module docstring)."""
    edits = dict(edits or {})
    p, machine, blank, labelled = _parse_run(run)
    if p != "p=0.55" or blank:
        raise ValueError(f"B's runs are p=0.55 with a machine option, not {run!r}")
    release = dict(machine=machine, rates=(ARM_B.k_d, ARM_B.k_s), dwell_s=ARM_B.tau_s)
    raw = gw._a1(dt=dt, end=ARM_B.horizon, every=ARM_B.every, symbols=None, release=release)
    block = next(o for o in raw["model"]["operators"] if o["law"] == gw.POLYMERISATION)
    chain = next(c for c in block["chains"] if c["id"] == "tx")
    chain["release"].update(
        durable_fraction=ARM_B.p, label=dict(at=edits.pop("label_at", "release"))
    )
    if chain["release"]["initial_copies"] != [0.0]:
        raise ValueError("B's hold starts empty (SPEC.md §2)")
    if labelled:
        raw = with_labels(raw, *ARM_B.window)
    if edits:
        raise ValueError(f"unknown edits {sorted(edits)}")
    return raw


def world(family, run, *, dt, edits=None):
    """Any registered world: (family, run name) at step dt."""
    if family == "B":
        return b(run, dt=dt, edits=edits)
    return hold(family, run, dt=dt, edits=edits)


# ------------------------------------------------------------------ the plants (CRITERIA.md §6)

PLANTS = {
    # name: (family, the honest run it plants, the run its records are judged as, edits)
    "P2": ("AF", "p=1 returned", "p=1 returned", {"p": 1.0 - 2.0**-30}),
    "P3a": ("AN", "p_sched returned", "p_sched returned", {"schedule": {"win": 1800.5}}),
    "P3b": ("AN", "p_sched returned", "p_sched returned", {"schedule": {"post": 5400.5}}),
    "P4 AN": ("AN", "p_sched returned", "p_sched returned", {"label_at": "completion"}),
    "P4 B": ("B", "p=0.55 returned", "p=0.55 returned", {"label_at": "completion"}),
    "P5": ("AF", "p_sched returned", "p_sched returned", {"k_s_factor": 1.0 + 1e-4}),
    "P7": ("AF", "p_sched returned", "p_sched held", {}),
    "P8": ("C", "p_sched returned", "p_sched returned", {"store_factor": 1.01}),
    "P8 blank": ("C", "blank returned", "blank", {"store_factor": 1.01}),
    "P9": ("D", "p_sched returned", "p_sched returned", {}),  # fr38_v2/plants.py's V0 patch
}


def plant(name, *, dt=H):
    """A world-data plant's definition (its honest world with the plant's edits), at h."""
    family, run, _, edits = PLANTS[name]
    return world(family, run, dt=dt, edits=copy.deepcopy(edits))


# ------------------------------------------------------------------ the parse-only check


def _parse(raw):
    """Parse a definition and build its model's initial values, without compiling or running."""
    from cells.definitions.specs import parse_spec
    from cells.registry.models import get_model

    spec = parse_spec(raw)
    get_model(spec.model).initial_values(spec)
    return spec


def check(rungs=RUNGS):
    """{(family, run, dt) or plant: "parses"}: every registered world at every rung, the
    restart's, and every plant's, each parsed and given its initial values (nothing compiled)."""
    out = {}
    for family in ("AF", "AN", "B", "C", "D"):
        for dt in rungs:
            for run in runs(family):
                _parse(world(family, run, dt=dt))
                out[f"{family} | {run} | dt={dt:g}"] = "parses"
    for name in PLANTS:
        _parse(plant(name))
        out[f"plant {name} | dt={H:g}"] = "parses"
    return out


def main():
    print(json.dumps(check(), indent=1))


if __name__ == "__main__":
    main()
