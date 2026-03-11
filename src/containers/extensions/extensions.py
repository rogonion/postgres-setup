import typer
from rich.console import Console
from .postgis import app as postgis_app
from .pgvector import app as pgvector_app
from .rum import app as rum_app

app = typer.Typer(help="Extensions for the postgres stack.")
console = Console()

app.add_typer(postgis_app, name="postgis")
app.add_typer(pgvector_app, name="pgvector")
app.add_typer(rum_app, name="rum")
