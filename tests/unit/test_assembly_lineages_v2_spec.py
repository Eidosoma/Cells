"""The definition of cells.model.assembly_lineages@2 (OL1): parse, round trip, and every refusal.

Structural only: nothing here computes a rate or a free energy (the lead's ruling of 17 November
2026: no numerical output of OL1's laws until the references' design is committed).

Each claim with a planted error it must catch (D187):
- a world parses, and its definition is a fixed point of parse and to_dict, with a stable world id
  (planted: a value changed changes the id);
- every convention is a named token with no default (planted: each token dropped in turn; a
  reserved, an unknown and a disallowed combination);
- D152's rules for steps: at most 3 molecules a side, positive integer counts, conserved moieties,
  no step that changes nothing, places that exist, and a locus that matches the places (planted:
  one breach each);
- the free-energy terms: the ideal term first and once; regular mixing with a symmetric, finite
  chi of zero diagonal over membrane species (planted: a diagonal, a pool species, a pair twice);
- the rate factor: catalysts of the condensed phase only (§0.2a), each pair once, ddG in its
  domain; a GARD law (hosted by @1) cannot be named (planted: each);
- the founder lists every finite place, and holds a membrane molecule under kept and extinct;
- a membrane place on both sides of a step parses under the multinomial measure, and under @1's
  only in a world declared `world_role: probe` (§0.2b rule 8: singular at N = r, +inf there);
  planted: the same step in a world without the role, and a role of another value;
- one declaration, two executions: D152's species and passive reaction entries parse here with
  `phase` in place of `sites` and their values carried unchanged;
- world_role comes only from a registered world file: the reader passes it on, the probe driver adds
  nothing to a world record, and a world the parser refuses is recorded (planted: a driver that adds
  the role);
- a registered refusal world is parsed under the probed pair its `refused_under` names, and rule 8
  refuses it there (planted: the first pair, under which it is an ordinary world);
- every run of the ladder (OL1-4b) has its own stream identity over all rungs and both pairs, as the
  references' design requires ("none shared"; planted: lineage word = the run's index on every
  rung, which repeats across rungs);
- OL5's registered OL2 and OL3 inputs (validation/ool/references/designs, as the references'
  export gives them): the reader maps every world and run, which the parser admits, adding no key
  the mapping does not name; and the parser refuses each of the 22 registered declarations
  (planted: a sigma_max whose missing source took the default provenance would be admitted,
  against the ruling of 22 November 2026; a world key the reader added is caught).
"""

import copy
import dataclasses
import json
from pathlib import Path

import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages import GARD_PAIR_CONSISTENT
from cells.models.assembly_lineages_v2 import MASS_ACTION, MODEL_ID, conventions
from cells.models.assembly_lineages_v2 import spec as v2_spec
from tests.assembly_lineage_v2_fixtures import definition, step, world
from validation.tissue import species_reactions_fixtures as d152


def parsed(the_world, **kw):
    return parse_spec(definition(the_world, **kw))


def refused(the_world, match):
    with pytest.raises(ConfigError, match=match):
        parsed(the_world)


def test_a_world_parses_and_its_definition_is_a_fixed_point():
    spec = parsed(world())
    data = spec.to_dict()
    again = parse_spec(data)
    assert again == spec and again.to_dict() == data and again.fingerprint == spec.fingerprint
    assert data["model"]["id"] == MODEL_ID
    names = [p.name for p in spec.model.world.places]
    assert names == [
        "L@pool", "S@pool", "F@pool", "L@membrane", "P@membrane", "D@membrane", "L@lumen",
        "S@lumen",
    ]  # fmt: skip
    # Planted: one value changed (a step's rate) changes the world's id and the fingerprint.
    other = world()
    other["steps"][0]["forward_rate_per_s"] = 11.0
    changed = parsed(other)
    assert v2_spec.world_id(changed.model.world) != v2_spec.world_id(spec.model.world)
    assert changed.fingerprint != spec.fingerprint


@pytest.mark.parametrize("token", sorted(conventions.TOKENS))
def test_every_convention_is_declared_with_no_default(token):
    planted = world()
    del planted["conventions"][token]
    refused(planted, "every token is declared, with no default")


