"""BuildCoreImage use case tests over fakes."""

from pathlib import Path

import pytest
from fakes import FakeDistro, FakeFetcher, FakeRegistry, FakeReporter, FakeSandbox

from core.application.build import BuildCoreImage
from core.domain.errors import VerificationError
from core.domain.models import core_image_tag

CORE_TAG = "localhost/postgres-setup/postgres:suse-0.1.0"


def _use_case(pins, profile, *, tags=None, sandbox=None):
    sandbox = sandbox or FakeSandbox(version_output="postgres (PostgreSQL) 18.1")
    registry = FakeRegistry(set(tags or []))
    distro = FakeDistro(sandbox)
    reporter = FakeReporter()
    build = BuildCoreImage(
        pins=pins,
        profile=profile,
        fetcher=FakeFetcher(Path("/cache/postgresql-18.1.tar.bz2")),
        sandbox=sandbox,
        registry=registry,
        reporter=reporter,
        distro=distro,
    )
    return build, sandbox, registry, distro, reporter


def test_build_core_commits_expected_tag_and_steps(pins, profile):
    build, sandbox, registry, distro, _ = _use_case(pins, profile)
    tag = build.run()

    assert tag == CORE_TAG
    assert tag == core_image_tag(profile)
    kinds = [call[0] for call in sandbox.calls]
    assert kinds == [
        "begin",
        "run_cached",  # distro refresh
        "run_cached",  # distro install build_packages
        "copy_in",
        "run_cached",  # configure
        "run_cached",  # compile + install-world-bin
        "capture",  # postgres --version
        "set_labels",
        "set_env",
        "commit",
        "finish",
    ]
    assert sandbox.calls[0][1] == profile.base_image
    assert sandbox.calls[0][2] == "localhost/postgres-setup/cache/suse/core"
    assert sandbox.calls[-2][1] == tag
    assert distro.calls[0] == ("refresh",)
    assert distro.calls[1][0] == "install"
    assert distro.calls[1][1] == ("gcc", "make", "bison", "flex")


def test_build_core_configure_carries_flags_and_cache_keys(pins, profile):
    build, sandbox, _, _, _ = _use_case(pins, profile)
    build.run()
    configure = [c for c in sandbox.calls if c[0] == "run_cached"][2]
    command = " ".join(configure[1])
    assert "./configure --prefix=/usr/local/pgsql --with-openssl --with-icu" in command
    assert configure[3]["sha256"] == pins.postgres.sha256
    assert configure[3]["version"] == "18.1"


def test_build_core_compile_uses_profile_jobs(pins, profile):
    build, sandbox, _, _, _ = _use_case(pins, profile)
    build.run()
    compile_step = [c for c in sandbox.calls if c[0] == "run_cached"][3]
    command = " ".join(compile_step[1])
    assert "make -j6" in command
    assert "make install-world-bin" in command


def test_build_core_skips_when_image_exists(pins, profile):
    build, sandbox, _, _, _ = _use_case(pins, profile, tags={CORE_TAG})
    build.run()
    assert sandbox.calls == []


def test_build_core_force_rebuilds_when_image_exists(pins, profile):
    build, sandbox, _, _, _ = _use_case(pins, profile, tags={CORE_TAG})
    build.run(force=True)
    assert sandbox.calls != []


def test_build_core_verifies_version(pins, profile):
    sandbox = FakeSandbox(version_output="postgres (PostgreSQL) 17.4 wrong")
    build, _, _, _, _ = _use_case(pins, profile, sandbox=sandbox)
    with pytest.raises(VerificationError, match="17.4"):
        build.run()


def test_build_core_finishes_sandbox_on_failure(pins, profile):
    class ExplodingSandbox(FakeSandbox):
        def run_cached(self, command, env=None, cache_keys=None):
            self.calls.append(("run_cached", tuple(command), env, dict(cache_keys or {})))
            raise RuntimeError("boom")

    sandbox = ExplodingSandbox(version_output="")
    build = BuildCoreImage(
        pins=pins,
        profile=profile,
        fetcher=FakeFetcher(Path("/cache/x.tar.bz2")),
        sandbox=sandbox,
        registry=FakeRegistry(),
        reporter=FakeReporter(),
        distro=FakeDistro(sandbox),
    )
    with pytest.raises(RuntimeError):
        build.run()
    assert sandbox.calls[-1][0] == "finish"
