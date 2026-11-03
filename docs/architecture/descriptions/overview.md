# Overview

`postgres-setup` builds a pinned PostgreSQL (plus pinned extensions) from
source and packages it as container images; the **runtime image is the
product** — consumers run it as a container, attached to a volume.

## Shape in one paragraph

A Python (uv) CLI builds, per distro profile, three tiers of images with
buildah: the **core** image (`postgres:<profile>-<version>`, compiled
PostgreSQL core + contrib), one **extension** image per enabled extension
(`extension/<name>:...`, built FROM the core image, which provides
`pg_config` and the headers), and the **runtime** image
(`runtime:<profile>-<version>`) that merges the core prefix with each
extension's artifacts, installs only the runtime packages, and shapes the
daemon (user 26:26, data dir, config, entrypoint, port 5432). Each tier's
intermediate steps are cached as hash-keyed layer images, so rebuilds replay
instead of recompiling. The host needs only uv, buildah, and a container
runtime store (ADR 0003).

## Repository map

| Path | Role |
| --- | --- |
| `apps/cli/setup/` | CLI (driving adapter): `build`, `build-core`, `build-extension`, `assemble`/`runtime`, `push`, `pull`, `clean`, `tag`, `profiles`; tests |
| `libs/python/core/` | hexagonal library: `domain/` (models, ports, errors), `application/` (use cases), `adapters/` (one dir per port) |
| `config/` | all user-editable toml: `default.toml`, `pins.toml`, `profiles.toml`, `registry.toml(.example)` |
| `resources/` | runtime-image resources copied into the runtime image: `entrypoint.sh`, `postgresql.conf`, `pg_hba.conf` |
| `deploy/` | podman quadlet units running the runtime image (`postgres.container`, `postgres-data.volume`) |
| `docs/architecture/` | ADRs (decisions) + descriptions (this file, development) |
| `.cache/` | verified source tarballs (git-ignored) |

## Layers

### Inputs & CLI (primary adapter)

- `config/pins.toml` — the single versions file: `[postgres]` + `[extensions.<name>]` (ADR 0005)
- `config/profiles.toml` — distro-keyed profiles, validated into pydantic models at the boundary
- `config/registry.toml` — optional registry namespace (ADR 0006)
- The typer CLI (`apps/cli/setup/src/setup/cli.py`) stays thin: parse flags,
  delegate to `composition.py`, translate `CoreError` into exit code 1

### Application (use cases)

- **BuildCoreImage** — fetch + verify the tarball, begin the sandbox, install
  build packages (via the `Distro` port) → copy in → `./configure` →
  `make -j<n> && make install-world-bin` → verify `postgres --version` →
  label → commit the core tag. Step order, cache keys, and the verification
  contract live here and nowhere else.
- **BuildExtensionImage** — FROM the core image: install the extension's own
  build packages, compile its pinned tarball with its recipe (code in
  `application/extensions.py`: postgis with protobuf + address_standardizer
  and the `LDFLAGS=-Wl,--allow-shlib-undefined` link workaround; pgvector
  with `OPTFLAGS` march/`-O3`/`-flto`; rum via PGXS), verify the control file
  landed in `<prefix>/share/extension`, commit the extension tag.
- **AssembleRuntimeImage** — resolve missing images (pull or build), then
  `copy --from` the core prefix into a fresh base sandbox, merge each
  extension's prefix over it, install the runtime packages, create the
  postgres user, copy in the config + entrypoint, verify daemon version and
  every control file, shape the image (env, volume, ports, entrypoint, cmd,
  user), label with full provenance, commit the runtime tag (ADR 0004).
- **PushImages / PullImages** — registry transport of all final images (ADR 0006).

### Domain

- Pydantic models for pins, distro profiles, extensions, registry, and the
  three-tier image naming (`core/domain/models.py`)
- Protocol ports (`core/domain/ports.py`): `SourceFetcher`, `Sandbox` (with
  `copy_from_image` and the image-shaping `set_*` methods), `ImageRegistry`,
  `ImageTransport`, `Reporter`, `Distro`, `ConfigLoader`
- The error taxonomy (`core/domain/errors.py`): the only exceptions raised
  anywhere; adapters translate infra failures into it at the boundary
  (ADR 0002)

### Adapters (one dir per port)

- `sandbox/buildah.py` — buildah from/run/copy/config/commit with hash-keyed
  layer caching, plus `copy_from_image` (`buildah copy --from`)
- `distro/{__init__,suse}.py` — per-distro package operations via the sandbox, selected by profile name
- `image_registry/buildah.py`, `image_transport/buildah.py` — image queries, push/pull
- `source_fetcher/httpx.py` — streams to `.cache/`, verifies sha256 on download and on every later use
- `config/toml.py` — the `ConfigLoader` over `config/*.toml` + workspace-root discovery
- `reporter/rich.py` — console progress

## Image topology

| Image | Built by | Role |
| --- | --- | --- |
| `localhost/postgres-setup/postgres:<p>-<v>` | BuildCoreImage | core artifact (compiled daemon + contrib) |
| `localhost/postgres-setup/extension/<name>:<p>-<v>` | BuildExtensionImage | extension artifact (control file + .so + SQL under the prefix) |
| `localhost/postgres-setup/runtime:<p>-<v>` | AssembleRuntimeImage | the product (assembled, verified, shaped) |
| `localhost/postgres-setup/cache/<p>/<scope>:<hash>` | all | replayable build layers (prunable) |

## Known workaround (documented)

Leap 16.0's GA `libldap-2` references `EVP_md2@OPENSSL_3.0.0`, a symbol
removed from the repo's current OpenSSL 3.5. The linker's eager
full-dep-libs check during postgis's GDAL probe fails on it. Runtime is
unaffected (lazy binding; the md2 path is never called by LDAP TLS), so the
postgis recipe links with `-Wl,--allow-shlib-undefined`. This is a
repo-drift issue, not a build defect; it should be removable once Leap
ships a libldap rebuilt against OpenSSL 3.5.

## How the pieces map to decisions

| Piece | ADR |
| --- | --- |
| Workspace layout | [0001](../ADRs/0001-workspace-layout.md) |
| Hexagonal core | [0002](../ADRs/0002-hexagonal-architecture.md) |
| Images as sandbox and artifact store | [0003](../ADRs/0003-images-sandbox-artifact-store.md) |
| Runtime image as the product | [0004](../ADRs/0004-runtime-image-for-daemons.md) |
| Pins and distro profiles | [0005](../ADRs/0005-pins-and-profiles.md) |
| Registry distribution | [0006](../ADRs/0006-registry-distribution.md) |
| Central config | [0007](../ADRs/0007-central-config.md) |
| uv + poe tooling | [0008](../ADRs/0008-python-uv-poe.md) |
| Deterministic from-source builds | [0009](../ADRs/0009-deterministic-from-source-builds.md) |
