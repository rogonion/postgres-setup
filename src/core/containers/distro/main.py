from ...spec import Distro
from ..buildah import BuildahContainer
from ..distro import Suse
from ..distro_base import BaseDistro


def init_base_distro(distro: Distro, container: BuildahContainer) -> BaseDistro:
    match distro:
        case Distro.SUSE:
            return Suse(container)