def test_reserved_unknown_and_disallowed_tokens_are_refused():
    refused(world(conventions={"free_energy_form": "continuum"}), "reserved for the deterministic")
    refused(world(conventions={"membrane_kinetics": "area_on_m"}), "membrane_kinetics is one of")
    refused(world(measure="multinomial_less_one", last="reversible"), "last_molecule 'reversible'")
    refused(world(measure="multinomial", last="extinct"), "last_molecule 'extinct'")
    planted = world()
    planted["conventions"]["extra"] = "x"
    refused(planted, "unknown=\\['extra'\\]")
    for measure, last in (
        ("multinomial", "kept"),
        ("multinomial", "reversible"),
        ("multinomial_less_one", "kept"),
        ("multinomial_less_one", "extinct"),
    ):
        spec = parsed(world(measure=measure, last=last, lumen=False, catalysis=False))
        assert spec.model.world.conventions.offset == conventions.OFFSET[measure]  # fmt: skip


def _with_step(entry, the_world=None):
    out = the_world or world()
    out["steps"].append(entry)
    return out


def test_d152_rules_for_steps_are_kept():
    refused(_with_step(step("four", {"L": 4}, {"D": 1}, 1.0, phase="membrane")), "4 reactant")
    refused(_with_step(step("four_out", {"D": 1}, {"L": 4}, 1.0, phase="membrane")), "4 product")
    refused(_with_step(step("same", {"L": 1}, {"L": 1}, 1.0, phase="membrane")), "changes nothing")
    refused(_with_step(step("half", {"L": 1.5}, {"D": 1}, 1.0, phase="membrane")), "positive int")
    refused(_with_step(step("unbalanced", {"L": 1}, {"P": 1}, 1.0, phase="membrane")), "moieties")
    refused(_with_step(step("nowhere", {"Q@pool": 1}, {"L@membrane": 1}, 1.0, locus="membrane")),
            "not a declared place")  # fmt: skip
    refused(_with_step(step("wrong", {"L@pool": 1}, {"L@membrane": 1}, 1.0, locus="pool")),
            "span phases, so its locus is the membrane")  # fmt: skip
    refused(_with_step(step("inside", {"S@pool": 2}, {"S@pool": 1, "S@lumen": 1}, 1.0,
                            locus="lumen")), "span phases")  # fmt: skip
    planted = world()
    planted["steps"].append(copy.deepcopy(planted["steps"][0]))
    refused(planted, "step IDs are unique")
    planted = world()
    planted["steps"][0]["law"] = "cells.exchange.reservoir_exchange@1"
    refused(planted, "law is one of")


def test_the_free_energy_terms_are_refused_out_of_form():
    planted = world()
    planted["free_energy"].reverse()
    refused(planted, "first, exactly once")
    planted = world()
    planted["free_energy"].append({"law": "cells.free_energy.ideal_mixing@1"})
    refused(planted, "first, exactly once")
    for pair, match in ((["L", "L"], "zero diagonal"), (["L", "S"], "not a membrane species")):
        planted = world()
        planted["free_energy"][1]["chi_kT"].append({"pair": pair, "chi": 1.0})
        refused(planted, match)
    planted = world()
    planted["free_energy"][1]["chi_kT"].append({"pair": ["P", "L"], "chi": 1.0})
    refused(planted, "listed twice")
    planted = world()
    planted["free_energy"][1]["chi_kT"][0]["chi"] = float("inf")
    refused(planted, "finite number")


def test_the_rate_factor_is_refused_out_of_its_scope():
    planted = world()
    planted["rate_factor"]["catalysing_phase"] = "lumen"
    refused(planted, "the catalysing phase is the membrane in OL1")
    planted = world()
    planted["rate_factor"]["entries"][0]["catalyst"] = "S"
    refused(planted, "is not a species of the membrane")
    planted = world()
    planted["rate_factor"]["entries"].append(dict(planted["rate_factor"]["entries"][0]))
    refused(planted, "listed twice")
    planted = world()
    planted["rate_factor"]["entries"][0]["ddG_kT"] = -31.0
    refused(planted, "ddG_kT is in")
    planted = world()
    planted["rate_factor"]["law"] = GARD_PAIR_CONSISTENT  # Hosted by @1: not this family's.
    refused(planted, "is not a cells.rate_factor_law@2 of cells.model.assembly_lineages@2")
    # A factor on a step wholly in the pool or wholly in the lumen (the lead's ruling of 20
    # November); one on a step through the wall (pool to lumen) stays admitted.
    entry = {"catalyst": "P", "step": "make_L", "ddG_kT": 0.4}
    planted = world()
    planted["rate_factor"]["entries"].append(entry)
    refused(planted, "lies wholly in the pool")
    planted = world()
    planted["phases"]["lumen"]["species"].append("F")
    planted["founder"]["F@lumen"] = 0
    planted["steps"].append(step("make_L_inside", {"F": 1}, {"L": 1}, 0.1, phase="lumen"))
    planted["rate_factor"]["entries"].append(dict(entry, step="make_L_inside"))
    refused(planted, "lies wholly in the lumen")
    planted = world()
    planted["rate_factor"]["entries"].append(dict(entry, step="permeate_S"))
    parsed(planted)


