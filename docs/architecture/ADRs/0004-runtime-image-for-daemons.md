# ADR 0004: The runtime image as the product (daemon dependencies)

- Status: accepted
- Date: 2026-11-03

## Context

ADR 0003 established container images as the unit of sandboxing and artifact
storage, and left one choice per application: whether a runtime image exists.
SQLite is a library consumed as a host prefix, so sqlite-setup's assembled
image is the artifact. Postgres is a daemon: consumers do not link against
it or copy prefixes — they **run** it, as a container, attached to volumes
and networks.

## Decision

For postgres-setup the `*-setup` project produces three image kinds, all
tagged `localhost/postgres-setup/<kind>:<profile>-<version>`:

1. **Core artifact image** — compiled daemon + contrib under its prefix.
   Rebuilt from pins; never run directly.
2. **Extension artifact images** — one per pinned extension, built against
   the core, holding just the extension's artifacts under the prefix.
3. **Runtime image** — the product: base image + core prefix copied in via
   `buildah copy --from` + each enabled extension's artifacts + only the
   *runtime* packages + a dedicated uid/gid, data dir, config files
   (`resources/`: entrypoint.sh, postgresql.conf, pg_hba.conf), entrypoint,
   cmd, ports, volumes, and user.

Assembly is a use case like any other (`AssembleRuntimeImage` in
`core/application/runtime.py`), not builder plumbing: it resolves missing
core/extension images (pull or build), verifies the daemon version and every
expected extension control file inside the image, and labels the image with
the full provenance (pins, profile, extensions).

## Consequences

Consumers run one image (`podman run ... localhost/postgres-setup/runtime:suse-0.1.0`)
with a volume at the data dir; `deploy/` ships quadlet units for that. The
runtime image is also what `push`/`pull` distribute as the primary artifact
(ADR 0006). Trade-off: the runtime image is larger than a bare artifact image
(runtime packages + config), accepted because the daemon is the consumption
unit.
