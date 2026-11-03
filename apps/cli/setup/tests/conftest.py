"""Shared fixtures: pin and profile models used across the suite."""

import pytest

from core.domain.models import ExtensionPin, ExtensionSpec, Pins, Profile, SourcePin


@pytest.fixture
def pins() -> Pins:
    return Pins(
        postgres=SourcePin(
            version="18.1",
            archive="postgresql-18.1.tar.bz2",
            url="https://example.org/postgresql-18.1.tar.bz2",
            sha256="a" * 64,
        ),
        extensions={
            "postgis": ExtensionPin(
                version="3.6.1",
                archive="postgis-3.6.1.tar.gz",
                url="https://example.org/postgis-3.6.1.tar.gz",
                sha256="b" * 64,
                control_file="postgis.control",
                configure_flags=["--with-protobuf"],
            ),
            "pgvector": ExtensionPin(
                version="0.8.1",
                archive="pgvector-0.8.1.tar.gz",
                url="https://example.org/pgvector-0.8.1.tar.gz",
                sha256="c" * 64,
                control_file="vector.control",
                make_flags=["-O3"],
            ),
        },
    )


@pytest.fixture
def profile() -> Profile:
    """The suse profile with the pgvector extension enabled."""
    return Profile(
        name="suse",
        version="0.1.0",
        base_image="registry.example.org/base:1.0",
        prefix="/usr/local/pgsql",
        build_packages=["gcc", "make", "bison", "flex"],
        configure_flags=["--with-openssl", "--with-icu"],
        runtime_packages=["shadow", "libicu77"],
        uid=26,
        gid=26,
        data_dir="/var/lib/pgsql/data/18",
        config_dir="/usr/share/postgresql/config",
        ports=[5432],
        jobs=6,
        extensions=[
            ExtensionSpec(
                name="pgvector",
                build_packages=["make", "gcc"],
                runtime_packages=[],
            )
        ],
    )


@pytest.fixture
def bare_profile() -> Profile:
    """The suse profile with no extensions enabled."""
    return Profile(
        name="suse",
        version="0.1.0",
        base_image="registry.example.org/base:1.0",
        prefix="/usr/local/pgsql",
        build_packages=["gcc", "make"],
        configure_flags=["--with-openssl"],
        runtime_packages=["shadow"],
        uid=26,
        gid=26,
        data_dir="/var/lib/pgsql/data/18",
        config_dir="/usr/share/postgresql/config",
        ports=[5432],
        jobs=6,
    )
