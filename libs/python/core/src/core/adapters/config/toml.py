"""Toml config loader: the shared ConfigLoader port over config/*.toml.

All user-editable configuration lives under ``<workspace root>/config/``
(ADR 0007), overridable via ``config_dir``. Missing files fall back to
model defaults (registry.toml is optional); invalid values raise
ConfigError.
"""

import tomllib
from pathlib import Path
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError

from core.domain.errors import ConfigError
from core.domain.models import Pins, Profiles, RegistryConfig, RootConfig

PROJECT_NAME = "postgres-setup"
CONFIG_DIR = "config"
ROOT_CONFIG_FILE = "default.toml"
PINS_FILE = "pins.toml"
PROFILES_FILE = "profiles.toml"
REGISTRY_FILE = "registry.toml"

ModelT = TypeVar("ModelT", bound=BaseModel)


def find_project_root(start: Path | None = None) -> Path:
    """Locate the workspace root: the nearest directory (starting at ``start``,
    default cwd, walking upward) marked as this project — a pyproject.toml
    naming postgres-setup or declaring a uv workspace, or a config/default.toml."""
    candidate = (start or Path.cwd()).resolve()
    for directory in [candidate, *candidate.parents]:
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            data = _read(pyproject)
            project = data.get("project", {})
            uv = data.get("tool", {}).get("uv", {})
            if project.get("name") == PROJECT_NAME or "workspace" in uv:
                return directory
        if (directory / CONFIG_DIR / ROOT_CONFIG_FILE).is_file():
            return directory
    raise ConfigError(f"could not locate the workspace root from {candidate}")


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc


def _validate(path: Path, data: dict[str, Any], model: Type[ModelT]) -> ModelT:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"invalid {path}: {exc}") from exc


class TomlConfigLoader:
    """ConfigLoader over the workspace's config/*.toml files."""

    def __init__(self, root: Path | None = None, *, config_dir: Path | None = None) -> None:
        self._root = root or find_project_root()
        if config_dir is not None and not config_dir.is_dir():
            raise ConfigError(f"config directory {config_dir} does not exist")
        self._config_dir = config_dir or self._root / CONFIG_DIR

    @property
    def root(self) -> Path:
        return self._root

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    def load_root_config(self) -> RootConfig:
        path = self._config_dir / ROOT_CONFIG_FILE
        return _validate(path, _read(path), RootConfig)

    def load_pins(self) -> Pins:
        path = self._config_dir / PINS_FILE
        return _validate(path, _read(path), Pins)

    def load_profiles(self) -> Profiles:
        path = self._config_dir / PROFILES_FILE
        data = _read(path)
        # the table key is the profile name; Profile.name is required
        profiles_raw = data.get("profiles", {})
        for name, table in profiles_raw.items():
            if isinstance(table, dict):
                table.setdefault("name", name)
        return _validate(
            path,
            {"default": data.get("default", "default"), "profiles": profiles_raw},
            Profiles,
        )

    def load_registry(self) -> RegistryConfig | None:
        path = self._config_dir / REGISTRY_FILE
        if not path.exists():
            return None
        return _validate(path, _read(path).get("registry", {}), RegistryConfig)
