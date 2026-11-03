"""AssembleRuntimeImage + PushImages/PullImages use case tests over fakes."""

from pathlib import Path

import pytest
from fakes import FakeDistro, FakeRegistry, FakeReporter, FakeSandbox, FakeTransport

from core.application.publish import PullImages, PushImages
from core.application.runtime import AssembleRuntimeImage
from core.domain.errors import ConfigError, ImageNotFoundError, VerificationError
from core.domain.models import (
    Profile,
    RegistryConfig,
    core_image_tag,
    extension_image_tag,
    profile_image_tags,
    remote_image_tag,
    runtime_image_tag,
)

CORE_TAG = "localhost/postgres-setup/postgres:suse-0.1.0"
EXT_TAG = "localhost/postgres-setup/extension/pgvector:suse-0.1.0"
RUNTIME_TAG = "localhost/postgres-setup/runtime:suse-0.1.0"


class StubCoreBuilder:
    def __init__(self, registry: FakeRegistry, profile: Profile) -> None:
        self._registry = registry
        self._tag = core_image_tag(profile)
        self.calls: list[dict] = []

    def run(self, *, force: bool = False, jobs: int | None = None) -> str:
        self.calls.append({"force": force, "jobs": jobs})
        self._registry.tags.add(self._tag)
        return self._tag


class StubExtensionBuilder:
    def __init__(self, registry: FakeRegistry, profile: Profile) -> None:
        self._registry = registry
        self._profile = profile
        self.calls: list[str] = []

    def run(self, name: str, *, force: bool = False, jobs: int | None = None) -> str:
        self.calls.append(name)
        tag = extension_image_tag(self._profile, name)
        self._registry.tags.add(tag)
        return tag


def _resources(tmp_path: Path) -> Path:
    resources = tmp_path / "resources"
    resources.mkdir()
    for name in ("postgresql.conf", "pg_hba.conf", "entrypoint.sh"):
        (resources / name).write_text("#\n")
    return resources


def _assembler(
    pins, profile, tmp_path, *, tags=None, sandbox=None, puller=None, registry_config=None
):
    registry = FakeRegistry(set(tags or []))
    sandbox = sandbox or FakeSandbox(version_output="postgres (PostgreSQL) 18.1")
    assembler = AssembleRuntimeImage(
        pins=pins,
        profile=profile,
        core_builder=StubCoreBuilder(registry, profile),
        extension_builder=StubExtensionBuilder(registry, profile),
        sandbox=sandbox,
        registry=registry,
        reporter=FakeReporter(),
        distro=FakeDistro(sandbox),
        resources_dir=_resources(tmp_path),
        puller=puller,
        registry_config=registry_config,
    )
    return assembler, sandbox, registry


def test_runtime_assembles_core_and_extensions(pins, profile, tmp_path):
    assembler, sandbox, registry = _assembler(pins, profile, tmp_path, tags={CORE_TAG, EXT_TAG})
    tag = assembler.run(source="build")

    assert tag == RUNTIME_TAG
    assert tag == runtime_image_tag(profile)
    kinds = [call[0] for call in sandbox.calls]
    assert kinds == [
        "begin",
        "copy_from_image",  # core prefix into the fresh base sandbox
        "run_cached",  # distro refresh
        "run_cached",  # distro install runtime packages (--no-recommends)
        "copy_from_image",  # extension prefix into staging
        "run",  # cp -a staging over the prefix
        "run",  # groupadd
        "run",  # useradd
        "run",  # mkdir data dir
        "run",  # chown data dir
        "run",  # mkdir config dir
        "copy_in",  # postgresql.conf
        "copy_in",  # pg_hba.conf
        "copy_in",  # entrypoint.sh
        "run",  # chmod entrypoint
        "run",  # chown config + entrypoint
        "capture",  # postgres --version
        "capture",  # ls vector.control
        "set_env",
        "set_volumes",
        "set_ports",
        "set_entrypoint",
        "set_cmd",
        "set_user",
        "set_labels",
        "commit",
        "finish",
    ]
    assert sandbox.calls[0][1] == profile.base_image
    assert sandbox.calls[0][2] == "localhost/postgres-setup/cache/suse/runtime"
    assert sandbox.calls[1] == ("copy_from_image", CORE_TAG, "/usr/local/pgsql", "/usr/local/pgsql")
    assert sandbox.calls[4] == (
        "copy_from_image",
        EXT_TAG,
        "/usr/local/pgsql",
        "/tmp/stage_pgvector",
    )
    assert "cp -a /tmp/stage_pgvector/. /usr/local/pgsql/" in sandbox.calls[5][1][2]
    # runtime packages = core + extension runtime packages, --no-recommends, via the distro
    install = [c for c in sandbox.calls if c[0] == "run_cached"][1]
    assert "libicu77" in install[1][2] and "shadow" in install[1][2]
    assert "--no-recommends" in install[1][2]
    # daemon shape
    useradd = [c for c in sandbox.calls if c[0] == "run" and "useradd" in " ".join(c[1])][0]
    assert useradd[1][3] == "26"  # -u <uid>
    env = [c for c in sandbox.calls if c[0] == "set_env"][0][1]
    assert env["PGDATA"] == "/var/lib/pgsql/data/18"
    assert env["PATH"] == "/usr/local/pgsql/bin:/usr/bin:/bin"
    assert [c for c in sandbox.calls if c[0] == "set_ports"][0][1] == (5432,)
    assert [c for c in sandbox.calls if c[0] == "set_volumes"][0][1] == ("/var/lib/pgsql/data/18",)
    assert [c for c in sandbox.calls if c[0] == "set_entrypoint"][0][1] == (
        "/usr/local/bin/entrypoint.sh",
    )
    assert [c for c in sandbox.calls if c[0] == "set_cmd"][0][1] == ("postgres",)
    assert [c for c in sandbox.calls if c[0] == "set_user"][0][1] == "26"
    labels = [c for c in sandbox.calls if c[0] == "set_labels"][0][1]
    assert labels["org.postgres-setup.extension.pgvector.version"] == "0.8.1"
    assert labels["org.postgres-setup.postgres.version"] == "18.1"
    assert sandbox.calls[-2][1] == tag


