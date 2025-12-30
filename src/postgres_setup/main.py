import typer
from .containers import app as containers_app

app = typer.Typer(help="Postgres Setup CLI Tool.")

app.add_typer(containers_app, name="containers")

if __name__ == "__main__":
    app()
