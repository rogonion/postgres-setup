"""Use case: assemble the runtime image for a profile.

Postgres is a daemon: the runtime image is the product (ADR 0004). The
assembly composes the artifact images — the core prefix copied in, then each
enabled extension's installed artifacts merged over it — installs only the
runtime packages, and shapes the image (user, dirs, config, entrypoint,
ports, volumes). Missing core/extension images are pulled (auto/pull) or
built first.
"""

from pathlib import Path

from core.application.build import BuildCoreImage
from core.application.extensions import BuildExtensionImage
from core.application.publish import PullImages
from core.domain import ports as domain_ports
from core.domain.errors import ImageNotFoundError, VerificationError
from core.domain.models import (
    Pins,
    Profile,
    RegistryConfig,
    cache_prefix,
    core_image_tag,
    extension_image_tag,
    runtime_image_tag,
)

SOURCES = ("auto", "build", "pull")

RUNTIME_CONFIG_FILES = ("postgresql.conf", "pg_hba.conf")
ENTRYPOINT_DEST = "/usr/local/bin/entrypoint.sh"


class AssembleRuntimeImage:
    """Compose core + extension artifact images into the runtime image."""

    def __init__(
        self,
        *,
        pins: Pins,
        profile: Profile,
        core_builder: BuildCoreImage,
        extension_builder: BuildExtensionImage,
        sandbox: domain_ports.Sandbox,
        registry: domain_ports.ImageRegistry,
        reporter: domain_ports.Reporter,
        distro: domain_ports.Distro,
        resources_dir: Path,
        puller: PullImages | None = None,
        registry_config: RegistryConfig | None = None,
    ) -> None:
        self._pins = pins
        self._profile = profile
        self._core = core_builder
        self._extensions = extension_builder
        self._sandbox = sandbox
        self._registry = registry
        self._reporter = reporter
        self._distro = distro
        self._resources_dir = resources_dir
        self._puller = puller
        self._registry_config = registry_config

    def run(
        self,
        *,
        force: bool = False,
        jobs: int | None = None,
        source: str = "auto",
    ) -> str:
        """Assemble the runtime image for the profile; return its tag."""
        if source not in SOURCES:
            raise ValueError(f"unknown source {source!r}; expected one of {', '.join(SOURCES)}")
        profile = self._profile
        tag = runtime_image_tag(profile)
        if not force and self._registry.image_exists(tag):
            self._reporter.info(f"image {tag} already exists (use --force to rebuild)")
            return tag
        if self._resolve_pulled(tag, source):
            return tag

        core_tag = self._ensure_core(source, jobs)
        extension_tags = {
            spec.name: self._ensure_extension(spec.name, source, jobs)
            for spec in profile.extensions
        }
        return self._assemble(tag, core_tag, extension_tags)

    def _resolve_pulled(self, tag: str, source: str) -> bool:
        """Pull the runtime image when possible. Returns True when pulled.

        --from build keeps the from-source path explicit; --from pull
        refuses to build.
        """
        if self._registry.image_exists(tag) or source == "build":
            return False
        if self._puller is not None:
            self._puller.run(self._registry_config)
            if self._registry.image_exists(tag):
                return True
        if source == "pull":
            raise ImageNotFoundError(
                f"--from pull but image {tag} could not be pulled; "
                "configure config/registry.toml or use --from build"
            )
        return False

    def _ensure_core(self, source: str, jobs: int | None) -> str:
        tag = core_image_tag(self._profile)
        if self._registry.image_exists(tag):
            return tag
        if source in ("auto", "pull") and self._puller is not None:
            self._puller.run(self._registry_config)
            if self._registry.image_exists(tag):
                return tag
        if source == "pull":
            raise ImageNotFoundError(
                f"--from pull but core image {tag} could not be pulled; "
                "configure config/registry.toml or use --from build"
            )
        self._reporter.info(f"core image {tag} missing; building it")
        return self._core.run(jobs=jobs)

    def _ensure_extension(self, name: str, source: str, jobs: int | None) -> str:
        tag = extension_image_tag(self._profile, name)
        if self._registry.image_exists(tag):
            return tag
        if source in ("auto", "pull") and self._puller is not None:
            self._puller.run(self._registry_config)
            if self._registry.image_exists(tag):
                return tag
        if source == "pull":
            raise ImageNotFoundError(
                f"--from pull but extension image {tag} could not be pulled; "
                "configure config/registry.toml or use --from build"
            )
        self._reporter.info(f"extension image {tag} missing; building it")
        return self._extensions.run(name, jobs=jobs)

    def _assemble(self, tag: str, core_tag: str, extension_tags: dict[str, str]) -> str:
        profile = self._profile
        names = [spec.name for spec in profile.extensions]
        self._reporter.info(
            f"assembling runtime {profile.name}-{profile.version} "
            f"({', '.join(names) or 'no extensions'}) -> {tag}"
        )
        runtime_packages = sorted(
            set(profile.runtime_packages)
            | {pkg for spec in profile.extensions for pkg in spec.runtime_packages}
        )

        self._sandbox.begin(profile.base_image, cache_prefix(profile, "runtime"))
        try:
            self._sandbox.copy_from_image(core_tag, profile.prefix, profile.prefix)
            self._distro.refresh_package_repository()
            self._distro.install_packages(
                runtime_packages,
                extra_cache_keys={"scope": "runtime"},
                no_recommends=True,
            )
            for spec in profile.extensions:
                staging = f"/tmp/stage_{spec.name}"
                self._sandbox.copy_from_image(extension_tags[spec.name], profile.prefix, staging)
                self._sandbox.run(
                    ["sh", "-c", f"cp -a {staging}/. {profile.prefix}/ && rm -rf {staging}"]
                )

            self._setup_user(profile)
            self._setup_config(profile)
            self._verify(names)

            self._sandbox.set_env(
                {
                    "PATH": f"{profile.prefix}/bin:/usr/bin:/bin",
                    "PGDATA": profile.data_dir,
                    "POSTGRES_SETUP_OUTPUT_DIR": profile.output_dir,
                }
            )
            self._sandbox.set_volumes([profile.data_dir])
            self._sandbox.set_ports(profile.ports)
            self._sandbox.set_entrypoint([ENTRYPOINT_DEST])
            self._sandbox.set_cmd(["postgres"])
            self._sandbox.set_user(str(profile.uid))
            self._sandbox.set_labels(
                {
                    **self._pins.labels(),
                    **profile.labels(),
                    **{
                        f"org.postgres-setup.extension.{name}.version": version
                        for name, version in self._pins.extension_versions(profile).items()
                    },
                }
            )
            self._sandbox.commit(tag)
        finally:
            self._sandbox.finish()

        self._reporter.info(f"runtime image ready: {tag}")
        return tag

    def _setup_user(self, profile: Profile) -> None:
        self._sandbox.run(["groupadd", "-r", "-g", str(profile.gid), "postgres"])
        self._sandbox.run(
            [
                "useradd",
                "-r",
                "-u",
                str(profile.uid),
                "-g",
                str(profile.gid),
                "-d",
                str(Path(profile.data_dir).parent),
                "-s",
                "/bin/sh",
                "-c",
                "PostgreSQL Server",
                "postgres",
            ]
        )
        self._sandbox.run(["mkdir", "-p", profile.data_dir])
        self._sandbox.run(["chown", "-R", f"{profile.uid}:{profile.gid}", profile.data_dir])

    def _setup_config(self, profile: Profile) -> None:
        self._sandbox.run(["mkdir", "-p", profile.config_dir])
        for name in RUNTIME_CONFIG_FILES:
            self._sandbox.copy_in(self._resources_dir / name, f"{profile.config_dir}/{name}")
        self._sandbox.copy_in(self._resources_dir / "entrypoint.sh", ENTRYPOINT_DEST)
        self._sandbox.run(["chmod", "+x", ENTRYPOINT_DEST])
        self._sandbox.run(
            ["chown", "-R", f"{profile.uid}:{profile.gid}", profile.config_dir, ENTRYPOINT_DEST]
        )

    def _verify(self, extensions: list[str]) -> None:
        profile = self._profile
        self._reporter.info("verifying runtime inside the image")
        version = self._sandbox.capture([f"{profile.prefix}/bin/postgres", "--version"]).strip()
        if self._pins.postgres.version not in version:
            raise VerificationError(
                f"runtime postgres reports {version!r}, expected {self._pins.postgres.version}"
            )
        for name in extensions:
            control = self._pins.extensions[name].control_file
            listing = self._sandbox.capture(["ls", f"{profile.prefix}/share/extension/{control}"])
            if control not in listing:
                raise VerificationError(f"runtime image lacks {control} ({name})")
