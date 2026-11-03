"""Domain error taxonomy: the single source of raised errors.

Adapters translate subprocess exit codes, missing binaries, buildah
failures, filesystem and HTTP failures into these errors at the boundary.
Raw exceptions, exit codes, and stderr never travel past the adapter that
produced them. CLIs catch `CoreError` at the edge.
"""


class CoreError(Exception):
    """Base for every error raised by core."""


# -- shared -----------------------------------------------------------------


class ConfigError(CoreError):
    """Configuration is missing, unreadable, or invalid."""


class FetchError(CoreError):
    """A source tarball download failed."""


# -- build ------------------------------------------------------------------


class SetupError(CoreError):
    """Base for postgres-setup build and distribution errors."""


class ChecksumError(SetupError):
    """A downloaded (or cached) tarball does not match its pinned sha256."""


class SandboxError(SetupError):
    """A buildah sandbox command failed or buildah is unavailable."""


class VerificationError(SetupError):
    """A built binary reports the wrong version or an extension artifact is missing."""


class ImageNotFoundError(SetupError):
    """A required artifact image is not present locally."""
