"""Use case: build one pinned extension into its own artifact image.

Extensions are the postgres analogue of valkey modules, with one structural
difference: they compile against the core build, so their sandbox begins
FROM the core artifact image, which provides pg_config and the headers. The
recipe per extension name lives in ``extension_recipe`` (code, not
configuration); verification is the extension's control file landing in
``<prefix>/share/extension``.
"""

from core.domain import ports as domain_ports
from core.domain.errors import ConfigError, ImageNotFoundError, VerificationError
from core.domain.models import (
    ExtensionPin,
    ExtensionSpec,
    Pins,
    Profile,
    cache_prefix,
    core_image_tag,
    effective_jobs,
    extension_image_tag,
)


def extension_recipe(
    name: str, pin: ExtensionPin, spec: ExtensionSpec, prefix: str, workers: int
) -> tuple[str, dict[str, str]]:
    """The pinned build recipe for an extension: (shell command, env)."""
    src = f"/tmp/{pin.source_dir}"
    pg_config = f"{prefix}/bin/pg_config"
    if name == "postgis":
        flags = f"--with-pgconfig={pg_config}"
        if pin.configure_flags:
            flags += " " + " ".join(pin.configure_flags)
        return (
            f"cd {src} && ./configure {flags} && make -j{workers} && make install",
            # Leap 16.0's GA libldap references EVP_md2@OPENSSL_3.0.0,
            # removed from the repo's OpenSSL 3.5: the linker's eager
            # full-dep-libs check (gdal-config --dep-libs) trips on it.
            # Runtime is unaffected (lazy binding; the md2 path is never
            # called), so the undefined cross-lib ref is allowed at link.
            {"LDFLAGS": "-Wl,--allow-shlib-undefined"},
        )
    if name == "pgvector":
        opt_flags = " ".join(pin.make_flags)
        return (
            f"cd {src} && make clean && "
            f"make OPTFLAGS='{opt_flags}' PG_CONFIG={pg_config} -j{workers} && "
            f"make PG_CONFIG={pg_config} install",
            {},
        )
    if name == "rum":
        return (
            f"cd {src} && make USE_PGXS=1 PG_CONFIG={pg_config} -j{workers} && "
            f"make USE_PGXS=1 PG_CONFIG={pg_config} install",
            {},
        )
    raise VerificationError(f"no recipe for extension {name!r}")


class BuildExtensionImage:
    """Compile one pinned extension into its own artifact image."""

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

    def run(self, extension: str, *, force: bool = False, jobs: int | None = None) -> str:
        """Build the extension image for ``extension``; return its tag."""
        profile = self._profile
        pin = self._pins.extensions.get(extension)
        if pin is None:
            pinned = ", ".join(self._pins.extensions) or "(none)"
            raise ConfigError(
                f"extension {extension!r} is not pinned in config/pins.toml "
                f"([extensions.{extension}]); pinned: {pinned}"
            )
        spec = profile.extension(extension)
        if spec is None:
            raise ConfigError(
                f"profile {profile.name!r} does not enable extension {extension!r}; "
                f"enabled: {', '.join(e.name for e in profile.extensions) or '(none)'}"
            )

        tag = extension_image_tag(profile, extension)
        if not force and self._registry.image_exists(tag):
            self._reporter.info(f"image {tag} already exists (use --force to rebuild)")
            return tag

        core_tag = core_image_tag(profile)
        if not self._registry.image_exists(core_tag):
            raise ImageNotFoundError(
                f"extension builds require the core image {core_tag}; run `setup build-core` first"
            )

        workers = effective_jobs(profile, jobs)
        command, env = extension_recipe(extension, pin, spec, profile.prefix, workers)
        self._reporter.info(
            f"building extension {extension} {pin.version} (FROM {core_tag}, -j{workers}) -> {tag}"
        )
        archive = self._fetcher.fetch(pin)

        # FROM the core artifact image: pg_config and headers come with it.
        self._sandbox.begin(core_tag, cache_prefix(profile, f"extension-{extension}"))
        try:
            self._distro.refresh_package_repository()
            self._distro.install_packages(
                spec.build_packages,
                extra_cache_keys={"extension": extension},
            )
            self._sandbox.copy_in(archive, f"/tmp/{pin.archive}")
            self._sandbox.run_cached(
                ["sh", "-c", f"cd /tmp && tar -xf {pin.archive} && {command}"],
                env=env,
                cache_keys={
                    "step": "compile",
                    "extension": extension,
                    "version": pin.version,
                    "sha256": pin.sha256,
                    "env": ",".join(f"{k}={v}" for k, v in sorted(env.items())),
                },
            )
            self._verify(extension, pin)
            self._sandbox.set_labels(
                {
                    **self._pins.labels(),
                    **profile.labels(),
                    "org.postgres-setup.extension": extension,
                }
            )
            self._sandbox.commit(tag)
        finally:
            self._sandbox.finish()

        self._reporter.info(f"extension artifact image ready: {tag}")
        return tag

    def _verify(self, extension: str, pin: ExtensionPin) -> None:
        profile = self._profile
        self._reporter.info(f"verifying {pin.control_file} present in the image")
        listing = self._sandbox.capture(
            ["ls", f"{profile.prefix}/share/extension/{pin.control_file}"]
        )
        if pin.control_file not in listing:
            raise VerificationError(f"extension {extension} did not install {pin.control_file}")
