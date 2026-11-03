"""Shared fakes over the ports, following the suite's fakes-over-ports
convention: use cases are tested against in-memory doubles, never against
buildah, the network, or the filesystem.
"""

from pathlib import Path

from core.domain.models import SourcePin


class FakeReporter:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(message)

    def warn(self, message: str) -> None:
        self.messages.append(message)


class FakeFetcher:
    def __init__(self, archive: Path) -> None:
        self.archive = archive
        self.fetched: list[str] = []

    def fetch(self, pin: SourcePin) -> Path:
        self.fetched.append(pin.version)
        return self.archive


class FakeDistro:
    """Records package operations and mirrors them into the sandbox as
    run_cached calls, like the real distro adapters do."""

    def __init__(self, sandbox) -> None:
        self._sandbox = sandbox
        self.calls: list[tuple] = []

    def refresh_package_repository(self) -> None:
        self.calls.append(("refresh",))
        self._sandbox.run_cached(
            ["sh", "-c", "zypper --non-interactive refresh"],
            cache_keys={"step": "refresh-package-repository"},
        )

    def install_packages(self, packages, extra_cache_keys=None, *, no_recommends=False) -> None:
        packages = list(packages)
        self.calls.append(("install", tuple(packages), dict(extra_cache_keys or {}), no_recommends))
        flags = "--no-recommends " if no_recommends else ""
        self._sandbox.run_cached(
            ["sh", "-c", f"zypper --non-interactive install {flags}-- {' '.join(packages)}"],
            cache_keys={
                "step": "install-packages",
                "packages": ",".join(sorted(packages)),
                "no_recommends": str(no_recommends),
                **(extra_cache_keys or {}),
            },
        )


class FakeRegistry:
    def __init__(self, tags: set[str] | None = None) -> None:
        self.tags = set(tags or [])
        self.pruned: list[str] = []

    def image_exists(self, tag: str) -> bool:
        return tag in self.tags

    def prune_cache(self, cache_prefix: str) -> list[str]:
        removed = [t for t in self.tags if t.startswith(cache_prefix + ":")]
        self.tags -= set(removed)
        self.pruned.extend(removed)
        return removed


class FakeSandbox:
    """Records sandbox calls; scripts capture() responses."""

    def __init__(
        self,
        *,
        version_output: str = "postgres (PostgreSQL) 18.1",
        ls_output: str | None = None,
    ) -> None:
        self.calls: list[tuple] = []
        self.version_output = version_output
        # None -> echo the ls argument back (file "present"); set to ""
        # to simulate a missing file.
        self.ls_output = ls_output

    def begin(self, base_image: str, cache_prefix: str) -> None:
        self.calls.append(("begin", base_image, cache_prefix))

    def run(self, command, env=None) -> None:
        self.calls.append(("run", tuple(command), env))

    def capture(self, command, env=None) -> str:
        self.calls.append(("capture", tuple(command), env))
        if "--version" in command:
            return self.version_output
        if command and command[0] == "ls":
            return self.ls_output if self.ls_output is not None else " ".join(command[1:])
        return ""

    def run_cached(self, command, env=None, cache_keys=None) -> None:
        self.calls.append(("run_cached", tuple(command), env, dict(cache_keys or {})))

    def copy_in(self, source: Path, dest: str) -> None:
        self.calls.append(("copy_in", source, dest))

    def copy_from_image(self, image: str, src: str, dest: str) -> None:
        self.calls.append(("copy_from_image", image, src, dest))

    def set_labels(self, labels) -> None:
        self.calls.append(("set_labels", dict(labels)))

    def set_env(self, env) -> None:
        self.calls.append(("set_env", dict(env)))

    def set_entrypoint(self, entrypoint) -> None:
        self.calls.append(("set_entrypoint", tuple(entrypoint)))

    def set_cmd(self, cmd) -> None:
        self.calls.append(("set_cmd", tuple(cmd)))

    def set_user(self, user: str) -> None:
        self.calls.append(("set_user", user))

    def set_ports(self, ports) -> None:
        self.calls.append(("set_ports", tuple(ports)))

    def set_volumes(self, volumes) -> None:
        self.calls.append(("set_volumes", tuple(volumes)))

    def commit(self, tag: str) -> None:
        self.calls.append(("commit", tag))

    def finish(self) -> None:
        self.calls.append(("finish",))


class FakeTransport:
    """Records pushes/pulls; pulls make the local tag resolvable."""

    def __init__(self, registry) -> None:
        self._registry = registry
        self.pushes: list[tuple[str, str]] = []
        self.pulls: list[tuple[str, str]] = []
        self.remote_has: set[str] = set()

    def push(self, local_tag, remote_tag, *, tls_verify=True):
        self.pushes.append((local_tag, remote_tag))
        self.remote_has.add(remote_tag)

    def pull(self, remote_tag, local_tag, *, tls_verify=True):
        if remote_tag not in self.remote_has:
            raise RuntimeError(f"remote {remote_tag} not found")
        self.pulls.append((remote_tag, local_tag))
        self._registry.tags.add(local_tag)