def test_the_founder_and_the_measure_s_refusals():
    planted = world()
    del planted["founder"]["S@pool"]
    refused(planted, "missing=\\['S@pool'\\]")
    planted = world()
    planted["founder"]["F@pool"] = 3
    refused(planted, "unknown=\\['F@pool'\\]")
    for last in ("kept", "extinct"):
        planted = world(measure="multinomial_less_one" if last == "extinct" else "multinomial",
                        last=last, catalysis=False)  # fmt: skip
        planted["founder"].update({"L@membrane": 0, "P@membrane": 0, "D@membrane": 0})
        refused(planted, "holds at least one molecule")
    empty = world(last="reversible")
    empty["founder"].update({"L@membrane": 0, "P@membrane": 0, "D@membrane": 0})
    assert parsed(empty).model.world.conventions.last_molecule == "reversible"
    # P on both sides: a P catalyses L + P -> D, written out (2 P + L -> D + P, balanced).
    both = step("catalysed", {"P": 2, "L": 1}, {"D": 1, "P": 1}, 1.0, phase="membrane")
    assert parsed(_with_step(copy.deepcopy(both), world(lumen=False))).model.world.steps[-1]
    one = world(measure="multinomial_less_one", lumen=False, catalysis=False)
    refused(_with_step(copy.deepcopy(both), copy.deepcopy(one)), "§0.2b rule 8")  # Planted.
    probe = _with_step(copy.deepcopy(both), copy.deepcopy(one))
    probe["world_role"] = "probe"
    spec = parsed(probe)
    assert spec.model.world.role == "probe" and spec.model.world.steps[-1].id == "catalysed"
    assert spec.to_dict()["model"]["world"]["world_role"] == "probe"  # It is part of the world.
    plain = parsed(world(lumen=False))
    assert "world_role" not in plain.to_dict()["model"]["world"]
    other = copy.deepcopy(probe)
    other["world_role"] = "run"  # Planted: a role of another value.
    refused(other, "world_role is probe")


def test_the_experiment_and_execution_are_refused_out_of_form():
    data = definition(world())
    del data["experiment"]["trace"]
    with pytest.raises(ConfigError, match="missing=\\['trace'\\]"):
        parse_spec(data)
    data = definition(world(), molecules=10)  # Below the founder's largest count (50).
    with pytest.raises(ConfigError, match="molecule_capacity"):
        parse_spec(data)
    data = definition(world())
    data["model"]["world"]["units"]["time"] = "nominal"
    with pytest.raises(ConfigError, match="physical units"):
        parse_spec(data)


def test_one_declaration_d152_s_entries_parse_with_their_values_unchanged():
    """D152's species and passive reaction entries, as its own fixtures write them, parse here with
    `phase` in place of `sites` (and no `factors`): stoichiometry, rate constant, potential and
    moieties are carried unchanged (SHARED_INVENTORY_REACTIONS_DESIGN §2.1; the design note
    §2.3)."""
    entries = [
        d152.species("A", moieties={"x": 1}, mu=-0.5),
        d152.species("B", moieties={"x": 1}, mu=0.25),
        d152.species("C", moieties={"x": 2}, mu=-2.0),
    ]
    reaction = d152.passive("bind", "all", {"A": 1, "B": 1}, {"C": 1}, 3.5)
    assert reaction["law"] == d152.PASSIVE
    the_world = world(lumen=False, regular=False, catalysis=False, held=False)
    the_world["species"] += entries
    the_world["phases"]["pool"]["species"] += [{"id": n, "kind": "finite"} for n in "ABC"]
    the_world["founder"].update({"A@pool": 3, "B@pool": 4, "C@pool": 0})
    here = {k: v for k, v in reaction.items() if k not in ("sites", "factors")}
    here.update(phase="pool", law=MASS_ACTION)
    the_world["steps"].append(here)
    spec = parsed(the_world)
    bound = spec.model.world.steps[-1]
    assert dict(bound.reactants) == {"A@pool": 1, "B@pool": 1}
    assert dict(bound.products) == {"C@pool": 1}
    assert bound.forward_rate_per_s == reaction["forward_rate_per_s"] and bound.locus == "pool"
    by_id = {s.id: s for s in spec.model.world.species}
    for entry in entries:
        assert by_id[entry["id"]].mu_solution == entry["standard_mu_RT"]
        assert dict(by_id[entry["id"]].moieties) == entry["moieties"]


