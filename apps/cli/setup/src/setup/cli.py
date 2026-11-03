"""Typer CLI: the primary (driving) adapter over the core use cases.

Commands stay thin: parse flags, delegate to the composition root, translate
domain errors into exit code 1.
"""

from pathlib import Path
from typing import Annotated, Optional

import typer

from core.domain.errors import CoreError
from setup.composition import (
    run_assemble,
    run_build,
    run_build_core,
    run_build_extension,
    run_clean,
    run_profiles,
    run_pull,
    run_push,
    run_tag,
)

app = typer.Typer(
    name="setup",
    help="Build pinned PostgreSQL from source into container artifact images "
    "and the runtime image (the product).",
    no_args_is_help=True,
)

ProfileOption = Annotated[
    Optional[str],
    typer.Option("--profile", "-p", help="Build profile (see config/profiles.toml)."),
]
ForceOption = Annotated[
    bool, typer.Option("--force", "-f", help="Rebuild even if the image exists.")
]
JobsOption = Annotated[
    Optional[int],
    typer.Option(
        "--jobs", "-j", help="Parallel compile jobs (default: profile jobs, else half the CPUs)."
    ),
]
FromOption = Annotated[
    str,
    typer.Option(
        "--from",
        help="How to resolve a missing image: auto (pull if a registry is "
        "configured, else build) | build | pull.",
    ),
]


@app.callback()
def main(
    ctx: typer.Context,
    config_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--config-dir",
            help="Config directory to read default.toml / pins.toml / profiles.toml / "
            "registry.toml from (default: <workspace-root>/config).",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ] = None,
) -> None:
    ctx.obj = {"config_dir": config_dir}


def _run(action) -> None:
    try:
        action()
    except CoreError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def build(
    ctx: typer.Context,
    profile: ProfileOption = None,
    force: ForceOption = False,
    jobs: JobsOption = None,
) -> None:
    """Build all of the profile's images: core, each enabled extension, runtime."""
    _run(
        lambda: run_build(profile=profile, force=force, jobs=jobs, config_dir=ctx.obj["config_dir"])
    )


@app.command()
def build_core(
    ctx: typer.Context,
    profile: ProfileOption = None,
    force: ForceOption = False,
    jobs: JobsOption = None,
) -> None:
    """Build only the core artifact image (postgres:<profile>-<version>)."""
    _run(
        lambda: run_build_core(
            profile=profile, force=force, jobs=jobs, config_dir=ctx.obj["config_dir"]
        )
    )


@app.command()
def build_extension(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Extension name (postgis, pgvector, rum).")],
    profile: ProfileOption = None,
    force: ForceOption = False,
    jobs: JobsOption = None,
) -> None:
    """Build one extension image FROM the core image (extension/<name>:...)."""
    _run(
        lambda: run_build_extension(
            name, profile=profile, force=force, jobs=jobs, config_dir=ctx.obj["config_dir"]
        )
    )


@app.command()
def assemble(
    ctx: typer.Context,
    profile: ProfileOption = None,
    force: ForceOption = False,
    jobs: JobsOption = None,
    from_source: FromOption = "auto",
) -> None:
    """Assemble the runtime image (runtime:<profile>-<version>) from core + extensions."""
    _run(
        lambda: run_assemble(
            profile=profile,
            force=force,
            jobs=jobs,
            source=from_source,
            config_dir=ctx.obj["config_dir"],
        )
    )


@app.command()
def runtime(
    ctx: typer.Context,
    profile: ProfileOption = None,
    force: ForceOption = False,
    jobs: JobsOption = None,
    from_source: FromOption = "auto",
) -> None:
    """Assemble the runtime image — the product (alias of `assemble`)."""
    _run(
        lambda: run_assemble(
            profile=profile,
            force=force,
            jobs=jobs,
            source=from_source,
            config_dir=ctx.obj["config_dir"],
        )
    )


@app.command()
def push(ctx: typer.Context, profile: ProfileOption = None) -> None:
    """Push the profile's final images (runtime, core, extensions) to the registry."""
    _run(lambda: run_push(profile=profile, config_dir=ctx.obj["config_dir"]))


@app.command()
def pull(ctx: typer.Context, profile: ProfileOption = None) -> None:
    """Pull the profile's final images from the registry, retagged local."""
    _run(lambda: run_pull(profile=profile, config_dir=ctx.obj["config_dir"]))


@app.command()
def clean(
    ctx: typer.Context,
    profile: ProfileOption = None,
    cache: Annotated[
        bool,
        typer.Option("--cache", help="Also prune the profile's layer-cache images."),
    ] = False,
) -> None:
    """Prune the profile's layer-cache images (with --cache)."""
    _run(lambda: run_clean(profile=profile, cache=cache, config_dir=ctx.obj["config_dir"]))


@app.command()
def tag(ctx: typer.Context, profile: ProfileOption = None) -> None:
    """Print the runtime image tag for the profile."""
    _run(lambda: typer.echo(run_tag(profile=profile, config_dir=ctx.obj["config_dir"])))


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List the available build profiles."""

    def action() -> None:
        loaded = run_profiles(config_dir=ctx.obj["config_dir"])
        for name in loaded.names():
            marker = " (default)" if name == loaded.default else ""
            typer.echo(f"{name}{marker}")
            profile = loaded.profiles[name]
            typer.echo(f"  version:    {profile.version}")
            typer.echo(f"  base image: {profile.base_image}")
            typer.echo(f"  prefix:     {profile.prefix}")
            typer.echo(f"  jobs:       {profile.jobs or 'auto (half the CPUs)'}")
            typer.echo(f"  uid/gid:    {profile.uid}/{profile.gid}")
            typer.echo(f"  data dir:   {profile.data_dir}")
            typer.echo(f"  ports:      {', '.join(str(p) for p in profile.ports) or '(none)'}")
            typer.echo(f"  extensions: {', '.join(e.name for e in profile.extensions) or '(none)'}")

    _run(action)
