"""Ports: the interfaces use cases see.

Shared ports (Reporter, Distro, ConfigLoader) plus the build domain's ports
(SourceFetcher, Sandbox, ImageRegistry, ImageTransport). Ports are
`typing.Protocol` classes — structural typing, adapters never subclass
them; one adapter directory per port lives under ``core/adapters/``.
"""

from pathlib import Path
from typing import Mapping, Protocol, Sequence

from core.domain.models import Pins, Profiles, RegistryConfig, RootConfig, SourcePin

# -- shared -----------------------------------------------------------------


class Reporter(Protocol):
    """Progress and warning surface for build stages."""

    def info(self, message: str) -> None: ...
    def warn(self, message: str) -> None: ...


class Distro(Protocol):
    """Distro-specific package operations, executed inside the build sandbox.

    Selected per profile by name (``suse`` -> zypper, ``ubuntu`` -> apt, ...)
    via the adapter factory in ``core/adapters/distro/``.
    """

    def refresh_package_repository(self) -> None: ...

    def install_packages(
        self,
        packages: Sequence[str],
        extra_cache_keys: Mapping[str, str] | None = None,
        *,
        no_recommends: bool = False,
    ) -> None: ...


class ConfigLoader(Protocol):
    """Loads workspace configuration into domain models.

    Reading config files is an adapter concern; the application layer only
    ever receives the validated models.
    """

    @property
    def config_dir(self) -> Path: ...

    def load_root_config(self) -> RootConfig: ...
    def load_pins(self) -> Pins: ...
    def load_profiles(self) -> Profiles: ...
    def load_registry(self) -> RegistryConfig | None: ...


# -- build domain -----------------------------------------------------------


class SourceFetcher(Protocol):
    """Fetches a pinned source tarball into the local cache, verifying it
    against its pinned sha256. An already-cached tarball is re-verified,
    not re-downloaded. Returns the cached archive path.
    """

    def fetch(self, pin: SourcePin) -> Path: ...


class Sandbox(Protocol):
    """A container-based build sandbox (one image per session).

    The container is the unit of sandboxing and artifact capture (ADR
    0003): steps run inside a working container, cached steps commit
    intermediate images, and the final step commits an artifact or runtime
    image. The ``set_*`` methods shape the committed image — the runtime
    image additionally uses entrypoint/cmd/user/ports/volumes (ADR 0004).
    """

    def begin(self, base_image: str, cache_prefix: str) -> None:
        """Create the working container from a base image."""
        ...

    def run(self, command: Sequence[str], env: Mapping[str, str] | None = None) -> None:
        """Run a command in the working container (no caching)."""
        ...

    def capture(self, command: Sequence[str], env: Mapping[str, str] | None = None) -> str:
        """Run a command and return its stdout."""
        ...

    def run_cached(
        self,
        command: Sequence[str],
        env: Mapping[str, str] | None = None,
        cache_keys: Mapping[str, str] | None = None,
    ) -> None:
        """Run a command, committing the result as a cache layer.

        A cache hit resumes the sandbox from the cached intermediate image
        instead of re-running the command.
        """
        ...

    def copy_in(self, source: Path, dest: str) -> None:
        """Copy a host file or directory into the working container."""
        ...

    def copy_from_image(self, image: str, src: str, dest: str) -> None:
        """Copy ``src`` out of another local image into the working
        container at ``dest`` (``buildah copy --from`` — rootless-safe,
        unlike ``buildah mount``)."""
        ...

    def set_labels(self, labels: Mapping[str, str]) -> None:
        """Record image labels on the working container."""
        ...

    def set_env(self, env: Mapping[str, str]) -> None:
        """Record image environment variables on the working container."""
        ...

    def set_entrypoint(self, entrypoint: Sequence[str]) -> None:
        """Record the image entrypoint on the working container."""
        ...

    def set_cmd(self, cmd: Sequence[str]) -> None:
        """Record the image default cmd on the working container."""
        ...

    def set_user(self, user: str) -> None:
        """Record the image user on the working container."""
        ...

    def set_ports(self, ports: Sequence[int]) -> None:
        """Record exposed ports on the working container."""
        ...

    def set_volumes(self, volumes: Sequence[str]) -> None:
        """Record volume mount points on the working container."""
        ...

    def commit(self, tag: str) -> None:
        """Commit the working container as an image."""
        ...

    def finish(self) -> None:
        """Remove the working container (best effort, always safe to call)."""
        ...


class ImageRegistry(Protocol):
    """Queries and manages local container images."""

    def image_exists(self, tag: str) -> bool:
        """True when an image with this exact tag exists locally."""
        ...

    def prune_cache(self, cache_prefix: str) -> list[str]:
        """Remove layer-cache images under a prefix; return removed tags."""
        ...


class ImageTransport(Protocol):
    """Pushes and pulls images between the local store and a registry."""

    def push(self, local_tag: str, remote_tag: str, *, tls_verify: bool = True) -> None: ...

    def pull(self, remote_tag: str, local_tag: str, *, tls_verify: bool = True) -> None:
        """Pull an image and retag it to its local name."""
        ...
