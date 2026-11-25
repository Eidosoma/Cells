"""The draws of LAWS section 6: Threefry-2x32 (20 rounds) in plain Python integers.

A key is a pair of 32-bit words.  `fold_in(key, word)` encrypts the block (0, word) under the key, a
seed's key is (high word, low word), and the 64-bit words of a draw are the blocks (0, 0) and (0, 1)
under the draw's key, the first output word being the high half.
"""

from __future__ import annotations

from decimal import Decimal

MASK = 0xFFFFFFFF
PARITY = 0x1BD11BDA
ROTATIONS = ((13, 15, 26, 6), (17, 29, 16, 24))
EVENTS_DOMAIN = 1


def threefry2x32(key, block):
    """The block cipher: 20 rounds, a subkey added after every fourth."""
    schedule = (key[0], key[1], key[0] ^ key[1] ^ PARITY)
    x0 = (block[0] + schedule[0]) & MASK
    x1 = (block[1] + schedule[1]) & MASK
    for group in range(5):
        for rotation in ROTATIONS[group % 2]:
            x0 = (x0 + x1) & MASK
            x1 = ((x1 << rotation) | (x1 >> (32 - rotation))) & MASK
            x1 ^= x0
        injection = group + 1
        x0 = (x0 + schedule[injection % 3]) & MASK
        x1 = (x1 + schedule[(injection + 1) % 3] + injection) & MASK
    return x0, x1


def fold_in(key, word):
    return threefry2x32(key, (0, word & MASK))


def fold_in_64(key, number):
    """Fold the low and then the high 32 bits of `number`."""
    return fold_in(fold_in(key, number & MASK), (number >> 32) & MASK)


def uniform_pair(seed, site, counter, domain=EVENTS_DOMAIN):
    """(u1, u2) of draw `counter`, each a double in (0, 1) that the rule gives exactly."""
    if not 0 <= seed < 2**32:
        raise ValueError(f"seed {seed} is outside [0, 2**32)")
    base = (0, seed)
    stream = fold_in(fold_in_64(base, site), domain)
    draw = fold_in_64(stream, counter)
    pair = []
    for element in range(2):
        high, low = threefry2x32(draw, (0, element))
        word = (high << 32) | low
        pair.append(((word & (2**52 - 1)) + 0.5) * 2.0**-52)
    return pair[0], pair[1]


def copy_table(seed, site, pairs):
    """The first `pairs` draws of one copy's stream: the lists of u1 and of u2."""
    rows = [uniform_pair(seed, site, counter) for counter in range(pairs)]
    return [row[0] for row in rows], [row[1] for row in rows]


def thresholds(u1, context):
    """E_k = -ln u1_k, each u1 read as the exact value of its double."""
    return [-context.ln(Decimal(value)) for value in u1]
