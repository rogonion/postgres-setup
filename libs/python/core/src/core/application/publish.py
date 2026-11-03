"""Use cases: publish and fetch a profile's final images.

Registry distribution (ADR 0006): the final images are the distribution
unit — the runtime image plus the core and per-extension images, so a
consumer can pull exactly what it needs. Never the hash-keyed cache layers.
The from-source build remains the audit path; the registry is the accelerator.
"""

from core.domain import ports as domain_ports
from core.domain.errors import ConfigError
from core.domain.models import (
    Pins,
    Profile,
    RegistryConfig,
    profile_image_tags,
    remote_image_tag,
)


class PushImages:
    """Push all of a profile's final images to the configured registry."""

    def __init__(
        self,
        *,
        pins: Pins,
        profile: Profile,
        transport: domain_ports.ImageTransport,
        reporter: domain_ports.Reporter,
    ) -> None:
        self._pins = pins
        self._profile = profile
        self._transport = transport
        self._reporter = reporter

    def run(self, config: RegistryConfig | None) -> list[str]:
        if config is None:
            raise ConfigError(
                "config/registry.toml is not configured; copy "
                "config/registry.toml.example to config/registry.toml and set "
                "the namespace"
            )
        remotes: list[str] = []
        for tag in profile_image_tags(self._profile):
            remote = remote_image_tag(tag, config)
            self._reporter.info(f"pushing {tag} -> {remote}")
            self._transport.push(tag, remote, tls_verify=config.tls_verify)
            remotes.append(remote)
        self._reporter.info(f"pushed {len(remotes)} image(s)")
        return remotes


class PullImages:
    """Pull all of a profile's final images, retagged to their local names."""

    def __init__(
        self,
        *,
        pins: Pins,
        profile: Profile,
        transport: domain_ports.ImageTransport,
        reporter: domain_ports.Reporter,
    ) -> None:
        self._pins = pins
        self._profile = profile
        self._transport = transport
        self._reporter = reporter

    def run(self, config: RegistryConfig | None) -> list[str]:
        if config is None:
            raise ConfigError(
                "config/registry.toml is not configured; copy "
                "config/registry.toml.example to config/registry.toml and set "
                "the namespace"
            )
        tags: list[str] = []
        for tag in profile_image_tags(self._profile):
            remote = remote_image_tag(tag, config)
            self._reporter.info(f"pulling {remote} -> {tag}")
            self._transport.pull(remote, tag, tls_verify=config.tls_verify)
            tags.append(tag)
        self._reporter.info(f"pulled {len(tags)} image(s)")
        return tags
