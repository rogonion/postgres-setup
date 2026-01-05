from pathlib import Path
from typing import Optional

import typer

from .builder import PgvectorBuilder
from postgres_setup.core import load_spec, BuildSpec

app = typer.Typer(help="Add vector similarity search capabilities to postgres.")


@app.command("build", help="Build pgvector binaries from source (pgvector).")
def build(
        version: str = typer.Option("latest", "--version", "--v", help="Postgis version."),
        spec_file: Optional[Path] = typer.Option("configs/build.yaml", "--spec", "--s",
                                                 help="Path to build specification file."),
        cache_prefix: Optional[str] = typer.Option("", "--cache-prefix", "--c",
                                                   help="Optional. Custom prefix for generated images acting as cache layers.")
):
    """
    Build pgvector binaries from source (pgvector).

    :param version: Version of pgvector to build.
    :param spec_file: Path to build spec file.
    :param cache_prefix: Custom prefix for cache layers generated.

    :return:
    """
    config = load_spec(spec_file, BuildSpec)

    builder = PgvectorBuilder(config, version, cache_prefix)
    builder.build()


@app.command("delete-cache", help="Delete cache images used to build pgvector binaries from source (pgvector).")
def delete_cache(
        spec_file: Optional[Path] = typer.Option("configs/build.yaml", "--spec", "--s",
                                                 help="Path to build specification file."),
        cache_prefix: Optional[str] = typer.Option("", "--cache-prefix", "--c",
                                                   help="Optional. Custom prefix for generated images acting as cache layers.")
):
    """
    Delete cache images used to build pgvector binaries from source (pgvector).

    :param spec_file: Path to build spec file.
    :param cache_prefix: Custom prefix for cache layers generated.

    :return:
    """
    config = load_spec(spec_file, BuildSpec)

    builder = PgvectorBuilder(config, cache_prefix)

    builder.prune_cache_images()
