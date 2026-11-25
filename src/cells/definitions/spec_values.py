"""The value parsers that the definition schemas share: finite signed and positive numbers,
identifiers, species-aligned tuples, typed immutable tuples and fractions.
"""

from cells.definitions.specs import ConfigError, _fields, _number


def signed_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a finite signed number")
    result = _number(abs(value), name)
    return -result if value < 0 else result


def positive(value, name):
    return _number(value, name, positive=True)


def identifier(value):
    if (
        not isinstance(value, str)
        or not value
        or not value.isascii()
        or any(not (c.isalnum() or c in "_-") for c in value)
    ):
        raise ConfigError("IDs require nonempty ASCII letters, digits, underscore or hyphen")
    return value


def aligned(mapping, ids, name, number=_number):
    _fields(mapping, set(ids), name)
    return tuple(number(mapping[s], name) for s in ids)


def _tuple(value, kind, name, *, size=None):
    if type(value) is not tuple or any(type(v) is not kind for v in value):
        raise ConfigError(f"{name} must be an immutable tuple of {kind.__name__}")
    if size is not None and len(value) != size:
        raise ConfigError(f"{name} has an incompatible length")


def fraction(value, name):
    value = _number(value, name)
    if value > 1:
        raise ConfigError(f"{name} must lie in [0, 1]")
    return value
