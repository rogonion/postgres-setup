"""Domain model and config loader tests."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from core.adapters.config.toml import TomlConfigLoader
from core.domain.errors import ConfigError
from core.domain.models import (
    ExtensionSpec,
    Profile,
    Profiles,
    cache_prefix,
    core_image_tag,
    extension_image_tag,
    profile_image_tags,
    runtime_image_tag,
)


def test_profile_defaults_derive_from_name_and_prefix(profile):
    assert profile.output_dir == "/usr/local/pgsql"
    assert profile.cache_prefix == "localhost/postgres-setup/cache/suse"


def test_image_tags(profile):
    assert core_image_tag(profile) == "localhost/postgres-setup/postgres:suse-0.1.0"
    assert extension_image_tag(profile, "pgvector") == (
        "localhost/postgres-setup/extension/pgvector:suse-0.1.0"
    )
    assert runtime_image_tag(profile) == "localhost/postgres-setup/runtime:suse-0.1.0"
    assert profile_image_tags(profile) == [
        "localhost/postgres-setup/postgres:suse-0.1.0",
        "localhost/postgres-setup/extension/pgvector:suse-0.1.0",
        "localhost/postgres-setup/runtime:suse-0.1.0",
    ]


def test_cache_prefix_per_scope(profile):
    assert cache_prefix(profile, "core") == "localhost/postgres-setup/cache/suse/core"
    assert cache_prefix(profile, "runtime") == "localhost/postgres-setup/cache/suse/runtime"


def test_extension_versions(pins, profile, bare_profile):
    assert pins.extension_versions(profile) == {"pgvector": "0.8.1"}
    assert pins.extension_versions(bare_profile) == {}


def test_unsupported_extension_rejected():
    with pytest.raises(ValidationError, match="unsupported extension"):
        ExtensionSpec(name="bogus")


def test_profiles_resolve_unknown_raises(profile):
    profiles = Profiles(default="suse", profiles={"suse": profile})
    with pytest.raises(KeyError):
        profiles.resolve("nope")


def test_profiles_default_must_be_defined(profile):
    with pytest.raises(ValidationError, match="default profile"):
        Profiles(default="nope", profiles={"suse": profile})


def test_profile_requires_version_and_base_image():
    with pytest.raises(ValidationError):
        Profile(
            name="suse",
            base_image="img",
            prefix="/usr/local/pgsql",
            build_packages=["gcc"],
            uid=26,
            gid=26,
            data_dir="/var/lib/pgsql/data",
            config_dir="/etc/pgsql",
        )


def _repo_root() -> Path:
    # apps/cli/setup/tests/test_models.py -> repo root
    return Path(__file__).resolve().parents[4]


def test_load_pins_and_profiles_from_repo_config():
    loader = TomlConfigLoader(_repo_root())
    pins = loader.load_pins()
    assert pins.postgres.version == "18.1"
    assert pins.extensions["postgis"].version == "3.6.1"
    assert pins.extensions["pgvector"].version == "0.8.1"
    assert pins.extensions["rum"].version == "1.3.15"
    assert pins.extensions["postgis"].control_file == "postgis.control"
    profiles = loader.load_profiles()
    assert profiles.default == "suse"
    suse = profiles.resolve(None)
    assert suse.version == "0.1.0"
    assert suse.uid == 26 and suse.gid == 26
    assert suse.ports == [5432]
    assert [e.name for e in suse.extensions] == ["postgis", "pgvector", "rum"]
    assert suse.extension("postgis").build_packages
    assert suse.runtime_packages


def test_load_root_config_from_repo_config():
    root_config = TomlConfigLoader(_repo_root()).load_root_config()
    assert root_config.cache_dir == ".cache"
    assert root_config.resources_dir == "resources"


def test_resolve_profile_by_name(tmp_path):
    (tmp_path / "pins.toml").write_text(
        '[postgres]\nversion = "18.0"\narchive = "postgresql-18.0.tar.bz2"\n'
        'url = "https://e/p.tar.bz2"\nsha256 = "%s"\n' % ("b" * 64)
    )
    (tmp_path / "profiles.toml").write_text(
        'default = "small"\n'
        '[profiles.small]\nversion = "0.2.0"\nbase_image = "img"\nprefix = "/opt/pg"\n'
        'build_packages = ["gcc"]\nuid = 26\ngid = 26\n'
        'data_dir = "/var/lib/pgsql/data"\nconfig_dir = "/etc/pgsql"\n'
    )
    loader = TomlConfigLoader(root=tmp_path, config_dir=tmp_path)
    assert loader.load_pins().postgres.version == "18.0"
    profile = loader.load_profiles().resolve("small")
    assert profile.prefix == "/opt/pg"
    assert profile.version == "0.2.0"
    assert profile.output_dir == "/opt/pg"  # derived default
    assert profile.cache_prefix == "localhost/postgres-setup/cache/small"


def test_load_pins_invalid_raises(tmp_path):
    (tmp_path / "pins.toml").write_text("[postgres]\nversion = '1'")
    loader = TomlConfigLoader(root=tmp_path, config_dir=tmp_path)
    with pytest.raises(ConfigError):
        loader.load_pins()


def test_load_profiles_missing_table_raises(tmp_path):
    (tmp_path / "profiles.toml").write_text('default = "x"\n')
    loader = TomlConfigLoader(root=tmp_path, config_dir=tmp_path)
    with pytest.raises(ConfigError):
        loader.load_profiles()


def test_load_registry_absent_returns_none(tmp_path):
    loader = TomlConfigLoader(root=tmp_path, config_dir=tmp_path)
    assert loader.load_registry() is None


def test_load_registry_from_file(tmp_path):
    (tmp_path / "registry.toml").write_text(
        '[registry]\nnamespace = "reg.example.org"\ntls_verify = false\n'
    )
    loader = TomlConfigLoader(root=tmp_path, config_dir=tmp_path)
    config = loader.load_registry()
    assert config is not None
    assert config.namespace == "reg.example.org"
    assert config.tls_verify is False
