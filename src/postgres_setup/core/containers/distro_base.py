from abc import ABC, abstractmethod
from typing import List, Dict

from .buildah import BuildahContainer


class BaseDistro(ABC):
    def __init__(self, container: BuildahContainer):
        self.container = container

    @abstractmethod
    def refresh_package_repository(self, args: Dict[str, any] = None):
        """
        Refresh package repository.
        Usually after adding a new repository.
        :return:
        """
        pass

    @abstractmethod
    def install_packages(self, packages: List[str], extra_cache_keys: Dict[str, str] = None,
                         args: Dict[str, any] = None):
        """
        Install packages into the system
        :param extra_cache_keys: cache layer.
        :param packages:
        :param args:
        :return:
        """
        pass

    @abstractmethod
    def remove_packages(self, packages: List[str], args: Dict[str, any] = None):
        pass

    @abstractmethod
    def clean_package_repository_cache(self, args: Dict[str, any] = None):
        pass

    @abstractmethod
    def remove_package_manager(self):
        pass
