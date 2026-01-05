from pathlib import Path
from typing import Optional, List, Tuple

import typer

from .builder import RuntimeBuilder
from postgres_setup.core import BuildSpec, load_spec

app = typer.Typer(help="A postgres runtime. Optionally with extensions.")


def parse_extensions(value: str) -> List[Tuple[str, str]]:
    """
    Converts 'postgis=3.6.1,pgvector=latest'
    into [('postgis', '3.6.1'), ('pgvector', 'latest')]
    """
    if not value:
        return []

    results = []
    for item in value.split(","):
        if "=" in item:
            name, version = item.split("=", 1)
            results.append((name.strip(), version.strip()))
        else:
            # Default to 'latest' or a version specified in your YAML
            results.append((item.strip(), "latest"))
    return results


@app.command("build", help="Build a postgres runtime image with extensions (optional).")
def build(
        spec_file: Optional[Path] = typer.Option("configs/build.yaml", "--spec", "--s",
                                                 help="Path to build specification file."),
        image_name: Optional[str] = typer.Option("postgres", "--image-name", "--n",
                                                 help="Name of new postgres runtime image."),
        image_tag: Optional[str] = typer.Option("", "--image-tag", "--t",
                                                help="Optional. Tag of new postgres runtime image"),
        extensions: Optional[str] = typer.Option("", "--extensions", "--e",
                                                 help="Optional. Comma-separated list of extensions e.g, postgis=3.6.1, pgvector=latest"),
        cache_prefix: Optional[str] = typer.Option("", "--cache-prefix", "--c",
                                                   help="Optional. Custom prefix for generated images acting as cache layers.")
):
    """
    Build postgres runtime image with optional extensions.

    :param cache_prefix:
    :param spec_file:
    :param image_name:
    :param image_tag:
    :param extensions:
    :return:
    """
    config = load_spec(spec_file, BuildSpec)

    extension_list = parse_extensions(extensions)

    builder = RuntimeBuilder(config, cache_prefix, image_name, image_tag, extensions=extension_list)

    builder.build()


@app.command("delete-cache", help="Delete cache images used to build postgres runtime image.")
def delete_cache(
        spec_file: Optional[Path] = typer.Option("configs/build.yaml", "--spec", "--s",
                                                 help="Path to build specification file."),
        cache_prefix: Optional[str] = typer.Option("", "--cache-prefix", "--c",
                                                   help="Optional. Custom prefix for generated images acting as cache layers.")
):
    """
    Delete cache images used to build postgres binaries from source (core).

    :param spec_file: Path to build spec file.
    :param cache_prefix: Custom prefix for cache layers generated.

    :return:
    """
    config = load_spec(spec_file, BuildSpec)

    builder = RuntimeBuilder(config, cache_prefix)

    builder.prune_cache_images()
