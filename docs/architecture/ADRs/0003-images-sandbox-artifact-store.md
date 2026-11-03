# ADR 0003: Container images as sandbox and artifact store

- Status: accepted
- Date: 2026-11-03

## Context

Build dependencies (gcc, make, the geo/math devel packages for postgis) must
never be installed on the host, and the build products must be movable
between machines (CI, second laptops) without recompiling — and selectable
per piece: a consumer may want only the core, only an extension, or the full
runtime.

## Decision

The buildah working container is the unit of sandboxing and artifact capture,
and images come in three tiers per profile (ADR 0005):

```
base image (profile.base_image)
  -> postgres:<profile>-<version>               compiled postgres core + contrib
       -> extension/<name>:<profile>-<version>  per enabled extension, FROM the core image
  -> runtime:<profile>-<version>               assembled runtime image (ADR 0004) — the product
```

- **Core** (`setup build-core`): fetch the pinned tarball, install the
  profile's `build_packages` via the `Distro` adapter, configure/compile/
  `make install-world-bin` into `prefix`, verify `postgres --version` against
  the pin, commit.
- **Extension** (`setup build-extension <name>`): the sandbox begins FROM the
  core image — postgres extensions need `pg_config` and the core headers,
  which is the structural difference from valkey modules; the extension's own
  `build_packages` are installed on top, its pinned tarball compiled by its
  recipe, verified by its control file landing in `<prefix>/share/extension`,
  committed as its own image.
- **Runtime** (`setup assemble` / `setup runtime` / `setup build`): a fresh
  base-image sandbox pulls the core prefix in with `buildah copy --from`,
  merges each extension's prefix over it (`copy --from` to staging + `cp -a`),
  installs the union of core + extension `runtime_packages`, shapes the daemon
  (user, dirs, config, entrypoint, ports), verifies, and commits.

Intermediate steps of each tier commit hash-keyed **layer-cache images**
under `<profile.cache_prefix>/<scope>:<hash>` (hash of current image +
command + env + explicit cache keys), so unchanged steps replay from cache.
Image tags carry `<profile>-<profile.version>`; pin versions live in labels
and cache keys — bump `Profile.version` when pins change.

The host needs only uv, buildah, and a container runtime store — no
compilers, no devel packages.

## Consequences

Reproducible, host-clean builds; rebuilds replay cached layers; each tier is
independently pullable/pushable (ADR 0006), so consumers pick the granularity
they need. Cost: buildah is required, and the image store is local to one
machine until pushed.
