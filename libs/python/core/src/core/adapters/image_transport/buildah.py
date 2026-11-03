"""Buildah image transport: the ImageTransport port over buildah push/pull (+tag)."""

import subprocess

from core.domain.errors import SandboxError


class BuildahTransport:
    """ImageTransport port implementation over buildah push/pull."""

    def __init__(self, buildah: str = "buildah") -> None:
        self._buildah = buildah

    def push(self, local_tag: str, remote_tag: str, *, tls_verify: bool = True) -> None:
        args = ["push"]
        if not tls_verify:
            args.append("--tls-verify=false")
        args += [local_tag, remote_tag]
        print(f"  buildah {' '.join(args)}")
        result = subprocess.run([self._buildah, *args])
        if result.returncode != 0:
            raise SandboxError(
                f"`buildah {' '.join(args)}` failed with exit code {result.returncode}"
            )

    def pull(self, remote_tag: str, local_tag: str, *, tls_verify: bool = True) -> None:
        args = ["pull"]
        if not tls_verify:
            args.append("--tls-verify=false")
        args.append(remote_tag)
        print(f"  buildah {' '.join(args)}")
        result = subprocess.run([self._buildah, *args])
        if result.returncode != 0:
            raise SandboxError(
                f"`buildah {' '.join(args)}` failed with exit code {result.returncode}"
            )
        if remote_tag != local_tag:
            print(f"  buildah tag {remote_tag} {local_tag}")
            result = subprocess.run([self._buildah, "tag", remote_tag, local_tag])
            if result.returncode != 0:
                raise SandboxError(f"buildah tag {remote_tag} -> {local_tag} failed")
