"""The comparison harness: each engine mitochondrial law against MT-1's registered component
references, row by row, within their registered bands (landing evidence for each head).

**What it reads.** The references' documented interface only, pinned to their registration tag
(REGISTRATION_TAG) with `git show`, whatever head runs it: `inputs.json` (each state's float64
inputs, the parameters and the constants) and `rows.json` (each row's reference values and its
band, whose x scale carries the appendix's band term M, §10). Never the references'
implementation. On the engine side: the law objects in the law registry and the cycle form's
public monomial pipeline (laws/cycles/forms.py: resolved, expand_rate, monomial_tables,
monomial_logs, sign_exact_flux), with x from the named potential set as the kind forms it
(species_registry.potential_set_values). No new engine entry point.

**What it compares,** at every registered row: x, S (= J+), J, J- and the slopes of ln S and of J.
The references give their slopes at fixed other inputs, some of which are bound forms or totals
(MgADP, total Pi); the engine's are over its free slots (free base forms and free ligands). The
harness carries the references' slopes onto the free slots by the binding relations of the
appendix's forms table (§0), with their bands carried the same way. A quantity passes where
|engine - reference| <= its band; a law passes where every row and quantity does.

**The engine stub (ENGINE).** One entry per reference law, keyed as the references key it: the
planned law ID, its mode, the parameter that is its population's capacity (k per unit S, in the
references' mol s-1 (L mito)-1), its parameter values and its role binding to the potential
set's rows. The kinds owner's first head fills it. A law whose ID is None, or that the head's
registry lacks, is reported as not built and never passes.

**Plants, run with every comparison:** the law evaluated with the wrong form (its affinity share
changed: n = 1 to 2, or n > 1 to 1) and with a factor dropped (its rate's last factor, else its
last order). Each is caught at a row where some quantity misses by POWER_MARGIN (3) bands, the
references' own margin; the harness reports how many rows catch each.

**Adapters:**
- `engine` (the default): the law registry's laws through the monomial pipeline;
- `pipeline-check`: lane-built monomial forms for complex I and the synthase, through the same
  pipeline, to test the harness's own path before any engine law exists; not the engine's laws;
- `dry-run`: the lane's appendix kernels (appendix_check.py, 50-digit), slopes by central
  differences: a dry run of the harness, not engine evidence. Its agreement with the references
  is a cross-check of the appendix.

The per-form outer membrane (§8) and the lumped cycle (§1.4, unused under host P) are not
compared in this version.

Run: PYTHONPATH=src:. JAX_ENABLE_X64=1 python -m validation.mitochondria.component_comparison
[--adapter engine|pipeline-check|dry-run] [--laws k1,k2] [--out FILE]. Seconds to a minute on one
core. Exit 0: every built law passes and every plant is caught; 1: a failure; 2: nothing built.
"""

import argparse
import json
import math
import subprocess
import sys
from decimal import Decimal, getcontext
from pathlib import Path
from typing import NamedTuple

import numpy as np

getcontext().prec = 50
D = Decimal
REGISTRATION_TAG = "mito-components-registration-2026-11-20"
INTERFACE = "validation/mitochondria/references/components/interface"
POWER_MARGIN = 3  # A plant is caught where some quantity misses by this many bands.
EPS = float(np.finfo(float).eps)
CORE = ("x", "S", "J", "J_minus")
COMPARED = (
    "complex_I", "complex_III_eq7", "complex_III_eq24", "complex_IV", "atp_synthase",
    "nucleotide_exchange", "phosphate_carrier", "k_h_exchange", "nadh_supply", "adenylate_kinase",
)  # fmt: skip
NOT_COMPARED = {
    "outer_membrane": "the per-form face (§8) comes later",
    "lumped_QO": "x only, unused under host P (§1.4, D235)",
}
ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ the references' interface


