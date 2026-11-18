"""Source layouts: no checkpoint crosses a source move (D188, D195 item 4).

Every checkpoint records the source that wrote it, `source_hashes`: each engine file's path under
src/cells with its SHA-256 (io.source_hashes). Its paths are the layout it was written in, so the
layout identity needs no field of its own, changes no byte a checkpoint holds, and covers the
checkpoints written before this module. A source move renames the engine's files. A checkpoint
written before a move is refused by both loaders, io.load_snapshot and batch_io.load_batch_snapshot,
before either identity comparison, so on both routes: without a continuity record and with one,
which cannot admit it. The refusal names the tag of the last tree before the move, where the
checkpoint restores.

A move is declared in MOVES once it is made, by the package folders it dissolved (paths relative to
src/cells): a checkpoint whose recorded files lie in one of them was written before the move. A
dissolved folder holds no engine file afterwards, and tests/unit/test_continuity_loaders.py holds
every declared move to this installation, so no checkpoint written after a move is refused for it.
A move that dissolves no folder needs another mark. The folders are written as plain paths, never
as module names, so a move's rewrite (scripts/source_moves.py) leaves them as they are.

This module imports nothing but the definitions' error: checkpoint continuity, which imports no
numpy, reaches it through the loaders.
"""

from typing import NamedTuple

from cells.definitions.specs import ConfigError


class Move(NamedTuple):
    """One made source move."""

    name: str  # The move as its decision names it, e.g. "D188 move 2".
    dissolved: tuple  # The package folders it dissolved, relative to src/cells.
    restores_at: str  # The tag of the last tree before the move.


# The made moves, oldest first. D188 move 2 declares itself in the commit after its move commit.
MOVES: tuple = (Move("D188 move 2", ("core", "processes"), "pre-d188-move2-2026-11-18"),)


def folders(sources):
    """The package folders that a recorded source map's files lie in (relative to src/cells)."""
    return {path.rpartition("/")[0] for path in sources if "/" in path}


def predates(sources):
    """The declared moves made since a source map was recorded, oldest first."""
    if not isinstance(sources, dict):  # Not a source map: the source comparison refuses it.
        return []
    held = folders(sources)
    return [
        move
        for move in MOVES
        if any(f == d or f.startswith(d + "/") for f in held for d in move.dissolved)
    ]


def require(sources, what):
    """Refuse a record (`what`, e.g. "Checkpoint") whose source map predates a declared move."""
    since = predates(sources)
    if since:
        move = since[0]
        raise ConfigError(
            f"{what} was written in the source layout before {move.name}; no checkpoint crosses "
            f"a source move (D195): it restores in the tree tagged {move.restores_at}"
        )
