"""Distro adapter: openSUSE Leap, driven by zypper."""

from typing import Mapping, Sequence

from core.domain.ports import Sandbox


class SuseDistro:
    """`Distro` for openSUSE Leap: every operation is a zypper call executed
    inside the build sandbox (cached as a layer)."""

    def __init__(self, *, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    def refresh_package_repository(self) -> None:
        self._sandbox.run_cached(
            ["sh", "-c", "zypper --non-interactive refresh"],
            cache_keys={"step": "refresh-package-repository"},
        )

    def install_packages(
        self,
        packages: Sequence[str],
        extra_cache_keys: Mapping[str, str] | None = None,
        *,
        no_recommends: bool = False,
    ) -> None:
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
