import typer
from rich.console import Console
from .postgis import app as postgis_app

app = typer.Typer(help="Extensions for the postgres stack.")
console = Console()

app.add_typer(postgis_app, name="postgis")