def registered_world(*, role=None):
    """A minimal registered world (the references' format, ool_references.world@1): a membrane of
    A, B and C, with A + B + C -> C + C (C on both sides: rule 8's step under @1's measure)."""
    species = [
        {"id": n, "moieties": m, "standard_mu_RT": {"bilayer": {"float": mu}}}
        for n, m, mu in (("A", {"a": 1}, 0.0), ("B", {"b": 1}, 0.0), ("C", {"a": 1, "b": 1}, -0.7))
    ]
    out = {
        "format": "ool_references.world@1",
        "units": {"time": "s"},
        "temperature_K": 298.15,
        "standard_concentration_mM": {"float": 1.0},
        "phases": {"membrane": {"kind": "condensed"}},
        "species": species,
        "places": [{"species": n, "phase": "membrane"} for n in "ABC"],
        "regular_mixing_chi": [],
        "steps": [
            {"id": "r", "law": MASS_ACTION, "locus": "membrane",
             "reactants": {"A@membrane": 1, "B@membrane": 1, "C@membrane": 1},
             "products": {"C@membrane": 2}, "forward_rate_per_s": {"float": 1.0},
             "transition_state_factor": []}
        ],
        "initial_state": {"A@membrane": 2, "B@membrane": 2, "C@membrane": 1},
    }  # fmt: skip
    if role is not None:
        out["world_role"] = role
    return out


def added_keys(registered, definition):
    """World keys a definition carries that its registered file does not state (none may be)."""
    world = definition["model"]["world"]
    stated = {"units", "conventions", "species", "phases", "steps", "free_energy", "founder"}
    stated |= (
        {"rate_factor"} if any(s["transition_state_factor"] for s in registered["steps"]) else set()
    )
    stated |= {"world_role"} if "world_role" in registered else set()
    return set(world) - stated


def test_world_role_comes_only_from_the_registered_file(tmp_path):
    """§0.2b rule 8: the role is the registered world's own declaration; the reader passes it on as
    it is, and the probe driver adds nothing to a world record. A world the parser refuses is
    recorded with the parser's message (planted: a driver that adds the role)."""
    from validation.assembly_lineages_v2 import probes

    pair = ("multinomial_less_one", "extinct")
    for role in (None, "probe"):
        source = registered_world(role=role)
        made = probes._definition(source, pair, horizon=1.0, events=1, row_every=1)
        assert added_keys(source, made) == set()
        assert made["model"]["world"].get("world_role") == role
    planted = probes._definition(registered_world(), pair, horizon=1.0, events=1, row_every=1)
    planted["model"]["world"]["world_role"] = "probe"  # Planted: the driver adds the role.
    assert added_keys(registered_world(), planted) == {"world_role"}
    # Without the role, rule 8 refuses the world, and the refusal is recorded, not raised.
    without = probes._definition(registered_world(), pair, horizon=1.0, events=1, row_every=1)
    assert probes._parsed_or_refusal(tmp_path / "a", without, {"role": "test"}) is None
    message = json.loads((tmp_path / "a" / "refused.json").read_text())["message"]
    assert "§0.2b rule 8" in message
    with_role = probes._definition(registered_world(role="probe"), pair, horizon=1.0, events=1,
                                   row_every=1)  # fmt: skip
    spec = probes._parsed_or_refusal(tmp_path / "b", with_role, {"role": "test"})
    assert spec is not None and spec.model.world.role == "probe"


def test_a_refusal_world_is_parsed_under_the_pair_it_names(tmp_path):
    from validation.assembly_lineages_v2 import probes

    source = registered_world() | {"refused_under": {"condensed_measure": "multinomial_less_one"}}
    assert probes.refusal_pair(source) == ("multinomial_less_one", "extinct")
    assert probes.refusal_pair(registered_world()) == probes.PAIRS[0]
    (tmp_path / "inputs" / "refusals").mkdir(parents=True)
    (tmp_path / "inputs" / "refusals" / "singular.world.json").write_text(json.dumps(source))
    probes.refusals(tmp_path / "inputs", tmp_path / "out")
    (entry,) = json.loads((tmp_path / "out" / "refusals" / "refusals.json").read_text())["results"]
    assert entry["refused"] and "§0.2b rule 8" in entry["message"]
    assert entry["conventions"]["condensed_measure"] == "multinomial_less_one"
    planted = probes._definition(source, probes.PAIRS[0], horizon=1.0, events=1, row_every=1)
    assert parse_spec(planted).model.world.role is None  # Planted: the first pair admits it.


