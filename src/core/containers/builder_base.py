from abc import ABC, abstractmethod

from rich.console import Console

from .buildah import BuildahContainer
from ..spec import BuildSpec

console = Console()


class BaseBuilder(ABC):
    def __init__(self, config: BuildSpec, cache_prefix: str = ""):
        self.config = config
        self._init_cache_prefix(cache_prefix)

    @abstractmethod
    def _init_cache_prefix(self, cache_prefix: str):
        pass

    @abstractmethod
    def build(self):
        pass

    def log(self, message: str, style: str = "white"):
        console.print(f"[{style}]{message}[/{style}]")


class BaseRuntime(ABC):
    def __init__(self, config: BuildSpec, src_container: BuildahContainer, ext_version: str = ''):
        self.config = config
        self.src_container = src_container
        self._init_ext_version(ext_version)

    @abstractmethod
    def _init_ext_version(self, ext_version: str):
        pass

    @abstractmethod
    def build(self):
        pass

    def log(self, message: str, style: str = "white"):
        console.print(f"[{style}]{message}[/{style}]")
