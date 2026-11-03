"""Buildah image registry: the ImageRegistry port over `buildah images`."""

import json
import subprocess

from core.domain.errors import SandboxError


class BuildahRegistry:
    """ImageRegistry port implementation over `buildah images`."""

    def __init__(self, buildah: str = "buildah") -> None:
        self._buildah = buildah

    def image_exists(self, tag: str) -> bool:
        # buildah exits non-zero when the tag is unknown: that means absent.
        result = subprocess.run(
            [self._buildah, "images", "-q", tag],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    def prune_cache(self, cache_prefix: str) -> list[str]:
        if not cache_prefix:
            raise SandboxError("cache prefix is empty")
        result = subprocess.run(
            [self._buildah, "images", "--json"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise SandboxError(f"buildah images failed: {result.stderr.strip()}")
        try:
            images = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise SandboxError(f"cannot parse buildah images output: {exc}") from exc

        removed: list[str] = []
        for image in images:
            for name in image.get("names", []):
                if name.startswith(cache_prefix + ":") and name not in removed:
                    removed.append(name)
        for name in removed:
            subprocess.run([self._buildah, "rmi", name], capture_output=True)
        return removed
