"""Explicit open-exterior admission declarations; ceilings are domain limits.

Private parent decoders validate real component/owner data without admitting a
closed simulation. The new open schemas alone perform open-system admission.
No reservoir flag, original amount or fixed background is replaced for parsing.
"""

from copy import deepcopy

from cells.core.specs import ConfigError, _fields, _number

EXTERIOR_POLICY = "static_declared_ideal_chemical_and_voltage_reservoirs@1"
DOMAIN_POLICY = "hard_global_ionic_moiety_ceilings_fmol_every_stage@1"
EXTRA = {"exterior_policy", "ionic_moiety_domain_policy", "ionic_moiety_ceiling_fmol"}


def decode(data, model_id, parent_id, parent):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "open owned calcium")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigError("Require open owned-calcium schema_version1")
    raw = deepcopy(data)
    model = raw["model"]
    if not isinstance(model, dict) or model.get("id") != model_id or not EXTRA <= model.keys():
        raise ConfigError("Require the explicit full-catalog open calcium/fuel model")
    extra = {key: model.pop(key) for key in EXTRA}
    if (
        extra["exterior_policy"] != EXTERIOR_POLICY
        or extra["ionic_moiety_domain_policy"] != DOMAIN_POLICY
    ):
        raise ConfigError("Declare static ideal reservoirs and hard ionic-moiety domain limits")
    model["id"] = parent_id
    ionic = model.get("ionic")
    if not isinstance(ionic, dict) or type(ionic.get("extracellular")) is not list:
        raise ConfigError("Declare the actual complete ionic exterior")
    # Both branches retain every ACTUAL reservoir flag. Empty-reservoir
    # reduction runs the original admitted parser and every existing guard.
    open_world = any(row.get("reservoir") is True for row in ionic["extracellular"])
    declared = parent._decode_components(raw) if open_world else parent.parse(raw)
    ceiling = extra["ionic_moiety_ceiling_fmol"]
    if open_world:
        _fields(ceiling, set(declared.model.species_ids), "global ionic-moiety ceiling in fmol")
        ceiling = tuple(
            _number(ceiling[name], name + " ceiling fmol", positive=True)
            for name in declared.model.species_ids
        )
    elif ceiling is not None:
        raise ConfigError("An empty-reservoir reduction requires null open-system ceilings")
    extra["ionic_moiety_ceiling_fmol"] = ceiling
    return declared, extra


def augment(raw, model, model_id):
    ceiling = model.ionic_moiety_ceiling_fmol
    raw["model"].update(
        id=model_id,
        exterior_policy=EXTERIOR_POLICY,
        ionic_moiety_domain_policy=DOMAIN_POLICY,
        ionic_moiety_ceiling_fmol=None
        if ceiling is None
        else dict(zip(model.species_ids, ceiling, strict=True)),
    )
    return raw
