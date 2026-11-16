"""Looping replay packages of living cells for the viewer (FR-11; docs/LOOPING_REPLAY_DESIGN.md).

A package is one real engine run of laws the engine has, written by the shared output path with
its run view (cells/run_view.py, D154), whose observed rows cover exactly one period of a
periodic state; the writer measures its closure and writes the view's loop block. Each package is
an illustration at a declared low level of detail (D175), never an experiment: no verdict, not
registered.

Each species' cell definition is a builder here (biological definitions apart from engine
mechanisms, ARCHITECTURE), and one generic driver writes every package (driver.py). Nothing
species-specific enters src/cells (D144). Outputs go under /mnt/workspaces/Cells/replay-<date>/.
"""
