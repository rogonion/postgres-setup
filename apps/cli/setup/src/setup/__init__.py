"""setup: the driving (CLI) adapter over the core hexagon."""

from setup.cli import app


def main() -> None:
    app()


__all__ = ["app", "main"]
