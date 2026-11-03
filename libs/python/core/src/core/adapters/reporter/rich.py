"""Rich reporter: the Reporter port implementation."""

from rich.console import Console


class RichReporter:
    """Console reporting with rich formatting."""

    def __init__(self) -> None:
        self._console = Console()

    def info(self, message: str) -> None:
        self._console.print(f"[bold blue]postgres-setup[/bold blue] {message}")

    def warn(self, message: str) -> None:
        self._console.print(f"[yellow]warning:[/yellow] {message}")