def test_every_ladder_run_has_its_own_stream_identity():
    from validation.assembly_lineages_v2 import probes

    spec = parse_spec(definition(world()))
    blocks = [(r, p) for r in range(len(probes.WB_RUNGS)) for p in range(len(probes.PAIRS))]

    def identities(specs):
        return [json.dumps(v2_spec.stream_identity(s), sort_keys=True) for s in specs]

    made = [i for rung, pair in blocks for i in identities(probes.wb_specs(spec, rung, pair))]
    assert len(made) == len(blocks) * probes.WB_RUNS == len(set(made))
    assert probes.wb_lineages(0, 0) == tuple(range(probes.WB_RUNS))  # the first block as before
    shared = [dataclasses.replace(spec, execution=dataclasses.replace(spec.execution, lineage=w))
              for w in range(probes.WB_RUNS)]  # fmt: skip
    planted = [i for _ in blocks for i in identities(shared)]  # Planted: index on every rung.
    assert len(set(planted)) == probes.WB_RUNS < len(planted)  # shared across rungs: caught


REGISTERED2 = Path(__file__).resolve().parents[2] / "validation" / "ool" / "references" / "designs"
KERNEL_WORLDS2 = ("ol2_wa", "ol2_wa_diffusion", "ol2_closed", "ol2_two")
WORLD_KEYS2 = {"units", "conventions", "species", "phases", "steps", "free_energy", "founder",
               "geometry", "population", "division"}  # fmt: skip


def registered2(name):
    """A registered OL2/OL3 document as OL5's export gives it: its free-text description and the
    role tags on a founder's vesicles removed (the export's two removed fields, not inputs)."""
    document = json.loads((REGISTERED2 / name).read_text())
    document.pop("description", None)
    for vesicle in (document.get("founder") or {}).get("vesicles") or []:
        vesicle.pop("role", None)
    return document


def test_the_registered_ol2_and_ol3_inputs_map_and_every_declaration_is_refused():
    """OL5's probe roles (FORMAT_OL2.md): every registered world and run maps and parses, with no
    key beyond the mapping's; each of the 22 declarations is refused by the parser, the reader
    raising for none. Parse only: no rate is computed."""
    from validation.assembly_lineages_v2 import probes2
    from validation.assembly_lineages_v2 import registered as reader

    settings = {"experiment": probes2.PROBE_EXPERIMENT, "execution": probes2.EXECUTION}
    division = registered2("ol3_division.json")["worlds"]
    for name in KERNEL_WORLDS2:
        document = registered2(f"{name}.world2.json")
        vesicle = 0 if "vesicles" in document["founder"] else None
        made = reader.definition2(document, vesicle=vesicle, **settings)
        assert set(made["model"]["world"]) <= WORLD_KEYS2
        parse_spec(made)
    runs = sorted(REGISTERED2.glob("*_run.json"))
    assert len(runs) == 6
    for path in runs:
        run = registered2(path.name)
        made = reader.definition2(registered2(f"{run['world']}.world2.json"), run=run,
                                  division=division.get(run["world"]), **settings)  # fmt: skip
        assert set(made["model"]["world"]) <= WORLD_KEYS2
        assert parse_spec(made).execution.mode == run["mode"]
    planted = copy.deepcopy(made)
    planted["model"]["world"]["registered_units"] = {}  # Planted: a key the reader added.
    assert not set(planted["model"]["world"]) <= WORLD_KEYS2
    declarations = sorted((REGISTERED2 / "refusals2").glob("*.json"))
    assert len(declarations) == 22
    for path in declarations:
        document = registered2(f"refusals2/{path.name}")
        if document["format"] == reader.RUN_FORMAT2:
            made = reader.definition2(registered2(f"{document['world']}.world2.json"),
                                      run=document, division=division.get(document["world"]),
                                      **settings)  # fmt: skip
        else:
            made = reader.definition2(document, **settings)
        with pytest.raises(ConfigError):
            parse_spec(made)
    # sigma_max's source (§0.2c rule 8, as ruled): a missing one passes through as no provenance.
    sourceless = registered2("refusals2/refuse_sigma_max_without_source.world2.json")
    made = reader.definition2(sourceless, **settings)
    sigma = made["model"]["world"]["geometry"]["sigma_max_N_per_m"]
    assert "provenance" not in sigma
    with pytest.raises(ConfigError, match="sigma_max_N_per_m is"):
        parse_spec(made)
    sigma["provenance"] = reader.provenance2(sourceless)  # Planted: the default put in its place.
    parse_spec(made)
