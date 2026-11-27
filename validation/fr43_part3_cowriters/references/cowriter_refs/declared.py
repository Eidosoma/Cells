"""The declared worlds as exact numbers, and the planted changes of LAWS section 9.

Every declared real is read as the exact value of its nearest double (LAWS, opening).  The grid (steps,
sample times, horizons) is read as the declared decimal, so that a horizon is a whole number of steps.
A block whose shape is not the one the laws cover is refused here, never reinterpreted.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

AVOGADRO_PER_MOL = Decimal("6.02214076e23")
FREE, ACTIVE = 0, 1
CHANNELS = ("assemble", "dissolve")
COUNTS_AFTER = {"assemble": [0, 1], "dissolve": [2, 0]}


def exact(value):
    """The exact value of a declared number's nearest double."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"not a declared number: {value!r}")
    return Decimal(float(value))


def grid(value):
    """A declared time of the grid, as the decimal it was declared as."""
    return Decimal(repr(float(value)))


def copy_fmol():
    """One molecule in fmol: the decimal quotient 10^15 / N_A, read as its nearest double."""
    return Decimal(float(Decimal(10) ** 15 / AVOGADRO_PER_MOL))


def _require(condition, what):
    if not condition:
        raise ValueError(f"the declared block is not of the shape the laws cover: {what}")


@dataclass(frozen=True)
class Site:
    """The population of one site of two subunits, and its transfer (LAWS section 1)."""

    assemble_rate: Decimal  # 1/s, or 1/s at 1 mM where the channel reads
    dissolve_rate: Decimal  # 1/s
    read: str | None  # "cell", "node" or None: where `assemble` reads the shared row
    conductance: Decimal  # pL/s of the one active unit


@dataclass(frozen=True)
class ReactionsWorld:
    """W5's and W5-exact's world: X -> S and S + Y -> W in the cell (LAWS section 2)."""

    name: str
    cell: Decimal
    node: Decimal
    end: Decimal
    samples: tuple
    start: dict
    make_rate: Decimal
    spend_rate: Decimal
    site: Site
    kind: str = "reactions"


@dataclass(frozen=True)
class GeneWorld:
    """W6's world: one gene unit beside the population (LAWS section 3)."""

    name: str
    cell: Decimal
    node: Decimal
    end: Decimal
    samples: tuple
    start: dict
    machines: Decimal  # fmol, every machine free at the start
    template_conc: Decimal  # mM
    stages: int
    residues: int
    stage_residues: int
    stage_rate: Decimal  # kappa, 1/s
    saturation: Decimal  # K_N, mM
    initiation: Decimal  # k_I, 1/(mM s)
    degradation: Decimal  # k_R, 1/s
    mu: dict  # RT units: N, M, Pi and the residue
    standard: Decimal  # c0, mM
    site: Site
    transcription_factor: bool = True  # False: 1 - e^x replaced by 1 (P11)
    degradation_factor: bool = True  # False: 1 - e^y replaced by 1 (P12)
    kind: str = "gene"


def _site(block, species):
    states = [(s["id"], s["subunits"]) for s in block["unit_states"]]
    _require(states == [("free", 1), ("active", 2)], "unit states")
    _require(block["initial_counts"] == {"free": 2, "active": 0}, "initial counts")
    assemble, dissolve = block["channels"]
    _require(
        (assemble["id"], assemble["reactants"], assemble["products"]) == ("assemble", {"free": 2}, {"active": 1}),
        "the channel assemble",
    )
    _require(
        (dissolve["id"], dissolve["reactants"], dissolve["products"]) == ("dissolve", {"active": 1}, {"free": 2}),
        "the channel dissolve",
    )
    _require(dissolve.get("read") is None, "dissolve reads nothing")
    read = assemble.get("read")
    if read is not None:
        _require(read["species"] == species and read["at"] in ("cell", "node"), "the read")
    transfer = block["transfer"]
    _require(transfer["species"] == species, "the transfer's species")
    _require(transfer["conductance_pL_per_s"]["free"] == 0.0, "free units conduct nothing")
    return Site(
        assemble_rate=exact(assemble["rate_constant"]),
        dissolve_rate=exact(dissolve["rate_constant"]),
        read=None if read is None else read["at"],
        conductance=exact(transfer["conductance_pL_per_s"]["active"]),
    )


