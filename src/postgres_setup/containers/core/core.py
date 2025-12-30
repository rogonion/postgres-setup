from pathlib import Path
from typing import Optional

import typer

from .builder import CoreBuilder
from postgres_setup.core import load_spec, BuildSpec

app = typer.Typer(help="Core binaries for postgres.")


@app.command("build", help="Build postgres binaries from source (core).")
def build(
        spec_file: Optional[Path] = typer.Option("specs/build.yaml", "--spec", "--s", help="Path to build specification file."),
        cache_prefix: Optional[str] = typer.Option("", "--cache-prefix", "--c", help="Optional. Custom prefix for generated images acting as cache layers.")
):
    """
    Build postgres binaries from source (core).

    :param spec_file: Path to build spec file.
    :param cache_prefix: Custom prefix for cache layers generated.

    :return:
    """
    config = load_spec(spec_file, BuildSpec)

    builder = CoreBuilder(config,cache_prefix)
    builder.build()


@app.command("delete-cache", help="Delete cache images used to build postgres binaries from source (core).")
def delete_cache(
        spec_file: Optional[Path] = typer.Option("specs/build.yaml", "--spec", "--s", help="Path to build specification file."),
        cache_prefix: Optional[str] = typer.Option("", "--cache-prefix", "--c", help="Optional. Custom prefix for generated images acting as cache layers.")
):
    """
    Delete cache images used to build postgres binaries from source (core).

    :param spec_file: Path to build spec file.
    :param cache_prefix: Custom prefix for cache layers generated.

    :return:
    """
    config = load_spec(spec_file, BuildSpec)


    builder = CoreBuilder(config, cache_prefix=cache_prefix)

    builder.prune_cache_images()
