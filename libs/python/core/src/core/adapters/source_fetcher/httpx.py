"""httpx source fetcher with sha256 verification at the boundary."""

import hashlib
from pathlib import Path

import httpx

from core.domain.errors import ChecksumError, FetchError
from core.domain.models import SourcePin


class HttpxSourceFetcher:
    """SourceFetcher port implementation over httpx, with a local cache.

    A present archive is re-verified (never re-downloaded); a fresh
    download streams to ``<archive>.part`` and only replaces the cache
    entry after its sha256 matches the pin.
    """

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir

    def fetch(self, pin: SourcePin) -> Path:
        destination = self._cache_dir / pin.archive
        if destination.exists():
            self._verify(destination, pin.sha256)
            return destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name + ".part")
        try:
            with (
                httpx.Client(follow_redirects=True) as client,
                client.stream("GET", pin.url) as response,
            ):
                response.raise_for_status()
                with open(partial, "wb") as out:
                    for chunk in response.iter_bytes(1024 * 1024):
                        out.write(chunk)
        except httpx.HTTPError as exc:
            partial.unlink(missing_ok=True)
            raise FetchError(f"failed to download {pin.url}: {exc}") from exc
        self._verify(partial, pin.sha256)
        partial.replace(destination)
        return destination

    @staticmethod
    def _verify(path: Path, sha256: str) -> None:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        actual = digest.hexdigest()
        if actual != sha256:
            path.unlink(missing_ok=True)
            raise ChecksumError(
                f"sha256 mismatch for {path.name}\n  expected {sha256}\n  got      {actual}"
            )