def _reactions(name, block):
    make, spend = block["reactions"]
    _require((make["id"], make["reactants"], make["products"]) == ("make", {"X": 1}, {"S": 1}), "make")
    _require((spend["id"], spend["reactants"], spend["products"]) == ("spend", {"S": 1, "Y": 1}, {"W": 1}), "spend")
    _require((make["rate_unit"], spend["rate_unit"]) == ("1/s", "1/(mM s)"), "the reactions' units")
    rows = block["rows_fmol"]
    return ReactionsWorld(
        name=name,
        cell=exact(block["cell_pL"]),
        node=exact(block["node_pL"]),
        end=grid(block["end_s"]),
        samples=tuple(grid(t) for t in block["samples_s"]),
        start={
            "n_S_c": exact(rows["S_cell"]),
            "n_S_o": exact(rows["S_node"]),
            "n_X": exact(rows["X"]),
            "n_Y": exact(rows["Y"]),
            "n_W": exact(rows["W"]),
        },
        make_rate=exact(make["rate_constant"]),
        spend_rate=exact(spend["rate_constant"]),
        site=_site(block["population"], "S"),
    )


def _gene(name, block):
    gene = block["gene"]
    _require(gene["product"] == "R" and gene["degradation"]["polymer"] == "R", "the product")
    _require(gene["draws"] == {"N": 1} and gene["releases"] == {"Pi": 2}, "the draws and releases")
    residues, stages = gene["residues"], gene["stages"]
    _require(residues % stages == 0, "stages divide the residues")
    _require(gene["degradation"]["monomers"] == {"M": residues}, "the degradation's monomers")
    _require(set(gene["saturation_mM"]) == {"N"}, "the saturation")
    rows, mu = block["rows_fmol"], gene["mu_RT"]
    cell, copy = exact(block["cell_pL"]), copy_fmol()
    return GeneWorld(
        name=name,
        cell=cell,
        node=exact(block["node_pL"]),
        end=grid(block["end_s"]),
        samples=tuple(grid(t) for t in block["samples_s"]),
        start={
            "n_R_c": exact(rows["R_cell"]),
            "n_R_o": exact(rows["R_node"]),
            "n_N": exact(rows["N"]),
            "n_M": exact(rows["M"]),
            "n_Pi": exact(rows["Pi"]),
        },
        machines=gene["machines_copies"] * copy,
        template_conc=gene["template_copies"] * copy / cell,
        stages=stages,
        residues=residues,
        stage_residues=residues // stages,
        stage_rate=exact(gene["speed_per_s"]) / (residues // stages),
        saturation=exact(gene["saturation_mM"]["N"]),
        initiation=exact(gene["initiation_per_mM_s"]),
        degradation=exact(gene["degradation"]["rate_per_s"]),
        mu={
            "N": exact(mu["N"]),
            "M": exact(mu["M"]),
            "Pi": exact(mu["Pi"]),
            "residue": Decimal(float(mu["R"]) / float(residues)),  # formed in doubles (LAWS section 3)
        },
        standard=exact(gene["c0_mM"]),
        site=_site(block["population"], "R"),
    )


def world(name, block):
    """The world of `inputs["worlds"][name]`.  Its divisions are formed in the current context."""
    _require(block["samples_s"][0] == 0.0 and block["samples_s"][-1] == block["end_s"], "the samples")
    if block["kind"] == "reactions":
        return _reactions(name, block)
    if block["kind"] == "gene":
        return _gene(name, block)
    raise ValueError(f"unknown kind {block['kind']!r}")


ONE_PERCENT = Decimal(1.01)  # the exact value of the declared factor's nearest double
SERIES_PLANTS = ("P1", "P2", "P5", "P9", "P10", "P10-W6", "P11", "P12")


def planted(base, plant):
    """The world with one reference plant's change (LAWS section 9), checked against `inputs.json`."""
    name, change, site = plant["id"], plant["change"], base.site
    if name == "P1" and change == {"reactions.make.rate_constant": "x 1.01"}:
        return replace(base, make_rate=base.make_rate * ONE_PERCENT)
    if name == "P2" and change == {"gene.initiation_per_mM_s": "x 1.01"}:
        return replace(base, initiation=base.initiation * ONE_PERCENT)
    if name == "P5" and change == {"population.channels.assemble.rate_constant": "x 1.01"}:
        return replace(base, site=replace(site, assemble_rate=site.assemble_rate * ONE_PERCENT))
    if name == "P9" and change == {"population.channels.assemble.read.at": "node"}:
        return replace(base, site=replace(site, read="node"))
    if name == "P10" and change == {"reactions": "both rate constants 0"}:
        return replace(base, make_rate=Decimal(0), spend_rate=Decimal(0))
    if name == "P10-W6" and change == {"gene.initiation_per_mM_s": 0}:
        return replace(base, initiation=Decimal(0))
    if name == "P11" and change == "transcription's reversibility factor 1 - e^x replaced by 1":
        return replace(base, transcription_factor=False)
    if name == "P12" and change == "the degradation's reversibility factor 1 - e^y replaced by 1":
        return replace(base, degradation_factor=False)
    raise ValueError(f"no series plant {name!r} with the change {change!r}")


def machine_start(base):
    """The machines at t = 0: every one free, every stage complex at exactly 0."""
    return [base.machines] + [Decimal(0)] * base.stages
