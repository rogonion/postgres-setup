# ADR 0009: Environment-identical PostgreSQL from pinned source

- Status: accepted
- Date: 2026-11-03

## Context

Taking PostgreSQL (or its extensions) from host or distribution packages
makes behavior environment-dependent: different versions, different
compile-time flags (ICU, LZ4, Zstd, systemd, OpenSSL), different transitive
geo libraries for postgis (GEOS/PROJ/GDAL) — different features and link
behavior between laptop, CI, and production.

## Decision

Never consume system PostgreSQL packages. Every environment obtains the
daemon by compiling the **same pinned upstream tarballs with the same
configure flags** (ADR 0005): download into a git-ignored cache with sha256
verification, build inside the image sandbox (ADR 0003), and run the
assembled runtime image (ADR 0004) — or pull it from the registry (ADR 0006).

## Consequences

- One daemon everywhere: identical versions, flags, and extension behavior;
  database artifacts are interchangeable between environments.
- Provenance: pinned, auditable source snapshots; the runtime image carries
  the pins in its labels.
- Trade-offs: compile cost in fresh environments (mitigated by layer caches
  and registry distribution, ADR 0006); we own upstream tracking;
  transitive geo libraries are pinned only insofar as the sandbox image
  provides them (the documented `libldap`/OpenSSL 3.5 link workaround for
  postgis lives in the recipe, not in config).
