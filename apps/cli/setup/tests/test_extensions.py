"""BuildExtensionImage use case tests over fakes."""

from pathlib import Path

import pytest
from fakes import FakeDistro, FakeFetcher, FakeRegistry, FakeReporter, FakeSandbox

from core.application.extensions import BuildExtensionImage, extension_recipe
from core.domain.errors import ConfigError, ImageNotFoundError, VerificationError
from core.domain.models import extension_image_tag

CORE_TAG = "localhost/postgres-setup/postgres:suse-0.1.0"
EXT_TAG = "localhost/postgres-setup/extension/pgvector:suse-0.1.0"
POSTGIS_TAG = "localhost/postgres-setup/extension/postgis:suse-0.1.0"


def _use_case(pins, profile, *, tags=None, sandbox=None):
    sandbox = sandbox or FakeSandbox(version_output="postgres (PostgreSQL) 18.1")
    registry = FakeRegistry(set(tags or []))
    distro = FakeDistro(sandbox)
    reporter = FakeReporter()
    build = BuildExtensionImage(
        pins=pins,
        profile=profile,
        fetcher=FakeFetcher(Path("/cache/pgvector-0.8.1.tar.gz")),
        sandbox=sandbox,
        registry=registry,
        reporter=reporter,
        distro=distro,
    )
    return build, sandbox, registry, distro, reporter


def test_extension_requires_core_image(pins, profile):
    build, _, _, _, _ = _use_case(pins, profile, tags=set())
    with pytest.raises(ImageNotFoundError, match="build-core"):
        build.run("pgvector")


def test_extension_requires_pin(pins, profile):
    build, _, _, _, _ = _use_case(pins, profile, tags={CORE_TAG})
    with pytest.raises(ConfigError, match="not pinned"):
        build.run("rum")


def test_extension_requires_profile_enablement(pins, bare_profile):
    build, _, _, _, _ = _use_case(pins, bare_profile, tags={CORE_TAG})
    with pytest.raises(ConfigError, match="does not enable"):
        build.run("pgvector")


def test_extension_builds_from_core_image(pins, profile):
    build, sandbox, registry, distro, _ = _use_case(pins, profile, tags={CORE_TAG})
    tag = build.run("pgvector")

    assert tag == EXT_TAG
    assert tag == extension_image_tag(profile, "pgvector")
    kinds = [call[0] for call in sandbox.calls]
    assert kinds == [
        "begin",
        "run_cached",  # distro refresh
        "run_cached",  # distro install extension build_packages
        "copy_in",
        "run_cached",  # extract + recipe compile + install
        "capture",  # ls control file
        "set_labels",
        "commit",
        "finish",
    ]
    # the sandbox begins FROM the core artifact image
    assert sandbox.calls[0][1] == CORE_TAG
    assert sandbox.calls[0][2] == "localhost/postgres-setup/cache/suse/extension-pgvector"
    assert sandbox.calls[-2][1] == tag
    # extension build packages went to the distro, not the core profile's
    assert distro.calls[1][1] == ("make", "gcc")
    assert distro.calls[1][2]["extension"] == "pgvector"
    compile_step = [c for c in sandbox.calls if c[0] == "run_cached"][2]
    command = " ".join(compile_step[1])
    assert "PG_CONFIG=/usr/local/pgsql/bin/pg_config" in command
    assert "make OPTFLAGS='-O3'" in command
    assert compile_step[3]["sha256"] == pins.extensions["pgvector"].sha256
    verify = [c for c in sandbox.calls if c[0] == "capture"][0]
    assert "vector.control" in " ".join(verify[1])
    labels = [c for c in sandbox.calls if c[0] == "set_labels"][0][1]
    assert labels["org.postgres-setup.extension"] == "pgvector"
    assert labels["org.postgres-setup.extension.pgvector.version"] == "0.8.1"


def test_extension_skips_when_image_exists(pins, profile):
    build, sandbox, _, _, _ = _use_case(pins, profile, tags={CORE_TAG, EXT_TAG})
    build.run("pgvector")
    assert sandbox.calls == []


def test_extension_missing_control_file_fails(pins, profile):
    sandbox = FakeSandbox(ls_output="")
    build, _, _, _, _ = _use_case(pins, profile, tags={CORE_TAG}, sandbox=sandbox)
    with pytest.raises(VerificationError, match="vector.control"):
        build.run("pgvector")


def test_postgis_recipe_carries_ldflags_workaround(pins, profile):
    spec = next(e for e in profile.extensions if e.name == "pgvector")
    command, env = extension_recipe("postgis", pins.extensions["postgis"], spec, profile.prefix, 6)
    assert "--with-pgconfig=/usr/local/pgsql/bin/pg_config --with-protobuf" in command
    assert env["LDFLAGS"] == "-Wl,--allow-shlib-undefined"


def test_rum_recipe_uses_pgxs(profile):
    from core.domain.models import ExtensionPin

    rum_pin = ExtensionPin(
        version="1.3.15",
        archive="rum-1.3.15.tar.gz",
        url="https://example.org/rum.tar.gz",
        sha256="d" * 64,
        control_file="rum.control",
    )
    command, env = extension_recipe("rum", rum_pin, profile.extensions[0], profile.prefix, 6)
    assert "USE_PGXS=1" in command
    assert "PG_CONFIG=/usr/local/pgsql/bin/pg_config" in command
    assert env == {}


def test_unknown_recipe_fails(pins, profile):
    spec = profile.extensions[0]
    with pytest.raises(VerificationError, match="no recipe"):
        extension_recipe("bogus", pins.extensions["pgvector"], spec, profile.prefix, 6)


def test_postgis_build_tag(pins, profile):
    # postgis is pinned but not enabled by the fixture profile; enable it ad hoc
    profile = profile.model_copy(
        update={
            "extensions": [
                *profile.extensions,
                type(profile.extensions[0])(
                    name="postgis", build_packages=["gcc"], runtime_packages=["libgeos3_12_2"]
                ),
            ]
        }
    )
    build, sandbox, _, _, _ = _use_case(pins, profile, tags={CORE_TAG})
    assert build.run("postgis") == POSTGIS_TAG
    assert sandbox.calls[0][1] == CORE_TAG
