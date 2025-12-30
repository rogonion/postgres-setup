from pathlib import Path
from typing import TypeVar, Type

import typer
import yaml
from pydantic import BaseModel
from rich.console import Console

console = Console()

T = TypeVar("T", bound=BaseModel)


def load_spec(spec_file: Path, model: Type[T]) -> T:
    """
    Parse YAML spec and validate it

    :param spec_file: path to spec file.
    :param model: Spec class.
    :return: Build configuration
    """
    if not spec_file.exists():
        console.print(f"[bold red]Error:[/bold red] Spec file '{spec_file}' not found.")
        raise typer.Exit(code=1)

    with open(spec_file, "r") as f:
        yaml_data = yaml.safe_load(f)

    try:
        return model(**yaml_data)
    except Exception as e:
        console.print(f"[bold red]Invalid Configuration:[/bold red]\n{e}")
        raise typer.Exit(code=1)