def interface(name, tag=REGISTRATION_TAG):
    """One interface file at the registration tag, as JSON (git show, so no head can drift it)."""
    text = subprocess.run(
        ["git", "show", f"{tag}:{INTERFACE}/{name}.json"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout  # fmt: skip
    return json.loads(text)


def parameter(inputs, name):
    p = inputs["parameters"]
    if name == "X_C3_without":
        return float(p["without_pi_control_X_C3"])
    return float(p["with_pi_control"][name])


# ------------------------------------------------------------------ free coordinates


def free_coordinates(values, inputs):
    """The row's free coordinates from its inputs: every free base form and free ligand it gives,
    and HPO4 from total Pi where only the total is given (HPO4 = Pi / (1 + h/k_dH))."""
    k_dh = parameter(inputs, "k_dH")
    out = {k: v for k, v in values.items() if k != "dpsi_mV" and not _bound(k)}
    for end in ("N", "P", "E"):
        pi, h = values.get(f"Pi_{end}"), values.get(f"h_{end}")
        if pi is not None and f"HPO4_{end}" not in values and h is not None:
            out[f"HPO4_{end}"] = pi / (1.0 + h / k_dh)
    return out


def _bound(name):
    head = name.rsplit("_", 1)[0]
    return head in ("MgATP", "MgADP", "H2PO4", "Pi", "ATPtot", "ADPtot")


def chain(name, free, inputs):
    """d ln(name)/d ln(free coordinate) for a reference input (the appendix's §0 forms): a free
    coordinate is itself; a bound form a monomial; a total its forms' weighted sum."""
    head, end = name.rsplit("_", 1)
    if not _bound(name):
        return {name: 1.0}
    mg, h = free.get(f"Mg_{end}"), free.get(f"h_{end}")
    if head == "MgATP":
        return {f"ATP4_{end}": 1.0, f"Mg_{end}": 1.0}
    if head == "MgADP":
        return {f"ADP3_{end}": 1.0, f"Mg_{end}": 1.0}
    if head == "H2PO4":
        return {f"HPO4_{end}": 1.0, f"h_{end}": 1.0}
    if head == "Pi":
        w = (h / parameter(inputs, "k_dH")) / (1.0 + h / parameter(inputs, "k_dH"))
        return {f"HPO4_{end}": 1.0, f"h_{end}": w}
    k = parameter(inputs, "K_MgATP" if head == "ATPtot" else "K_MgADP")
    w = (mg / k) / (1.0 + mg / k)
    return {f"{'ATP4' if head == 'ATPtot' else 'ADP3'}_{end}": 1.0, f"Mg_{end}": w}


def reference_on_free(row, free, inputs):
    """A row's reference values and bands, its slopes carried onto the free coordinates."""
    ref, band = row["ref"], row["band"]
    out = {q: (D(ref[q]), D(repr(band[q]))) for q in CORE}
    for kind in ("slopes_lnS", "slopes_J"):
        values, bands = {}, {}
        for name, value in ref[kind].items():
            if name == "u":
                values["u"] = values.get("u", D(0)) + D(value)
                bands["u"] = bands.get("u", D(0)) + D(repr(band[kind][name]))
                continue
            for coordinate, weight in chain(name, free, inputs).items():
                w = D(repr(weight))
                values[coordinate] = values.get(coordinate, D(0)) + D(value) * w
                bands[coordinate] = bands.get(coordinate, D(0)) + D(repr(band[kind][name])) * abs(w)
        out[kind] = (values, bands)
    return out


# ------------------------------------------------------------------ the engine adapter


class EngineSpec(NamedTuple):
    """One law's entry in the stub (module docstring)."""

    law_id: str | None  # The registered law, as definitions write it; None until a head builds it.
    mode: str | None = None  # The mode's ID in its form (None: the first).
    capacity: str | None = None  # The inputs.json parameter that is k per unit S.
    capacity_scale: float = 1.0  # A declared factor on it (the head's, e.g. 1/2 per O2).
    parameters: tuple = ()  # ((law parameter, inputs.json parameter or a number), ...)
    roles: tuple = ()  # ((role, the potential set's row), ...)
    potential_set: str = "cells.potential_set.beard2005@1"
    # ((input, value), ...): inputs the law reads that the references' rows do not give, where its
    # value is independent of them (complex III's Eq. 7: k_Pi3 = k_Pi4, so phi_Pi = 1 at any Pi).
    fixed: tuple = ()


# The planned laws (the coordinator, 20 November 2026): complexes I, III and IV as three laws; the
# synthase, the exchange, the phosphate carrier, K+/H+; cells.cycle.held_reductant_supply@1 and the kinase;
# the per-form face later. The kinds owner's first head fills the IDs, modes, capacities,
# parameters and role bindings; until then each entry is not built.
# Filled by the kinds owner's first head (a recorded exception in the lane's file, by the lead's
# leave, 20 November 2026): complexes I, III and IV, the synthase and the three carriers; and by
# its second, under the same leave: the supply and the kinase.
_C3_ROLES = (("QH2", "QH2"), ("Q", "Q"), ("c_ox", "cytc_ox"), ("c_red", "cytc_red"), ("H", "H"),
             ("Pi", "Pi"))  # fmt: skip
ENGINE = {
    "complex_I": EngineSpec(
        "cells.cycle.nadh_ubiquinone_proton_cycle@1",
        "oxidation",
        "X_C1",
        roles=(("NADH", "NADH"), ("Q", "Q"), ("NAD", "NAD"), ("QH2", "QH2"), ("H", "H")),
    ),
    "complex_III_eq7": EngineSpec(  # Eq. 7 is the law with k_Pi3 = k_Pi4 (the lead's ruling 2).
        "cells.cycle.ubiquinol_cytochrome_c_proton_cycle@1",
        "oxidation",
        "X_C3_without",
        parameters=(("k_Pi3", 1.0), ("k_Pi4", 1.0)),
        roles=_C3_ROLES,
        fixed=(("HPO4_N", 1e-3),),
    ),
    "complex_III_eq24": EngineSpec(
        "cells.cycle.ubiquinol_cytochrome_c_proton_cycle@1",
        "oxidation",
        "X_C3",
        parameters=(("k_Pi3", "k_Pi3_mM"), ("k_Pi4", "k_Pi4_mM")),
        roles=_C3_ROLES,
    ),
    "complex_IV": EngineSpec(
        "cells.cycle.cytochrome_c_oxygen_proton_cycle@1",
        "reduction",
        "X_C4",
        parameters=(("k_O2", "k_O2"),),
        roles=(("O2", "O2"), ("c_red", "cytc_red"), ("c_ox", "cytc_ox"), ("H", "H")),
    ),
    "atp_synthase": EngineSpec(
        "cells.cycle.proton_coupled_atp_synthesis_cycle@1",
        "synthesis",
        "X_F1",
        parameters=(("K_MgADP", "K_MgADP"), ("K_MgATP", "K_MgATP")),
        roles=(("ADP", "ADP"), ("Pi", "Pi"), ("ATP", "ATP"), ("H", "H")),
    ),
    "nucleotide_exchange": EngineSpec(
        "cells.cycle.electrogenic_nucleotide_exchange@1",
        "exchange",
        "X_ANT",
        parameters=(("theta_P", "theta_P"), ("k_mADP", "k_mADP")),
        roles=(("ATP", "ATP"), ("ADP", "ADP")),
    ),
    "phosphate_carrier": EngineSpec(
        "cells.cycle.phosphate_proton_symport@1",
        "import",
        "X_PiHt",
        parameters=(("k_PiHt", "k_PiHt_mM"),),
        roles=(("Pi", "Pi"), ("H", "H")),
    ),
    "k_h_exchange": EngineSpec(
        "cells.cycle.potassium_proton_exchange@1",
        "exchange",
        "X_KH",
        roles=(("K", "K"), ("H", "H")),
    ),
    "nadh_supply": EngineSpec(
        "cells.cycle.held_reductant_supply@1",
        "reduction",
        "X_DH",
        parameters=(("r", "r"), ("k_Pi1", "k_Pi1_mM"), ("k_Pi2", "k_Pi2_mM")),
        roles=(
            ("S_red", "S_red"),
            ("NAD", "NAD"),
            ("S_ox", "S_ox"),
            ("NADH", "NADH"),
            ("H", "H"),
            ("Pi", "Pi"),
        ),
    ),
    "adenylate_kinase": EngineSpec(
        "cells.cycle.adenylate_kinase@1",
        "phosphotransfer",
        "X_AK",
        parameters=(("K_MgATP", "K_MgATP"),),
        roles=(("ADP", "ADP"), ("ATP", "ATP"), ("AMP", "AMP"), ("Mg", "Mg")),
        potential_set="cells.potential_set.beard2005@2",
    ),
}

# The potential set's rows and forms as the references name their inputs.
SET_INPUT = {
    "H": "h",
    "ATP": "ATP4",
    "ADP": "ADP3",
    "Pi": "HPO4",
    "cytc_red": "c2",
    "cytc_ox": "c3",
}


class MonomialAdapter:
    """One law's form through forms' public monomial pipeline, at one mode."""

    def __init__(self, form, spec, inputs):
        from cells.laws.cycles import forms
        from cells.laws.electrochemistry import R
        from cells.registry import species_registry as registry

        self.forms, self.inputs = forms, inputs
        self.T = float(inputs["constants"]["T_K"])
        self.rt = R * self.T  # J/mol
        self.spec = spec
        values = {name: (parameter(inputs, v) if isinstance(v, str) else float(v))
                  for name, v in spec.parameters}  # fmt: skip
        self.form = forms.resolved(form, values)
        modes = [m for m, _ in form.modes]
        self.index = modes.index(spec.mode) if spec.mode is not None else 0
        self.counts = forms.resolve(self.form, values)[0][self.index]
        s = registry.POTENTIAL_SETS[spec.potential_set]
        self.mu = registry.potential_set_values(
            spec.potential_set, temperature_K=self.T, standard_concentration_mM=registry.SET_C0_MM
        )
        self.valence = dict(s.rows)
        self.set_forms = {}
        for f in s.forms:
            self.set_forms.setdefault(f.row, []).append(f)
        self.form_by_id = {f.id: f for f in s.forms}
        self.roles = dict(spec.roles)
        self.capacity = parameter(inputs, spec.capacity) * spec.capacity_scale
        self.slots = {}

    def slot(self, row, end):
        return self.slots.setdefault((row, end), len(self.slots))

    def _form_monomial(self, f, end):
        log_c = self.mu[f.row] + sum(n * self.mu[ligand] for ligand, n in f.counts) - self.mu[f.id]
        coefficients = ((self.slot(f.row, end), 1.0),) + tuple(
            (self.slot(ligand, end), float(n)) for ligand, n in f.counts
        )
        return self.forms.Monomial(log_c, coefficients)

    def read(self, reference):
        row = self.roles[reference.role]
        base = self.forms.Monomial(0.0, ((self.slot(row, reference.end), 1.0),))
        if reference.form == "free":
            return (base,)
        if reference.form == "total":
            return (base,) + tuple(
                self._form_monomial(f, reference.end) for f in self.set_forms[row]
            )
        return (self._form_monomial(self.form_by_id[reference.form], reference.end),)

    def _log_k(self, rate):
        """The kind's own log k (kinds/transporter.cited_log_k, which builds a CitedConstant, a
        RateConstant or a number), at this harness's T: one function, never a copy."""
        from types import SimpleNamespace

        from cells.kinds import transporter

        world = SimpleNamespace(model=SimpleNamespace(temperature_K=self.T))
        return transporter.cited_log_k(world, rate.log_k)

    def rate(self, plant=None):
        rate = self.form.monomial.rates[self.index]
        if plant == "wrong_form":
            rate = rate._replace(share=1 if rate.share > 1 else 2)
        elif plant == "dropped_factor":
            if rate.factors:
                rate = rate._replace(factors=rate.factors[:-1])
            else:
                rate = rate._replace(orders=rate.orders[:-1])
        return rate

    def evaluate(self, values, free, plant=None):
        """x, S, J, J- and the slopes over the free coordinates and u, at one row."""
        f, np_ = self.forms, np
        free = {**dict(self.spec.fixed), **free}
        u = values["dpsi_mV"] * float(self.inputs["constants"]["F_RT_per_mV"])
        rate = self.rate(plant)
        expanded = f.expand_rate(rate, self.read, self._log_k(rate))
        rows = [(self.roles[role], end) for role, end in self.form.rows]
        for row in rows:
            self.slot(*row)
        names = {
            index: f"{SET_INPUT.get(row, row)}_{end}" for (row, end), index in self.slots.items()
        }
        n = len(self.slots)
        ln_a = np_.array([[math.log(free[names[i]])] for i in range(n)])
        q = sum(
            int(c) * self.valence[row]
            for c, (row, end) in zip(self.counts, rows, strict=True)
            if end == "P"
        )
        x = sum(int(c) * (self.mu[row] + math.log(free[names[self.slot(row, end)]]))
                for c, (row, end) in zip(self.counts, rows, strict=True)) + q * u  # fmt: skip
        tables = f.monomial_tables([expanded], n)
        t = type(tables)(*(np_.asarray(v)[..., None] for v in tables))
        logs = f.monomial_logs(t, ln_a, np_.array([-u]), np_.array([[x]]), xp=np_)
        log_plus = float(logs.log_s[0, 0]) + math.log(self.capacity)
        j = float(f.sign_exact_flux(np_.array(log_plus), np_.array(x), xp=np_))
        s, j_minus = math.exp(log_plus), math.exp(log_plus + x)
        nu = {}
        for c, row in zip(self.counts, rows, strict=True):
            nu[names[self.slot(*row)]] = nu.get(names[self.slot(*row)], 0) + int(c)
        d_x = float(logs.d_x[0, 0])
        slopes_ln_s = {names[i]: float(logs.d_ln_a[0, i, 0]) + d_x * nu.get(names[i], 0)
                       for i in range(n)}  # fmt: skip
        slopes_ln_s["u"] = -float(logs.d_psi[0, 0]) + d_x * q
        slopes_j = {k: j * v - j_minus * (q if k == "u" else nu.get(k, 0))
                    for k, v in slopes_ln_s.items()}  # fmt: skip
        return dict(x=x, S=s, J=j, J_minus=j_minus, slopes_lnS=slopes_ln_s, slopes_J=slopes_j)


def engine_adapter(key, inputs):
    """The engine law of a stub entry through the pipeline, or a reason it is not built."""
    spec = ENGINE[key]
    if spec.law_id is None:
        return None, "not built: no law ID in the stub on this head"
    from cells.registry import laws as law_registry
    from cells.registry import species_registry as registry

    try:
        law = law_registry.active().lookup(spec.law_id)
    except KeyError:
        return None, f"not built: {spec.law_id} is not in this head's law registry"
    if getattr(law, "cycle", None) is None or law.cycle.kinetics != "monomial":
        return None, f"not built: {spec.law_id} has no monomial form on this head"
    if spec.potential_set not in registry.POTENTIAL_SETS:
        return None, f"not built: the potential set {spec.potential_set} is not on this head"
    if not spec.roles:
        return None, "not built: the stub binds no roles"
    return MonomialAdapter(law.cycle, spec, inputs), None


# ------------------------------------------------------------------ the pipeline check's forms


def pipeline_forms():
    """Lane-built monomial forms for complex I and the synthase (the appendix's S, §1.1 and §2,
    in the monomial's terms), to run the harness's engine path before any engine law exists. They
    are not the engine's laws."""
    from cells.laws.cycles.forms import (
        CitedConstant,
        CycleForm,
        MonomialForm,
        MonomialRate,
        Reference,
    )

    c1 = CycleForm(
        kinetics="monomial",
        roles=(("NADH", -2), ("NAD", -1), ("Q", 0), ("QH2", 0), ("H", 1)),
        rows=(("NADH", "N"), ("NAD", "N"), ("Q", "N"), ("QH2", "N"), ("H", "N"), ("H", "P")),
        modes=(("forward", (-1, 1, -1, 1, -5, 4)),),
        monomial=MonomialForm(
            rates=(
                MonomialRate(
                    log_k=CitedConstant(-69.37, protons=-1),
                    orders=((Reference("NADH", "N"), 1.0), (Reference("Q", "N"), 1.0),
                            (Reference("QH2", "N"), -1.0), (Reference("H", "N"), 5.0),
                            (Reference("H", "P"), -4.0)),
                    zeta=4.0,
                ),
            ),
        ),
    )  # fmt: skip
    f1 = CycleForm(
        kinetics="monomial",
        roles=(("ADP", -3), ("Pi", -2), ("ATP", -4), ("H", 1)),
        rows=(("ADP", "N"), ("Pi", "N"), ("ATP", "N"), ("H", "N"), ("H", "P")),
        modes=(("synthesis", (-1, -1, 1, 2, -3)),),
        monomial=MonomialForm(
            rates=(
                MonomialRate(
                    log_k=CitedConstant(36.03, offset=math.log(347.0e-6 / 24.0e-6)),
                    orders=((Reference("ADP", "N", "MgADP"), 1.0),
                            (Reference("Pi", "N", "total"), 1.0),
                            (Reference("H", "P"), 3.0), (Reference("H", "N"), -3.0)),
                    zeta=-3.0,
                ),
            ),
        ),
    )  # fmt: skip
    for form in (c1, f1):
        problems = form.errors()
        if problems:
            raise ValueError("; ".join(problems))
    roles_c1 = (("NADH", "NADH"), ("NAD", "NAD"), ("Q", "Q"), ("QH2", "QH2"), ("H", "H"))
    roles_f1 = (("ADP", "ADP"), ("Pi", "Pi"), ("ATP", "ATP"), ("H", "H"))
    return {
        "complex_I": (c1, EngineSpec("pipeline-check: complex I", capacity="X_C1", roles=roles_c1)),
        "atp_synthase": (
            f1,
            EngineSpec("pipeline-check: synthase", capacity="X_F1", roles=roles_f1),
        ),
    }


# ------------------------------------------------------------------ the dry run's adapter


class DryRunAdapter:
    """The lane's appendix kernels (appendix_check.py, 50 digits) as a stand-in engine: x and S in
    closed form, slopes by central differences over the free coordinates. A dry run of the
    harness, not engine evidence."""

    STEP = D("1e-12")

    def __init__(self, key, inputs):
        from validation.mitochondria import appendix_check as kernels

        self.k, self.key, self.inputs = kernels, key, inputs
        self.kappa = {"complex_III_eq7": 2, "complex_III_eq24": 2, "complex_IV": 4}.get(key, 1)

    def _state(self, c):
        return dict(
            u=c.get("u", D(0)), H_N=c.get("h_N", D(1)), H_P=c.get("h_P", D(1)),
            NADH=c.get("NADH_N"), NAD=c.get("NAD_N"), Q=c.get("Q_N"), QH2=c.get("QH2_N"),
            cred=c.get("c2_P"), cox=c.get("c3_P"), O2=c.get("O2_N"), Mg_N=c.get("Mg_N"),
            Mg_P=c.get("Mg_P"), HPO4_N=c.get("HPO4_N"), HPO4_P=c.get("HPO4_P"),
            ATP_N=c.get("ATP4_N"), ADP_N=c.get("ADP3_N"), ATP_P=c.get("ATP4_P"),
            ADP_P=c.get("ADP3_P"), AMP_P=c.get("AMP_P"), K_N=c.get("K_N"), K_P=c.get("K_P"),
        )  # fmt: skip

    def x_and_s(self, c, plant=None):
        k, key, s = self.k, self.key, self._state(c)
        one = k.ONE
        if key == "complex_I":
            _, _, x, _, a, _ = k.c1(s)
            factor = s["Q"] / s["QH2"]
        elif key == "complex_III_eq7":
            _, _, x, _, a, _ = k.c3_eq7(s)
            a = a * D(repr(parameter(self.inputs, "X_C3_without"))) / k.P["X_C3"]
            a, factor = a / (one + k.exp(x / 2)), (s["QH2"] / s["Q"]).sqrt()
        elif key == "complex_III_eq24":
            _, _, x, _, _, _ = k.c3_eq24(s)
            factor = k.phi_pi(s)
            a = factor * k.c3_eq7(s)[4] / (one + k.exp(x / 2))
        elif key == "complex_IV":
            _, _, x, _, a, _ = k.c4(s)
            a = a / 2 / sum(k.exp(D(i) * x / 4) for i in range(4))
            factor = one / (one + k.P["k_O2"] / s["O2"])
        elif key == "atp_synthase":
            _, _, x, _, a, _ = k.f1(s)
            factor = one + s["H_N"] / k.K_DH  # the total Pi's binding polynomial
        elif key == "nucleotide_exchange":
            _, _, x, _, a, _ = k.ant(s)
            factor = one / (one + k.P["k_mADP"] / s["ADP_P"])
        elif key == "phosphate_carrier":
            _, _, x, _, a, _ = k.piht(s)
            h2 = s["H_P"] * s["HPO4_P"] / k.K_DH
            factor = h2 / (h2 + k.P["k_PiHt"] * k.MM)
        elif key == "k_h_exchange":
            _, _, x, _, a, _ = k.kh(s)
            factor = s["K_P"]
        elif key == "nadh_supply":
            _, _, _, _, a, _ = k.supply(s)
            mu = k.potentials(self.inputs_T())
            ratio = c["S_ox_N"] * s["NADH"] * s["H_N"] / (c["S_red_N"] * s["NAD"])
            x = mu["S_ox"] + mu["NADH"] + mu["H"] - mu["S_red"] - mu["NAD"] + k.ln(ratio)
            pi = s["HPO4_N"] * (one + s["H_N"] / k.K_DH)
            factor = (one + pi / (k.P["k_Pi1"] * k.MM)) / (one + pi / (k.P["k_Pi2"] * k.MM))
        elif key == "adenylate_kinase":
            _, _, x, _, _, _ = k.ak(s)
            factor = one + s["Mg_P"] / k.P["K_MgATP"]
            a = k.P["X_AK"] * factor * k.K_BASE * s["ADP_P"] ** 2
        else:
            raise KeyError(key)
        if plant == "wrong_form":
            n = self.kappa
            a = (
                a / (one + k.exp(x / 2))
                if n == 1
                else a * sum(k.exp(D(i) * x / n) for i in range(n))
            )
        elif plant == "dropped_factor":
            a = a / factor
        return x, a

    def inputs_T(self):
        return float(self.inputs["constants"]["T_K"])

    def evaluate(self, values, free, plant=None):
        c = {name: D(repr(v)) for name, v in free.items()}
        c["u"] = D(repr(values["dpsi_mV"])) * self.k.F_OVER_RT_PER_MV
        x, s = self.x_and_s(c, plant)
        exp = self.k.exp
        out = dict(x=x, S=s, J=s * (1 - exp(x)), J_minus=s * exp(x), slopes_lnS={}, slopes_J={})
        h = self.STEP
        for name in [n for n in c if n in self.coordinates()] + ["u"]:
            up, down = dict(c), dict(c)
            if name == "u":
                up["u"], down["u"] = c["u"] + h, c["u"] - h
            else:
                up[name], down[name] = c[name] * exp(h), c[name] * exp(-h)
            (xu, su), (xd, sd) = self.x_and_s(up, plant), self.x_and_s(down, plant)
            out["slopes_lnS"][name] = (su.ln() - sd.ln()) / (2 * h)
            ju, jd = su * (1 - exp(xu)), sd * (1 - exp(xd))
            out["slopes_J"][name] = (ju - jd) / (2 * h)
        return out

    def coordinates(self):
        return {
            "complex_I": ("NADH_N", "NAD_N", "Q_N", "QH2_N", "h_N", "h_P"),
            "complex_III_eq7": ("QH2_N", "Q_N", "c3_P", "c2_P", "h_N", "h_P"),
            "complex_III_eq24": ("QH2_N", "Q_N", "c3_P", "c2_P", "h_N", "h_P", "HPO4_N"),
            "complex_IV": ("O2_N", "c2_P", "c3_P", "h_N", "h_P"),
            "atp_synthase": ("ATP4_N", "ADP3_N", "HPO4_N", "Mg_N", "h_N", "h_P"),
            "nucleotide_exchange": ("ATP4_N", "ADP3_N", "ATP4_P", "ADP3_P"),
            "phosphate_carrier": ("HPO4_N", "HPO4_P", "h_N", "h_P"),
            "k_h_exchange": ("K_N", "K_P", "h_N", "h_P"),
            "nadh_supply": ("NAD_N", "NADH_N", "HPO4_N", "h_N", "S_red_N", "S_ox_N"),
            "adenylate_kinase": ("ADP3_P", "ATP4_P", "AMP_P", "Mg_P"),
        }[self.key]


# ------------------------------------------------------------------ the comparison


def compare_row(result, reference):
    """{quantity: |engine - reference| / band} at one row, slopes per free coordinate."""
    out = {}
    for q in CORE:
        value, band = reference[q]
        engine = result[q] if isinstance(result[q], D) else D(repr(float(result[q])))
        out[q] = abs(engine - value) / band
    for kind in ("slopes_lnS", "slopes_J"):
        values, bands = reference[kind]
        floor = reference["J"][1] if kind == "slopes_J" else D(repr(16 * EPS))
        for name in set(values) | set(result[kind]):
            engine = result[kind].get(name, 0.0)
            engine = engine if isinstance(engine, D) else D(repr(float(engine)))
            band = bands.get(name, D(0)) or floor
            out[f"{kind}[{name}]"] = abs(engine - values.get(name, D(0))) / band
    return out


def compare_law(key, adapter, inputs, rows, plants=("wrong_form", "dropped_factor")):
    states = {s["id"]: s["inputs"] for s in inputs["states"][key]}
    form = next(iter(rows["laws"][key]))
    worst, out_of_band, caught = {}, {}, {p: 0 for p in plants}
    registered = rows["laws"][key][form]
    for row in registered:
        values = states[row["id"]]
        free = free_coordinates(values, inputs)
        reference = reference_on_free(row, free, inputs)
        ratios = compare_row(adapter.evaluate(values, free), reference)
        for q, r in ratios.items():
            worst[q] = max(worst.get(q, D(0)), r)
            if r > 1:
                out_of_band[q] = out_of_band.get(q, 0) + 1
        for p in plants:
            planted = compare_row(adapter.evaluate(values, free, plant=p), reference)
            if max(planted.values()) >= POWER_MARGIN:
                caught[p] += 1
    rows_n = len(registered)
    passed = not out_of_band
    plants_caught = all(caught[p] >= 0.9 * rows_n for p in plants)
    return dict(
        status="compared", form=form, rows=rows_n, passed=passed,
        worst={q: f"{r:.3e}" for q, r in sorted(worst.items(), key=lambda kv: -kv[1])[:8]},
        out_of_band=out_of_band,
        plants={p: dict(caught=caught[p], rows=rows_n) for p in plants},
        plants_caught=plants_caught,
    )  # fmt: skip


LABELS = {
    "engine": "engine evidence: the head's registered laws through forms' monomial pipeline",
    "pipeline-check": "a check of the harness's engine path with lane-built monomial forms for "
    "complex I and the synthase, not the engine's laws",
    "dry-run": "a dry run of the harness with the lane's appendix kernels, not engine evidence",
}


def run(adapter_kind="engine", laws=None, tag=REGISTRATION_TAG):
    inputs, rows = interface("inputs", tag), interface("rows", tag)
    keys = list(laws or COMPARED)
    report = dict(adapter=adapter_kind, label=LABELS[adapter_kind], registration=tag,
                  power_margin=POWER_MARGIN, laws={})  # fmt: skip
    pipeline = pipeline_forms() if adapter_kind == "pipeline-check" else {}
    for key in keys:
        if key in NOT_COMPARED:
            report["laws"][key] = dict(status=f"not compared: {NOT_COMPARED[key]}")
            continue
        if adapter_kind == "dry-run":
            adapter, reason = DryRunAdapter(key, inputs), None
        elif adapter_kind == "pipeline-check":
            if key not in pipeline:
                report["laws"][key] = dict(status="not in the pipeline check")
                continue
            form, spec = pipeline[key]
            adapter, reason = MonomialAdapter(form, spec, inputs), None
        else:
            adapter, reason = engine_adapter(key, inputs)
        if adapter is None:
            report["laws"][key] = dict(status=reason, passed=False)
            continue
        report["laws"][key] = compare_law(key, adapter, inputs, rows)
    compared = [v for v in report["laws"].values() if v.get("status") == "compared"]
    report["compared"] = len(compared)
    report["passed"] = bool(compared) and all(v["passed"] and v["plants_caught"] for v in compared)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--adapter", default="engine", choices=sorted(LABELS))
    parser.add_argument("--laws", help="comma-separated law keys (default: every compared law)")
    parser.add_argument("--out", help="write the report as JSON here")
    args = parser.parse_args(argv)
    report = run(args.adapter, args.laws.split(",") if args.laws else None)
    text = json.dumps(report, indent=1)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(f"{report['label']}\nregistration {report['registration']}: {report['compared']} laws "
          f"compared, passed={report['passed']}")  # fmt: skip
    for key, law in report["laws"].items():
        if law.get("status") != "compared":
            print(f"  {key}: {law['status']}")
            continue
        plants = ", ".join(f"{p} {v['caught']}/{v['rows']}" for p, v in law["plants"].items())
        worst = next(iter(law["worst"].items()))
        print(f"  {key}: {law['rows']} rows, in band: {law['passed']}, worst {worst[0]} "
              f"{worst[1]} bands; plants caught: {plants}")  # fmt: skip
    if not report["compared"]:
        return 2
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
