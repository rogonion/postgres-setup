from pathlib import Path
from typing import Optional

import typer

from .builder import PostgisBuilder
from postgres_setup.core import load_spec, BuildSpec

app = typer.Typer(help="Add geospatial capabilities to postgres.")


@app.command("build", help="Build postgis binaries from source (postgis).")
def build(
        version: str = typer.Option("latest", "--version", "--v", help="Postgis version."),
        spec_file: Optional[Path] = typer.Option("specs/build.yaml", "--spec", "--s",
                                                 help="Path to build specification file."),
        cache_prefix: Optional[str] = typer.Option("", "--cache-prefix", "--c",
                                                   help="Optional. Custom prefix for generated images acting as cache layers.")
):
    """
    Build postgis binaries from source (postgis).

    :param version: Version of postgis to build.
    :param spec_file: Path to build spec file.
    :param cache_prefix: Custom prefix for cache layers generated.

    :return:
    """
    config = load_spec(spec_file, BuildSpec)

    builder = PostgisBuilder(config, version, cache_prefix)
    builder.build()


@app.command("delete-cache", help="Delete cache images used to build postgis binaries from source (postgis).")
def delete_cache(
        spec_file: Optional[Path] = typer.Option("specs/build.yaml", "--spec", "--s",
                                                 help="Path to build specification file."),
        cache_prefix: Optional[str] = typer.Option("", "--cache-prefix", "--c",
                                                   help="Optional. Custom prefix for generated images acting as cache layers.")
):
    """
    Delete cache images used to build postgis binaries from source (postgis).

    :param spec_file: Path to build spec file.
    :param cache_prefix: Custom prefix for cache layers generated.

    :return:
    """
    config = load_spec(spec_file, BuildSpec)

    builder = PostgisBuilder(config, cache_prefix)

    builder.prune_cache_images()
