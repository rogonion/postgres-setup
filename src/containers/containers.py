import typer
from rich.console import Console
from .core import app as core_app
from .extensions import app as extensions_app
from .runtime import app as runtime_app

app = typer.Typer(help="Container components for the postgres stack.")
console = Console()

app.add_typer(core_app, name="core")
app.add_typer(extensions_app, name="extensions")
app.add_typer(runtime_app, name="runtime")
