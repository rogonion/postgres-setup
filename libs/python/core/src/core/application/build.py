"""Use case: build the pinned postgres core artifact image for a profile.

Compiles postgres (core + contrib via ``make install-world-bin``) into
``localhost/postgres-setup/postgres:<profile>-<version>``. Orchestrates
ports only (hexagonal dependency rule): the source fetcher, the distro
package operations, the container sandbox, the image registry, and the
reporter. Step order, cache keys, and the verification contract live here.
"""

from core.domain import ports as domain_ports
from core.domain.errors import VerificationError
from core.domain.models import (
    Pins,
    Profile,
    SourcePin,
    cache_prefix,
    core_image_tag,
    effective_jobs,
)


class BuildCoreImage:
    """The pinned core build routine as one orchestrating use case."""

    def __init__(
        self,
        *,
        pins: Pins,
        profile: Profile,
        fetcher: domain_ports.SourceFetcher,
        sandbox: domain_ports.Sandbox,
        registry: domain_ports.ImageRegistry,
        reporter: domain_ports.Reporter,
        distro: domain_ports.Distro,
    ) -> None:
        self._pins = pins
        self._profile = profile
        self._fetcher = fetcher
        self._sandbox = sandbox
        self._registry = registry
        self._reporter = reporter
        self._distro = distro

    def run(self, *, force: bool = False, jobs: int | None = None) -> str:
        """Build the core artifact image; return its tag."""
        profile = self._profile
        tag = core_image_tag(profile)
        if not force and self._registry.image_exists(tag):
            self._reporter.info(f"image {tag} already exists (use --force to rebuild)")
            return tag

        pin = self._pins.postgres
        workers = effective_jobs(profile, jobs)
        self._reporter.info(
            f"building postgres {pin.version} ({profile.name} profile, -j{workers}) -> {tag}"
        )
        archive = self._fetcher.fetch(pin)
        flags = " ".join(profile.configure_flags)

        self._sandbox.begin(profile.base_image, cache_prefix(profile, "core"))
        try:
            self._distro.refresh_package_repository()
            self._distro.install_packages(profile.build_packages)
            self._sandbox.copy_in(archive, f"/tmp/{pin.archive}")
            self._sandbox.run_cached(
                [
                    "sh",
                    "-c",
                    f"cd /tmp && tar -xf {pin.archive} && "
                    f"cd {pin.source_dir} && "
                    f"./configure --prefix={profile.prefix} {flags}",
                ],
                cache_keys={
                    "step": "configure",
                    "version": pin.version,
                    "sha256": pin.sha256,
                    "flags": ",".join(sorted(profile.configure_flags)),
                },
            )
            self._sandbox.run_cached(
                [
                    "sh",
                    "-c",
                    f"cd /tmp/{pin.source_dir} && make -j{workers} && make install-world-bin",
                ],
                cache_keys={
                    "step": "compile",
                    "version": pin.version,
                    "sha256": pin.sha256,
                    "flags": ",".join(sorted(profile.configure_flags)),
                },
            )
            self._verify(pin)
            self._sandbox.set_labels({**self._pins.labels(), **profile.labels()})
            self._sandbox.set_env({"PATH": f"{profile.prefix}/bin:/usr/bin:/bin"})
            self._sandbox.commit(tag)
        finally:
            self._sandbox.finish()

        self._reporter.info(f"core artifact image ready: {tag}")
        return tag

    def _verify(self, pin: SourcePin) -> None:
        profile = self._profile
        self._reporter.info("verifying built postgres inside the image")
        version = self._sandbox.capture([f"{profile.prefix}/bin/postgres", "--version"]).strip()
        if pin.version not in version:
            raise VerificationError(f"built postgres reports {version!r}, expected {pin.version}")
