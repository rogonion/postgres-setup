"""Pydantic models for pinned upstream sources, distro build profiles, the
runtime image shape, registry config, and image naming.

Pins, profiles and registry config are loaded and validated at the CLI
boundary from ``config/*.toml`` (ADR 0005/0007); valid state is trusted
inside the use cases — one versions file, checksums pinned, no floating
versions.

Image topology (ADR 0003/0004): a profile builds a **core** artifact image
(``postgres:<profile>-<version>``), one image per enabled extension
(``extension/<name>:<profile>-<version>``, built FROM the core image), and
the **runtime** image (``runtime:<profile>-<version>``) — the product for a
daemon: the core prefix plus each extension's artifacts merged in, only the
runtime packages, and the daemon shape (user, data dir, config, entrypoint,
ports). Tags carry profile name + profile version; pin versions live in image
labels and layer-cache keys — bump ``Profile.version`` when pins change (or
pass --force).
"""

import os

from pydantic import BaseModel, Field, field_validator, model_validator

ARTIFACT_REPOSITORY = "localhost/postgres-setup"
CACHE_PREFIX_TEMPLATE = "localhost/postgres-setup/cache/{profile}"

SUPPORTED_EXTENSIONS = ("postgis", "pgvector", "rum")


class SourcePin(BaseModel):
    """One pinned upstream source tarball."""

    version: str
    archive: str = Field(pattern=r"\.tar\.(gz|bz2|xz)$")
    url: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @property
    def source_dir(self) -> str:
        """Directory name the tarball extracts to."""
        return self.archive.removesuffix(".tar.gz").removesuffix(".tar.bz2").removesuffix(".tar.xz")


class ExtensionPin(SourcePin):
    """A pinned postgres extension: its control file (the verification
    marker) plus the recipe-specific configure/make flags. Per-distro
    build/runtime packages live in the profile's ExtensionSpec."""

    control_file: str = Field(pattern=r"\.control$")
    configure_flags: list[str] = Field(default_factory=list)
    make_flags: list[str] = Field(default_factory=list)


class Pins(BaseModel):
    """The complete pinned version set: postgres core plus extensions."""

    postgres: SourcePin
    extensions: dict[str, ExtensionPin] = Field(default_factory=dict)

    def labels(self) -> dict[str, str]:
        labels = {
            "org.postgres-setup.postgres.version": self.postgres.version,
            "org.postgres-setup.postgres.sha256": self.postgres.sha256,
        }
        for name, pin in self.extensions.items():
            labels[f"org.postgres-setup.extension.{name}.version"] = pin.version
            labels[f"org.postgres-setup.extension.{name}.sha256"] = pin.sha256
        return labels

    def extension_versions(self, profile: "Profile") -> dict[str, str]:
        """Version of each extension a profile enables, by name."""
        return {
            spec.name: self.extensions[spec.name].version
            for spec in profile.extensions
            if spec.name in self.extensions
        }


class ExtensionSpec(BaseModel):
    """One extension enabled by a profile.

    The extension is compiled FROM the core artifact image into its own
    image (its own ``build_packages``), then merged into the runtime image
    together with its ``runtime_packages``. The pin (version/url/sha256,
    control file, recipe flags) lives in ``config/pins.toml``.
    """

    name: str
    build_packages: list[str] = Field(default_factory=list)
    runtime_packages: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _supported(cls, value: str) -> str:
        if value not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"unsupported extension {value!r}; supported: {', '.join(SUPPORTED_EXTENSIONS)}"
            )
        return value


