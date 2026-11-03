"""Buildah sandbox: the Sandbox port implementation over the buildah CLI.

All commands run via subprocess with argument lists (no ``shell=True`` on
the host); a ``sh -c`` argument is only used deliberately as the command
executed inside the container. Cached steps commit intermediate images
under the profile's cache prefix, keyed by a hash of the current image,
command, environment, and explicit cache keys. The ``set_*`` methods record
image configuration (labels, env, entrypoint, cmd, user, ports, volumes) for
the committed artifact/runtime image.
"""

import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from core.domain.errors import SandboxError

CONTAINER_NAME = "postgres-setup-build"


class BuildahSandbox:
    """Sandbox port implementation driving `buildah`."""

    def __init__(self, buildah: str = "buildah") -> None:
        self._buildah = buildah
        self._container = CONTAINER_NAME
        self._current_image: str | None = None

    def begin(self, base_image: str, cache_prefix: str) -> None:
        self._cache_prefix = cache_prefix
        self._rm()
        self._spawn(base_image)
        print(f"  buildah from {base_image} -> {self._container}")

    def run(self, command: Sequence[str], env: Mapping[str, str] | None = None) -> None:
        self._buildah_run(command, env=env)

    def capture(self, command: Sequence[str], env: Mapping[str, str] | None = None) -> str:
        return self._buildah_run(command, env=env, capture=True)

    def run_cached(
        self,
        command: Sequence[str],
        env: Mapping[str, str] | None = None,
        cache_keys: Mapping[str, str] | None = None,
    ) -> None:
        digest = self._layer_digest(command, env, cache_keys)
        cache_tag = f"{self._cache_prefix}:{digest}"

        if self._image_exists(cache_tag):
            print(f"  using cached layer {digest}")
            self._rm()
            self._spawn(cache_tag)
            return

        self.run(command, env=env)
        self.commit(cache_tag)

    def copy_in(self, source: Path, dest: str) -> None:
        if not source.exists():
            raise SandboxError(f"source file {source} does not exist")
        self._invoke(["copy", self._container, str(source), dest])

    def copy_from_image(self, image: str, src: str, dest: str) -> None:
        self._invoke(["copy", "--from", image, self._container, src, dest])

    def set_labels(self, labels: Mapping[str, str]) -> None:
        args = ["config"]
        for key, value in labels.items():
            args += ["--label", f"{key}={value}"]
        self._invoke(args + [self._container])

    def set_env(self, env: Mapping[str, str]) -> None:
        args = ["config"]
        for key, value in env.items():
            args += ["-e", f"{key}={value}"]
        self._invoke(args + [self._container])

    def set_entrypoint(self, entrypoint: Sequence[str]) -> None:
        self._config_raw(["--entrypoint", json.dumps(list(entrypoint))])

    def set_cmd(self, cmd: Sequence[str]) -> None:
        self._config_raw(["--cmd", json.dumps(list(cmd))])

    def set_user(self, user: str) -> None:
        self._config_raw(["--user", user])

    def set_ports(self, ports: Sequence[int]) -> None:
        for port in ports:
            self._config_raw(["--port", str(port)])

    def set_volumes(self, volumes: Sequence[str]) -> None:
        for volume in volumes:
            self._config_raw(["--volume", volume])

    def commit(self, tag: str) -> None:
        print(f"  buildah commit {self._container} -> {tag}")
        self._invoke(["commit", "--squash", self._container, tag])
        self._current_image = tag

    def finish(self) -> None:
        self._rm()

    def _buildah_run(
        self,
        command: Sequence[str],
        env: Mapping[str, str] | None,
        capture: bool = False,
    ) -> str:
        args = ["run"]
        for key, value in (env or {}).items():
            args += ["-e", f"{key}={value}"]
        args += [self._container, "--", *command]
        print(f"  buildah {' '.join(args)}")
        if capture:
            result = subprocess.run([self._buildah, *args], capture_output=True, text=True)
            if result.returncode != 0:
                raise SandboxError(f"`{' '.join(command)}` failed: {result.stderr.strip()}")
            return result.stdout
        result = subprocess.run([self._buildah, *args])
        if result.returncode != 0:
            raise SandboxError(f"`{' '.join(command)}` failed with exit code {result.returncode}")

    def _config_raw(self, pairs: list[str]) -> None:
        self._invoke(["config", *pairs, self._container])

    def _layer_digest(
        self,
        command: Sequence[str],
        env: Mapping[str, str] | None,
        cache_keys: Mapping[str, str] | None,
    ) -> str:
        hasher = hashlib.sha256()
        hasher.update((self._current_image or "").encode())
        for item in (command, dict(env or {}), dict(cache_keys or {})):
            hasher.update(json.dumps(item, sort_keys=True).encode())
        return hasher.hexdigest()[:12]

    def _image_exists(self, tag: str) -> bool:
        # buildah exits non-zero when the tag is unknown: that means absent.
        result = subprocess.run(
            [self._buildah, "images", "-q", tag],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    def _spawn(self, from_image: str) -> None:
        try:
            self._invoke(["from", "--name", self._container, from_image])
        except SandboxError as exc:
            if "already in use" in str(exc):
                self._rm()
                self._invoke(["from", "--name", self._container, from_image])
            else:
                raise
        self._current_image = from_image

    def _rm(self) -> None:
        result = subprocess.run(
            [self._buildah, "rm", self._container],
            capture_output=True,
            text=True,
        )
        # buildah exits non-zero when the container is unknown: that is a no-op.
        if result.returncode != 0 and "not known" not in result.stderr:
            raise SandboxError(f"buildah rm failed: {result.stderr.strip()}")
        self._current_image = None

    def _invoke(self, args: Sequence[str]) -> None:
        print(f"  buildah {' '.join(args)}")
        result = subprocess.run([self._buildah, *args])
        if result.returncode != 0:
            raise SandboxError(
                f"`buildah {' '.join(args)}` failed with exit code {result.returncode}"
            )
