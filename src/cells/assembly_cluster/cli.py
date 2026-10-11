"""Public cluster CLI using the established detached coupled-job lifecycle."""

from cells.assembly_cell.cli import main as coupled_main


def main(argv=None):
    return coupled_main(argv, cluster=True)
