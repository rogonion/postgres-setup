"""Distro adapters: map a profile name (the distro) to its `Distro` implementation."""

from typing import Type

from core.adapters.distro.suse import SuseDistro
from core.domain.errors import ConfigError
from core.domain.models import Profile
from core.domain.ports import Distro, Sandbox

_DISTROS: dict[str, Type[Distro]] = {
    "suse": SuseDistro,
}


def available_distros() -> list[str]:
    return sorted(_DISTROS)


def distro_for(profile: Profile, *, sandbox: Sandbox) -> Distro:
    """The distro adapter for a profile, keyed by the profile name.

    Adding a distro = one adapter module + one entry here + one profile
    table in config/profiles.toml.
    """
    cls = _DISTROS.get(profile.name)
    if cls is None:
        raise ConfigError(
            f"no distro adapter for profile {profile.name!r}; "
            f"available: {', '.join(available_distros())}"
        )
    return cls(sandbox=sandbox)
