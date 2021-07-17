"""Main script.

This module provides basic CLI entrypoint.

"""

import sys
from typing import Optional

import typer

cli = typer.Typer()  # this is actually callable and thus can be an entry point


@cli.command()
def main(x: int = typer.Option(default=1, help="Dummy argument.")) -> Optional[int]:
    """Command line interface for kilroy."""

    typer.echo(x)  # typer.echo instead of print, because it's better


if __name__ == '__main__':
    # entry point for "python -m"
    sys.exit(cli())
