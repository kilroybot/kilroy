"""Main script.

This module provides basic CLI entrypoint.

"""
from dataclasses import dataclass
from typing import Callable

import typer

from kilroy.api.controller import APIController
from kilroy.server import Server

cli = typer.Typer()  # this is actually callable and thus can be an entry point

Log = Callable[[str], None]


@dataclass
class State:
    server: Server


def logger() -> Log:
    return lambda message: typer.echo(message)


def setup(host: str, port: int, log: Log) -> State:
    log("Setting up...")

    controller = APIController()
    server = Server(host=host, port=port, controller=controller)
    state = State(server=server)

    log("Setting up complete.")

    return state


def run(state: State, log: Log) -> None:
    log("Running...")
    state.server.run()


def cleanup(state: State, log: Log) -> None:
    log("Cleaning up...")
    log("Cleaning up complete.")


@cli.command()
def main(
    host: str = typer.Option(
        default="localhost", help="Host to run the server at."
    ),
    port: int = typer.Option(default=8080, help="Port to run the server at."),
) -> None:
    """Command line interface for kilroy."""

    log = logger()
    try:
        state = setup(host, port, log)
    except Exception as e:
        log(f"Exception occurred during setup: {e}")
        raise typer.Exit(1)

    try:
        run(state, log)
    except KeyboardInterrupt:
        log("Server closed by user.")
    except Exception as e:
        log(f"Server closed because of an exception: {e}.")
        raise typer.Exit(2)
    finally:
        cleanup(state, log)


if __name__ == "__main__":
    # entry point for "python -m"
    cli()