def test_runtime_skips_when_image_exists(pins, profile, tmp_path):
    assembler, sandbox, _ = _assembler(
        pins, profile, tmp_path, tags={CORE_TAG, EXT_TAG, RUNTIME_TAG}
    )
    assembler.run(source="build")
    assert sandbox.calls == []


def test_runtime_builds_missing_pieces(pins, profile, tmp_path):
    assembler, sandbox, registry = _assembler(pins, profile, tmp_path)
    tag = assembler.run(source="build")
    assert tag == RUNTIME_TAG
    assert CORE_TAG in registry.tags and EXT_TAG in registry.tags
    assert sandbox.calls != []


def test_runtime_rejects_unknown_source(pins, profile, tmp_path):
    assembler, _, _ = _assembler(pins, profile, tmp_path, tags={RUNTIME_TAG})
    with pytest.raises(ValueError, match="unknown source"):
        assembler.run(source="bogus")


def test_runtime_pull_mode_pulls_instead_of_building(pins, profile, tmp_path):
    registry = FakeRegistry()
    transport = FakeTransport(registry)
    config = RegistryConfig(namespace="reg.example.org")
    for tag in profile_image_tags(profile):
        transport.remote_has.add(remote_image_tag(tag, config))
    puller = PullImages(pins=pins, profile=profile, transport=transport, reporter=FakeReporter())

    assembler, sandbox, _ = _assembler(
        pins, profile, tmp_path, puller=puller, registry_config=config
    )
    assembler._registry = registry  # share the registry the transport writes into
    tag = assembler.run(source="pull")

    assert tag == RUNTIME_TAG
    assert sandbox.calls == []
    assert registry.image_exists(RUNTIME_TAG)
    assert len(transport.pulls) == len(profile_image_tags(profile))


def test_runtime_pull_mode_requires_pullable_image(pins, profile, tmp_path):
    class NoopPuller:
        """A puller whose registry has nothing: the pull 'succeeds' but the
        runtime image is still missing locally."""

        def __init__(self) -> None:
            self.calls = 0

        def run(self, config) -> list[str]:
            self.calls += 1
            return []

    puller = NoopPuller()
    assembler, _, _ = _assembler(
        pins,
        profile,
        tmp_path,
        puller=puller,
        registry_config=RegistryConfig(namespace="reg.example.org"),
    )
    with pytest.raises(ImageNotFoundError, match="pull"):
        assembler.run(source="pull")
    assert puller.calls == 1


def test_runtime_verifies_daemon_version(pins, profile, tmp_path):
    sandbox = FakeSandbox(version_output="postgres (PostgreSQL) 17.4")
    assembler, _, _ = _assembler(pins, profile, tmp_path, tags={CORE_TAG, EXT_TAG}, sandbox=sandbox)
    with pytest.raises(VerificationError, match="17.4"):
        assembler.run(source="build")


def test_runtime_verifies_extension_control_file(pins, profile, tmp_path):
    sandbox = FakeSandbox(version_output="postgres (PostgreSQL) 18.1", ls_output="")
    assembler, _, _ = _assembler(pins, profile, tmp_path, tags={CORE_TAG, EXT_TAG}, sandbox=sandbox)
    with pytest.raises(VerificationError, match="vector.control"):
        assembler.run(source="build")


def test_push_pull_mapping(pins, profile, tmp_path):
    registry = FakeRegistry({RUNTIME_TAG})
    transport = FakeTransport(registry)
    config = RegistryConfig(namespace="reg.example.org", tls_verify=False)

    # without registry config: ConfigError
    with pytest.raises(ConfigError, match="registry.toml"):
        PushImages(pins=pins, profile=profile, transport=transport, reporter=FakeReporter()).run(
            None
        )

    # push maps every final local tag into the configured namespace
    remotes = PushImages(
        pins=pins, profile=profile, transport=transport, reporter=FakeReporter()
    ).run(config)
    assert remotes == [remote_image_tag(tag, config) for tag in profile_image_tags(profile)]
    assert remote_image_tag(RUNTIME_TAG, config) == (
        "reg.example.org/postgres-setup/runtime:suse-0.1.0"
    )

    # pull retags back to the local names
    tags = PullImages(pins=pins, profile=profile, transport=transport, reporter=FakeReporter()).run(
        config
    )
    assert tags == profile_image_tags(profile)
    assert registry.image_exists(RUNTIME_TAG)