class Profile(BaseModel):
    """One named build configuration of the pinned postgres source.

    Profile names are distro names (``suse``, ``ubuntu``, ...) and select
    the `Distro` adapter. A profile selects the build sandbox (base image),
    the core build packages, the configure flags, the runtime packages and
    the runtime image shape (user, data/config dirs, ports), and the
    extensions built against the core.
    """

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    version: str = Field(min_length=1)
    base_image: str
    prefix: str = Field(pattern=r"^/[A-Za-z0-9_./-]+$")
    output_dir: str = Field(pattern=r"^/")
    build_packages: list[str]
    configure_flags: list[str] = Field(default_factory=list)
    runtime_packages: list[str] = Field(default_factory=list)
    uid: int = Field(ge=1, le=65535)
    gid: int = Field(ge=1, le=65535)
    data_dir: str = Field(pattern=r"^/")
    config_dir: str = Field(pattern=r"^/")
    ports: list[int] = Field(default_factory=list)
    jobs: int | None = Field(default=None, ge=1)
    cache_prefix: str = Field(min_length=1)
    extensions: list[ExtensionSpec] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _fill_defaults(cls, data: object) -> object:
        if isinstance(data, dict):
            if not data.get("output_dir"):
                data["output_dir"] = data.get("prefix", "/")
            if not data.get("cache_prefix"):
                data["cache_prefix"] = CACHE_PREFIX_TEMPLATE.format(profile=data.get("name", ""))
        return data

    def extension(self, name: str) -> ExtensionSpec | None:
        for spec in self.extensions:
            if spec.name == name:
                return spec
        return None

    def labels(self) -> dict[str, str]:
        return {
            "org.postgres-setup.profile": self.name,
            "org.postgres-setup.profile.version": self.version,
            "org.postgres-setup.prefix": self.prefix,
            "org.postgres-setup.uid": str(self.uid),
            "org.postgres-setup.gid": str(self.gid),
            "org.postgres-setup.extensions": ",".join(e.name for e in self.extensions),
        }


class Profiles(BaseModel):
    """The complete profile set, plus the profile used when none is named."""

    default: str = "default"
    profiles: dict[str, Profile]

    @model_validator(mode="after")
    def _default_defined(self) -> "Profiles":
        if self.default not in self.profiles:
            raise ValueError(f"default profile {self.default!r} is not defined")
        return self

    def resolve(self, name: str | None) -> Profile:
        key = name or self.default
        if key not in self.profiles:
            raise KeyError(key)
        return self.profiles[key]

    def names(self) -> list[str]:
        return list(self.profiles)


def core_image_tag(profile: Profile) -> str:
    """Tag of the core artifact image (compiled postgres + contrib, no extensions)."""
    return f"{ARTIFACT_REPOSITORY}/postgres:{profile.name}-{profile.version}"


def extension_image_tag(profile: Profile, extension: str) -> str:
    """Tag of an extension artifact image (built FROM the core image)."""
    return f"{ARTIFACT_REPOSITORY}/extension/{extension}:{profile.name}-{profile.version}"


def runtime_image_tag(profile: Profile) -> str:
    """Tag of the assembled runtime image — the product."""
    return f"{ARTIFACT_REPOSITORY}/runtime:{profile.name}-{profile.version}"


def profile_image_tags(profile: Profile) -> list[str]:
    """All final images of a profile: core, one per enabled extension, runtime."""
    return [
        core_image_tag(profile),
        *(extension_image_tag(profile, spec.name) for spec in profile.extensions),
        runtime_image_tag(profile),
    ]


def cache_prefix(profile: Profile, scope: str = "core") -> str:
    """Layer-cache image prefix for a profile's intermediate steps, per scope."""
    return f"{profile.cache_prefix}/{scope}"


def effective_jobs(profile: Profile, override: int | None = None) -> int:
    """Parallel compile jobs: CLI override > profile.jobs > half the CPUs.

    Compile parallelism is bounded deliberately: unbounded make -j on a
    memory-constrained host starves during large C++ builds.
    """
    if override is not None and override >= 1:
        return override
    if profile.jobs is not None:
        return profile.jobs
    return max(1, (os.cpu_count() or 1) // 2)


class RegistryConfig(BaseModel):
    """User-local registry configuration (config/registry.toml, git-ignored).

    The namespace replaces the ``localhost/`` prefix of image names, so a
    pushed image keeps its project-relative name:
    localhost/postgres-setup/runtime:suse-0.1.0 ->
    <namespace>/postgres-setup/runtime:suse-0.1.0.
    """

    namespace: str = Field(min_length=1)
    tls_verify: bool = True


def remote_image_tag(local_tag: str, config: RegistryConfig) -> str:
    """Remote name of a locally-tagged image under the configured registry."""
    return local_tag.replace("localhost/", f"{config.namespace}/", 1)


class RootConfig(BaseModel):
    """Global repository config (``config/default.toml``).

    Relative paths resolve against the repository root.
    """

    cache_dir: str = ".cache"
    resources_dir: str = "resources"
