# postgres-setup

Pinned from-source builder for [PostgreSQL] (and extensions: postgis,
pgvector, rum): **container images are the unit of sandboxing and artifact
storage, and the runtime image is the product** (ADR 0003/0004). The host
needs only `uv`, `buildah`, and a container CLI.

```
├── config/            all user config: default.toml, pins.toml, profiles.toml, registry.toml(.example)
├── apps/cli/setup/    CLI (uv workspace member; thin driving adapter over core)
├── libs/python/core/  the hexagonal library: domain / application / adapters
├── resources/         entrypoint.sh, postgresql.conf, pg_hba.conf (baked into the runtime image)
├── deploy/            podman quadlet units running the runtime image
└── docs/              architecture docs: ADRs + descriptions
```

## Architecture

Per **distro profile** (`config/profiles.toml`, e.g. `suse`), three image
tiers are built with buildah (ADR 0003):

- **core** — `localhost/postgres-setup/postgres:<profile>-<version>`:
  `setup build-core` compiles the pinned PostgreSQL (core + contrib via
  `make install-world-bin`) in a sandbox.
- **extension** — `localhost/postgres-setup/extension/<name>:<profile>-<version>`:
  `setup build-extension <name>` builds FROM the core image — postgres
  extensions need `pg_config` and the core headers — into its own image,
  verified by its control file landing in `<prefix>/share/extension`.
- **runtime** — `localhost/postgres-setup/runtime:<profile>-<version>`:
  `setup runtime` (alias `assemble`) merges the core prefix with each enabled
  extension's artifacts (`buildah copy --from`), installs only the runtime
  packages, and shapes the daemon (user 26:26, data dir, config, entrypoint,
  port 5432). This is the product.

Intermediate steps of each tier are cached as layer images keyed by a hash of
the command, env, pins, and flags — unchanged steps replay from cache. Image
tags carry `<profile>-<profile.version>`; pin versions live in image labels
and cache keys — bump the profile `version` when pins change (ADR 0005).

**Task runner** is poethepoet: `uv run poe <task>` (ADR 0008).

## Requirements

- [uv](https://docs.astral.sh/uv/) (auto-installs managed Python)
- [buildah](https://buildah.io/) 1.41+ (or a podman that ships it)
- A container runtime store for images (podman's rootless store by default)

Nothing else: build dependencies (gcc, make, ...) are installed inside the
build sandbox by the profile, never on the host.

## Quickstart

```shell
uv sync                                # once: one venv for the whole workspace
uv run poe lint                        # ruff check + format check
uv run poe apps-cli-setup:test         # pytest suite (fakes, no buildah)

uv run poe apps-cli-setup:build        # core + postgis + pgvector + rum + runtime, suse profile
uv run poe apps-cli-setup:profiles     # list distro profiles
uv run poe apps-cli-setup:tag          # print the runtime image tag
```

Granular: `build-core`, `build-extension pgvector`, `assemble` —
`uv run poe apps-cli-setup:<task> --profile suse --force` (args append
directly; no `--` separator with this poe version).
Or directly: `uv run setup <command> --help`.

## Running the runtime image

```shell
podman run --rm localhost/postgres-setup/runtime:suse-0.1.0 postgres --version

podman volume exists postgres || podman volume create postgres
podman unshare chown -R 26:26 $(podman volume inspect postgres --format '{{.Mountpoint}}')
podman run -d --name postgres18 --network <net> -p 5432:5432 \
  -v postgres:/var/lib/pgsql/data:Z \
  -e POSTGRES_PASSWORD=postgres2025 \
  localhost/postgres-setup/runtime:suse-0.1.0
podman exec -e PGPASSWORD=postgres2025 postgres18 psql -U postgres -c \
  "CREATE EXTENSION IF NOT EXISTS postgis; SELECT postgis_version();"
```

`deploy/` holds podman quadlet units (`postgres.container`,
`postgres-data.volume`) as an alternative.

## Extensions

- **postgis** 3.6.1 — geospatial types + functions (GEOS/PROJ/GDAL), topology, address_standardizer
- **pgvector** 0.8.1 — `vector` type with HNSW and IVFFlat indexes, built with `-march=x86-64-v3 -O3 -flto`
- **rum** 1.3.15 — inverted index with weights/positions for fast relevance ranking

Contrib is built by default (`make install-world-bin`), so
`pg_stat_statements`, `pg_trgm`, `unaccent`, `btree_gin`, `pgcrypto`, etc.
are available via `CREATE EXTENSION` without any pin.

## Profiles

Profiles are distro-keyed (`default = "suse"` in `config/profiles.toml`):

- **suse** — openSUSE Leap 16.0 base, zypper package operations, PostgreSQL
  with openssl/libxml/ICU/LZ4/Zstd/systemd at `/usr/local/pgsql`, and the
  postgis/pgvector/rum extensions enabled (their own build/runtime packages
  in their `[[profiles.suse.extensions]]` tables; the pins live in
  `config/pins.toml [extensions.<name>]`).
- **ubuntu** — planned: one `[profiles.ubuntu]` table + one apt `Distro`
  adapter.

## Upgrading versions

Edit `config/pins.toml` (version, URL, archive name and sha256 — compute
with `sha256sum` after downloading), bump the profile `version` in
`config/profiles.toml`, and re-run `build`. A stale image rebuilds
automatically; older cache layers prune with
`uv run poe apps-cli-setup:clean --cache`. Never leave a floating version
in the file.

## Documentation

- `docs/architecture/descriptions/overview.md` — the entry point: layers,
  image topology, outputs, and the decision map (includes the documented
  `libldap`/OpenSSL 3.5 link workaround)
- `docs/architecture/descriptions/development.md` — command reference
- `docs/architecture/ADRs/` — numbered decisions, genesis numbering from 0001
- `AGENTS.md` — rules for AI coding agents working in this repo

[PostgreSQL]: https://www.postgresql.org/
