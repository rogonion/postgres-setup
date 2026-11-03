"""Composition root for the setup CLI: flags -> config -> adapters -> use cases.

All wiring lives here; the use cases receive only domain models and ports —
never argv, CLI paths, or raw toml.
"""

from pathlib import Path

from core.adapters.config.toml import TomlConfigLoader
from core.adapters.distro import distro_for
from core.adapters.image_registry.buildah import BuildahRegistry
from core.adapters.image_transport.buildah import BuildahTransport
from core.adapters.reporter.rich import RichReporter
from core.adapters.sandbox.buildah import BuildahSandbox
from core.adapters.source_fetcher.httpx import HttpxSourceFetcher
from core.application.build import BuildCoreImage
from core.application.extensions import BuildExtensionImage
from core.application.publish import PullImages, PushImages
from core.application.runtime import AssembleRuntimeImage
from core.domain.errors import ConfigError
from core.domain.models import Pins, Profile, Profiles, cache_prefix, runtime_image_tag


def _select_profile(loader: TomlConfigLoader, name: str | None) -> Profile:
    profiles = loader.load_profiles()
    try:
        return profiles.resolve(name)
    except KeyError:
        raise ConfigError(
            f"unknown profile {name or profiles.default!r}; "
            f"available: {', '.join(profiles.names())}"
        ) from None


class _Wiring:
    """One profile's adapters, built once per command invocation."""

    def __init__(self, config_dir: Path | None, profile_name: str | None) -> None:
        self.loader = TomlConfigLoader(config_dir=config_dir)
        self.reporter = RichReporter()
        self.pins: Pins = self.loader.load_pins()
        self.profile: Profile = _select_profile(self.loader, profile_name)
        self.registry = BuildahRegistry()
        self.sandbox = BuildahSandbox()
        self.distro = distro_for(self.profile, sandbox=self.sandbox)
        root_config = self.loader.load_root_config()
        self.fetcher = HttpxSourceFetcher(cache_dir=self.loader.root / root_config.cache_dir)
        self.resources_dir = self.loader.root / root_config.resources_dir

    def core_builder(self) -> BuildCoreImage:
        return BuildCoreImage(
            pins=self.pins,
            profile=self.profile,
            fetcher=self.fetcher,
            sandbox=self.sandbox,
            registry=self.registry,
            reporter=self.reporter,
            distro=self.distro,
        )

    def extension_builder(self) -> BuildExtensionImage:
        return BuildExtensionImage(
            pins=self.pins,
            profile=self.profile,
            fetcher=self.fetcher,
            sandbox=self.sandbox,
            registry=self.registry,
            reporter=self.reporter,
            distro=self.distro,
        )

    def assembler(self) -> AssembleRuntimeImage:
        registry_config = self.loader.load_registry()
        return AssembleRuntimeImage(
            pins=self.pins,
            profile=self.profile,
            core_builder=self.core_builder(),
            extension_builder=self.extension_builder(),
            sandbox=self.sandbox,
            registry=self.registry,
            reporter=self.reporter,
            distro=self.distro,
            resources_dir=self.resources_dir,
            puller=PullImages(
                pins=self.pins,
                profile=self.profile,
                transport=BuildahTransport(),
                reporter=self.reporter,
            ),
            registry_config=registry_config,
        )


def run_build_core(
    *, profile: str | None, force: bool, jobs: int | None, config_dir: Path | None
) -> str:
    """Build only the core artifact image."""
    return _Wiring(config_dir, profile).core_builder().run(force=force, jobs=jobs)


def run_build_extension(
    name: str, *, profile: str | None, force: bool, jobs: int | None, config_dir: Path | None
) -> str:
    """Build one extension image FROM the core image."""
    return _Wiring(config_dir, profile).extension_builder().run(name, force=force, jobs=jobs)


def run_assemble(
    *,
    profile: str | None,
    force: bool,
    jobs: int | None,
    source: str,
    config_dir: Path | None,
) -> str:
    """Assemble the runtime image from core + enabled extension images."""
    return _Wiring(config_dir, profile).assembler().run(force=force, jobs=jobs, source=source)


def run_build(
    *, profile: str | None, force: bool, jobs: int | None, config_dir: Path | None
) -> str:
    """Build all of the profile's images: core, each extension, runtime."""
    wiring = _Wiring(config_dir, profile)
    wiring.core_builder().run(force=force, jobs=jobs)
    for spec in wiring.profile.extensions:
        wiring.extension_builder().run(spec.name, force=force, jobs=jobs)
    return wiring.assembler().run(force=force, jobs=jobs, source="build")


def run_push(*, profile: str | None, config_dir: Path | None) -> list[str]:
    """Push the profile's final images (runtime, core, extensions)."""
    wiring = _Wiring(config_dir, profile)
    return PushImages(
        pins=wiring.pins,
        profile=wiring.profile,
        transport=BuildahTransport(),
        reporter=wiring.reporter,
    ).run(wiring.loader.load_registry())


def run_pull(*, profile: str | None, config_dir: Path | None) -> list[str]:
    """Pull the profile's final images, retagged to their local names."""
    wiring = _Wiring(config_dir, profile)
    return PullImages(
        pins=wiring.pins,
        profile=wiring.profile,
        transport=BuildahTransport(),
        reporter=wiring.reporter,
    ).run(wiring.loader.load_registry())


def run_clean(*, profile: str | None, cache: bool, config_dir: Path | None) -> None:
    """With --cache, prune the profile's layer-cache images."""
    wiring = _Wiring(config_dir, profile)
    if cache:
        removed = wiring.registry.prune_cache(cache_prefix(wiring.profile))
        if removed:
            wiring.reporter.info(f"pruned {len(removed)} cache image(s)")
        else:
            wiring.reporter.info("no cache images to prune")


def run_tag(*, profile: str | None, config_dir: Path | None) -> str:
    """The runtime image tag for the profile (no build)."""
    wiring = _Wiring(config_dir, profile)
    return runtime_image_tag(wiring.profile)


def run_profiles(*, config_dir: Path | None) -> Profiles:
    """The loaded profile set (for the `profiles` listing command)."""
    return TomlConfigLoader(config_dir=config_dir).load_profiles()
